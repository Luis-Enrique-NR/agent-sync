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
  DecisionStatus,
  MatchSession,
  MockData,
} from "@/lib/types";
import mockData from "@/data/mockData.json";

const data = mockData as unknown as MockData;

const STORAGE_KEY = "agentsync-demo-v2";

interface AgentSyncState {
  agents: AgentProfile[];
  sessions: MatchSession[];
  agentsById: Record<string, AgentProfile>;
  resolveDecision: (sessionId: string, status: DecisionStatus) => void;
  toggleAgentActive: (agentId: string) => void;
  resetDemo: () => void;
}

const AgentSyncContext = createContext<AgentSyncState | null>(null);

export function AgentSyncProvider({ children }: { children: React.ReactNode }) {
  const [agents, setAgents] = useState<AgentProfile[]>(data.agents);
  const [sessions, setSessions] = useState<MatchSession[]>(data.sessions);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as { agents?: AgentProfile[]; sessions?: MatchSession[] };
      if (parsed.sessions) setSessions(parsed.sessions);
      if (parsed.agents) setAgents(parsed.agents);
    } catch {
      // estado corrupto: se ignora y se usa el mock
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ agents, sessions }));
    } catch {
      // almacenamiento no disponible: la demo sigue en memoria
    }
  }, [agents, sessions]);

  const resolveDecision = useCallback((sessionId: string, status: DecisionStatus) => {
    setSessions((prev) =>
      prev.map((session) => {
        if (session.session_id !== sessionId || !session.pending_decision) {
          return session;
        }
        const resolved: MatchSession["status"] =
          status === "REJECTED" ? "REJECTED" : "RESOLVED";
        const contact =
          status === "REJECTED"
            ? session.revealed_contact
            : session.revealed_contact ?? {
                agent_id: session.agent_2_id,
                contact: `demo-contact@${session.agent_2_id.replace("agent-", "")}.example`,
                revealed_at: new Date().toISOString(),
              };
        return {
          ...session,
          status: resolved,
          pending_decision: { ...session.pending_decision, status },
          revealed_contact: contact,
        };
      }),
    );
  }, []);

  const toggleAgentActive = useCallback((agentId: string) => {
    setAgents((prev) =>
      prev.map((agent) =>
        agent.agent_id === agentId ? { ...agent, active: !agent.active } : agent,
      ),
    );
  }, []);

  const resetDemo = useCallback(() => {
    setAgents(data.agents);
    setSessions(data.sessions);
  }, []);

  const agentsById = useMemo(
    () => Object.fromEntries(agents.map((agent) => [agent.agent_id, agent])),
    [agents],
  );

  const value = useMemo(
    () => ({
      agents,
      sessions,
      agentsById,
      resolveDecision,
      toggleAgentActive,
      resetDemo,
    }),
    [agents, sessions, agentsById, resolveDecision, toggleAgentActive, resetDemo],
  );

  return (
    <AgentSyncContext.Provider value={value}>{children}</AgentSyncContext.Provider>
  );
}

export function useAgentSync(): AgentSyncState {
  const ctx = useContext(AgentSyncContext);
  if (!ctx) throw new Error("useAgentSync debe usarse dentro de AgentSyncProvider");
  return ctx;
}
