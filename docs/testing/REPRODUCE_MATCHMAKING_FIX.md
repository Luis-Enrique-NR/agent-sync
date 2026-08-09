# Reproduce Matchmaking Fix — Guía de Replicación Local

- **Audiencia:** Anthony (Frontend) y equipo
- **Rama:** `feat/eda-worker`

---

## 1. Configuración Local

```bash
cd agent-sync/backend
python -m venv .venv
.venv\Scripts\Activate.ps1      # Windows
pip install -e ".[test]"
```

**Requisitos:** Python 3.11+, `.env` creado desde `.env.example` (no se necesita `OPENAI_API_KEY` para tests).

---

## 2. Réplica Paso a Paso

```bash
git checkout feat/eda-worker
git pull origin feat/eda-worker
pytest tests/integration/test_api_agent_eda_pipeline.py -v
python scripts/demo_e2e_frontend_flow.py
```

---

## 3. Salida Esperada

### `pytest` output

```
tests/integration/test_api_agent_eda_pipeline.py::test_register_agent_triggers_full_eda_matchmaking_cycle PASSED
tests/integration/test_api_agent_eda_pipeline.py::test_two_compatible_agents_trigger_matchmaking PASSED
```

### `demo_e2e_frontend_flow.py` output

```
================================================================
  AgentSync -- Frontend E2E Flow Demo
================================================================

[HTTP 201] Registering Seller...
  -> Agent ID: ... Status: AVAILABLE

[HTTP 201] Registering Buyer...
  -> Agent ID: ... Status: AVAILABLE

[DB Update] After matchmaking:
  Valentina: BUSY
  Mateo:     BUSY

[DB Update] Negotiation Session Created:
  Session ID: 5ae85144-405c-4997-904f-3265a74f2f0f
  Status:     PENDING_HUMAN_APPROVAL
  Channel:    ch_match_...

[Audit] 1 record(s) written
  [INFO] SESSION_CREATED

================================================================
  MATCHMAKING E2E CYCLE VERIFIED SUCCESSFULLY
================================================================
```

---

## 4. Verificación Manual vía API

```bash
# 1. Registrar vendedor
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{"display_name":"Seller","entity_type":"person","public_description":"t","personality":"t","objectives":["t"],"interests":["sell_bike"],"capabilities":["buy_bike"]}'

# 2. Registrar comprador
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{"display_name":"Buyer","entity_type":"person","public_description":"t","personality":"t","objectives":["t"],"interests":["buy_bike"],"capabilities":["cash"]}'

# 3. Ver negociaciones
curl http://localhost:8000/api/v1/negotiations | jq .
```

---

## 5. Troubleshooting

| Síntoma | Causa | Solución |
|---------|-------|----------|
| Agentes quedan en `AVAILABLE` | `agent.registered` no llega al handler | Verificar que `message.author_id` esté poblado en el envelope |
| `ModuleNotFoundError: langgraph` | Dependencias no instaladas | `pip install -e ".[test]"` |
| `OPENAI_API_KEY` missing | Engine intenta usar OpenAI real | Los tests usan `ScriptedLLMProvider` — no necesita API key |
