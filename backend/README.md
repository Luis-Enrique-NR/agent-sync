# AgentSync Backend — AI Brain

This first backend slice implements the `/backend/ai` domain described by the SRD. It is intentionally independent from REST, persistence, and Portal.

## Setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
```

Set `OPENAI_API_KEY` only on the server. The default tests use a scripted provider and do not need credentials.

## Test

```powershell
python -m pytest
```

## Public integration surface

```python
from ai.service import build_engine_from_env

engine = build_engine_from_env()
result = engine.start_session(profile_a, profile_b)

# Persist result.state and its events in Backend API.
# Later, pass the persisted state back to resume_session.
```

Only events of type `TURN_READY` may be sent to the counterpart. `APPROVAL_REQUIRED` belongs in the human decision inbox. `CANDIDATE_BLOCKED` is an audit event and must never be published as agent speech.
