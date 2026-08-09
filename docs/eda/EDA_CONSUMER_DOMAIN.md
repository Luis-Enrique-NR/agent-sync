# EDA Consumer Domain — Especificación técnica

- **Estado:** Aceptada
- **Fecha:** 2026-08-08
- **Rama:** `feat/eda-worker`
- **Dominio:** EDA / Persistencia / Orquestación

---

## 1. Frontera de Dominios — Delimitación vs. Canales

### Responsabilidades de Transporte (Canales — Ingeniero 1)

| Responsabilidad | Archivo | Descripción |
|----------------|---------|-------------|
| Verificación HMAC-SHA256 | `transport/webhooks.py` | `verify_portal_signature()` sobre raw bytes |
| Normalización de eventos | `transport/webhooks.py` | `PortalEvent` → `TransportEnvelopeV1` |
| Admisión en bus durable | `transport/redis_bus.py` | `RedisStreamsEventBus.accept()` — Lua atómico, dedup por `event_id` |
| Endpoint HTTP | `api/portal_webhooks.py` | FastAPI `POST /webhooks/portal` — verifica, normaliza, acepta |
| Administración de canales | `transport/portal.py` | `HttpPortalClient` — publicar mensajes, agregar/quitar miembros |

### Responsabilidades de Dominio (Nuestro Rol — EDA + Persistencia)

| Responsabilidad | Archivo | Descripción |
|----------------|---------|-------------|
| Consumo asíncrono | `eda/consumer.py` | `consume_forever()` — poll del bus, lease, ack/fail, graceful shutdown |
| Orquestación del AI Brain | `eda/handlers.py` | `NegotiationHandler` — invoca `engine.run_until_pause()`, persiste resultado |
| Máquina de estados | `eda/handlers.py` + `ai/engine/graph.py` | Transiciones `ACTIVE` → `PENDING_HUMAN_APPROVAL` → `RESOLVED`/`REJECTED` |
| Persistencia SQLModel | `persistence/repository.py` | `save_negotiation_state()`, `write_audit()`, `load_negotiation_state()` |
| Auditoría | `persistence/repository.py` | `audit_records` — trazabilidad notarial PRD §8 |
| Despacho outbound | `eda/handlers.py` | `NegotiationHandler` → `PortalAdmin.execute(PublishMessage)` |
| Trazabilidad E2E | `eda/trace.py` | `[EDA_TRACE][stamp][STEP]` → `logs/eda_e2e_trace.log` |

---

## 2. Catálogo de Eventos Consumidos

| Evento | Handler | Acción de dominio | AuditAction emitido |
|--------|---------|------------------|---------------------|
| `message.published` | `_handle_message_published()` | Recargar `NegotiationState` → `engine.run_until_pause()` → persistir resultado → publicar turno a Portal | `TURN_PUBLISHED` (LLM) |
| `message.published` + `pending_decision` | `_handle_message_published()` | Detectar `PENDING_HUMAN_APPROVAL` → `APPROVAL_REQUESTED` audit → **NO** publicar a Portal | `TURN_PUBLISHED` + `APPROVAL_REQUESTED` |
| `message.retracted` | `handle_message_retracted()` | Escribir audit `CANDIDATE_BLOCKED` — no se invoca el engine | `CANDIDATE_BLOCKED` (SYSTEM, WARNING) |
| `agent.registered` | `_handle_agent_event()` | Escribir audit `AGENT_PUBLISHED` — punto de entrada para matchmaking futuro | `AGENT_PUBLISHED` (SYSTEM, INFO) |
| `intent.published` | `_handle_agent_event()` | Ídem — registro de intención en el ecosistema | `AGENT_PUBLISHED` (SYSTEM, INFO) |

---

## 3. Flujo de Escalamiento Humano

