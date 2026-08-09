# Frontend API Specification — AgentSync

- **Versión:** 1.0
- **Rama:** `feat/eda-worker`
- **Audiencia:** Anthony (Frontend) y equipo de integración

---

## Base URL

```
http://localhost:8000/api/v1
```

---

## Endpoints

### 1. POST /api/v1/agents — Registrar agente

**Request:**
```json
{
  "display_name": "Valentina",
  "entity_type": "person",
  "public_description": "Vende bicicleta urbana usada",
  "personality": "Amable, directa",
  "objectives": ["Vender la bicicleta"],
  "interests": ["sell_used_bicycle", "find_buyer_nearby"],
  "capabilities": ["sell_bicycle", "weekend_availability"],
  "price_range": {"min": 300, "max": 500},
  "logistics_preferences": ["cash_payment", "public_meeting"]
}
```

**Response 201:**
```json
{
  "agent_id": "f0000000-0000-0000-0000-000000000001",
  "user_id": "a0000000-0000-0000-0000-000000000099",
  "display_name": "Valentina",
  "entity_type": "person",
  "status": "AVAILABLE",
  "public_description": "Vende bicicleta urbana usada",
  "interests": ["sell_used_bicycle", "find_buyer_nearby"],
  "capabilities": ["sell_bicycle", "weekend_availability"],
  "price_range": {"min": 300, "max": 500},
  "logistics_preferences": ["cash_payment", "public_meeting"],
  "objectives": ["Vender la bicicleta"],
  "created_at": "2026-08-08T18:00:00Z",
  "updated_at": "2026-08-08T18:00:00Z"
}
```

---

### 2. GET /api/v1/agents/{agent_id} — Perfil de agente

**Response 200:** Igual que POST response.

**Response 404:** `{"detail": "agent not found"}`

---

### 3. GET /api/v1/agents — Listar agentes

**Response 200:**
```json
{
  "agents": [ ... ],
  "total": 5
}
```

---

### 4. GET /api/v1/negotiations?agent_id={id} — Negociaciones de un agente

**Response 200:**
```json
{
  "negotiations": [
    {
      "session_id": "b0000000-0000-0000-0000-000000000100",
      "agent_1_id": "b0000000-0000-0000-0000-000000000001",
      "agent_2_id": "b0000000-0000-0000-0000-000000000002",
      "status": "ACTIVE",
      "portal_channel_id": "ch_match_f0000000_f0000000",
      "turn_count": 3,
      "started_at": "2026-08-08T17:30:00Z",
      "closed_at": null
    }
  ],
  "total": 1
}
```

---

### 5. GET /api/v1/negotiations/{session_id} — Detalle con transcript

**Response 200:**
```json
{
  "session_id": "b0000000-0000-0000-0000-000000000100",
  "agent_1_id": "...",
  "agent_2_id": "...",
  "status": "ACTIVE",
  "portal_channel_id": "ch_match_f0000000_f0000000",
  "turn_count": 3,
  "started_at": "2026-08-08T17:30:00Z",
  "closed_at": null,
  "initiator_id": "...",
  "max_turns": 8,
  "deadline_at": "2026-08-08T17:32:00Z",
  "last_error_code": null,
  "transcript": [
    {
      "speaker_id": "f0000000-0000-0000-0000-000000000001",
      "turn_index": 1,
      "public_message": "Hola! Vi que buscas una bicicleta.",
      "intent": "OFFER",
      "approved_by_human": false,
      "created_at": "2026-08-08T17:30:01Z"
    }
  ]
}
```

---

### 6. POST /api/v1/negotiations/{session_id}/approval — Decisión humana

**Request:**
```json
{
  "action": "APPROVE",
  "reason": "Precio aceptable"
}
```

**Response 200:**
```json
{
  "decision_id": "d0000000-0000-0000-0000-000000000001",
  "session_id": "b0000000-0000-0000-0000-000000000100",
  "action": "APPROVE",
  "new_status": "ACTIVE"
}
```

**Acciones válidas:** `APPROVE`, `REJECT`, `REPLACE`

**Response 400:** Si la sesión no está en `PENDING_HUMAN_APPROVAL`

---

### 7. GET /api/v1/negotiations/{session_id}/audit — Traza de auditoría

**Response 200:**
```json
{
  "records": [
    {
      "audit_id": "c0000000-0000-0000-0000-000000000001",
      "action": "SESSION_CREATED",
      "actor_type": "SYSTEM",
      "severity": "INFO",
      "reason": "matched agent=f000... interests->capabilities",
      "occurred_at": "2026-08-08T17:30:00Z"
    },
    {
      "audit_id": "c0000000-0000-0000-0000-000000000002",
      "action": "TURN_PUBLISHED",
      "actor_type": "LLM",
      "severity": "INFO",
      "reason": "channel=ch_match_f0000000_f0000000 author=... seq=1",
      "occurred_at": "2026-08-08T17:30:01Z"
    }
  ],
  "total": 2
}
```

---

## Máquina de Estados de Negociación

```
SEARCHING
    │  matchmaking encuentra candidato
    ▼
ACTIVE ◄─────────────────────────────┐
    │                                │
    │  escalamiento detectado        │  humano APRUEBA
    ▼                                │  humano REEMPLAZA
PENDING_HUMAN_APPROVAL ─────────────┘
    │
    │  humano RECHAZA
    ▼
REJECTED  (terminal — agentes liberados)
    │
    │  (DECLINE explícito del agente)
    ▼
COMPLETED / RESOLVED  (terminal)

FAILED  (timeout, guardrail agotado — terminal)
```

### Qué renderizar según estado

| Estado | Componente Frontend |
|--------|-------------------|
| `SEARCHING` | Spinner de búsqueda — "Buscando agentes compatibles..." |
| `ACTIVE` | Chat en vivo con transcript |
| `PENDING_HUMAN_APPROVAL` | Bandeja de decisión con `APPROVE` / `REJECT` / `REPLACE` |
| `RESOLVED` | Pantalla de match confirmado — revelar contacto |
| `REJECTED` | Pantalla de descarte |
| `FAILED` | Mensaje de error con `last_error_code` |

## Códigos HTTP

| Código | Significado |
|--------|-------------|
| 200 | OK |
| 201 | Agente creado |
| 400 | Estado inválido (ej. aprobar sesión no pendiente) |
| 404 | Recurso no encontrado |
| 422 | Validación fallida (campo inválido) |
