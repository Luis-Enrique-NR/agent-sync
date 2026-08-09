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
  ConversationDecision,
  DecisionStatus,
  HumanDecision,
  HumanDecisionAction,
  MatchScore,
  MatchSession,
  MockData,
  Segment,
  TurnIntent,
} from "@/lib/types";
import { segmentOf } from "@/lib/types";
import { DEMO_OWNER_AGENT_ID } from "@/lib/demo";
import mockData from "@/data/mockData.json";

const data = mockData as unknown as MockData;

const STORAGE_KEY = "agentsync-demo-v6";

export const INCOMING_DECISION_DELAY_MS = 5_500;

interface IncomingDecisionNotice {
  session_id: string;
  category: string;
  summary: string;
  counterpart_name: string;
  arrived_at: string;
}

interface AgentSyncState {
  agents: AgentProfile[];
  sessions: MatchSession[];
  agentsById: Record<string, AgentProfile>;
  incomingDecision: IncomingDecisionNotice | null;
  simulateIncomingDecision: () => void;
  dismissIncomingDecision: () => void;
  /** AIBackendService.resume_negotiation — aprueba/rechaza/reemplaza y reanuda. */
  dispatchHumanDecision: (sessionId: string, decision: HumanDecision) => void;
  toggleAgentStatus: (agentId: string) => void;
  /** agent.registered → persiste perfil y dispara matchmaking simulado. */
  registerAgent: (profile: AgentProfile) => number;
  updateAgent: (profile: AgentProfile) => void;
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

interface IncomingDecisionScenario {
  key: string;
  counterpartId: string;
  summary: string;
  category: string;
  decisionSummary: string;
  proposal: string;
  flaggedDetail: string;
  valueRef?: string;
  messages: Array<{
    sender: "owner" | "counterpart";
    content: string;
    intent: TurnIntent;
  }>;
  decisions: Array<{
    actor: "owner" | "counterpart";
    category: string;
    summary: string;
    status: Exclude<DecisionStatus, "PENDING">;
  }>;
  continuation: [string, string];
}

const INCOMING_DECISION_SCENARIOS: IncomingDecisionScenario[] = [
  {
    key: "sofia-final-price",
    counterpartId: "agent-p2p-sofia",
    summary: "Valentina evalúa una oferta verificada de Sofía",
    category: "Aceptar precio final",
    decisionSummary:
      "Sofía ofrece USD 8.150 por transferencia inmediata y pide reservar el Hyundai durante 24 horas.",
    proposal:
      "Aceptar USD 8.150 y reservar el vehículo durante 24 horas mientras se verifica la transferencia",
    flaggedDetail:
      "El precio cumple tu mínimo, pero aceptar la oferta crea un compromiso de reserva.",
    messages: [
      {
        sender: "owner",
        content:
          "El Hyundai 2021 sigue disponible. Tiene 45.000 km y mantenimiento en agencia.",
        intent: "OFFER",
      },
      {
        sender: "counterpart",
        content:
          "Me interesa. Puedo pagar por transferencia verificada si la documentación está al día.",
        intent: "QUESTION",
      },
      {
        sender: "owner",
        content:
          "La documentación está vigente y puedo mostrar las facturas de mantenimiento antes de cerrar.",
        intent: "ACCEPT",
      },
      {
        sender: "counterpart",
        content:
          "Ofrezco USD 8.150 por transferencia inmediata. Necesito 24 horas para completar la verificación bancaria.",
        intent: "OFFER",
      },
      {
        sender: "owner",
        content:
          "La oferta está sobre el mínimo configurado. Puedo preparar una reserva si Valentina confirma el precio final.",
        intent: "COUNTER_OFFER",
      },
    ],
    decisions: [
      {
        actor: "owner",
        category: "Compartir mantenimiento",
        summary:
          "Valentina permitió mostrar las facturas sin revelar datos personales.",
        status: "APPROVED",
      },
      {
        actor: "counterpart",
        category: "Forma de pago",
        summary:
          "Sofía confirmó que usaría una transferencia bancaria verificable.",
        status: "APPROVED",
      },
      {
        actor: "owner",
        category: "Verificación documental",
        summary:
          "Valentina aceptó presentar la documentación antes de recibir el pago.",
        status: "APPROVED",
      },
      {
        actor: "counterpart",
        category: "Subir la oferta",
        summary:
          "Sofía amplió su presupuesto inicial hasta USD 8.150.",
        status: "REPLACED",
      },
      {
        actor: "counterpart",
        category: "Reserva temporal",
        summary:
          "Sofía solicitó reservar el vehículo solo durante la verificación bancaria.",
        status: "APPROVED",
      },
    ],
    continuation: [
      "Acepto USD 8.150 y reservo el vehículo por 24 horas mientras verificas la transferencia.",
      "Perfecto. Inicio la verificación y te confirmo apenas el banco la complete.",
    ],
  },
  {
    key: "mateo-meeting-point",
    counterpartId: "agent-p2p-mateo",
    summary: "Valentina coordina una inspección con Mateo",
    category: "Confirmar lugar de encuentro",
    decisionSummary:
      "Mateo propone revisar el auto con su mecánico el sábado y solicita confirmar un taller en la zona norte.",
    proposal:
      "Confirmar el taller público como punto de encuentro para la inspección del sábado",
    flaggedDetail:
      "Confirmar un encuentro físico requiere tu aprobación, aunque sea en un lugar público.",
    valueRef: "meeting_ref_north_workshop",
    messages: [
      {
        sender: "counterpart",
        content:
          "Busco un vehículo familiar y me interesa revisar el Hyundai con un mecánico independiente.",
        intent: "QUESTION",
      },
      {
        sender: "owner",
        content:
          "Se puede coordinar una inspección. El vehículo está disponible el fin de semana en la zona norte.",
        intent: "ACCEPT",
      },
      {
        sender: "counterpart",
        content:
          "Mi mecánico puede el sábado por la mañana. Prefiero un taller público y pagar la revisión por mi cuenta.",
        intent: "OFFER",
      },
      {
        sender: "owner",
        content:
          "Eso respeta las condiciones configuradas. Puedo evaluar talleres sin compartir una dirección privada.",
        intent: "ACCEPT",
      },
      {
        sender: "counterpart",
        content:
          "Propongo el taller de la avenida principal a las 10:30. ¿Confirmamos el encuentro allí?",
        intent: "QUESTION",
      },
    ],
    decisions: [
      {
        actor: "counterpart",
        category: "Inspección independiente",
        summary:
          "Mateo decidió asumir el costo de una revisión mecánica externa.",
        status: "APPROVED",
      },
      {
        actor: "owner",
        category: "Disponibilidad",
        summary:
          "Valentina permitió explorar horarios durante el fin de semana.",
        status: "APPROVED",
      },
      {
        actor: "counterpart",
        category: "Horario de inspección",
        summary:
          "Mateo confirmó disponibilidad para el sábado por la mañana.",
        status: "APPROVED",
      },
      {
        actor: "owner",
        category: "Proteger dirección privada",
        summary:
          "Valentina mantuvo su dirección oculta y pidió usar un punto público.",
        status: "REPLACED",
      },
      {
        actor: "counterpart",
        category: "Taller propuesto",
        summary:
          "Mateo eligió un taller en zona norte que acepta inspecciones externas.",
        status: "APPROVED",
      },
    ],
    continuation: [
      "Confirmo el taller público para el sábado a las 10:30. No compartiré una dirección privada.",
      "De acuerdo. Mi mecánico y yo llegaremos al taller a la hora acordada.",
    ],
  },
  {
    key: "carlos-contact",
    counterpartId: "agent-p2p-carlos",
    summary: "Carlos solicita el contacto para cerrar la compra",
    category: "Compartir teléfono",
    decisionSummary:
      "Carlos mejoró su oferta a USD 8.050 y solicita un teléfono para coordinar el pago y la prueba de manejo.",
    proposal:
      "Compartir el teléfono protegido con Carlos después de aceptar la oferta de USD 8.050",
    flaggedDetail:
      "El teléfono es un dato privado y solo puede revelarse con tu permiso explícito.",
    valueRef: "contact_ref_valentina_phone",
    messages: [
      {
        sender: "counterpart",
        content:
          "Revisé el valor de mercado y puedo mejorar mi propuesta si el historial está completo.",
        intent: "COUNTER_OFFER",
      },
      {
        sender: "owner",
        content:
          "El historial está completo. El precio mínimo sigue siendo USD 8.000.",
        intent: "COUNTER_OFFER",
      },
      {
        sender: "counterpart",
        content:
          "Puedo ofrecer USD 8.050 en efectivo y cerrar esta semana.",
        intent: "OFFER",
      },
      {
        sender: "owner",
        content:
          "La oferta cumple el mínimo. Antes de compartir contacto debo pedir autorización a Valentina.",
        intent: "ACCEPT",
      },
      {
        sender: "counterpart",
        content:
          "Confirmo intención de compra. ¿Podemos intercambiar teléfono para coordinar el pago?",
        intent: "QUESTION",
      },
    ],
    decisions: [
      {
        actor: "counterpart",
        category: "Revisar valor de mercado",
        summary:
          "Carlos permitió que su agente consultara precios de referencia.",
        status: "APPROVED",
      },
      {
        actor: "owner",
        category: "Mantener precio mínimo",
        summary:
          "Valentina conservó USD 8.000 como límite de venta.",
        status: "APPROVED",
      },
      {
        actor: "counterpart",
        category: "Mejorar la oferta",
        summary:
          "Carlos subió su propuesta hasta USD 8.050 para cerrar esta semana.",
        status: "REPLACED",
      },
      {
        actor: "owner",
        category: "Aceptar efectivo",
        summary:
          "Valentina permitió continuar con pago en efectivo sujeto a verificación.",
        status: "APPROVED",
      },
      {
        actor: "counterpart",
        category: "Intención de compra",
        summary:
          "Carlos confirmó que está listo para avanzar si puede coordinar directamente.",
        status: "APPROVED",
      },
    ],
    continuation: [
      "Acepto la oferta de USD 8.050 y autorizo compartir mi teléfono para coordinar.",
      "Perfecto. Te contactaré únicamente para organizar el pago y la prueba.",
    ],
  },
];

function isoAt(baseMs: number, minuteOffset: number) {
  return new Date(baseMs + minuteOffset * 60_000).toISOString();
}

function buildIncomingDecisionSession(
  scenario: IncomingDecisionScenario,
  baseMs: number,
): MatchSession {
  const sessionId = `ses-live-demo-${scenario.key}-${baseMs}`;
  const decisionId = `dec-live-demo-${scenario.key}-${baseMs}`;
  const counterpart = data.agents.find(
    (agent) => agent.agent_id === scenario.counterpartId,
  );

  return {
    session_id: sessionId,
    segment: "P2P",
    agent_1_id: DEMO_OWNER_AGENT_ID,
    agent_2_id: scenario.counterpartId,
    initiator_id: scenario.counterpartId,
    status: "PENDING_HUMAN_APPROVAL",
    summary: scenario.summary,
    started_at: isoAt(baseMs, -14),
    max_turns: 12,
    current_turn: 6,
    messages: scenario.messages.map((message, index) => ({
      id: `${sessionId}-message-${index + 1}`,
      sender_agent_id:
        message.sender === "owner"
          ? DEMO_OWNER_AGENT_ID
          : scenario.counterpartId,
      content: message.content,
      intent: message.intent,
      sent_at: isoAt(baseMs, -14 + index * 2),
    })),
    pending_script: [
      {
        id: `${sessionId}-pending-owner`,
        sender_agent_id: DEMO_OWNER_AGENT_ID,
        content: scenario.continuation[0],
        intent: "ACCEPT",
        sent_at: isoAt(baseMs, 1),
        pending_human_approval: true,
        flagged: {
          category: scenario.category,
          detail: scenario.flaggedDetail,
          requires_human: true,
          value_ref: scenario.valueRef,
        },
      },
      {
        id: `${sessionId}-pending-counterpart`,
        sender_agent_id: scenario.counterpartId,
        content: scenario.continuation[1],
        intent: "ACCEPT",
        sent_at: isoAt(baseMs, 2),
      },
    ],
    pending_decision: {
      decision_id: decisionId,
      session_id: sessionId,
      speaker_id: DEMO_OWNER_AGENT_ID,
      category: scenario.category,
      summary: scenario.decisionSummary,
      proposal: scenario.proposal,
      requested_by: DEMO_OWNER_AGENT_ID,
      reasons: [scenario.valueRef ? "MANDATORY_PERSONAL_DATA" : "USER_RULE"],
      matched_rule_ids: [
        scenario.valueRef ? "esc-val-phone" : "esc-val-price",
      ],
      created_at: new Date(baseMs).toISOString(),
      status: "PENDING",
    },
    decision_history: scenario.decisions.map((decision, index) => ({
      decision_id: `${sessionId}-history-${index + 1}`,
      agent_id:
        decision.actor === "owner"
          ? DEMO_OWNER_AGENT_ID
          : scenario.counterpartId,
      category: decision.category,
      summary: decision.summary,
      status: decision.status,
      created_at: isoAt(baseMs, -13 + index * 2),
      decided_at: isoAt(baseMs, -12 + index * 2),
    })),
    matchmaking: {
      score: 0.86,
      ic_score: 0.9,
      logistics_score: 0.76,
      price_pass: true,
      direction: { a_to_b: 0.9, b_to_a: 0.8 },
      channel_id: `ch-live-${scenario.key}-${baseMs}`,
      channel_status: "CREATED",
    },
    raw_state: {
      session_id: sessionId,
      status: "PENDING_HUMAN_APPROVAL",
      turn_count: 6,
      max_turns: 12,
      current_speaker_id: DEMO_OWNER_AGENT_ID,
      demo_scenario: scenario.key,
      counterpart_name: counterpart?.display_name,
    },
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
  const [incomingDecision, setIncomingDecision] =
    useState<IncomingDecisionNotice | null>(null);

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

  const simulateIncomingDecision = useCallback(() => {
    const baseMs = Date.now();
    const scenario =
      INCOMING_DECISION_SCENARIOS[
        Math.floor(baseMs / 1_000) % INCOMING_DECISION_SCENARIOS.length
      ];
    const session = buildIncomingDecisionSession(scenario, baseMs);
    const counterpart = data.agents.find(
      (agent) => agent.agent_id === scenario.counterpartId,
    );

    setSessions((prev) => {
      const generated = prev
        .filter((item) => item.session_id.startsWith("ses-live-demo-"))
        .slice(0, 4);
      const permanent = prev.filter(
        (item) => !item.session_id.startsWith("ses-live-demo-"),
      );
      return [session, ...generated, ...permanent];
    });
    setIncomingDecision({
      session_id: session.session_id,
      category: scenario.category,
      summary: scenario.decisionSummary,
      counterpart_name: counterpart?.display_name.split(" — ")[0] ?? "Otra persona",
      arrived_at: new Date(baseMs).toISOString(),
    });
  }, []);

  const dismissIncomingDecision = useCallback(() => {
    setIncomingDecision(null);
  }, []);

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
          const recordedDecision: ConversationDecision = {
            decision_id: pending.decision_id,
            agent_id: pending.requested_by,
            category: pending.category,
            summary: pending.summary,
            status: decisionStatus,
            created_at: pending.created_at,
            decided_at: now,
            manual_response:
              action === "REPLACE"
                ? decision.replacement_message?.trim()
                : undefined,
          };
          const nextDecisionHistory = [
            ...(session.decision_history ?? []).filter(
              (item) => item.decision_id !== pending.decision_id,
            ),
            recordedDecision,
          ];

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
              decision_history: nextDecisionHistory,
              audit: nextAudit,
              outcome: {
                outcome_id: uid(),
                session_id: sessionId,
                resolution: "REJECTED",
                summary: "Decisión sensible rechazada por el propietario.",
                created_at: now,
              },
              raw_state: { ...session.raw_state, status: "REJECTED" },
              pending_decision: {
                ...pending,
                status: decisionStatus,
                manual_response: undefined,
              },
            };
          }

