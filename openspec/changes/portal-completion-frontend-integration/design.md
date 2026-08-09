# Design: Portal Completion + Frontend Integration

## Architecture Overview

```
main.py ──→ create_app()
              ├── TransportSettings.from_env()
              ├── WebhookSecretFetcher(PORTAL_SECRET_KEY, PORTAL_WEBHOOK_URL)
              ├── RedisStreamsEventBus(redis.from_url(REDIS_URL))
              ├── HttpPortalClient(secret)           ← Phase 2 mint_token
              └── NegotiationHandler(engine, portal)

              lifespan:
                start → asyncio.create_task(consume_forever(bus, handler))
                stop  → cancel consumer task

              routes:
                /health              → static {status, version}
                /webhooks/portal     → existing
                /api/portal-token    → Phase 2 proxy
                /api/v1/*            → existing
                /api/v1/negotiations/{id}/stream → Phase 3 SSE
```

## Architecture Decisions

### Decision 1: EDA consumer startup

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `asyncio.create_task` in FastAPI lifespan | Shares event loop; consumer cancels cleanly on shutdown; zero new deps | **Chosen** |
| Separate thread | Thread-safe Redis concerns; harder graceful shutdown | Rejected |
| Subprocess | Full isolation but operational complexity; overkill for co-located consumer | Rejected |

**Rationale**: `consume_forever()` already handles `CancelledError` for graceful shutdown. FastAPI lifespan's `shutdown` event is the natural hook. Single event loop means no thread-safety issues with the existing `get_session()` pattern.

### Decision 2: WebhookSecretFetcher caching

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Lazy-init + invalidate-on-failure + 5s cooldown | First request pays fetch cost; avoids hammering Portal on repeated failures | **Chosen** |
| Fetch at startup | Simplest but blocks startup on Portal availability | Rejected |
| TTL-based refresh | Adds complexity without clear benefit given signature-failure-driven invalidation | Rejected |

**Rationale**: The webhook path already handles `get_secret() is None → 503`. Lazy-init keeps startup fast. Invalidation-on-failure matches the spec scenario: "signature failure triggers secret re-fetch". The 5s cooldown prevents a burst of bad-signature requests from flooding the Portal API.

### Decision 3: Health endpoint

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Static JSON `{status, version}` | Fast, no deps; sufficient for readiness probes | **Chosen** |
| Redis + Portal connectivity check | More informative but couples health to external services | Rejected |

**Rationale**: The spec requires `{ status: "ok", version: "0.1.0" }`. A deeper readiness check belongs in a future `/health/ready` endpoint, not this phase.

### Decision 4: Portal token endpoint auth

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `?userId=` query param | No auth system needed; appropriate for Phase 2 | **Chosen** |
| Session/auth header | Requires auth infrastructure not in scope | Deferred |

### Decision 5: SSE event fan-out

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `dict[session_id, asyncio.Queue]` + callback from handler | Simple; zero new deps; handler calls SSE module's publish fn | **Chosen** |
| Event bus (second Redis stream) | Decoupled but adds Redis overhead per SSE event | Rejected |
| Direct async generator polling DB | Simpler code but adds polling latency | Rejected |

**Rationale**: `NegotiationHandler._handle_message_published()` already processes turns. After `save_negotiation_state()`, it calls `_sse_broadcaster.notify(session_id, TranscriptMessageDTO(...))` if a broadcaster is injected. The SSE endpoint does `queue = get_or_create_queue(session_id)` then `async for msg in queue`. On disconnect, the queue is removed; idle timeout (5 min) cleans orphaned queues.

## Data Flow Diagrams

### Startup
```
main.py → load .env → TransportSettings.from_env()
       → WebhookSecretFetcher(env)         [lazy, no fetch yet]
       → redis.from_url(REDIS_URL)         [connects]
       → RedisStreamsEventBus(redis)
       → NegotiationHandler(engine, portal)
       → create_app(settings, secret_provider, bus)
       → lifespan: create_task(consume_forever(bus, handler))
       → uvicorn.run(app)
```

### Webhook Secret Fetch
```
portal_webhooks.py: get_secret() → fetcher._secret is None?
  YES → POST {PORTAL_WEBHOOK_URL}/v1/webhook-secret
         Bearer {PORTAL_SECRET_KEY}
         → 200 → cache response.secret, return
         → fail → return None (webhook responds 503)
  NO  → return cached secret

  verify_portal_signature() fails?
    → invalidate cache → next webhook re-fetches (subject to 5s cooldown)
```

