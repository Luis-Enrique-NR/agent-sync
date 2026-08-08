# AgentSync Backend

The AI Brain remains independent from REST, persistence, and Portal. Transport adds verified webhook admission, a durable Redis Streams bus, and a closed Portal publish adapter without changing `backend/ai`.

## Setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
```

Set `OPENAI_API_KEY`, `REDIS_URL`, and `PORTAL_SECRET_KEY` only in the server-side deployment secret store. `PORTAL_WEBHOOK_URL` is the public HTTPS callback URL configured in `portal.config.ts`; never expose these values to a frontend or commit them.

## Portal transport rollout

1. Provide durable Redis ownership and set `REDIS_URL` for the runtime; the disposable Docker Redis database 15 is test-only.
2. In the Portal project, set the project-level `webhooks.url` in `portal.config.ts` to the public HTTPS endpoint ending in `/webhooks/portal`, then run `portal deploy`.
3. After the webhook-bearing configuration is activated, fetch `GET /v1/webhooks/secret` server-side with `Authorization: Bearer <PORTAL_SECRET_KEY>` and inject the returned secret through `WebhookSecretProvider`. A 404 means the webhook configuration is not active.
4. Enable the route and consumers only after the real secret provider and Redis bus are composed by Backend API.

## Test

```powershell
pytest -q tests/test_portal_webhooks.py tests/test_portal_api.py
$env:REDIS_URL = "redis://localhost:6379/15"; pytest -q tests/test_redis_bus.py
pytest -q tests/test_portal_client.py
pytest -q
```

## Rollback

Disable the Portal webhook configuration and Backend route/consumers, then revert the transport release without deleting Redis stream or dedupe records. Restore verified configuration before replaying pending envelopes.

## Public integration surface

```python
from ai.service import build_engine_from_env

engine = build_engine_from_env()
result = engine.start_session(profile_a, profile_b)

# Persist result.state and its events in Backend API.
# Later, pass the persisted state back to resume_session.
```

Only events of type `TURN_READY` may be sent to the counterpart. `APPROVAL_REQUIRED` belongs in the human decision inbox. `CANDIDATE_BLOCKED` is an audit event and must never be published as agent speech.
