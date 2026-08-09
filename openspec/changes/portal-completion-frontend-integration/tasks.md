# Tasks: Portal Completion + Frontend Integration

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~218 |
| 800-line budget risk | Low |
| Chained PRs recommended | No |
| Delivery strategy | ask-on-risk |
| Decision needed before apply | No |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

## Phase 1 — Backend Runnable

- [ ] 1.1 **ADD** `backend/main.py` — compose all deps, FastAPI lifespan starting EDA consumer via `asyncio.create_task(consume_forever(...))`, graceful `CancelledError` shutdown, `uvicorn.run(app)`. Verify: `uvicorn backend.main:app` starts without error.
- [ ] 1.2 **ADD** `backend/transport/secret_fetcher.py` — `WebhookSecretFetcher` implementing `WebhookSecretProvider` protocol. Lazy-init on first `get_secret()`, POST to Portal API, cache result, invalidate on signature failure with 5s cooldown, return None when unreachable. Verify: `pytest backend/tests/transport/test_secret_fetcher.py -v`.
- [ ] 1.3 **FIX** `backend/eda/handlers.py` — inspect `PortalOutcome` in `_handle_message_published()`: `PortalRetryable`/`PortalUncertain` → re-raise for `bus.fail()`; `PortalRejected` → `logger.warning` + return (implicit `bus.ack()`). Verify: `pytest backend/tests/eda/test_handlers.py -v -k "outcome"`.
- [ ] 1.4 **FIX** `backend/api/v1/endpoints/agents.py` — delete duplicate lines 128–145 (second get_agent + list_agents). Verify: `pytest backend/tests/api/v1/test_agents.py -v`.
- [ ] 1.5 **ADD** `GET /health` to `backend/api/app.py` — returns `{status: "ok", version: "0.1.0"}`. Verify: `curl localhost:8000/health` → 200 with expected JSON.
- [ ] 1.6 **ADD** `uvicorn` to `backend/pyproject.toml` dependencies. Verify: `pip install -e backend/.` succeeds.

## Phase 2 — Portal Token Endpoint

- [ ] 2.1 **ADD** `mint_token(userId, claims=None, channels=None, ttl=None)` to `HttpPortalClient` in `backend/transport/portal.py` — POST to Portal token API, returns `{token, expiresAt}`. 401 → `PortalAuthError`, timeout → `PortalUncertain`. Verify: `pytest backend/tests/transport/test_portal.py -v -k "mint_token"`.
- [ ] 2.2 **ADD** `GET /api/portal-token?userId=` route to `backend/api/app.py` — calls `mint_token()`, returns `{token, expiresAt}`. Missing param → 422, upstream error → 502. Verify: `curl "localhost:8000/api/portal-token?userId=test"` → 200.

## Phase 3 — Frontend Readiness

- [ ] 3.1 **ADD** `backend/api/v1/sse.py` — `SessionQueueManager` with `dict[session_id, asyncio.Queue]`, 5-min idle timeout, `CancelledError` cleanup. Wire `GET /api/v1/negotiations/{session_id}/stream` in `app.py`. Validate session (404 if missing), `StreamingResponse` on `text/event-stream`. On disconnect: remove queue. Verify: `pytest backend/tests/api/v1/test_sse.py -v`.
- [ ] 3.2 **INSTALL** `@portalsdk/core` + `@portalsdk/react` in `frontend/package.json`. Verify: `npm ls @portalsdk/core @portalsdk/react` — both found.
- [ ] 3.3 **ADD** `frontend/.env.example` — `NEXT_PUBLIC_API_URL=http://localhost:8000`. Verify: file exists with expected content.
- [ ] 3.4 **ADD** `docs/frontend/DEVELOPER_SETUP.md` — setup steps: copy .env.example, `npm install`, `npm run dev` on :3000, backend on :8000, SDK importable. Verify: manual walkthrough matches all steps.