### PortalOutcome Decision
```
PortalAdmin.execute() returns PortalOutcome:
  PublishedMessage | CommandApplied → return (caller acks)
  PortalRetryable | PortalUncertain → raise PortalPublishError → bus.fail()
  PortalRejected → logger.warning → return (caller acks silently)
```

### Token Minting
```
frontend: GET /api/portal-token?userId=user-1
  → app.py route → HttpPortalClient.mint_token(userId)
    → POST https://api.useportal.co/v1/token {userId, claims?, ttl?}
       Bearer {PORTAL_SECRET_KEY}
    → 200 → {token, expiresAt}
    → 401 → raise PortalAuthError → 502
    → timeout → PortalUncertain → 502
  → 200 {token, expiresAt}
```

### SSE Event Flow
```
EDA handler: _handle_message_published()
  → engine.run_until_pause(state) → save result
  → for each TURN_READY event with audience=PUBLIC:
       publisher = {session_id: asyncio.Queue}
       await queue.put(TranscriptMessageDTO(...))

SSE endpoint: GET /api/v1/negotiations/{id}/stream
  → validate session exists (404 if not)
  → queue = get_or_create_queue(session_id)
  → StreamingResponse(event_generator(queue), media_type="text/event-stream")
  → on disconnect: remove queue, cancel generator
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/main.py` | **Create** | Load .env, wire deps, lifespan with consumer, uvicorn.run |
| `backend/transport/secret_fetcher.py` | **Create** | WebhookSecretFetcher: lazy-init, cache, invalidate, cooldown |
| `backend/transport/portal.py` | Modify | Add `mint_token()` to HttpPortalClient |
| `backend/eda/handlers.py` | Modify | Inspect PortalOutcome before ACK/FAIL; accept optional SSE broadcaster |
| `backend/api/v1/endpoints/agents.py` | Modify | Delete duplicate lines 128–145 |
| `backend/api/app.py` | Modify | Add GET /health, /api/portal-token, SSE stream route |
| `backend/api/v1/sse.py` | **Create** | SessionQueueManager, SSE endpoint generator |
| `backend/pyproject.toml` | Modify | Add `uvicorn` dep |
| `frontend/package.json` | Modify | Add `@portalsdk/core`, `@portalsdk/react` |
| `frontend/.env.example` | **Create** | `NEXT_PUBLIC_API_URL=http://localhost:8000` |
| `docs/frontend/DEVELOPER_SETUP.md` | **Create** | Startup instructions, env vars, SDK import |

## Error Handling

| Component | Failure | Response |
|-----------|---------|----------|
| WebhookSecretFetcher | Portal API down | `get_secret() → None` → webhook returns 503 |
| WebhookSecretFetcher | Stale secret | Signature fails → invalidate cache → next call re-fetches |
| HttpPortalClient | Token API timeout | `PortalUncertain` → 502 |
| HttpPortalClient | Token API 401 | `PortalAuthError` → 502 |
| EDA handler | PortalRejected on publish | Logged, no exception, bus.ack() |
| EDA handler | PortalRetryable/Uncertain on publish | Exception raised, bus.fail() |
| SSE endpoint | Nonexistent session | 404 |
| SSE endpoint | Idle > 5 min | Connection closed, queue removed |

## Testing Strategy

| Phase | Layer | What | Approach |
|-------|-------|------|----------|
| 1 | Unit | WebhookSecretFetcher cache/invalidate/cooldown | pytest-asyncio, mock httpx |
| 1 | Unit | PortalOutcome decision branches | pytest, import handler directly |
| 1 | Unit | Duplicate endpoints removed | pytest, FastAPI TestClient, verify route count |
| 1 | Unit | /health returns expected shape | pytest, TestClient |
| 1 | Integration | main.py starts, /health 200 | subprocess + httpx |
| 2 | Unit | mint_token happy + error paths | pytest-asyncio + respx |
| 2 | Unit | /api/portal-token with/without userId | pytest + TestClient |
| 3 | Unit | SSE queue lifecycle | pytest-asyncio |
| 3 | Unit | NegotiationHandler calls broadcaster | mock broadcaster, verify notify() called |
| 3 | Smoke | SSE connects + receives event | pytest-asyncio + httpx streaming |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. `main.py` starts uvicorn programmatically via `uvicorn.run()` (library call, not subprocess). The EDA consumer runs as an `asyncio.create_task` within the same event loop.

## Migration / Rollout

No migration required. Each phase is independently revertible by removing the new/modified files. Phase 3 frontend changes are additive (`package.json` deps, new docs file).

## Open Questions

None — all design decisions are resolved by the specs and existing codebase patterns.
