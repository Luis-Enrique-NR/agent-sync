// ─────────────────────────────────────────────────────────────────────────────
// Contratos de datos — alineados con los DTOs ai.v1 reales:
//   backend/ai/api/dto.py        → DTOs expuestos al cliente (schema "ai.v1")
//   backend/ai/domain/models.py  → enums y modelos de dominio
//   backend/persistence/models.py→ filas SQLModel
// El Frontend solo renderiza lo que el Backend API/AI declara seguro: datos
// reales únicamente cuando pasaron guardrails y fueron aprobados por la
// bitácora/vault. Los datos sensibles viajan como referencias opacas value_ref.
// ─────────────────────────────────────────────────────────────────────────────

export const API_SCHEMA_VERSION = "ai.v1";

// ── Enums de dominio (ai/domain/models.py) ──────────────────────────────────

export type EntityType = "company" | "person";
export type Segment = "B2B" | "P2P";

/** AgentStatus del backend (ai/domain/models.py). */
export type AgentStatus = "AVAILABLE" | "BUSY" | "PAUSED";

/** SessionStatus del backend (ai/domain/models.py) + estados terminales. */
export type SessionStatus =
  | "SEARCHING"
  | "ACTIVE"
  | "PENDING_HUMAN_APPROVAL"
  | "RESOLVED"
  | "REJECTED"
  | "FAILED"
  | "WITHDRAWN"
  | "EXPIRED";

/** DecisionStatus — DecisionRequestDTO.status. */
export type DecisionStatus =
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "REPLACED"
  | "CANCELLED"
  | "EXPIRED";

/** DecisionKind — DecisionRequestDTO.kind. */
export type DecisionKind =
  | "OUTBOUND_TURN"
  | "INBOUND_ACTION"
  | "TOOL_EXECUTION"
  | "SYSTEM";

/** HumanDecisionAction — acciones que despacha el humano al AIBackendService. */
export type HumanDecisionAction = "APPROVE" | "REJECT" | "REPLACE";

/** GoalCompletionMode — AgentProfileDTO.goal_completion_mode. */
export type GoalCompletionMode = "ONE_SHOT" | "QUANTITY" | "CONTINUOUS";

export type SensitiveDataCategory =
  | "PHONE"
  | "EMAIL"
  | "EXACT_ADDRESS"
  | "LIVE_LOCATION"
  | "MEETING_POINT";

export type EscalationRuleType =
  | "ANY_FINAL_PRICE"
  | "AMOUNT_ABOVE"
  | "SHARE_PERSONAL_DATA"
  | "COMMIT_DATE"
  | "FINAL_AGREEMENT"
  | "REQUEST_ACTION";

export type ActionType =
  | "MEETING"
  | "RESERVE_RESOURCE"
  | "SEND_DOCUMENT"
  | "SEND_EMAIL"
  | "OTHER";

export type CommitmentKind = "DATE" | "MEETING" | "OTHER";

export type NumericOperator = "gt" | "gte" | "lt" | "lte" | "eq";

export type TurnIntent =
  | "QUESTION"
  | "OFFER"
  | "COUNTER_OFFER"
  | "ACCEPT"
  | "DECLINE";

export type ToolApprovalMode = "AUTO" | "ALWAYS";

export type ChannelStatus = "CREATED" | "PENDING" | "FAILED";

/** ActorType del audit_records (HUMAN / SYSTEM / LLM). */
export type ActorType = "HUMAN" | "SYSTEM" | "LLM";

/** B2B ↔ company, P2P ↔ person. */
export function segmentOf(entityType: EntityType): Segment {
  return entityType === "company" ? "B2B" : "P2P";
}

// ── Sub-modelos del dominio (ai/domain/models.py) ───────────────────────────

/** NumericLimit — límite duro determinístico (fuera del LLM). */
export interface NumericLimit {
  key: string;
  operator: NumericOperator;
  value: number;
  unit?: string | null;
}

