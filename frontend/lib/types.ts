export type EntityType = "empresa" | "persona";

export type SessionStatus =
  | "SEARCHING"
  | "ACTIVE"
  | "PENDING_HUMAN_APPROVAL"
  | "RESOLVED"
  | "REJECTED";

export type DecisionStatus = "PENDING" | "APPROVED" | "REJECTED" | "REPLACED";

export interface AgentTool {
  id: string;
  name: string;
  simulated: boolean;
  notes?: string;
}

export interface AgentProfile {
  agent_id: string;
  entity_type: EntityType;
  display_name: string;
  personality: string;
  objectives: string[];
  hard_limits: Record<string, number | boolean>;
  sensitive_defaults: string[];
  tools: AgentTool[];
  active: boolean;
}

export interface SensitiveCategory {
  id: string;
  label: string;
  required: boolean;
  enabled: boolean;
}

export interface ChatMessage {
  id: string;
  sender_agent_id: string;
  content: string;
  sent_at: string;
  blocked_by_guardrail?: boolean;
  flagged?: {
    category: string;
    detail: string;
    requires_human: boolean;
  };
}

export interface PendingDecision {
  id: string;
  session_id: string;
  category: string;
  summary: string;
  proposal: string;
  requested_by: string;
  created_at: string;
  status: DecisionStatus;
}

export interface MatchSession {
  session_id: string;
  segment: "B2B" | "P2P";
  agent_1_id: string;
  agent_2_id: string;
  status: SessionStatus;
  summary: string;
  started_at: string;
  max_turns: number;
  current_turn: number;
  messages: ChatMessage[];
  pending_script?: ChatMessage[];
  pending_decision?: PendingDecision;
  revealed_contact?: {
    agent_id: string;
    contact: string;
    revealed_at: string;
  };
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
