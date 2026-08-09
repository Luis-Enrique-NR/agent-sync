# Developer Setup — AgentSync Frontend

This guide walks through setting up the full stack (backend + frontend) for local development.

## Prerequisites

- Python 3.12+
- Node.js 20+
- Redis 7+ (running on `localhost:6379`)

## 1. Clone & Checkout

```bash
git clone <repo-url> agent-sync
cd agent-sync
git checkout feat/runtime-contract-reconciliation-v2
```

## 2. Backend Setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"
```

### 2.1 Environment Variables

Copy and fill in the backend `.env`:

```bash
cp .env.example .env
```

Required variables:

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key for the LLM engine |
| `PORTAL_SECRET_KEY` | Portal API secret key for webhook validation and token minting |
| `PORTAL_WEBHOOK_URL` | Portal webhook endpoint URL |
| `REDIS_URL` | Redis connection string (default: `redis://localhost:6379`) |
| `AGENTSYNC_LLM_PROVIDER` | LLM provider: `openai` or `fake` (for tests without API calls) |

### 2.2 Start the Backend

```bash
python main.py
```

The API starts at `http://localhost:8000`. Verify:

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0"}
```

## 3. Frontend Setup

```bash
cd frontend
npm install
```

### 3.1 Environment Variables

```bash
cp .env.example .env.local
```

Edit `.env.local` as needed:

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |
| `NEXT_PUBLIC_PORTAL_PUBLISHABLE_KEY` | `pk_your_publishable_key` | Portal publishable key for the frontend SDK |

### 3.2 Start the Frontend

```bash
npm run dev
```

Open `http://localhost:3000`.

## 4. Available Endpoints

Full API reference: [`docs/api/FRONTEND_API_SPEC.md`](../api/FRONTEND_API_SPEC.md)

Quick reference:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/agents` | Register an agent |
| `GET` | `/api/v1/agents/{agent_id}` | Agent profile |
| `GET` | `/api/v1/agents` | List agents |
| `GET` | `/api/v1/negotiations?agent_id={id}` | Agent's negotiations |
| `GET` | `/api/v1/negotiations/{session_id}` | Negotiation detail + transcript |
| `POST` | `/api/v1/negotiations/{session_id}/approval` | Submit human decision |
| `GET` | `/api/v1/negotiations/{session_id}/audit` | Audit trail |
| `GET` | `/api/v1/negotiations/{session_id}/stream` | SSE transcript stream |

## 5. How to Get a Portal Token

The Portal token is used by the frontend SDK to authenticate with Portal's real-time API.

```bash
# Backend proxies the request to Portal (requires PORTAL_SECRET_KEY in backend .env)
curl "http://localhost:8000/api/portal-token?userId=your-user-id"
```

Response:

```json
{
  "token": "pt_abc123...",
  "expiresAt": "2026-08-09T02:00:00Z"
}
```

Use the returned `token` to initialize the Portal SDK on the frontend.

## 6. SSE Stream URL

Real-time transcript updates are delivered via Server-Sent Events:

```
GET /api/v1/negotiations/{session_id}/stream
```

- **Format**: `text/event-stream` (SSE)
- **Events**: `data: {json}\n\n` — each event is a `TranscriptMessageDTO` JSON object
- **Keepalive**: `: ping\n\n` every 30 seconds
- **Timeout**: Idle connections close after 5 minutes

Example event:

```json
{
  "speaker_id": "f0000000-0000-0000-0000-000000000001",
  "turn_index": 4,
  "public_message": "Te ofrezco $400 con envio incluido.",
  "intent": "COUNTER_OFFER",
  "approved_by_human": false,
  "created_at": "2026-08-08T17:31:30Z"
}
```

The event stream is only available while the negotiation is active (`SEARCHING` or `ACTIVE`). Closed/completed sessions return an empty stream that closes immediately.
