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

const STORAGE_KEY = "agentsync-demo-v9";

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
  ownerObjectiveId: string;
  counterpartObjectiveId: string;
  summary: string;
  category: string;
  decisionSummary: string;
  proposal: string;
  flaggedDetail: string;
  matchedRuleId: string;
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
    ownerObjectiveId: "obj-valentina-venta",
    counterpartObjectiveId: "obj-sofia-compra",
    summary: "Valentina evalúa una oferta verificada de Sofía",
    category: "Aceptar precio final",
    decisionSummary:
      "Sofía ofrece USD 8.150 por transferencia inmediata y pide reservar el Hyundai durante 24 horas.",
    proposal:
      "Aceptar USD 8.150 y reservar el vehículo durante 24 horas mientras se verifica la transferencia",
    flaggedDetail:
      "El precio cumple tu mínimo, pero aceptar la oferta crea un compromiso de reserva.",
    matchedRuleId: "esc-val-price",
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
    key: "laura-tutoring-schedule",
    counterpartId: "agent-p2p-laura",
    ownerObjectiveId: "obj-valentina-tutorias",
    counterpartObjectiveId: "obj-laura-tutor",
    summary: "Laura propone un horario fijo para las clases de matemática",
    category: "Confirmar horario semanal",
    decisionSummary:
      "Laura acepta la tarifa de PEN 50 por hora y propone reservar martes y jueves a las 18:30 durante dos meses.",
    proposal:
      "Reservar dos horarios semanales para clases virtuales durante los próximos dos meses",
    flaggedDetail:
      "El plan cumple tus condiciones, pero bloquear dos horarios recurrentes requiere tu confirmación.",
    matchedRuleId: "esc-val-schedule",
    messages: [
      {
        sender: "counterpart",
        content:
          "Busco refuerzo de matemática para dos estudiantes de secundaria, dos veces por semana.",
        intent: "QUESTION",
      },
      {
        sender: "owner",
        content:
          "Valentina tiene tres cupos y puede cubrir álgebra, geometría y preparación de exámenes.",
        intent: "OFFER",
      },
      {
        sender: "counterpart",
        content:
          "Podemos martes y jueves después de las 18:00. Preferimos clases virtuales y seguimiento semanal.",
        intent: "OFFER",
      },
      {
        sender: "owner",
        content:
          "La tarifa es PEN 50 por hora e incluye material de práctica. Es compatible con esos horarios.",
        intent: "COUNTER_OFFER",
      },
      {
        sender: "counterpart",
        content:
          "Acepto la tarifa. ¿Reservamos martes y jueves a las 18:30 durante dos meses?",
        intent: "QUESTION",
      },
    ],
    decisions: [
      {
        actor: "counterpart",
        category: "Cantidad de alumnos",
        summary:
          "Laura confirmó que las clases serán para dos estudiantes.",
        status: "APPROVED",
      },
      {
        actor: "owner",
        category: "Cupos disponibles",
        summary:
          "Valentina permitió que su agente ofreciera dos de sus tres cupos.",
        status: "APPROVED",
      },
      {
        actor: "counterpart",
        category: "Modalidad de clase",
        summary:
          "Laura eligió modalidad virtual con seguimiento semanal.",
        status: "APPROVED",
      },
      {
        actor: "owner",
        category: "Tarifa propuesta",
        summary:
          "Valentina autorizó negociar desde PEN 45 y proponer PEN 50 por hora.",
        status: "APPROVED",
      },
      {
        actor: "counterpart",
        category: "Duración del plan",
        summary:
          "Laura propuso mantener las clases durante dos meses.",
        status: "APPROVED",
      },
    ],
    continuation: [
      "Confirmo martes y jueves a las 18:30 durante dos meses, comenzando con una clase diagnóstica.",
      "Perfecto. Enviaré los temas actuales de ambos estudiantes antes de la primera clase.",
    ],
  },
  {
    key: "diego-cardboard-supply",
    counterpartId: "agent-p2p-diego-carton",
    ownerObjectiveId: "obj-valentina-carton",
    counterpartObjectiveId: "obj-diego-carton",
    summary: "Diego presenta una oferta mensual de cartón corrugado",
    category: "Confirmar compra recurrente",
    decisionSummary:
      "Diego ofrece 300 planchas mensuales a PEN 2,60 por unidad con entrega incluida y pide un compromiso inicial de tres meses.",
    proposal:
      "Aceptar el suministro de 300 planchas mensuales durante tres meses, sujeto a validar las muestras",
    flaggedDetail:
      "La oferta respeta el precio máximo, pero crea una compra recurrente que requiere tu confirmación.",
    matchedRuleId: "esc-val-cardboard",
    messages: [
      {
        sender: "owner",
        content:
          "Busco 300 planchas mensuales de cartón corrugado de doble pared con entrega local.",
        intent: "QUESTION",
      },
      {
        sender: "counterpart",
        content:
          "Puedo ofrecer ese volumen a PEN 2,75 por plancha, con la entrega incluida.",
        intent: "OFFER",
      },
      {
        sender: "owner",
        content:
          "El precio entra en el límite. Necesito validar resistencia y medidas antes de acordar recurrencia.",
        intent: "COUNTER_OFFER",
      },
      {
        sender: "counterpart",
        content:
          "Enviaré diez muestras sin costo. Si se aprueban, reduzco el precio a PEN 2,60 por plancha.",
        intent: "COUNTER_OFFER",
      },
      {
        sender: "counterpart",
        content:
          "Para mantener PEN 2,60 necesito un compromiso inicial de tres meses. ¿Lo confirmamos sujeto a las muestras?",
        intent: "QUESTION",
      },
    ],
    decisions: [
      {
        actor: "owner",
        category: "Volumen requerido",
        summary:
          "Valentina fijó el pedido en 300 planchas mensuales.",
        status: "APPROVED",
      },
      {
        actor: "owner",
        category: "Precio máximo",
        summary:
          "Valentina estableció un máximo de PEN 2,80 por plancha.",
        status: "APPROVED",
      },
      {
        actor: "counterpart",
        category: "Muestras de calidad",
        summary:
          "Diego autorizó enviar diez muestras y la ficha técnica sin costo.",
        status: "APPROVED",
      },
      {
        actor: "counterpart",
        category: "Descuento por volumen",
        summary:
          "Diego redujo su propuesta de PEN 2,75 a PEN 2,60 por plancha.",
        status: "REPLACED",
      },
      {
        actor: "counterpart",
        category: "Condición de recurrencia",
        summary:
          "Diego pidió un compromiso mínimo de tres meses para mantener el descuento.",
        status: "APPROVED",
      },
    ],
    continuation: [
      "Acepto el acuerdo inicial de tres meses, sujeto a que las muestras cumplan la calidad indicada.",
      "Perfecto. Mantendré el precio de PEN 2,60 y programaré el primer lote cuando apruebes las muestras.",
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
    agent_1_objective_id: scenario.ownerObjectiveId,
    agent_2_objective_id: scenario.counterpartObjectiveId,
    initiator_id: scenario.counterpartId,
    decision_turn: "OWNER",
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
      matched_rule_ids: [scenario.matchedRuleId],
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
