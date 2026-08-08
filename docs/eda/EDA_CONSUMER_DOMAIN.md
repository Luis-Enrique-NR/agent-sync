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

## 7. Trabajo pendiente

- Activar `agent.registered` / `intent.published` como eventos reales del bus (hoy están limitados por `TransportEnvelopeV1.event_type` Literal)
- Integrar `seed_private_resolutions()` en el handler para resolver PII post-aprobación
- Implementar `resume_session()` desde la bandeja de decisiones humanas
- Motor de matchmaking: cruzar `interests` ∩ `capabilities` entre agentes `SEARCHING`
