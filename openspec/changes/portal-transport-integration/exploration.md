# Exploration: portal-transport-integration

## Current State

AgentSync's PRD/SRD describe four layers: a Next.js/React frontend, a Python Backend API, a LangChain/LangGraph AI Brain, and a Portal SDK middleware layer. The AI Brain already exists on `origin/codex/ai-backend` as a bounded domain module. It exposes a small, deterministic contract:

```text
start_session(...) -> EngineResult
run_until_pause(state) -> EngineResult
resume_session(state, human_decision) -> EngineResult
```

where `EngineResult = NegotiationState + list[EngineEvent]`. The engine never imports Portal, persistence, REST, or transport concerns. Events are typed: `TURN_READY` (authorized agent speech), `APPROVAL_REQUIRED` (human inbox), `CANDIDATE_BLOCKED` / `SESSION_RESOLVED` / `SESSION_REJECTED` / `SESSION_FAILED` (audit/internal).

The current `work/alexa` branch contains only the OpenSpec bootstrap (`openspec/config.yaml`, `openspec/specs/`, `openspec/changes/`). No Backend API, transport, or Portal integration code exists yet. Existing decision documents under `docs/` on `origin/main` are written in neutral professional Spanish and define the AI Brain boundary and the hard-limit vs. sensitive-decision separation.

Portal documentation (retrieved via MCP) confirms the integration surface:

- Webhooks are project-level and relay `message.published` and `message.retracted` as signed HTTP POSTs.
- Signature header: `portal-signature: t=<unix-seconds>,v1=<hex>`.
- Verification: `HMAC-SHA256(secret, "{t}.{rawBody}")` using the exact raw body bytes, constant-time comparison, and a timestamp tolerance.
- Secret is fetched server-side with `GET /v1/webhooks/secret` (secret key) and should be cached; it is stable across deploys.
- Delivery is at-least-once with retries at 30s, 5m, 30m, 2h, and 6h; deduplicate on the top-level event `id`.
- Server-side REST includes `POST /v1/channels/{channelId}/messages` (secret-key server publish, `senderId` required, content ≤ 2KB), `POST /v1/users/{userId}/notifications`, plus channel membership/bans and config endpoints.

## Affected Areas

- `backend/api/` (new) — owns HTTP routes, the Portal webhook endpoint, persistence calls, and enqueueing work to the internal bus.
- `backend/transport/` or `backend/portal/` (new) — owns the Portal SDK abstraction, webhook verification, server publishing, notifications, and channel access helpers.
- `backend/ai/domain/models.py` (read-only contract) — `EngineResult` / `EngineEvent` is the integration seam; transport must not modify it.
- `pyproject.toml` / backend package manifest (new or extended) — dependencies for HTTP client, web framework, bus, and any crypto/hmac utilities.
- `.env.example` (new or extended) — Portal secret key, API base URL, webhook tolerance, bus/redis settings.
- `docs/arquitectura/` (future) — a transport-boundary ADR should be added if a hard-to-reverse seam decision is made during design.

## Scope Boundary

This change owns the **authenticated webhook ingestion pipeline**, the **resilient internal asynchronous message bus/queue**, and the **internal Portal SDK abstraction for channel and access administration**.

It explicitly does **not** own:

- LangGraph orchestration or agent turn generation (AI Brain).
- Deterministic guardrails or escalation policies (AI Brain policies).
- Domain persistence schema or matchmaking logic (Backend API / Domain).
- Frontend behavior, UI copy, or client-side Portal SDK usage (Frontend).
- Resolution of private `value_ref` values into real secrets (a secure component owned by Backend API/Domain).

Transport may publish already-authorized public messages and route events; it must not decide what is safe to publish.

## Approaches

### Internal Bus

#### 1. In-memory `asyncio` queue + FastAPI background tasks

A single Python process runs the web server and one or more worker tasks consuming an `asyncio.Queue`. The webhook handler verifies and parses the Portal event, checks deduplication, and enqueues a command. A worker dequeues, invokes Backend API / AI Brain orchestration, and uses the Portal SDK to publish results.

- **Pros:** Zero external infrastructure; fastest setup for a 36-hour hackathon; trivial local demo; no serialization/versioning complexity.
- **Cons:** Messages are lost on process restart; no horizontal scaling; retries and dead-letter behavior must be re-implemented in-process; a crash during processing can lose the demo turn.
- **Effort:** Low
- **Delivery semantics:** At-least-once only if the handler acks after enqueue and the worker never crashes; in practice best-effort within a single process.
- **Idempotency:** Must be implemented explicitly with an in-memory or persistent dedupe store keyed by Portal event `id`.
- **Retries/Dead-letter:** Manual retry loop inside the worker; no durable dead-letter without extra code.
- **Testability:** High in unit tests (replace the queue with a list), but does not exercise durability.
- **Demo resilience:** Medium — works well if the server stays up, but fragile to restarts.

#### 2. Redis Streams / Redis Queue (RQ) with a small worker pool

Use Redis as a durable stream or queue. The webhook handler pushes verified events to a stream. Separate worker processes consume, run the orchestration, and publish back to Portal. Redis also stores the deduplication set and retry counters.

