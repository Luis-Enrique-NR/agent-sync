// ─────────────────────────────────────────────────────────────────────────────
// Contratos de datos — alineados con los DTOs ai.v1 (Diogo) y los modelos
// agnósticos B2B/P2P (Lucho): ai/domain/models.py + persistence/models.py.
// El Frontend solo renderiza lo que el Backend API/AI declara seguro: datos
// reales únicamente cuando pasaron guardrails y fueron aprobados por la
// bitácora/vault. Los datos sensibles viajan como referencias opacas value_ref.
// ─────────────────────────────────────────────────────────────────────────────

// ── Tipos base agnósticos (B2B/P2P) ─────────────────────────────────────────

export type EntityType = "company" | "person";
export type Segment = "B2B" | "P2P";

/** AgenteStatus del backend (ai/domain/models.py). */
export type AgentStatus = "AVAILABLE" | "BUSY" | "PAUSED";

/** SessionStatus del backend + estados terminales del contrato ai.v1. */
export type SessionStatus =
  | "SEARCHING"
  | "ACTIVE"
  | "PENDING_HUMAN_APPROVAL"
  | "RESOLVED"
  | "REJECTED"
  | "FAILED"
  | "WITHDRAWN"
  | "EXPIRED";

export type DecisionStatus = "PENDING" | "APPROVED" | "REJECTED" | "REPLACED";

/** HumanDecisionAction — acciones que despacha el humano al AIBackendService. */
export type HumanDecisionAction = "APPROVE" | "REJECT" | "REPLACE";

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
  | "FINAL_AGREEMENT";

export type NumericOperator = "gt" | "gte" | "lt" | "lte" | "eq";

/** ActorType del audit_records (HUMAN / SYSTEM / LLM). */
export type ActorType = "HUMAN" | "SYSTEM" | "LLM";

export type TurnIntent =
  | "QUESTION"
  | "OFFER"
  | "COUNTER_OFFER"
  | "ACCEPT"
  | "DECLINE";

export type ChannelStatus = "CREATED" | "PENDING" | "FAILED";

/** B2B ↔ company, P2P ↔ person. */
export function segmentOf(entityType: EntityType): Segment {
  return entityType === "company" ? "B2B" : "P2P";
}

// ── Modelos de dominio (SQLModel raw / JSON agnóstico) ─────────────────────

/** NumericLimit — límite duro determinístico (fuera del LLM). */
export interface NumericLimit {
  key: string;
  operator: NumericOperator;
  value: number;
  unit?: string;
}

export interface NumericTerm {
  key: string;
  value: number;
  unit?: string;
}

/** DisclosureRequest — pedido estructurado de un dato propio. value_ref es opaco. */
export interface DisclosureRequest {
  category: SensitiveDataCategory;
  value_ref: string;
  purpose: string;
}

export interface Commitment {
  kind: "DATE" | "MEETING" | "OTHER";
  value: string;
}

/** EscalationRule — regla de escalamiento humano configurada por el propietario. */
export interface EscalationRule {
  rule_id: string;
  rule_type: EscalationRuleType;
  key?: string;
  threshold?: number;
  categories: SensitiveDataCategory[];
  enabled: boolean;
}

export interface AgentTool {
  id: string;
  name: string;
  simulated: boolean;
  notes?: string;
}

// ── DTO ai.v1 — AgentProfileDTO ─────────────────────────────────────────────

export interface AgentProfile {
  agent_id: string;
  display_name: string;
  entity_type: EntityType;
  public_description: string;
  personality: string;
  objectives: string[];
  interests: string[];
  capabilities: string[];
  hard_limits: NumericLimit[];
  never_disclose: SensitiveDataCategory[];
  escalation_rules: EscalationRule[];
  status: AgentStatus;
  price_range?: { min?: number; max?: number } | null;
  logistics_preferences?: string[];
  tools: AgentTool[];
}

/** Firma de registro del agente (evento agent.registered → matchmaking). */
export interface AgentRegistrationDTO {
  event_type: "agent.registered";
  profile: AgentProfile;
  sent_at: string;
}

// ── DTO ai.v1 — TranscriptMessageDTO / Turno público ───────────────────────

export interface ChatMessage {
  id: string;
  sender_agent_id: string;
  content: string;
  sent_at: string;
  intent?: TurnIntent;
  numeric_terms?: NumericTerm[];
  disclosures?: DisclosureRequest[];
  commitments?: Commitment[];
  blocked_by_guardrail?: boolean;
  /** Turno en espera de aprobación humana; los datos sensibles son value_ref. */
  pending_human_approval?: boolean;
  flagged?: {
    category: string;
    detail: string;
    requires_human: boolean;
    value_ref?: string;
  };
}

// ── DTO ai.v1 — DecisionRequestDTO + HumanDecisionDTO ──────────────────────

export interface PendingDecision {
  decision_id: string;
  session_id: string;
  speaker_id: string;
  category: string;
  summary: string;
  proposal: string;
  requested_by: string;
  reasons?: string[];
  matched_rule_ids?: string[];
  created_at: string;
  status: DecisionStatus;
  manual_response?: string;
}

/** HumanDecisionDTO — el humano aprueba/rechaza/reemplaza; reanuda o retira. */
export interface HumanDecision {
  decision_id: string;
  action: HumanDecisionAction;
  replacement_message?: string;
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
  segment: Segment;
  agent_1_id: string;
  agent_2_id: string;
  initiator_id?: string;
  status: SessionStatus;
  summary: string;
  started_at: string;
  max_turns: number;
  current_turn: number;
  messages: ChatMessage[];
  pending_script?: ChatMessage[];
  pending_decision?: PendingDecision;
  matchmaking?: MatchScore;
  audit?: AuditRecord[];
  raw_state?: Record<string, unknown>;
  outcome?: NegotiationOutcome;
  revealed_contact?: {
    agent_id: string;
    contact: string;
    revealed_at: string;
  };
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