```
message.published recibido
    │
    ▼
NegotiationHandler._handle_message_published()
    │
    │  SELECT negotiation_states WHERE portal_channel_id=?
    │  load_negotiation_state(session_id)
    │
    ▼
engine.run_until_pause(state)
    │
    │  ┌─ LangGraph evalúa guardrails
    │  │  ┌─ GuardrailPipeline → allowed?
    │  │  │  ├─ Sí → EscalationEvaluator → required?
    │  │  │  │  ├─ Sí → state.pending_decision = DecisionRequest
    │  │  │  │  │       state.status = PENDING_HUMAN_APPROVAL
    │  │  │  │  └─ No  → publicar turno a Portal
    │  │  │  └─ No  → CANDIDATE_BLOCKED, reintentar o FAILED
    │
    ▼
save_negotiation_state(result)
    │
    ▼
¿result.state.status == PENDING_HUMAN_APPROVAL?
    │
    ├─ SÍ → write_audit(APPROVAL_REQUESTED, severity=WARNING)
    │        NO llamar a portal.execute(PublishMessage)
    │        Estado visible en bandeja de decisiones del usuario
    │
    └─ NO  → portal.execute(PublishMessage)
              write_audit(TURN_PUBLISHED, severity=INFO)
```

### Regla de bloqueo outbound

> Si `result.state.status == SessionStatus.PENDING_HUMAN_APPROVAL`, el handler **no** publica el mensaje a Portal. El turno queda pendiente en `state.pending_decision.candidate_turn` hasta que el humano apruebe/rechace/reemplace vía `resume_session()`.

---

## 4. Registro de Trazabilidad y Auditoría

### Acciones emitidas durante el ciclo EDA

| Paso | AuditAction | actor_type | severity | Cuándo |
|------|-----------|------------|----------|--------|
| Turno publicado a Portal | `TURN_PUBLISHED` | `LLM` | `INFO` | Engine generó turno sin escalamiento |
| Decisión pendiente detectada | `APPROVAL_REQUESTED` | `SYSTEM` | `WARNING` | Engine pausó por regla de escalamiento o dato personal |
| Candidato bloqueado por guardrail | `CANDIDATE_BLOCKED` | `SYSTEM` | `WARNING` | `message.retracted` o guardrail agotó reintentos |
| Agente publicado en ecosistema | `AGENT_PUBLISHED` | `SYSTEM` | `INFO` | `agent.registered` o `intent.published` |

### Correlación de eventos

Cada entrega del bus genera un `correlation_id = envelope.event_id` que encadena:
- `WORKER_POLL` (consumer) → `HANDLER_LOOKUP` (handler) → `AUDIT_WRITE` (persistencia) → `BUS_ACK` (consumer)
- Si hay engine: + `engine.run_until_pause()` → `save_negotiation_state()`

---

## 5. Arquitectura de dependencias

```
eda/consumer.py
    │  DurableEventBus (Protocol) ← injectado
    │  EventHandler (Protocol)    ← injectado
    ▼
eda/handlers.py
    │  NegotiationHandler(engine, portal)
    │  ├── NegotiationEngine  ← de ai.engine.graph
    │  └── PortalAdmin        ← de transport.portal (Protocol)
    ▼
persistence/repository.py
    │  SQLite via SQLModel
    │  save_negotiation_state(), write_audit(), load_negotiation_state()
    ▼
agentsync.db (SQLite)
```

**Regla de importación:** Los handlers **nunca** importan `HttpPortalClient`, `RedisStreamsEventBus`, ni `FastAPI`. Solo dependen de Protocolos y modelos de dominio.

---

## 6. Archivos del módulo

| Archivo | Rol |
|---------|-----|
| `eda/__init__.py` | Paquete |
| `eda/consumer.py` | Bucle asíncrono `consume_forever()` + `EventHandler` Protocol |
| `eda/handlers.py` | `NegotiationHandler` (engine + portal) + handlers legacy |
| `eda/trace.py` | Trazabilidad `[EDA_TRACE]` a `logs/eda_e2e_trace.log` |
| `tests/test_eda_consumer.py` | 8 tests unitarios (FakeBus + FakeEngine + FakePortal) |
| `tests/test_eda_e2e_trace.py` | 1 test E2E con trazabilidad completa de 6 pasos |

