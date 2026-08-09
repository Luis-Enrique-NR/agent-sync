# Portal Token Endpoint Specification

## Purpose

Server-side proxy for Portal token minting, enabling `@portalsdk/react` to authenticate users via a secure backend endpoint.

## Requirements

| # | Requirement | Strength | Summary |
|---|------------|----------|---------|
| 1 | HttpPortalClient supports token minting | MUST | `mint_token()` method calls Portal's `POST /v1/tokens` with secret key Bearer auth |
| 2 | GET /api/portal-token proxies Portal token API | MUST | Accepts `?userId=` query param, delegates to `mint_token()`, returns `{ token, expiresAt }` |

### Requirement 1: Token Minting Method

The system MUST add a `mint_token(userId, claims=None, channels=None, ttl=None)` method to `HttpPortalClient` in `backend/transport/portal.py`. The method MUST call `POST https://api.useportal.co/v1/tokens` with `Authorization: Bearer <secret_key>`, body `{ userId, claims?, channels?, ttl? }`, and return the parsed `{ token, expiresAt }` response.

#### Scenario: Mint token for a user

- GIVEN a valid secret key and userId `"user-1"`
- WHEN `mint_token(userId="user-1")` is called
- THEN Portal API is called and returns `{ token: "<jwt>", expiresAt: "<ISO8601>" }`

#### Scenario: Token minting with optional claims and TTL

- GIVEN userId `"agent-42"`, claims `{ role: "agent" }`, ttl `"1h"`
- WHEN `mint_token(userId="agent-42", claims={"role":"agent"}, ttl="1h")` is called
- THEN the request body includes claims and ttl, and a valid token is returned

#### Scenario: Portal API returns error

- GIVEN the Portal token API returns 401 (unauthorized)
- WHEN `mint_token()` is called
- THEN the method raises an exception carrying the Portal error context

### Requirement 2: Token Proxy Endpoint

The system MUST expose `GET /api/portal-token` that accepts a `userId` query parameter, delegates to `HttpPortalClient.mint_token()`, and returns `{ token, expiresAt }` with status 200. The endpoint MUST be mounted in `backend/api/app.py`.

#### Scenario: Successful token proxy

- GIVEN the backend is running and Portal API is reachable
- WHEN `GET /api/portal-token?userId=test-user` is called
- THEN the response is 200 with body `{ "token": "<jwt>", "expiresAt": "<datetime>" }`

#### Scenario: Missing userId parameter

- GIVEN the token endpoint
- WHEN `GET /api/portal-token` is called without a `userId` query parameter
- THEN the response is 422 with a validation error

#### Scenario: Portal API timeout

- GIVEN the Portal token API times out
- WHEN `GET /api/portal-token?userId=test-user` is called
- THEN the response is 502 with an error message indicating upstream unavailability
