# Tasks: Portal Transport Integration

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 900–1,250 authored lines |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | Gate → admission → bus → administration |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 0 | Confirm backend handoff | Coordination | `git show origin/codex/ai-backend:backend/pyproject.toml` | N/A: no runtime behavior | Handoff record |
| 1 | Verified admission | PR 1 | `cd backend; python -m pytest tests/test_portal_webhooks.py tests/test_portal_api.py` | ASGI with injected fakes | `api/`, webhook transport, docs/tests |
| 2 | Durable delivery | PR 2 | `cd backend; python -m pytest tests/test_redis_bus.py` | Disposable Redis restart/reclaim | Bus transport, docs/tests |
| 3 | Typed administration | PR 3 | `cd backend; python -m pytest tests/test_portal_client.py` | MockTransport and offline fake | Portal adapters, docs/tests |

## Phase 1: Coordination and Compatibility

- [ ] 1.1 Confirm `origin/codex/ai-backend` is available and agree its branch-based incorporation/handoff; do not merge, copy, modify, or own `backend/ai`.
- [ ] 1.2 Record the gate in next `docs/seguimiento/N. Portal transport integration handoff.md` with all required documentation metadata.
- [ ] 1.3 Provision Redis ownership, Portal secret/webhook configuration, and only MCP-documented Portal operations before enabling any route or consumer.

## Phase 2: Webhook Admission

- [x] 2.1 Add RED tests for invalid, missing, altered, and stale exact-byte signatures rejecting before parse/enqueue; then add strict models, settings, verifier, and normalizer.
- [x] 2.2 Create `backend/api/app.py` and `portal_webhooks.py`: verify raw bytes first; map `200`/`400`/`401`/`503` contract outcomes.
- [x] 2.3 Add RED/green tests for published and audit-only retracted envelopes, unsupported no-write behavior, and no AI/Portal-administration invocation.
- [x] 2.4 Pair PR 1 with next `docs/seguridad/N. Portal webhook admission.md` and `docs/pruebas/N. Webhook evidence.md`, with required metadata/evidence.

## Phase 3: Durable Internal Bus

- [x] 3.1 Add RED Redis tests for duplicate ID, atomic failure (no records), restart/reclaim, success-only `XACK`, and failure pending.
- [x] 3.2 Create `DurableEventBus` and Redis Streams adapter: prevalidated atomic Lua acceptance, group setup, `XAUTOCLAIM`, `ack`, and failure metadata.
- [x] 3.3 Pair PR 2 with next `docs/arquitectura/N. Durable transport bus.md` and `docs/pruebas/N. Redis evidence.md`, with required metadata/evidence.

## Phase 4: Portal Administration

- [x] 4.1 Add RED tests for closed authorized commands, unknown shapes making zero calls, and timeouts not retrying mutations.
- [x] 4.2 Create typed commands/outcomes, `PortalAdmin`, lifespan-scoped `HttpPortalClient`, and recording fake using documented operations only.
- [x] 4.3 Pair PR 3 with next `docs/arquitectura/N. Portal administration seam.md` and `docs/pruebas/N. Portal adapter evidence.md`, with required metadata/evidence.

## Phase 5: Rollout Boundary

- [ ] 5.1 Update `backend/pyproject.toml`, `.env.example`, and `README.md` with transport dependencies, settings, run/test steps, and preserve-Redis rollback.
- [ ] 5.2 Before each PR, verify its focused command and runtime harness, document the exact result, and keep docs/tests in that same work unit; mark superseded historical docs `Replaced`, never delete them.
