# Design: Portal Transport Integration

## Technical Approach

Add a FastAPI imperative shell under `backend/api/` and keep transport models, verification, and adapters under `backend/transport/`. This follows the AI branch's strict Pydantic models, `Protocol` seams, injected fakes, and environment composition. The executable AI base is `origin/backend/ai` at `5dc00c5`, incorporated by tracker merge `094c444`; the transport chain extends it without owning `backend/ai`. No transport module imports `backend/ai` or initiates domain work.

## Architecture Decisions

### Decision: Verify before parsing

| Option | Tradeoff | Decision |
|---|---|---|
| FastAPI `Request.body()` → pure verifier → strict parse | Requires manual OpenAPI body schema | Chosen: preserves exact bytes; cache the server-fetched secret briefly; return `401` for invalid/stale signatures and `503` when the secret is unavailable. |
| Parsed request model first | Convenient but changes the signed representation | Rejected. |

### Decision: Redis Streams bus

| Option | Tradeoff | Decision |
|---|---|---|
| Stream + consumer group + dedupe hash | Requires Redis and recovery logic | Chosen: one Lua operation prevalidates key types, checks event ID, and writes both records; uncertain client results are resolved by retrying the same ID. `XAUTOCLAIM` recovers stale work and `XACK` follows success only. |
| In-memory queue or RQ | Loses restart safety or obscures the required acceptance contract | Rejected. |

### Decision: Closed Portal command interface

| Option | Tradeoff | Decision |
|---|---|---|
| Discriminated commands with required `authorization_id` | Backend owns authorization provenance | Chosen: only publish, add/remove member, and ban/unban are modeled; there is no arbitrary HTTP method/path escape hatch. |
| Endpoint-shaped public methods | Larger, easier-to-misuse interface | Rejected. |

### Decision: Real and fake adapters

| Option | Tradeoff | Decision |
|---|---|---|
| Injected `PortalAdmin`/`WebhookSecretProvider` protocols | Two adapters to maintain | Chosen: shared outcomes and errors give offline parity; `HttpPortalClient` owns one lifespan-scoped `httpx.AsyncClient`. |
| Patch network calls in tests | Couples tests to implementation | Rejected. |

## Data Flow

```text
Portal ─POST→ fixed webhook route ─raw bytes→ verify ─parse/normalize→ Redis Stream
                                                    duplicate ─────→ 200, no write
Backend worker ─receive/reclaim→ domain handling (outside scope) ─success→ XACK
Backend-authorized command ─→ PortalAdmin ─→ HTTP or fake adapter ─→ typed outcome
```

`message.retracted` becomes an audit envelope only. Portal also emits webhooks for server publishes; ingestion therefore never calls AI or Portal administration, preventing a transport-owned echo loop.

## File Changes

| File | Action | Description |
|---|---|---|
| `backend/api/__init__.py`, `backend/api/app.py`, `backend/api/portal_webhooks.py` | Create | Composition root and raw-body webhook route. |
| `backend/transport/__init__.py`, `backend/transport/config.py`, `backend/transport/models.py`, `backend/transport/webhooks.py` | Create | Public exports, validated settings, strict payload/envelope/command models, verification and normalization. |
| `backend/transport/bus.py`, `backend/transport/redis_bus.py` | Create | Async bus protocol and Redis Streams adapter. |
| `backend/transport/portal.py`, `backend/transport/fake_portal.py` | Create | Protocols, HTTP adapter, and recording fake. |
| `backend/tests/test_portal_webhooks.py`, `backend/tests/test_redis_bus.py`, `backend/tests/test_portal_client.py`, `backend/tests/test_portal_api.py` | Create | Unit, contract, Redis, and route coverage. |
| `backend/pyproject.toml`, `backend/.env.example`, `backend/README.md` | Modify | Add API/transport packages, FastAPI/HTTPX/redis test dependencies, server-only settings, and run instructions. |

## Interfaces / Contracts

- `TransportEnvelopeV1`: strict `schema_version=1`, Portal event ID/type/time/environment/channel, and strict message snapshot; retractions require `retracted=true` and `content=null`.
- `DurableEventBus`: async `accept(envelope)`, `receive(consumer, lease_ms)`, `ack(delivery)`, and `fail(delivery, code)`; failure records metadata but leaves the stream entry pending.
- `PortalAdmin.execute(AuthorizedPortalCommand)`: closed union returning `PublishedMessage(id, seq, timestamp)` or `CommandApplied`; validation or unsupported shapes make zero network calls.
- `PortalOutcome`: distinguishes rejected, retryable, and uncertain failures; mutation POSTs are not retried automatically after an ambiguous timeout.
- `POST /webhooks/portal`: `200` after durable acceptance and for duplicate/unsupported events, `401` invalid/stale signature, `400` verified malformed event, and `503` secret/bus unavailable. Parsing occurs only after verification.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | Exact-byte HMAC, header/tolerance cases, strict normalization, command closure, fake parity, no ingestion-triggered publish | Fixed clocks/secrets and Pydantic fixtures. |
| Integration | Atomic duplicate/failure, restart reclaim, success-only ack | Disposable real Redis; recreate clients/consumers between steps. |
| E2E | HTTP status and route-to-stream flow | HTTPX ASGI transport with injected secret provider and Redis; no live Portal dependency. |
| Contract | Paths, bearer auth, bodies, outcomes, timeout/error mapping | HTTPX `MockTransport`. |

## Threat Matrix

The fixed HTTP route is applicable routing, so the matrix was reviewed; its executable/VCS cases are not part of this change.

| Boundary | Minimum adversarial cases | Applicability | Design response | Planned RED tests |
|---|---|---|---|---|
| Documentation-like paths | `requirements.txt`, `CMakeLists.txt`, executable Markdown/MDX, `README.sh` | N/A: no file classification/execution | No path-to-execution seam | None |
| Git repository selection | `git -C`, relative paths, absolute paths | N/A: no Git invocation | No repository selector | None |
| Commit state | staged, `commit -a`, empty index | N/A: no VCS mutation | No index/worktree behavior | None |
| Push state | tracking branch, first push, explicit refspec | N/A: no push automation | No ref resolution | None |
| PR commands | explicit `--head`, environment prefix, composed commands | N/A: no PR/process commands | No command composition | None |

## Migration / Rollout

No data migration required. The AI base is already incorporated through `094c444`; provision owned Redis persistence, create the consumer group idempotently, then enable the route after Portal webhook activation and server-side secret retrieval. Rollback disables route/consumers without deleting streams or dedupe records.

## Open Questions

None.
