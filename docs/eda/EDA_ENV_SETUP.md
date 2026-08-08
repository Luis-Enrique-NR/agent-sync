# EDA Environment Setup — Guía técnica

- **Estado:** Aceptada
- **Fecha:** 2026-08-08
- **Rama:** `feat/eda-worker`
- **Alcance:** Capa EDA de Dominio (Ingesta, Bus, Workers, Handlers, Auditoría)
- **Excluido:** Matchmaking y lógica de compatibilidad

---

## 1. Requisitos de Infraestructura Local

| Componente | Requerido | Versión | Notas |
|-----------|----------|---------|-------|
| Python | ✅ | 3.11+ | `python --version` |
| Redis | ⚠️ Opcional | 7.x | Tests de bus usan `TracedFakeBus` sin Redis. Para `test_redis_bus.py` se necesita Redis corriendo. |
| SQLite | ✅ | incluido en Python | `sqlmodel` gestiona el archivo `dev_eda.db` |
| Docker | ⚠️ Opcional | — | Solo si se quiere Redis vía contenedor |

### Stack de dependencias

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1      # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -e ".[test]"
```

Paquetes instalados: `langgraph`, `openai`, `pydantic`, `sqlmodel`, `aiosqlite`, `fastapi`, `httpx`, `redis`, `pytest`, `pytest-asyncio`

---

## 2. Variables de Entorno

Copiar `.env.example` a `.env` y ajustar según entorno local:

```env
# ── AI Engine ──
OPENAI_API_KEY=
AGENTSYNC_LLM_MODEL=gpt-4o-mini
AGENTSYNC_LLM_TIMEOUT_SECONDS=25
AGENTSYNC_LLM_MAX_RETRIES=1
AGENTSYNC_MAX_TURNS=8
AGENTSYNC_SESSION_TIMEOUT_SECONDS=90

# ── Transport / Portal ──
PORTAL_WEBHOOK_TOLERANCE_SECONDS=300
REDIS_URL=redis://localhost:6379/0
PORTAL_SECRET_KEY=
PORTAL_WEBHOOK_URL=

# ── EDA Consumer (solo desarrollo local) ──
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///./dev_eda.db
EDA_CONSUMER_POLL_INTERVAL=0.1

# ── Feature flags ──
MATCHMAKING_ENABLED=false
```

**Notas:**
- `REDIS_URL` vacío es válido — los tests de bus se saltan automáticamente
- `OPENAI_API_KEY` vacío es válido — los tests del engine usan `ScriptedLLMProvider`
- `MATCHMAKING_ENABLED=false` es **obligatorio** en esta fase

---

## 3. Inicio rápido

```bash
# 1. Verificar entorno
python scripts/check_eda_env.py

# 2. Ejecutar suite EDA completa
pytest backend/tests/test_eda_consumer.py backend/tests/test_eda_e2e_trace.py -v

# 3. Suite completa del proyecto
pytest

# 4. Ver traza del último E2E
type logs\eda_e2e_trace.log      # Windows
# cat logs/eda_e2e_trace.log     # Linux/macOS
```

---

## 4. Matriz de Diagnóstico

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| `ConnectionRefusedError: Redis` | Redis no está corriendo | Iniciar Redis o ignorar — los tests usan `TracedFakeBus` (solo `test_redis_bus.py` requiere Redis real) |
| `OperationalError: no such table` | Migraciones no aplicadas | Ejecutar `python -c "from persistence.database import init_db; init_db()"` |
| `ModuleNotFoundError: langgraph` | Dependencias no instaladas | `pip install -e ".[test]"` dentro del venv |
| `HMAC verification failed` | Secret mismatch | Copiar `.env.example` a `.env` |
| `2 skipped` en test summary | Redis no disponible (esperado) | Aceptable — los 2 tests son `test_redis_bus.py` |
| `ImportError: cannot import name 'NegotiationHandler'` | Rama incorrecta | `git checkout feat/eda-worker` |

---

## 5. Servicios opcionales

### Redis vía Docker

```bash
docker run -d --name agent-sync-redis -p 6379:6379 redis:7-alpine
```

Con Redis corriendo, los 2 tests de `test_redis_bus.py` pasan (actualmente saltan).

### Sin Redis

Todos los tests de dominio EDA (8 consumer + 1 E2E) son **determinísticos y no requieren Redis**. Usan `FakeDurableEventBus` en memoria.

---

## 6. Script de diagnóstico

```bash
python scripts/check_eda_env.py
```

Salida esperada:
```
[ENV_OK]    Python 3.14.6
[ENV_OK]    SQLite dev_eda.db initialized
[ENV_WARN]  Redis not available on localhost:6379 (tests will skip)
[ENV_OK]    MATCHMAKING_ENABLED=false (correcto para esta fase)
[ENV_OK]    Entorno EDA correctamente configurado
```

---

## 7. Feature flags activas en esta fase

| Flag | Valor | Significado |
|------|-------|-------------|
| `MATCHMAKING_ENABLED` | `false` | Motor de compatibilidad **no** implementado ni probado |
| `EDA_CONSUMER_POLL_INTERVAL` | `0.1` | Solo para desarrollo local (producción: 1.0+) |
| `AGENTSYNC_LLM_MODEL` | `gpt-4o-mini` | Modelo por defecto; los tests usan proveedor falso |
