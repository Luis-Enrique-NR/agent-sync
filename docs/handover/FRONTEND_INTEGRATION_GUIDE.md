# Frontend Integration Guide — AgentSync

**Audiencia:** Anthony (Frontend Lead)
**Rama:** `feat/consolidacion-backend`

---

## 1. Requisitos y Configuración Rápida (< 5 min)

```bash
git clone https://github.com/Luis-Enrique-NR/agent-sync.git
cd agent-sync
git checkout feat/consolidacion-backend

# Opción A: Docker (Redis incluido)
docker compose up -d

# Opción B: Manual
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[test]" uvicorn python-dotenv
copy .env.example .env
# Editar .env:
#   PORTAL_SECRET_KEY=demo-secret
#   OPENAI_API_KEY=demo-key
#   AGENTSYNC_LLM_PROVIDER=fake

# Sembrar datos y arrancar
cd ..
python scripts/seed_demo_data.py
cd backend
python main.py
# -> http://localhost:8000
# -> http://localhost:8000/docs (OpenAPI / Swagger)
```

---

## 2. Endpoints y Mapeo de Pantallas

| Pantalla MVP | Endpoint | Método | Payload clave en respuesta |
|-------------|----------|--------|---------------------------|
| Configuración del Agente | `POST /api/v1/agents` | POST | `agent_id`, `display_name`, `status`, `interests`, `capabilities`, `price_range` |
| Dashboard (estado) | `GET /api/v1/agents/{id}` | GET | `status` (`AVAILABLE`/`BUSY`/`PAUSED`), `created_at` |
| Ecosistema / Portal | `GET /api/v1/agents` | GET | Array de agentes con `interests`/`capabilities` |
| Conversación agente-agente | `GET /api/v1/negotiations/{id}` | GET | `transcript[]` con `speaker_id`, `turn_index`, `public_message`, `intent` |
| Bandeja de decisiones | `GET /api/v1/negotiations?agent_id={id}` | GET | Array filtrable por `status=PENDING_HUMAN_APPROVAL` |
| Match confirmado | `GET /api/v1/negotiations/{id}` | GET | `status=RESOLVED`, `closed_at`, `turn_count` |

### Ejemplo: GET /api/v1/negotiations/c0000000-0000-0000-0000-000000000001

```json
{
  "session_id": "c0000000-...",
  "agent_1_id": "b0000000-...",
  "agent_2_id": "b0000000-...",
  "status": "ACTIVE",
  "portal_channel_id": "ch_demo_b2b_active",
  "turn_count": 4,
  "transcript": [
    {
      "speaker_id": "b0000000-...",
      "turn_index": 1,
      "public_message": "Buenos dias. Tenemos disponibilidad...",
      "intent": "OFFER",
      "approved_by_human": false
    }
  ]
}
```

---

## 3. Manejo de Estados de Aprobación

### POST /api/v1/negotiations/{id}/approval

```json
// APPROVE
{"action": "APPROVE", "reason": "Precio aceptable"}
// REJECT
{"action": "REJECT", "reason": "Fuera de presupuesto"}
// REPLACE
{"action": "REPLACE", "replacement_turn": "Nueva propuesta con envio incluido"}
```

**Estados:** `SEARCHING` → `ACTIVE` → `PENDING_HUMAN_APPROVAL` → `RESOLVED` / `REJECTED` / `FAILED`

---

## 4. Agentes de Prueba Pre-cargados

| ID | Nombre | Tipo | Intereses | Capacidades |
|----|--------|------|-----------|-------------|
| `b0000000-...0001` | Agente Ventas SaaS TechCorp | company | `enterprise_saas`, `bulk_deals` | `saas_platform`, `volume_discount` |
| `b0000000-...0002` | Agente Venta Laptop Usada | person | `sell_laptop`, `quick_sale` | `sell_electronics`, `weekend_delivery` |

## 5. Sesiones de Prueba Pre-cargadas

| ID | Estado | Turnos | Descripción |
|----|--------|--------|-------------|
| `c0000000-...0001` | `ACTIVE` | 4 | Negociación B2B en curso |
| `c0000000-...0002` | `PENDING_HUMAN_APPROVAL` | 3 | Venta P2P — oferta bajo límite, espera decisión |

---

## 6. Troubleshooting

| Síntoma | Solución |
|---------|----------|
| `PORTAL_SECRET_KEY is required` | Setear en `.env`: `PORTAL_SECRET_KEY=demo` |
| `OPENAI_API_KEY` missing | Setear: `OPENAI_API_KEY=demo`, `AGENTSYNC_LLM_PROVIDER=fake` |
| `ModuleNotFoundError: uvicorn` | `pip install uvicorn` |
| Redis `connection refused` | `docker compose up -d redis` o ignorar (tests usan fake bus) |
