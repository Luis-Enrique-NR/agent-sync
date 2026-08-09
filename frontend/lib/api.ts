/**
 * Typed fetch layer for the AgentSync Frontend API.
 *
 * Every function throws {@link ApiError} on non-2xx responses.
 * The `X-Agent-ID` header is read from localStorage key `agentsync-agent-id`
 * and attached to every request automatically.
 */

import type { AuditRecord } from "@/lib/types";

// ── Re-exports from backend DTOs for convenience ───────────────────────

export type {
  AgentProfile,
  AgentRegistrationDTO,
  AuditRecord,
  ChatMessage,
  ConversationDecision,
  HumanDecision,
  HumanDecisionAction,
  MatchScore,
  MatchSession,
  NegotiationOutcome,
  PendingDecision,
  SensitiveCategory,
} from "@/lib/types";

// ── API-specific payload types (aligned with backend schemas.py) ──────

/** POST /api/v1/agents — body */
export interface AgentRegisterPayload {
  display_name: string;
  entity_type: "company" | "person";
  public_description: string;
  personality: string;
  objectives: string[];
  interests?: string[];
  capabilities?: string[];
  price_range?: { min?: number; max?: number } | null;
  logistics_preferences?: string[];
}

/** GET /api/v1/agents/{id} response */
export interface AgentProfileResponse {
  agent_id: string;
  user_id: string;
  display_name: string;
  entity_type: string;
  status: string;
  public_description: string;
  interests: string[];
  capabilities: string[];
  price_range: { min?: number; max?: number } | null;
  logistics_preferences: string[];
  objectives: string[];
  created_at: string;
  updated_at: string;
}

/** GET /api/v1/agents response */
export interface AgentListResponse {
  agents: AgentProfileResponse[];
  total: number;
}

/** GET /api/v1/negotiations/{id} response */
export interface NegotiationDetail {
  session_id: string;
  agent_1_id: string;
  agent_2_id: string;
  status: string;
  portal_channel_id: string | null;
  turn_count: number;
  started_at: string;
  closed_at: string | null;
  initiator_id: string;
  max_turns: number;
  deadline_at: string | null;
  last_error_code: string | null;
  transcript: TranscriptMessage[];
}

export interface TranscriptMessage {
  speaker_id: string;
  turn_index: number;
  public_message: string;
  intent: string;
  approved_by_human: boolean;
  created_at: string;
}

/** GET /api/v1/negotiations response */
export interface NegotiationSummary {
  session_id: string;
  agent_1_id: string;
  agent_2_id: string;
  status: string;
  portal_channel_id: string | null;
  turn_count: number;
  started_at: string;
  closed_at: string | null;
}

export interface NegotiationListResponse {
  negotiations: NegotiationSummary[];
  total: number;
}

/** POST /api/v1/negotiations/{id}/approval — body */
export interface HumanDecisionPayload {
  action: "APPROVE" | "REJECT" | "REPLACE";
  reason?: string | null;
  replacement_turn?: string | null;
}

/** POST /api/v1/negotiations/{id}/approval response */
export interface DecisionResponse {
  decision_id: string;
  session_id: string;
  action: string;
  new_status: string;
}

// ── Error class ───────────────────────────────────────────────────────

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `API request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

// ── Internal helpers ──────────────────────────────────────────────────

const BASE =
  typeof window === "undefined"
    ? process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"
    : ""; // Client-side: empty string → same-origin via Next.js rewrites

function agentIdHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const id = window.localStorage.getItem("agentsync-agent-id");
  return id ? { "X-Agent-ID": id } : {};
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const url = `${BASE}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...agentIdHeader(),
  };

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let errorBody: unknown;
    const cloned = res.clone();
    try {
      errorBody = await cloned.json();
    } catch {
      errorBody = await res.text();
    }
    throw new ApiError(res.status, errorBody);
  }

  return res.json() as Promise<T>;
}

// ── Public API functions ──────────────────────────────────────────────

/** POST /api/v1/agents — register a new agent */
export async function createAgent(
  payload: AgentRegisterPayload,
): Promise<AgentProfileResponse> {
  return request<AgentProfileResponse>("POST", "/api/v1/agents", payload);
}

/** GET /api/v1/agents/{id} — fetch a single agent profile */
export async function getAgent(id: string): Promise<AgentProfileResponse> {
  return request<AgentProfileResponse>("GET", `/api/v1/agents/${id}`);
}

/** GET /api/v1/agents — list all registered agents */
export async function listAgents(): Promise<AgentListResponse> {
  return request<AgentListResponse>("GET", "/api/v1/agents");
}

/** GET /api/v1/negotiations/{id} — fetch full negotiation with transcript */
export async function getNegotiation(
  id: string,
): Promise<NegotiationDetail> {
  return request<NegotiationDetail>("GET", `/api/v1/negotiations/${id}`);
}

/** GET /api/v1/negotiations — list negotiations, optionally filtered */
export async function listNegotiations(params?: {
  status?: string;
  agent_id?: string;
}): Promise<NegotiationListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.agent_id) searchParams.set("agent_id", params.agent_id);
  const qs = searchParams.toString();
  return request<NegotiationListResponse>(
    "GET",
    `/api/v1/negotiations${qs ? `?${qs}` : ""}`,
  );
}

/** POST /api/v1/negotiations/{id}/approval — submit a human decision */
export async function submitApproval(
  id: string,
  decision: HumanDecisionPayload,
): Promise<DecisionResponse> {
  return request<DecisionResponse>(
    "POST",
    `/api/v1/negotiations/${id}/approval`,
    decision,
  );
}

export interface AuditListResponse {
  records: AuditRecord[];
  total: number;
}

/** GET /api/v1/negotiations/{id}/audit — fetch audit trail */
export async function getAudit(
  id: string,
): Promise<AuditListResponse> {
  return request<AuditListResponse>("GET", `/api/v1/negotiations/${id}/audit`);
}
