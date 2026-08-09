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

# A sensitive inbound action pauses for its receiving owner. Approval does not
# execute it: first publish REVALIDATION_REQUIRED to the orchestration layer.
approved = engine.resume_session(result.state, human_decision)
continued = engine.apply_revalidation(approved.state, revalidation_result)

# Authenticated withdrawals and expirations may arrive while a human decision
# is pending. Applying the same external event twice is idempotent.
withdrawn = engine.apply_external_event(result.state, external_event)
```

Only events with `audience=PUBLIC` may leave the AI Brain for the counterpart. The
engine currently assigns that audience exclusively to `TURN_READY`; integration code
should validate both fields before publishing.

`APPROVAL_REQUIRED` belongs in the human decision inbox. It may contain opaque
references needed to approve a proposed disclosure, so it must remain internal.
`CANDIDATE_BLOCKED`, decision and session lifecycle events are also internal and must
never be published as agent speech.

An `AgentTurn` distinguishes two privacy operations:

- `data_requests` asks the counterpart for a category and never carries a `value_ref`.
- `proposed_disclosures` proposes sharing one of the speaker's own opaque references.

After approval, public transcripts and `TURN_READY` events retain only the disclosed
category, never the opaque reference or the real protected value.

Meeting and other counterpart requests use `requested_actions`. They are evaluated
against the receiving agent's `REQUEST_ACTION` rules after the public turn is
accepted by outbound guardrails. If a rule matches, the receiving owner gets an
`INBOUND_ACTION` decision. Approving it moves the session to `REVALIDATING`; only a
matching proposal revision can resume the LLM with a fresh execution timeout.

`COUNTERPART_WITHDREW` and `PROPOSAL_EXPIRED` are terminal business outcomes, not
technical failures. A resolved agreement emits one internal
`GOAL_PROGRESS_REVIEW_REQUIRED` per participant so Domain/Persistence can ask the
owner whether to complete or continue the objective.

## Tools and MCP boundary

The model cannot execute tools directly. It returns a structured `ProviderStep` with
either a public `TURN` or one private `TOOL_CALL`. `ToolGateway` then checks:

- the capability is registered and enabled in the agent's `tool_grants`;
- every argument is allowlisted and has the declared primitive type;
- the descriptor's minimum approval cannot be weakened by agent configuration;
- external writes have explicit human approval;
- the same `call_id` is not executed twice;
- timeouts, failures and oversized outputs become sanitized internal results.

The default composition root still registers deterministic simulations for local
tests. Production can select `AGENTSYNC_TOOLS_PROVIDER=mcp` and point
`AGENTSYNC_MCP_SERVERS_JSON` at the first-party Streamable HTTP server in
[`mcp_servers/README.md`](mcp_servers/README.md), which exposes web search,
calendar, prices, inventory, email and meeting capabilities. The email and
meeting operations are always treated as external writes and pause for human
approval. Tool results remain private to the requesting agent and are never
emitted as `TURN_READY`.

`MCPToolAdapter` is the provider-agnostic boundary for the remote MCP client.
`HTTPMCPClient` speaks Streamable HTTP, validates JSON-RPC responses, sends the
current protocol envelope and supports bounded `tools/list` discovery. Only
locally registered tool names and schemas reach it. Authentication tokens,
server URLs and transport retries belong in the injected server-side `MCPClient`,
not in agent profiles, model prompts, transcripts or tool arguments.

Each session also has `max_tool_calls`, independent from `max_turns`, so a model cannot
replace a conversation loop with an unbounded tool loop.
