# Deploy en Railway

## Servicios

El proyecto usa **2 servicios** en Railway:

### 1. Backend (FastAPI)
- **Directorio raíz**: `backend/`
- **Dockerfile**: `backend/Dockerfile`
- **Puerto**: `8000`

### 2. Frontend (Next.js)
- **Directorio raíz**: `frontend/`
- **Dockerfile**: `frontend/Dockerfile`
- **Puerto**: `3000`

### 3. Redis
- Usar el **plugin de Redis** de Railway (no Docker).

---

## Variables de entorno

### Backend

| Variable | Valor | Obligatoria |
|---|---|---|
| `PORTAL_SECRET_KEY` | `sk_...` (tu key de Portal) | ✅ |
| `REDIS_URL` | URL de Redis (Railway la provee automático) | ✅ |
| `AGENTSYNC_LLM_PROVIDER` | `openai` o `fake` (demo) | ✅ |
| `OPENAI_API_KEY` | Tu API key de OpenAI | Solo si usás `openai` |
| `AGENTSYNC_LLM_MODEL` | `gpt-4o-mini` | No |
| `AGENTSYNC_MAX_TURNS` | `8` | No |

### Frontend

| Variable | Valor | Obligatoria |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | URL del backend en Railway (ej: `https://agent-sync-backend.up.railway.app`) | ✅ |

---

## Pasos en Railway

1. **Crear proyecto** en Railway
2. **Agregar Redis** desde el marketplace de plugins
3. **Agregar servicio Backend**:
   - Source: GitHub repo
   - Root directory: `backend/`
   - Configurar variables de entorno
4. **Agregar servicio Frontend**:
   - Source: GitHub repo
   - Root directory: `frontend/`
   - Variable `NEXT_PUBLIC_API_URL` = URL del servicio backend
5. **Seed data** (opcional): ejecutar `python scripts/seed_demo_data.py` en el backend

---

## Desarrollo local

```bash
# Redis
docker compose up -d redis

# Backend
cd backend && py -3 main.py

# Frontend
cd frontend && npm run dev
```
