# Backend Runnable Specification

## Purpose

Entry point and infrastructure to start the backend, verify Portal webhook secrets, fix the EDA ACK logic, remove duplicate endpoint definitions, and expose a health endpoint.

## Requirements

| # | Requirement | Strength | Summary |
|---|------------|----------|---------|
| 1 | Entry point composes and starts backend | MUST | `main.py` loads settings, wires Redis bus + HttpPortalClient, creates FastAPI app, launches EDA consumer as background task, starts uvicorn |
| 2 | WebhookSecretProvider fetches and caches signing secret | MUST | Reads `PORTAL_SECRET_KEY` env var, fetches webhook secret from Portal API, caches in memory, re-fetches on verification failure |
| 3 | EDA handler inspects PortalOutcome before ACK/FAIL | MUST | Retryable/Uncertain outcomes → re-raise for `bus.fail()`; Rejected → log + ack |
| 4 | Duplicate endpoint definitions removed | MUST | Lines 128-145 in `agents.py` must not exist |
| 5 | Health endpoint returns status | MUST | `GET /health` returns `{ "status": "ok", "version": "0.1.0" }` |

### Requirement 1: Backend Entry Point

The system MUST provide `backend/main.py` that loads TransportSettings from environment, creates an HttpPortalClient, connects a Redis-backed DurableEventBus, composes the FastAPI app via `create_app()`, launches `consume_forever()` as a background asyncio task on startup, and calls `uvicorn.run()`. The entry point MUST add `uvicorn` as a dependency in `pyproject.toml`.

#### Scenario: Backend starts successfully

- GIVEN valid env vars (`PORTAL_SECRET_KEY`, `REDIS_URL`, `OPENAI_API_KEY`)
- WHEN `uvicorn backend.main:app` is executed
- THEN the server starts, logs startup, and the EDA consumer polls the bus for deliveries

#### Scenario: Missing required environment variable

- GIVEN `PORTAL_SECRET_KEY` is not set
- WHEN the entry point loads settings
- THEN the process exits with a clear error message before binding the port

### Requirement 2: WebhookSecretProvider Implementation

The system MUST implement a concrete class (replacing the Protocol-only stub at `backend/transport/portal.py:15`) that reads `PORTAL_SECRET_KEY` from the environment, calls `GET https://api.useportal.co/v1/webhooks/secret` with `Authorization: Bearer <secret_key>`, caches the returned signing secret in memory on first fetch, and invalidates the cache to re-fetch on any signature verification failure.

#### Scenario: Initial fetch succeeds

- GIVEN `PORTAL_SECRET_KEY` is set to a valid Portal secret key
- WHEN the provider's `get_secret()` is called for the first time
- THEN it fetches the webhook signing secret from Portal and returns it

#### Scenario: Signature verification triggers re-fetch

- GIVEN a previously cached webhook secret
- WHEN a webhook request fails HMAC signature verification
- THEN the cached secret is invalidated and re-fetched before the next verification attempt

#### Scenario: Portal API unavailable

- GIVEN the Portal API returns an error or times out
- WHEN `get_secret()` is called
- THEN the provider returns `None`, and the webhook endpoint MUST respond 503

### Requirement 3: EDA Handler PortalOutcome Inspection

The system MUST inspect the `PortalOutcome` returned by `self._portal.execute(cmd)` in `NegotiationHandler._handle_message_published()` (currently lines 237-240 of `eda/handlers.py`). When the outcome is `PortalRetryable` (rate_limited or transient) or `PortalUncertain` (timeout), the handler MUST re-raise an exception so the consumer calls `bus.fail()`. When the outcome is `PortalRejected`, the handler MUST log the rejection and continue without raising, allowing normal ACK.

#### Scenario: Retryable failure triggers bus.fail()

- GIVEN a Portal publish returns `PortalRetryable` (HTTP 429 or 5xx)
- WHEN the EDA handler inspects the outcome
- THEN an exception is raised, caught by `consume_forever()`, and `bus.fail(delivery, ...)` is called

#### Scenario: Timeout triggers bus.fail()

- GIVEN a Portal publish returns `PortalUncertain` (timeout)
- WHEN the EDA handler inspects the outcome
- THEN an exception is raised so the consumer retries via `bus.fail()`

#### Scenario: Permanent rejection is ACKed

- GIVEN a Portal publish returns `PortalRejected` (invalid data, forbidden)
- WHEN the EDA handler inspects the outcome
- THEN the rejection is logged, no exception is raised, and `bus.ack(delivery)` is called

### Requirement 4: Remove Duplicate Endpoint Definitions

The system MUST NOT contain duplicate endpoint definitions. Lines 128-145 in `backend/api/v1/endpoints/agents.py` — which duplicate `get_agent` and `list_agents` — MUST be removed.

#### Scenario: Each endpoint defined once

- GIVEN the file `backend/api/v1/endpoints/agents.py`
- WHEN inspected for route definitions
- THEN `get_agent` appears exactly once and `list_agents` appears exactly once

### Requirement 5: Health Endpoint

The system MUST expose `GET /health` returning status 200 with body `{ "status": "ok", "version": "0.1.0" }`. The endpoint SHALL be mounted in `backend/api/app.py`.

#### Scenario: Health check returns ok

- GIVEN the backend is running
- WHEN `GET /health` is called
- THEN the response is 200 with `{ "status": "ok", "version": "0.1.0" }`