---

## 7. Protocolo de Testing y Diagnóstico de Entorno

### Comandos de prueba

```bash
# 1. Verificar variables y servicios del entorno local
python scripts/check_eda_env.py

# 2. Ejecutar la suite completa de pruebas EDA con trazabilidad
pytest backend/tests/test_eda_consumer.py backend/tests/test_eda_e2e_trace.py -v

# 3. Suite completa del proyecto
pytest

# 4. Inspeccionar el log generado tras la ejecución
cat logs/eda_e2e_trace.log         # Linux/macOS
type logs\eda_e2e_trace.log        # Windows (PowerShell)
```

### Salida esperada de `check_eda_env.py`

```
[ENV_OK]    Python 3.14.6
[ENV_OK]    SQLite initialized (dev_eda.db)
[ENV_WARN]  Redis not available on localhost:6379 (tests will skip)
[ENV_OK]    MATCHMAKING_ENABLED=false (correcto para esta fase)
[ENV_OK]    All 9 dependencies installed
[ENV_OK]    Core EDA modules import correctly
[ENV_OK]    Trace log ready (logs\eda_e2e_trace.log)

============================================================
  [ENV_OK] Entorno EDA correctamente configurado
============================================================
```

### Traza E2E esperada (6 pasos)

```
[EDA_TRACE][...][ADMISSION]     simulated POST /webhooks/portal
[EDA_TRACE][...][BUS_ACCEPT]    deduplicating event_id=...
[EDA_TRACE][...][BUS_ACCEPT]    accepted — delivery_id=msg_0
[EDA_TRACE][...][WORKER_POLL]   received delivery msg_0
[EDA_TRACE][...][HANDLER_LOOKUP] querying negotiation_states by portal_channel_id=...
[EDA_TRACE][...][AUDIT_WRITE]   TURN_PUBLISHED session=...
[EDA_TRACE][...][BUS_ACK]       acked delivery msg_0
[EDA_TRACE][...][E2E_END]       VERIFIED: 1 audit record
```

### Matriz de diagnóstico

| Síntoma | Causa Probable | Solución |
|---------|---------------|----------|
| `ConnectionRefusedError: Redis` | Servicio de Redis apagado | Iniciar Docker/Redis local o ignorar — tests usan `TracedFakeBus` |
| `OperationalError: no such table` | Migraciones no aplicadas | Ejecutar `python -c "from persistence.database import init_db; init_db()"` |
| `ModuleNotFoundError: langgraph` | Dependencias no instaladas | `pip install -e ".[test]"` en venv |
| `HMAC Verification Failed` | Secret mismatch en `.env` | Copiar `.env.example` a `.env` |
| `2 skipped` en test summary | Redis no disponible | **Esperado** — `test_redis_bus.py` requiere Redis |
| `ImportError: cannot import NegotiationHandler` | Rama incorrecta | `git checkout feat/eda-worker` |
| `MATCHMAKING_ENABLED=true` | Flag activado prematuramente | Setear `MATCHMAKING_ENABLED=false` en `.env` |

### Alcance excluido en esta fase

| Componente | Estado |
|-----------|--------|
| Motor de matchmaking | ❌ `MATCHMAKING_ENABLED=false` |
| Algoritmo de compatibilidad (intereses ∩ capacidades) | ❌ No implementado |
| `resume_session()` desde bandeja humana | ❌ Pendiente |

---

## 8. Trabajo pendiente

- `agent.registered`, `intent.published`, `negotiation.failed` y `negotiation.rejected` ya son admitidos por el catálogo de integración y llegan al dispatcher EDA; queda validar en Portal el campo de identidad del agente que acompaña cada payload.
- Integrar `seed_private_resolutions()` en el handler para resolver PII post-aprobación
- Implementar `resume_session()` desde la bandeja de decisiones humanas
- Motor de matchmaking: cruzar `interests` ∩ `capabilities` entre agentes `SEARCHING`
