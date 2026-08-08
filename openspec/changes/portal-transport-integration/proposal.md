# Proposal: Portal Transport Integration

## Intent

Build a reliable Portal transport seam that authenticates inbound events, preserves accepted work across restarts, and executes only Backend-authorized commands. Transport makes no business decisions.

## Scope

### In Scope
- Ingest `message.published` and `message.retracted`: verify raw bodies and timestamps, deduplicate, normalize, and enqueue.
- Provide a Redis-backed asynchronous bus behind a small interface; pending messages survive restarts.
- Provide a typed Portal client interface with HTTP and fake adapters for publishing and documented access administration.
- Audit capture of `message.retracted` without automatic negotiation rollback.

### Out of Scope
- LangGraph, prompts, guardrails, private `value_ref` resolution, domain persistence, matchmaking, frontend behavior, or decisions about when to publish or invoke AI.

## Capabilities

### New Capabilities
- `portal-webhook-ingestion`: Verify, deduplicate, normalize, and enqueue supported Portal events.
- `durable-internal-event-bus`: Persist typed transport envelopes in Redis with restart-safe consumption.
- `portal-administration-client`: Execute authorized publishing and documented channel/access commands through typed real and fake adapters.

### Modified Capabilities
- None.

## Approach

Verify Portal HMAC signatures against exact request bytes before parsing. Normalize events into versioned envelopes and atomically coordinate Redis deduplication and enqueueing by event ID. Consumers acknowledge completed work only. Backend API/Matchmaking remains authoritative over AI invocation and access lifecycle; the adapter executes documented commands only.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `backend/api/` | New | Portal webhook entry point |
| `backend/transport/` | New | Verification, bus, Portal client/fake |
| `pyproject.toml`, `.env.example` | Modified | Runtime dependencies and configuration |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Signature mistakes | Medium | Official-algorithm contract tests |
| Dedupe/enqueue race | Medium | Atomic Redis operation and restart tests |
| Portal contract drift | Medium | Implement MCP-documented operations only; block missing methods |

## Rollback Plan

Disable the route and worker, remove the Portal webhook target if needed, and revert the release without deleting Redis data. After restoration, verify before replaying preserved envelopes.

## Dependencies

- Available Redis deployment and operational ownership.
- Portal secret/webhook configuration and official MCP documentation.
- Backend command/envelope contract; undocumented access operations block corresponding methods.

## Success Criteria

- [ ] 100% of invalid or stale signatures are rejected before parsing or enqueueing.
- [ ] Repeated delivery of one Portal event ID produces exactly one queued envelope.
- [ ] Pending accepted envelopes remain consumable after API and worker restarts.
- [ ] `message.retracted` creates an audit envelope and triggers no automatic rollback.
- [ ] Publishing and documented access commands pass offline fake-adapter tests.