          // APPROVE / REPLACE → reanudar negociación
          let messages = session.messages;
          let pendingScript = (session.pending_script ?? []).map(
            (message, index) => ({
              ...message,
              sent_at: new Date(
                new Date(now).getTime() + index * 60_000,
              ).toISOString(),
            }),
          );
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
            decision_history: nextDecisionHistory,
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
            pending_decision: {
              ...pending,
              status: decisionStatus,
              manual_response:
                action === "REPLACE"
                  ? decision.replacement_message?.trim()
                  : undefined,
            },
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
        const next = agent.status === "PAUSED" ? "AVAILABLE" : "PAUSED";
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

  const updateAgent = useCallback((profile: AgentProfile) => {
    setAgents((prev) =>
      prev.map((agent) =>
        agent.agent_id === profile.agent_id ? profile : agent,
      ),
    );
  }, []);

  const resetDemo = useCallback(() => {
    setAgents(data.agents);
    setSessions(data.sessions);
    setIncomingDecision(null);
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
      incomingDecision,
      simulateIncomingDecision,
      dismissIncomingDecision,
      dispatchHumanDecision,
      toggleAgentStatus,
      registerAgent,
      updateAgent,
      resetDemo,
    }),
    [
      agents,
      sessions,
      agentsById,
      incomingDecision,
      simulateIncomingDecision,
      dismissIncomingDecision,
      dispatchHumanDecision,
      toggleAgentStatus,
      registerAgent,
      updateAgent,
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