export interface NumericTerm {
  key: string;
  value: number;
  unit?: string | null;
}

/** DataRequest — pedido estructurado de un dato propio. value_ref es opaco. */
export interface DataRequest {
  category: SensitiveDataCategory;
  purpose: string;
  value_ref?: string;
}

export interface ProposedDisclosure {
  category: SensitiveDataCategory;
  value_ref: string;
  purpose: string;
}

export interface Commitment {
  kind: CommitmentKind;
  value: string;
}

/** RequestedAction — action del motor (MEETING, SEND_EMAIL, …). */
export interface RequestedAction {
  action_id?: string;
  action_type: ActionType;
  purpose: string;
  parameters?: Record<string, string | number | boolean | null>;
  valid_until?: string | null;
}

/** EscalationRule — regla de escalamiento humano configurada por el propietario. */
export interface EscalationRule {
  rule_id: string;
  rule_type: EscalationRuleType;
  key?: string | null;
  threshold?: number | null;
  categories: SensitiveDataCategory[];
  action_types: ActionType[];
  enabled: boolean;
}

/** ToolGrant — AgentProfileDTO.tool_grants. */
export interface ToolGrant {
  tool_name: string;
  enabled: boolean;
  approval_mode: ToolApprovalMode;
}

/** AgentTool — catálogo de herramientas que el agente puede usar en la demo. */
export interface AgentTool {
  id: string;
  name: string;
  simulated: boolean;
  notes?: string;
}

/**
 * Contexto de negociación asociado a un objetivo concreto.
 *
 * `objectives`, `interests` y `capabilities` se conservan temporalmente en
 * AgentProfile para mantener compatibilidad con el contrato ai.v1 actual.
 */
export interface AgentObjectiveContext {
  objective_id: string;
  goal: string;
  seeks: string[];
  offers: string[];
  negotiation_context: string;
}

// ── DTO ai.v1 — AgentProfileDTO ─────────────────────────────────────────────

export interface AgentProfile {
  agent_id: string;
  display_name: string;
  entity_type: EntityType;
  status: AgentStatus;
  public_description: string;
  interests: string[];
  capabilities: string[];
  price_range?: { min?: number; max?: number } | null;
  logistics_preferences: string[];
  personality: string;
  objectives: string[];
  objective_contexts?: AgentObjectiveContext[];
  hard_limits: NumericLimit[];
  never_disclose: SensitiveDataCategory[];
  escalation_rules: EscalationRule[];
  tool_grants?: ToolGrant[];
  tools?: AgentTool[];
  goal_completion_mode?: GoalCompletionMode;
  remaining_goal_units?: number | null;
}

/** Firma de registro del agente (evento agent.registered → matchmaking). */
export interface AgentRegistrationDTO {
  event_type: "agent.registered";
  profile: AgentProfile;
  created_at: string;
}

// ── DTO ai.v1 — PublicTranscriptMessageDTO ──────────────────────────────────

/** Turno público del transcript (NUNCA viaja con datos sensibles en claro). */
export interface TranscriptMessage {
  speaker_id: string;
  turn_index: number;
  proposal_id: string;
  proposal_revision: number;
  responds_to?: {
    proposal_id: string;
    revision: number;
  } | null;
  public_message: string;
  intent: TurnIntent;
  numeric_terms: NumericTerm[];
  data_requests: DataRequest[];
  disclosed_categories: SensitiveDataCategory[];
  requested_actions: RequestedAction[];
  created_at: string;
  approved_by_human: boolean;
}

/** Extensión UI del transcript para la demo (no es parte del DTO). */
export interface ChatMessage extends TranscriptMessage {
  id: string;
  commitments?: Commitment[];
  blocked_by_guardrail?: boolean;
  pending_human_approval?: boolean;
  flagged?: {
    category: string;
    detail: string;
    requires_human: boolean;
    value_ref?: string;
  };
}

// ── DTO ai.v1 — DecisionRequestDTO + HumanDecisionDTO ──────────────────────

