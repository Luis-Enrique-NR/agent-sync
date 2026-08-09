"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type {
  AgentProfile,
  HumanDecision,
  MatchSession,
  Segment,
  SessionStatus,
} from "@/lib/types";
import * as api from "@/lib/api";

// ── API response → frontend-type mappers ────────────────────────────────

function toAgentProfile(r: api.AgentProfileResponse): AgentProfile {
  return {
    agent_id: r.agent_id,
    display_name: r.display_name,
    entity_type: r.entity_type as AgentProfile["entity_type"],
    public_description: r.public_description,
    personality: "",
    objectives: r.objectives ?? [],
    interests: r.interests ?? [],
    capabilities: r.capabilities ?? [],
    hard_limits: [],
    never_disclose: [],
    escalation_rules: [],
    status: r.status as AgentProfile["status"],
    price_range: r.price_range ?? null,
    logistics_preferences: r.logistics_preferences ?? [],
    tools: [],
  };
}

function toMatchSession(s: api.NegotiationSummary): MatchSession {
  return {
    session_id: s.session_id,
    segment: "P2P" as Segment,
    agent_1_id: s.agent_1_id,
    agent_2_id: s.agent_2_id,
    status: s.status as SessionStatus,
    summary: "",
    started_at: s.started_at,
    max_turns: 0,
    current_turn: s.turn_count,
    messages: [],
  };
}

// ── belongsToAgent — was in demo.ts, inlined here ──────────────────────

export function belongsToAgent(
  session: MatchSession,
  agentId: string | null,
): boolean {
  if (!agentId) return false;
  return session.agent_1_id === agentId || session.agent_2_id === agentId;
}

// ── Public interface (preserved from mock store) ───────────────────────

interface AgentSyncState {
  agents: AgentProfile[];
  sessions: MatchSession[];
  agentsById: Record<string, AgentProfile>;
  dispatchHumanDecision: (sessionId: string, decision: HumanDecision) => Promise<void>;
  registerAgent: (profile: api.AgentRegisterPayload) => Promise<string>;
  refreshSessions: () => Promise<void>;
}

const AgentSyncContext = createContext<AgentSyncState | null>(null);

export function AgentSyncProvider({ children }: { children: React.ReactNode }) {
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [sessions, setSessions] = useState<MatchSession[]>([]);

  // On mount, fetch agents and sessions from the API
  useEffect(() => {
    const load = async () => {
      try {
        const [agentsRes, sessionsRes] = await Promise.all([
          api.listAgents(),
          api.listNegotiations(),
        ]);
        setAgents(agentsRes.agents.map(toAgentProfile));
        setSessions(sessionsRes.negotiations.map(toMatchSession));
      } catch (err) {
        console.error("Failed to load initial data", err);
      }
    };
    load();
  }, []);

  const refreshSessions = useCallback(async () => {
    try {
      const sessionsRes = await api.listNegotiations();
      setSessions(sessionsRes.negotiations.map(toMatchSession));
    } catch (err) {
      console.error("Failed to refresh sessions", err);
    }
  }, []);

  const registerAgent = useCallback(
    async (profile: api.AgentRegisterPayload): Promise<string> => {
      const response = await api.createAgent(profile);
      const agent = toAgentProfile(response);
      setAgents((prev) => [...prev, agent]);
      return response.agent_id;
    },
    [],
  );

  const dispatchHumanDecision = useCallback(
    async (sessionId: string, decision: HumanDecision): Promise<void> => {
      const payload: api.HumanDecisionPayload = {
        action: decision.action,
        reason: null,
        replacement_turn: decision.replacement_message ?? null,
      };
      await api.submitApproval(sessionId, payload);
      await refreshSessions();
    },
    [refreshSessions],
  );

  const agentsById = useMemo(
    () => Object.fromEntries(agents.map((a) => [a.agent_id, a])),
    [agents],
  );

  const value = useMemo(
    () => ({
      agents,
      sessions,
      agentsById,
      dispatchHumanDecision,
      registerAgent,
      refreshSessions,
    }),
    [agents, sessions, agentsById, dispatchHumanDecision, registerAgent, refreshSessions],
  );

  return (
    <AgentSyncContext.Provider value={value}>
      {children}
    </AgentSyncContext.Provider>
  );
}

export function useAgentSync(): AgentSyncState {
  const ctx = useContext(AgentSyncContext);
  if (!ctx) throw new Error("useAgentSync debe usarse dentro de AgentSyncProvider");
  return ctx;
}
