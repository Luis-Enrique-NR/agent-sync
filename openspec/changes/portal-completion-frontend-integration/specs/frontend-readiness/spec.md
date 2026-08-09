# Frontend Readiness Specification

## Purpose

Real-time Server-Sent Events streaming for negotiation transcripts, Portal SDK frontend integration, and developer onboarding documentation.

## Requirements

| # | Requirement | Strength | Summary |
|---|------------|----------|---------|
| 1 | SSE endpoint streams negotiation transcript events | MUST | `GET /api/v1/negotiations/{id}/stream` pushes `TranscriptMessageDTO` via SSE, per-session `asyncio.Queue`, CancelledError cleanup, idle timeout |
| 2 | Portal SDK packages installed | MUST | `@portalsdk/core` and `@portalsdk/react` added to frontend dependencies |
| 3 | Frontend environment example | MUST | `frontend/.env.example` with `NEXT_PUBLIC_API_URL=http://localhost:8000` |
| 4 | Frontend developer setup documented | MUST | `docs/frontend/DEVELOPER_SETUP.md` with exact steps |

### Requirement 1: SSE Transcript Stream

The system MUST expose `GET /api/v1/negotiations/{session_id}/stream` that establishes a Server-Sent Events (SSE) connection. The endpoint MUST use a per-session `asyncio.Queue` to buffer `TranscriptMessageDTO` events (new turns, status changes). The connection MUST close and release all resources on `asyncio.CancelledError` (client disconnect). The endpoint MUST apply an idle timeout that cleanly closes the connection after a configured period of inactivity.

#### Scenario: Client connects and receives new turn events

- GIVEN an active negotiation session with id `"abc-123"`
- WHEN a client opens `GET /api/v1/negotiations/abc-123/stream` and a new turn is published
- THEN an SSE event with `data: { "session_id": "abc-123", "turn_index": N, ... }` is pushed to the client

#### Scenario: Client disconnects, resources cleaned

- GIVEN a connected SSE client
- WHEN the client disconnects (triggers `asyncio.CancelledError`)
- THEN the per-session Queue is removed and no orphaned asyncio tasks remain

#### Scenario: Idle timeout closes connection

- GIVEN an active SSE connection with no events published for the configured idle period
- WHEN the idle timeout expires
- THEN the server closes the connection cleanly with no error logged at WARNING or above

#### Scenario: Nonexistent session

- GIVEN a session ID that does not exist in the database
- WHEN `GET /api/v1/negotiations/nonexistent-id/stream` is called
- THEN the response is 404

### Requirement 2: Portal SDK Packages

The system MUST include `@portalsdk/core` and `@portalsdk/react` as dependencies in `frontend/package.json`.

#### Scenario: Packages are installable

- GIVEN the updated `package.json`
- WHEN `npm install` is run in the `frontend/` directory
- THEN both `@portalsdk/core` and `@portalsdk/react` are installed without errors

### Requirement 3: Frontend Environment Example

The system MUST provide `frontend/.env.example` containing at minimum `NEXT_PUBLIC_API_URL=http://localhost:8000`.

#### Scenario: Developer copies env example

- GIVEN `frontend/.env.example` exists
- WHEN a developer copies it to `.env.local`
- THEN `NEXT_PUBLIC_API_URL` is configured to point at the local backend

### Requirement 4: Developer Setup Documentation

The system MUST provide `docs/frontend/DEVELOPER_SETUP.md` with exact steps to: install frontend dependencies, configure environment variables, start the backend, start the frontend dev server, and verify that `@portalsdk/react` components are importable.

#### Scenario: Developer follows setup steps

- GIVEN a clean checkout of the repository
- WHEN the developer follows the documented steps in order
- THEN the backend starts on port 8000, the frontend starts on port 3000, and `@portalsdk/react` can be imported in app code
