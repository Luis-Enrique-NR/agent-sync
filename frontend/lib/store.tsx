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
  AuditRecord,
  DecisionStatus,
  HumanDecision,
  HumanDecisionAction,
  MatchScore,
  MatchSession,
  MockData,
  Segment,
} from "@/lib/types";
import { segmentOf } from "@/lib/types";
import mockData from "@/data/mockData.json";

const data = mockData as unknown as MockData;

const STORAGE_KEY = "agentsync-demo-v3";

interface AgentSyncState {
  agents: AgentProfile[];
  sessions: MatchSession[];
  agentsById: Record<string, AgentProfile>;
  /** AIBackendService.resume_negotiation — aprueba/rechaza/reemplaza y reanuda. */
  dispatchHumanDecision: (sessionId: string, decision: HumanDecision) => void;
  toggleAgentStatus: (agentId: string) => void;
  /** agent.registered → persiste perfil y dispara matchmaking simulado. */
  registerAgent: (profile: AgentProfile) => number;
  resetDemo: () => void;
}

const AgentSyncContext = createContext<AgentSyncState | null>(null);

function uid(): string {
  const rand =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `id-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  return rand;
}

function audit(
  partial: Omit<AuditRecord, "audit_id" | "occurred_at" | "actor_id"> & {
    actor_id?: string;
  },
): AuditRecord {
  return {
    audit_id: uid(),
    actor_id: partial.actor_id ?? "",
    occurred_at: new Date().toISOString(),
    ...partial,
  };
}

function directionScores(a: AgentProfile, b: AgentProfile): {
  a_to_b: number;
  b_to_a: number;
} {
  const aInterests = new Set(a.interests ?? []);
  const aCaps = new Set(a.capabilities ?? []);
  const bInterests = new Set(b.interests ?? []);
  const bCaps = new Set(b.capabilities ?? []);
  const a_to_b = aInterests.size
    ? [...aInterests].filter((i) => bCaps.has(i)).length / aInterests.size
    : 0;
  const b_to_a = bInterests.size
    ? [...bInterests].filter((i) => aCaps.has(i)).length / bInterests.size
    : 0;
  return { a_to_b, b_to_a };
}

function priceRangesConflict(a: AgentProfile, b: AgentProfile): boolean {
  const pa = a.price_range;
  const pb = b.price_range;
  if (!pa || !pb) return false;
  const aMin = pa.min ?? 0;
  const aMax = pa.max ?? Infinity;
  const bMin = pb.min ?? 0;
  const bMax = pb.max ?? Infinity;
  return aMax < bMin || bMax < aMin;
}

function logisticsScore(a: AgentProfile, b: AgentProfile): number {
  const setA = new Set(a.logistics_preferences ?? []);
  const setB = new Set(b.logistics_preferences ?? []);
  if (setA.size === 0 && setB.size === 0) return 0.5;
  if (setA.size === 0 || setB.size === 0) return 0.3;
  const intersection = [...setA].filter((x) => setB.has(x)).length;
  const union = new Set([...setA, ...setB]).size;
  return intersection / union;
}

/** Refleja calculate_match_score() del backend (matchmaking/evaluator.py). */
function computeMatch(a: AgentProfile, b: AgentProfile): MatchScore {
  const direction = directionScores(a, b);
  const ic = (direction.a_to_b + direction.b_to_a) / 2;
  const price_pass = !priceRangesConflict(a, b);
  if (!price_pass || ic <= 0) {
    return {
      score: 0,
      ic_score: ic,
      logistics_score: 0,
      price_pass,
      direction,
      channel_id: "",
      channel_status: "PENDING",
    };
  }
  const logistics = logisticsScore(a, b);
  return {
    score: Math.round((0.7 * ic + 0.3 * logistics) * 100) / 100,
    ic_score: Math.round(ic * 100) / 100,
    logistics_score: Math.round(logistics * 100) / 100,
    price_pass,
    direction,
    channel_id: "",
    channel_status: "PENDING",
  };
}

export function AgentSyncProvider({ children }: { children: React.ReactNode }) {
  const [agents, setAgents] = useState<AgentProfile[]>(data.agents);
  const [sessions, setSessions] = useState<MatchSession[]>(data.sessions);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as {
        agents?: AgentProfile[];
        sessions?: MatchSession[];
      };
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

  /**
   * AIBackendService.resume_negotiation(user_id, session_id, human_decision).
   * APPROVE → reanuda (ACTIVE) y el vault resuelve value_ref → RESOLVED.
   * REJECT  → retira la negociación (REJECTED), no se publica nada.
   * REPLACE → reemplaza el turno candidato por el mensaje del humano.
   */
  const dispatchHumanDecision = useCallback(
    (sessionId: string, decision: HumanDecision) => {
      const release = (ids: string[]) =>
        setAgents((prev) =>
          prev.map((agent) =>
            ids.includes(agent.agent_id) && agent.status === "BUSY"
              ? { ...agent, status: "AVAILABLE" }
              : agent,
          ),
        );

      setSessions((prev) =>
        prev.map((session) => {
          if (session.session_id !== sessionId || !session.pending_decision) {
            return session;
          }
          const pending = session.pending_decision;
          const now = new Date().toISOString();
          const action = decision.action;
          const decisionStatus: DecisionStatus =
            action === "APPROVE"
              ? "APPROVED"
              : action === "REJECT"
                ? "REJECTED"
                : "REPLACED";

          const nextAudit: AuditRecord[] = [
            ...(session.audit ?? []),
            audit({
              session_id: sessionId,
              agent_id: pending.requested_by,
              actor_type: "HUMAN",
              actor_id: "human-owner",
              action:
                action === "APPROVE"
                  ? "DECISION_APPROVED"
                  : action === "REJECT"
                    ? "DECISION_REJECTED"
                    : "DECISION_REPLACED",
              severity: "INFO",
              entity_type: "DecisionRequest",
              reason:
                action === "REPLACE"
                  ? "respuesta manual reemplaza el turno candidato"
                  : undefined,
            }),
          ];

          if (action === "REJECT") {
            nextAudit.push(
              audit({
                session_id: sessionId,
                agent_id: pending.requested_by,
                actor_type: "SYSTEM",
                actor_id: "engine",
                action: "SESSION_REJECTED",
                severity: "WARNING",
                entity_type: "NegotiationState",
                reason: "decisión humana rechazada — el turno no fue publicado",
              }),
            );
            release([session.agent_1_id, session.agent_2_id]);
            return {
              ...session,
              status: "REJECTED",
              messages: session.messages,
              pending_script: [],
              audit: nextAudit,
              outcome: {
                outcome_id: uid(),
                session_id: sessionId,
                resolution: "REJECTED",
                summary: "Decisión sensible rechazada por el propietario.",
                created_at: now,
              },
              raw_state: { ...session.raw_state, status: "REJECTED" },
              pending_decision: { ...pending, status: decisionStatus },
            };
          }

          // APPROVE / REPLACE → reanudar negociación
          let messages = session.messages;
          let pendingScript = [...(session.pending_script ?? [])];
          const blocked = pendingScript.shift();
          if (blocked) {
            if (action === "REPLACE") {
              messages = [
                ...messages,
                {
                  ...blocked,
                  id: uid(),
                  content:
                    decision.replacement_message?.trim() ?? blocked.content,
                  pending_human_approval: false,
                  flagged: undefined,
                },
              ];
            } else {
              messages = [...messages, { ...blocked, pending_human_approval: false }];
            }
            if (blocked.flagged?.value_ref) {
              nextAudit.push(
                audit({
                  session_id: sessionId,
                  agent_id: pending.requested_by,
                  actor_type: "SYSTEM",
                  actor_id: "vault",
                  action: "PRIVATE_DATA_RESOLVED",
                  severity: "INFO",
                  entity_type: "PrivateResolution",
                  reason: `resolved value_ref=${blocked.flagged.value_ref} tras aprobación`,
                }),
              );
            }
          }
          messages = [...messages, ...pendingScript];
          pendingScript = [];

          const revealed_contact = session.revealed_contact ?? {
            agent_id: session.agent_2_id,
            contact: `demo-contact@${session.agent_2_id.replace("agent-", "")}.example`,
            revealed_at: now,
          };

          nextAudit.push(
            audit({
              session_id: sessionId,
              agent_id: pending.requested_by,
              actor_type: "SYSTEM",
              actor_id: "engine",
              action: "SESSION_RESOLVED",
              severity: "INFO",
              entity_type: "NegotiationState",
              reason:
                action === "REPLACE"
                  ? "negociación reanudada con respuesta manual del propietario"
                  : "negociación reanudada tras aprobación humana",
            }),
          );
          release([session.agent_1_id, session.agent_2_id]);

          return {
            ...session,
            status: "RESOLVED",
            messages,
            pending_script: pendingScript,
            audit: nextAudit,
            outcome: {
              outcome_id: uid(),
              session_id: sessionId,
              resolution: "RESOLVED",
              summary:
                action === "REPLACE"
                  ? "Acuerdo cerrado con respuesta manual del propietario."
                  : "Negociación reanudada tras aprobación humana.",
              created_at: now,
            },
            raw_state: { ...session.raw_state, status: "RESOLVED" },
            revealed_contact,
            pending_decision: { ...pending, status: decisionStatus },
          };
        }),
      );
    },
    [],
  );

  const toggleAgentStatus = useCallback((agentId: string) => {
    setAgents((prev) =>
      prev.map((agent) => {
        if (agent.agent_id !== agentId) return agent;
        const next =
          agent.status === "PAUSED"
            ? "AVAILABLE"
            : agent.status === "BUSY"
              ? "BUSY"
              : "PAUSED";
        return { ...agent, status: next };
      }),
    );
  }, []);

  /** agent.registered → persiste y dispara matchmaking automático bidireccional.
   *  Devuelve cuántos candidatos compatibles encontró (0 = sin matches). */
  const registerAgent = useCallback(
    (profile: AgentProfile): number => {
      const exists = agents.some((a) => a.agent_id === profile.agent_id);
      setAgents((prev) =>
        exists
          ? prev.map((a) => (a.agent_id === profile.agent_id ? profile : a))
          : [...prev, profile],
      );

      const pool = agents.length > 0 ? agents : data.agents;
      const candidate = { ...profile, status: "AVAILABLE" as const };
      const now = new Date().toISOString();
      const segment: Segment = segmentOf(candidate.entity_type);
      const created: MatchSession[] = [];

      for (const other of pool) {
        if (other.agent_id === candidate.agent_id) continue;
        if (other.status === "PAUSED") continue;
        const match = computeMatch(candidate, other);
        if (match.score <= 0) continue;

        const channelId = `ch_match_${candidate.agent_id.slice(-8)}_${other.agent_id.slice(-8)}`;
        const sessionId = `ses-${candidate.agent_id.slice(-6)}-${other.agent_id.slice(-6)}-${now.slice(17, 23).replace(/[:.]/g, "")}`;
        created.push({
          session_id: sessionId,
          segment,
          agent_1_id: candidate.agent_id,
          agent_2_id: other.agent_id,
          initiator_id: candidate.agent_id,
          status: "ACTIVE",
          summary: `${candidate.display_name} negocia con ${other.display_name}`,
          started_at: now,
          max_turns: 8,
          current_turn: 1,
          messages: [
            {
              id: uid(),
              sender_agent_id: candidate.agent_id,
              content: `Hola, soy ${candidate.display_name}. Vi que ${other.display_name} encaja con lo que busco. ¿Podemos hablar de una propuesta?`,
              intent: "QUESTION",
              sent_at: now,
            },
          ],
          matchmaking: {
            ...match,
            channel_id: channelId,
            channel_status: "CREATED",
          },
          raw_state: {
            session_id: sessionId,
            status: "ACTIVE",
            turn_count: 1,
            max_turns: 8,
            current_speaker_id: other.agent_id,
          },
          audit: [
            audit({
              session_id: sessionId,
              agent_id: candidate.agent_id,
              actor_type: "SYSTEM",
              actor_id: "transport",
              action: "AGENT_PUBLISHED",
              severity: "INFO",
              entity_type: "TransportEnvelope",
              reason: "agent.registered — publicado en el ecosistema",
            }),
            audit({
              session_id: sessionId,
              agent_id: candidate.agent_id,
              actor_type: "SYSTEM",
              actor_id: "matchmaking",
              action: "MATCHMAKING_EVALUATED",
              severity: "INFO",
              entity_type: "NegotiationState",
              reason: `matched ${other.agent_id} interests->capabilities score=${match.score.toFixed(2)}`,
            }),
            audit({
              session_id: sessionId,
              agent_id: candidate.agent_id,
              actor_type: "SYSTEM",
              actor_id: "matchmaking",
              action: "SESSION_CREATED",
              severity: "INFO",
              entity_type: "NegotiationState",
              reason: `channel=${channelId} members=[${candidate.agent_id},${other.agent_id}]`,
            }),
          ],
        });
      }

      if (created.length > 0) {
        setSessions((prev) => [...created, ...prev]);
        setAgents((prev) =>
          prev.map((a) =>
            a.agent_id === candidate.agent_id ? { ...a, status: "BUSY" } : a,
          ),
        );
      }
      return created.length;
    },
    [agents],
  );

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
      dispatchHumanDecision,
      toggleAgentStatus,
      registerAgent,
      resetDemo,
    }),
    [
      agents,
      sessions,
      agentsById,
      dispatchHumanDecision,
      toggleAgentStatus,
      registerAgent,
      resetDemo,
    ],
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