/** Decisión pendiente tal como la ve el propietario del agente. */
export interface PendingDecision {
  schema_version: string;
  decision_id: string;
  session_id: string;
  owner_agent_id: string;
  requester_agent_id?: string | null;
  kind: DecisionKind;
  /** Categoría legible de la decisión (alineada con el contrato ai.v1). */
  category?: string;
  reasons: string[];
  matched_rule_ids: string[];
  candidate_turn?: Record<string, unknown> | null;
  proposal_id?: string | null;
  proposal_revision?: number | null;
  requested_actions: RequestedAction[];
  tool_call?: Record<string, unknown> | null;
  requires_revalidation: boolean;
  status: DecisionStatus;
  created_at: string;
  resolved_at?: string | null;
  resolution?: string | null;
  /** Copia para la demo (derivada del candidate_turn). */
  summary?: string;
  proposal?: string;
  manual_response?: string;
}

/** HumanDecisionDTO — el humano aprueba/rechaza/reemplaza; reanuda o retira. */
export interface HumanDecision {
  decision_id: string;
  action: HumanDecisionAction;
  replacement_turn?: {
    public_message: string;
    intent?: TurnIntent;
  } | null;
}

// ── DTO ai.v1 — AuditRecord (bitácora estructurada) ────────────────────────

export interface AuditRecord {
  audit_id: string;
  correlation_id?: string;
  session_id?: string;
  agent_id?: string;
  actor_type: ActorType;
  actor_id: string;
  action: string;
  severity: "INFO" | "WARNING" | "ERROR";
  entity_type?: string;
  reason?: string;
  occurred_at: string;
}

// ── DTO ai.v1 — MatchScore (scoring bidireccional + canal Portal) ──────────

export interface MatchScore {
  score: number;
  ic_score: number;
  logistics_score: number;
  price_pass: boolean;
  direction: { a_to_b: number; b_to_a: number };
  channel_id: string;
  channel_status: ChannelStatus;
}

// ── SQLModel — NegotiationOutcomeRow ───────────────────────────────────────

export interface NegotiationOutcome {
  outcome_id: string;
  session_id: string;
  resolution: "RESOLVED" | "REJECTED" | "FAILED" | "WITHDRAWN" | "EXPIRED";
  agreed_price?: number;
  agreed_terms?: Record<string, unknown>;
  disclosed_data?: Record<string, unknown>;
  summary: string;
  created_at: string;
}

// ── DTO ai.v1 — NegotiationStateDTO ────────────────────────────────────────

export interface MatchSession {
  session_id: string;
  owner_user_id?: string | null;
  current_speaker_id?: string;
  segment: Segment;
  agent_1_id: string;
  agent_2_id: string;
  initiator_id?: string;
  status: SessionStatus;
  summary: string;
  started_at: string;
  deadline_at?: string;
  max_turns: number;
  current_turn: number;
  messages: ChatMessage[];
  pending_script?: ChatMessage[];
  pending_decision?: PendingDecision;
  pending_revalidation?: Record<string, unknown> | null;
  matchmaking?: MatchScore;
  audit?: AuditRecord[];
  raw_state?: Record<string, unknown>;
  outcome?: NegotiationOutcome;
  revealed_contact?: {
    agent_id: string;
    contact: string;
    revealed_at: string;
  };
  last_error_code?: string | null;
}

// ── UI — metadatos de categorías sensibles (configuración) ─────────────────

export interface SensitiveCategory {
  id: string;
  label: string;
  required: boolean;
  enabled: boolean;
  ruleType: EscalationRuleType;
  categories?: SensitiveDataCategory[];
  key?: string;
  threshold?: number;
}

export interface MockData {
  schemaVersion: string;
  meta: {
    source: string;
    environment: string;
    purpose: string;
  };
  agents: AgentProfile[];
  sessions: MatchSession[];
  sensitive_categories: {
    default_required: SensitiveCategory[];
    editable: SensitiveCategory[];
  };
}
