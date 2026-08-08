# Matchmaking Architecture — Fases 1, 2 y 3

- **Estado:** Completada
- **Fecha:** 2026-08-08
- **Rama:** `feat/eda-worker`

---

## Fase 1 — Quick-Win: Orquestación Completa

### Objetivo
Conectar `find_matches()` con el pipeline EDA y el SDK de Portal para que al registrarse un agente compatible se cree automáticamente la negociación y se emita el primer mensaje del AI Brain.

### Componentes

| Archivo | Rol |
|---------|-----|
| `matchmaking/service.py` | `find_matches()` — intersección de etiquetas `interests ∩ capabilities` |
| `matchmaking/orchestrator.py` | `process_agent_matching()` — canal Portal + engine + estado |
| `eda/handlers.py` | `_handle_agent_event()` → dispara `process_agent_matching()` |
| `scripts/demo_quickwin_match.py` | Demo E2E: registra 2 agentes, match, 8 turnos, PENDING_HUMAN_APPROVAL |

### Flujo

```
agent.registered
  └─ _handle_agent_event()
     └─ process_agent_matching()
        ├─ find_matches() → compatible agents
        ├─ AddChannelMembers() → Portal channel
        ├─ engine.start_session() → AI negotiation
        ├─ update_agent_status() → BUSY
        └─ write_audit() → SESSION_CREATED
```

---

## Fase 2 — Scoring Bidireccional

### Objetivo
Evolucionar `find_matches()` para soportar compatibilidad bidireccional, filtros duros de precio/logística y ordenamiento por score.

### Componentes

| Archivo | Rol |
|---------|-----|
| `matchmaking/evaluator.py` | `calculate_match_score()`, `price_ranges_conflict()`, `logistics_score()`, `interests_capabilities_score()` |
| `ai/domain/models.py` | `AgentProfile.price_range`, `AgentProfile.logistics_preferences` |

### Fórmula de scoring

```
calculate_match_score(a, b):
  if price_ranges_conflict(a, b) → 0.0
  ic = (a→b + b→a) / 2           # average of both directions
  if ic == 0.0 → 0.0
  return 0.7 * ic + 0.3 * logistics_score(a, b)
```

- **`price_ranges_conflict`**: `a.max < b.min or b.max < a.min`
- **`logistics_score`**: Jaccard `|A ∩ B| / |A ∪ B|`
- **`interests_capabilities_score`**: promedio simple (permite matches unidireccionales)

---

## Fase 3 — Resiliencia: Cooldown y Re-Match

### Objetivo
Dotar al motor de manejo de ciclo de vida completo (liberación/re-intentos) y evitar re-emparejamientos fallidos mediante un Cooldown Window.

### Componentes

| Archivo | Rol |
|---------|-----|
| `matchmaking/evaluator.py` | `is_in_cooldown()` — consulta `negotiation_states` por sesiones cerradas recientes |
| `matchmaking/service.py` | `find_matches()` filtra pares en cooldown |
| `eda/handlers.py` | `_handle_negotiation_closed()` — libera agentes y re-dispara matchmaking |

### Cooldown Window

```
is_in_cooldown(a, b, session, cooldown_minutes=60):
  SELECT * FROM negotiation_states
  WHERE status IN ("REJECTED", "FAILED")
    AND closed_at >= now() - 60min
    AND {agent_1_id, agent_2_id} = {a, b}
  → True if match found
```

### Re-match automático

```
negotiation.failed / negotiation.rejected
  └─ _handle_negotiation_closed()
     ├─ update_agent_status(a1 → AVAILABLE)
     ├─ update_agent_status(a2 → AVAILABLE)
     ├─ write_audit(SESSION_FAILED / SESSION_REJECTED)
     └─ process_agent_matching(initiator_id)
```

---

## Infraestructura y Dependencias

### Redis (opcional)

Los 2 tests de `test_redis_bus.py` requieren un servidor Redis local. Si no está disponible, `pytest` los salta automáticamente:

```python
await redis.ping()  # ← si falla → pytest.skip("Redis is unavailable")
```

**No es necesario Redis para el desarrollo de dominio.** Todos los tests EDA y matchmaking usan `FakeDurableEventBus` determinístico.

### Warning httpx/starlette

```
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated
```

Proviene de `fastapi.testclient` usando `httpx<2`. No afecta funcionalidad. Se resuelve actualizando a `httpx>=2` en el futuro.

---

## Suite de pruebas

| Categoría | Tests | Archivos |
|-----------|-------|----------|
| EDA Consumer | 8 | `test_eda_consumer.py` |
| EDA E2E Trace | 1 | `test_eda_e2e_trace.py` |
| AI Engine | 8 | `test_engine.py` |
| Escalation | 2 | `test_escalation.py` |
| Guardrails | 6 | `test_guardrails.py` |
| Models | 3 | `test_models.py` |
| OpenAI Provider | 1 | `test_openai_provider.py` |
| Matchmaking (F1) | 5 | `test_matchmaking.py` |
| Matchmaking Scoring (F2) | 5 | `test_matchmaking_scoring.py` |
| Matchmaking Resilience (F3) | 3 | `test_matchmaking_resilience.py` |
| Portal API | 4 | `test_portal_api.py` |
| Portal Client | 11 | `test_portal_client.py` |
| Portal Webhooks | 4 | `test_portal_webhooks.py` |
| Redis Bus | 2 (skip) | `test_redis_bus.py` |
| **Total** | **61 passed + 2 skipped** | |

---

## Backlog / Pendientes

| Prioridad | Ítem |
|-----------|------|
| Alta | Embeddings semánticos vectoriales para matching semántico (más allá de tags) |
| Alta | Distributed locks en Redis para evitar race conditions en matchmaking concurrente |
| Media | `resume_session()` desde bandeja humana (PENDING_HUMAN_APPROVAL → ACTIVE) |
| Media | `seed_private_resolutions()` integrado en handler para PII post-aprobación |
| Baja | Migrar `TransportEnvelopeV1.event_type` a admitir los nuevos eventos de dominio |
| Baja | Actualizar `httpx` a v2 para eliminar el warning de Starlette |
