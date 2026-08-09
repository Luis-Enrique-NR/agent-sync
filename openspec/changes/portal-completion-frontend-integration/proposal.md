# Proposal: Portal Completion + Frontend Integration

## Intent

The backend has a working AI engine, persistence, REST API, and Portal webhook ingestion — but **cannot be started** (no entry point), has **no Portal token endpoint** (blocking `@portalsdk/react`), and has a **critical false-ACK bug** that would silently lose outbound Portal messages. The frontend consumes only static mock data. This change bridges both halves so the system is end-to-end runnable and the frontend can integrate with Portal SDK.

## Scope

### In Scope
- Backend entry point (`main.py`) composing all dependencies and launching EDA consumer
- Real `WebhookSecretProvider` (lazy-init, cache on first fetch, re-fetch on sig failure)
- Fix false-ACK: inspect `PortalOutcome`, re-raise retryable/uncertain, log+ack rejected
- Remove duplicate endpoint definitions in `agents.py`
- `GET /health` endpoint returning `{ status: "ok", version: "0.1.0" }`
- `GET /api/portal-token` endpoint proxying Portal's token mint API
- `HttpPortalClient.mint_token()` method
- SSE endpoint `GET /api/v1/negotiations/{session_id}/stream` for transcript streaming
- Install `@portalsdk/core` + `@portalsdk/react` in frontend
- Frontend `.env.example`, dev setup docs, type generation script

### Out of Scope
- Frontend type alignment with backend DTOs (separate change)
- CORS config from environment
- Dead-letter queue for failed publishes
- Rate limiting on token endpoint
- Shared Pydantic types between frontend and backend
- `portal.config.ts` deployment

## Capabilities

### New Capabilities
- `backend-startup`: Entry point composing app factory, Redis bus, Portal client, EDA consumer as background task
- `portal-token-endpoint`: Server-side token mint proxy for `@portalsdk/react`
- `transcript-sse-stream`: Real-time transcript push per negotiation session

### Modified Capabilities
- `portal-webhook-ingestion`: WebhookSecretProvider changed from Protocol-only to lazy-init implementation; false-ACK bug fixed via PortalOutcome inspection

## Approach

Three phases, each independently verifiable:

| Phase | Deliverable | Verification |
|-------|-------------|--------------|
| 1 — Backend Runnable | `main.py`, `WebhookSecretProvider`, false-ACK fix, duplicate cleanup, `/health` | `uvicorn backend.main:app` starts, `/health` returns 200, webhook handler correctly fails on retryable outcomes |
| 2 — Portal Token | `GET /api/portal-token` + `HttpPortalClient.mint_token()` | `curl localhost:8000/api/portal-token?userId=test` returns `{ token, expiresAt }` |
| 3 — Frontend Ready | SSE endpoint, `@portalsdk/*` installed, dev docs | SSE connectable, `npm run dev` starts with SDK imports |

Phase gating: each phase completes and is verified before starting the next. Phase 3 unblocks frontend development but defers type alignment to a follow-up change.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/main.py` | **New** | Entry point: compose deps, start uvicorn + EDA consumer |
| `backend/transport/portal.py` | Modified | Add `WebhookSecretProvider` class + `mint_token()` |
| `backend/eda/handlers.py` | Modified | Fix false-ACK via PortalOutcome inspection |
| `backend/api/v1/endpoints/agents.py` | Modified | Remove duplicate endpoints (L128–145) |
| `backend/api/app.py` | Modified | Mount `/health`, `/api/portal-token`, SSE stream route |
| `backend/pyproject.toml` | Modified | Add `uvicorn` dependency |
| `frontend/package.json` | Modified | Add `@portalsdk/core`, `@portalsdk/react` |
| `frontend/.env.example` | **New** | `NEXT_PUBLIC_API_URL` |
| `docs/frontend/DEVELOPER_SETUP.md` | **New** | Frontend dev onboarding |
| `scripts/generate-frontend-types.sh` | **New** | Type generation from `/openapi.json` |

## Risks

| Risk | Mitigation |
|------|------------|
| WebhookSecretProvider fetch fails at startup | Lazy-init on first webhook request; 503 with clear error until secret loads |
| Token endpoint hit by concurrent refreshes | `HttpPortalClient` handles Portal API contention; endpoint is stateless proxy |
| SSE connection leaks on consumer restart | Cleanup on `asyncio.CancelledError`, connection timeout on idle |
| Phase 3 blocks on unbounded type alignment | Explicitly deferred to follow-up change per scope |

## Rollback Plan

Each phase is independently revertible: remove `main.py` and revert `pyproject.toml` / `app.py` changes to undo Phase 1; revert token route and `HttpPortalClient` additions for Phase 2; revert SSE route, package.json, and new docs/files for Phase 3.

## Success Criteria

- [ ] `uvicorn backend.main:app` starts without errors, `/health` returns 200
- [ ] Webhook POST to `/webhooks/portal` with valid HMAC processes event, false-ACK no longer occurs on transient failures
- [ ] `GET /api/portal-token?userId=test` returns valid token from Portal API
- [ ] `GET /api/v1/negotiations/{id}/stream` establishes SSE connection and pushes transcript events
- [ ] `npm run dev` in frontend starts with `@portalsdk/*` packages importable