- **Pros:** Survives restarts; supports explicit retries and a dead-letter stream; allows multiple workers; good demo resilience if Redis is available locally or via Docker.
- **Cons:** Requires a Redis service; more setup time; serialization/deserialization overhead; workers must be started separately.
- **Effort:** Medium
- **Delivery semantics:** At-least-once with explicit acknowledgment; unacknowledged messages can be redelivered.
- **Idempotency:** Natural with Redis `SETNX` on event `id` before enqueue.
- **Retries/Dead-letter:** Easy to implement with stream consumer groups or RQ's retry/dead-letter patterns.
- **Testability:** Medium — can use fakeredis or a test Redis container; tests must cover serialization.
- **Demo resilience:** High — the most robust option that still fits a hackathon if Redis is part of the environment.

### Portal SDK Adapter Shape

#### A. Thin HTTP adapter

A small module wrapping `httpx`/`requests` for the exact endpoints needed: fetch webhook secret, server publish, send notification, and channel membership/bans if matchmaking needs them.

- **Pros:** Minimal dependencies; easy to mock with responses/HTTPretty; no hidden SDK behavior; exact control over headers and retries.
- **Cons:** Must manually track URL paths, auth headers, rate limits, and error codes; more boilerplate if the endpoint surface grows.
- **Effort:** Low

#### B. Typed `PortalClient` class with a fake adapter

A class exposing a narrow interface such as `verify_webhook(raw_body, signature, secret)`, `publish(channel_id, sender_id, content)`, `notify(user_id, payload)`, `get_webhook_secret()`, with an internal HTTP client and in-memory secret caching. A `FakePortalClient` implements the same interface for offline demos and tests.

- **Pros:** Clean seam that matches the codebase-design deep-module vocabulary; testable without network; hides URL/auth details; can evolve behind the interface.
- **Cons:** Slightly more upfront design; still requires raw-body discipline at the HTTP entry point.
- **Effort:** Low-Medium

### Webhook Verification Placement

Verification belongs at the **HTTP entry point**, before any JSON parsing or business logic:

1. Capture the exact raw request bytes (e.g., FastAPI/Starlette raw body middleware or `Request.body()`).
2. Read `portal-signature` header.
3. Fetch and cache the secret from `GET /v1/webhooks/secret`.
4. Compute `HMAC-SHA256(secret, "{t}.{rawBody}")` and compare in constant time.
5. Reject with `401` on failure; return `200` as soon as possible after successful verification.
6. Deduplicate on the top-level event `id` immediately after verification and before enqueueing to the bus.

The verification module should live in the transport/SDK package, but the HTTP route that calls it lives in Backend API.

## Recommendation

For a 36-hour hackathon, choose the **in-memory `asyncio` queue** for the bus to keep the runtime stack minimal, but hide it behind a small `MessageBus` interface so it can be swapped for Redis/RQ later without changing business logic.

Adopt the **typed `PortalClient` class with a fake adapter**. It gives the cleanest seam, is easy to mock for offline demos, and keeps webhook verification isolated at the HTTP entry point.

Place the new module adjacent to the AI Brain under `backend/transport/` (or `backend/portal/`). The exact package name should be confirmed with the Backend API owner because the bus and SDK will be consumed by that domain. Do not hardcode the final path until that ownership point is agreed.

Do not implement LangGraph, guardrails, domain persistence, matchmaking, or frontend behavior in this change.

## Risks

- **Backend API ownership overlap.** The bus and SDK are called by Backend API, but transport must not leak into matchmaking or persistence. Agree on the `MessageBus` and `PortalClient` interfaces before implementation starts.
- **Raw body handling mistakes.** If the web framework parses JSON before HMAC verification, signatures will fail. Must use raw bytes at the route level.
- **At-least-once duplication.** Portal retries on non-2xx or timeout. Without idempotency keyed on event `id`, duplicate agent turns can be triggered.
- **Private reference resolution.** The AI Brain emits opaque `value_ref` values for sensitive data. Transport must never resolve or publish actual secret values; resolution belongs to a secure component owned by Backend API/Domain.
- **Demo fragility.** An in-memory bus loses in-flight messages on crash or restart. For the live pitch, avoid server restarts and keep a scripted fallback path.
- **Insufficient evidence for exact channel lifecycle.** Portal docs describe publishing and membership, but the project has not yet decided whether channels are created implicitly on first use or pre-provisioned by matchmaking. The design phase must clarify this before implementing channel administration helpers.

## Documentation Gaps

The following Portal behaviors are not fully specified in the retrieved evidence and should be resolved before design is finalized:

1. Exact request/response shape for channel membership and ban endpoints (paths, required fields, idempotency).
2. Whether server-published messages trigger webhooks back to the same project, and how to avoid echo loops.
3. Recommended timestamp tolerance for webhook signature verification (Portal docs show the algorithm but not a canonical window).
4. Whether `message.retracted` webhooks need any action from AgentSync beyond audit logging.

## Ready for Proposal

Yes. The exploration has enough evidence to write a proposal, but the proposal should first confirm two things with the Backend API owner:

1. The package name and repository location for the transport module (`backend/transport/` vs. `backend/portal/`).
2. The bus choice (in-memory with a swappable interface vs. Redis) based on whether Redis will be available in the hackathon environment.

Until those are resolved, do not commit to an implementation path.
