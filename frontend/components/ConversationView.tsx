"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import type {
  ChatMessage,
  ConversationDecision,
  DecisionStatus,
  MatchSession,
} from "@/lib/types";
import { useAuth } from "@/lib/auth";
import { useAgentSync } from "@/lib/store";
import { HumanEscalationModal, maskSensitiveContent } from "@/components/HumanEscalationModal";

const TURN_DELAY_MS = 1800;

function formatDecisionDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("es", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function shortAgentName(name?: string) {
  return name?.split(" — ")[0] ?? "La contraparte";
}

function agentInitials(name?: string) {
  return shortAgentName(name)
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function pauseDuration(decision: ConversationDecision) {
  if (!decision.decided_at) return "un momento";
  const duration =
    new Date(decision.decided_at).getTime() -
    new Date(decision.created_at).getTime();
  const minutes = Math.max(1, Math.round(duration / 60_000));
  return minutes === 1 ? "1 min" : `${minutes} min`;
}

const DECISION_STATUS: Record<
  DecisionStatus,
  { label: string; className: string }
> = {
  PENDING: { label: "Por decidir", className: "is-pending" },
  APPROVED: { label: "Aprobada", className: "is-approved" },
  REJECTED: { label: "Rechazada", className: "is-rejected" },
  REPLACED: { label: "Ajustada", className: "is-replaced" },
};

type Phase =
  | "searching"
  | "live"
  | "paused"
  | "waiting_approval"
  | "resolved"
  | "rejected"
  | "failed"
  | "withdrawn"
  | "expired";

function phaseOf(session: MatchSession): Phase {
  switch (session.status) {
    case "PENDING_HUMAN_APPROVAL":
      return "waiting_approval";
    case "RESOLVED":
      return "resolved";
    case "REJECTED":
      return "rejected";
    case "FAILED":
      return "failed";
    case "WITHDRAWN":
      return "withdrawn";
    case "EXPIRED":
      return "expired";
    case "SEARCHING":
      return session.messages.length === 0 ? "searching" : "live";
    case "ACTIVE":
      return "live";
    default:
      return "live";
  }
}

const PHASE_BADGES: Record<Phase, { label: string; className: string } | null> = {
  searching: {
    label: "Buscando agentes compatibles…",
    className: "text-[var(--muted)]",
  },
  live: {
    label: "Conversación en vivo",
    className: "text-[var(--accent-2)]",
  },
  paused: {
    label: "Pausada",
    className: "text-[var(--warning)]",
  },
  waiting_approval: {
    label: "⏸ Esperando tu decisión",
    className: "text-[var(--warning)]",
  },
  resolved: {
    label: "✓ Match confirmado",
    className: "text-[var(--accent-2)]",
  },
  rejected: {
    label: "✕ Negociación descartada",
    className: "text-[var(--danger)]",
  },
  failed: {
    label: "✕ Sesión falló",
    className: "text-[var(--danger)]",
  },
  withdrawn: {
    label: "Retirada por la contraparte",
    className: "text-[var(--warning)]",
  },
  expired: {
    label: "Expirada",
    className: "text-[var(--muted)]",
  },
};

export function ConversationView({
  session,
  agentsById,
}: {
  session: MatchSession;
  agentsById: Record<string, { display_name: string; entity_type: "company" | "person" }>;
}) {
  const { dispatchHumanDecision } = useAgentSync();
  const { agentId } = useAuth();
  const queueRef = useRef<ChatMessage[]>([]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>(session.messages);
  const [streamedExtra, setStreamedExtra] = useState<ChatMessage[]>([]);
  const [typingAgent, setTypingAgent] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);

  const phase = phaseOf(session);
  const pendingCandidate = session.pending_script?.find(
    (m) => m.flagged?.requires_human,
  );
  const canStream =
    session.status === "ACTIVE" &&
    (session.pending_script ?? []).some((m) => !m.flagged?.requires_human);

  const clearTimer = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const revealNext = () => {
    const next = queueRef.current.shift();
    if (!next) return;
    setTypingAgent(next.sender_agent_id);
    setStreamedExtra((prev) => [...prev, next]);
    window.setTimeout(() => setTypingAgent(null), 900);
    if (queueRef.current.length > 0) {
      timerRef.current = setTimeout(revealNext, TURN_DELAY_MS);
    }
  };

  // Re-sincroniza el transcript desde el store (fuente de verdad).
  useEffect(() => {
    setMessages(session.messages);
  }, [session.messages]);

  // Streaming local solo para turnos NO sensibles de sesiones ACTIVE.
  useEffect(() => {
    queueRef.current = (session.pending_script ?? []).filter(
      (m) => !m.flagged?.requires_human,
    );
    setStreamedExtra([]);
    setTypingAgent(null);
    clearTimer();
    if (!paused && session.status === "ACTIVE" && queueRef.current.length > 0) {
      timerRef.current = setTimeout(revealNext, TURN_DELAY_MS);
    }
    return clearTimer;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.session_id, session.status, session.pending_script, paused]);

  const allMessages = [...messages, ...streamedExtra];
  const visibleMessages = allMessages.slice(-5);
  const firstVisibleIndex = allMessages.length - visibleMessages.length;
  const ownerAgentId =
    agentId && [session.agent_1_id, session.agent_2_id].includes(agentId)
      ? agentId
      : session.agent_1_id;
  const decisions: ConversationDecision[] = [
    ...(session.decision_history ?? []),
  ];

  if (
    session.pending_decision &&
    !decisions.some(
      (decision) =>
        decision.decision_id === session.pending_decision?.decision_id,
    )
  ) {
    decisions.push({
      decision_id: session.pending_decision.decision_id,
      agent_id: session.pending_decision.requested_by,
      category: session.pending_decision.category,
      summary: session.pending_decision.summary,
      status: session.pending_decision.status,
      created_at: session.pending_decision.created_at,
      manual_response: session.pending_decision.manual_response,
    });
  }

  const chronologicalDecisions = [...decisions].sort(
    (a, b) =>
      new Date(a.decided_at ?? a.created_at).getTime() -
      new Date(b.decided_at ?? b.created_at).getTime(),
  );
  const recentDecisions = [...chronologicalDecisions].reverse();
  const completedDecisionCount = decisions.filter(
    (decision) => decision.status !== "PENDING",
  ).length;

  const pauseBeforeMessage = (visibleIndex: number) => {
    const messageIndex = firstVisibleIndex + visibleIndex;
    const currentTime = new Date(allMessages[messageIndex].sent_at).getTime();
    const previousTime =
      messageIndex > 0
        ? new Date(allMessages[messageIndex - 1].sent_at).getTime()
        : new Date(session.started_at).getTime();

    return chronologicalDecisions.findLast((decision) => {
      if (decision.status === "PENDING" || !decision.decided_at) return false;
      const decidedAt = new Date(decision.decided_at).getTime();
      return decidedAt > previousTime && decidedAt <= currentTime;
    });
  };

  const badge = PHASE_BADGES[phase];

  return (
    <div className="conversation-workspace">
      <main className="conversation-main">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {badge ? (
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${badge.className} ${
                  badge.className.includes("text-[var(--muted)]")
                    ? "bg-[var(--surface-2)]"
                    : "bg-[var(--surface-2)]/70"
                }`}
              >
                {phase === "live" ? (
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--accent-2)]" />
                ) : null}
                {badge.label}
              </span>
            ) : null}
          </div>

          {canStream ? (
            <button
              type="button"
              onClick={() => setPaused((p) => !p)}
              className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3.5 py-1.5 text-xs font-semibold transition hover:brightness-110"
            >
              {paused ? "Continuar" : "Pausar"}
            </button>
          ) : null}
        </div>

        <div className="conversation-transcript flex flex-col gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
          {allMessages.length > 0 ? (
            <div className="conversation-window-label">
              <span>Conversación reciente</span>
              <small>
                Últimos {visibleMessages.length} de {allMessages.length} mensajes
              </small>
            </div>
          ) : null}

          {visibleMessages.map((message, visibleIndex) => {
            const sender = agentsById[message.sender_agent_id];
            const isOwner = message.sender_agent_id === ownerAgentId;
            const pauseDecision = pauseBeforeMessage(visibleIndex);
            const pauseActor = pauseDecision
              ? pauseDecision.agent_id === ownerAgentId
                ? "tu decisión"
                : `una decisión de ${shortAgentName(
                    agentsById[pauseDecision.agent_id]?.display_name,
                  )}`
              : null;

            return (
              <Fragment key={message.id}>
                {pauseDecision ? (
                  <div className="decision-pause-divider" role="separator">
                    <span />
                    <p>
                      Pausa de {pauseDuration(pauseDecision)} por {pauseActor}
                    </p>
                    <span />
                  </div>
                ) : null}
                <div
                  className={`flex max-w-[86%] flex-col gap-1.5 ${
                    isOwner ? "self-start" : "self-end items-end"
                  }`}
                >
                  <div
                    className={`rounded-2xl border px-4 py-2.5 ${
                      message.blocked_by_guardrail
                        ? "border-[var(--danger)]/50 bg-[var(--danger)]/5"
                        : message.flagged
                          ? "border-[var(--warning)]/50 bg-[var(--surface-2)]"
                          : "border-[var(--border)] bg-[var(--background)]"
                    }`}
                  >
                    <p
                      className={`text-xs font-semibold ${
                        isOwner
                          ? "text-[var(--accent)]"
                          : "text-[var(--accent-2)]"
                      }`}
                    >
                      {shortAgentName(sender?.display_name) ?? message.sender_agent_id}
                    </p>
                    <p className="mt-1 text-sm leading-relaxed">
                      {message.content}
                    </p>
                  </div>
                  {message.flagged ? (
                    <span className="rounded-full bg-[var(--warning)]/10 px-2.5 py-0.5 text-[11px] font-semibold text-[var(--warning)]">
                      ⏸ {message.flagged.category} — {message.flagged.detail}
                    </span>
                  ) : null}
                  {message.blocked_by_guardrail ? (
                    <span className="rounded-full bg-[var(--danger)]/10 px-2.5 py-0.5 text-[11px] font-semibold text-[var(--danger)]">
                      Bloqueado por tu configuración — no se envió
                    </span>
                  ) : null}
                </div>
              </Fragment>
            );
          })}

          {phase === "searching" ? (
            <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
              <span className="flex gap-1">
                <span className="h-2 w-2 animate-bounce rounded-full bg-[var(--accent)]" />
                <span
                  className="h-2 w-2 animate-bounce rounded-full bg-[var(--accent)]"
                  style={{ animationDelay: "150ms" }}
                />
                <span
                  className="h-2 w-2 animate-bounce rounded-full bg-[var(--accent)]"
                  style={{ animationDelay: "300ms" }}
                />
              </span>
              <p className="text-sm text-[var(--muted)]">
                Buscando agentes compatibles en el ecosistema…
              </p>
            </div>
          ) : null}

          {typingAgent ? (
            <div className="self-end max-w-[82%]">
              <p className="text-xs font-semibold text-[var(--accent-2)]">
                {shortAgentName(agentsById[typingAgent]?.display_name)}
              </p>
              <div className="mt-1 flex items-center gap-1 rounded-2xl border border-[var(--border)] bg-[var(--background)] px-4 py-2.5">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--muted)]" />
                <span
                  className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--muted)]"
                  style={{ animationDelay: "150ms" }}
                />
                <span
                  className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--muted)]"
                  style={{ animationDelay: "300ms" }}
                />
              </div>
            </div>
          ) : null}

          {phase === "waiting_approval" && pendingCandidate ? (
            <div className="self-start max-w-[86%] rounded-2xl border border-dashed border-[var(--warning)]/50 bg-[var(--background)] px-4 py-2.5">
              <p className="text-xs font-semibold text-[var(--warning)]">
                Propuesta pendiente de aprobación
              </p>
              <p className="mt-1 text-sm leading-relaxed">
                {maskSensitiveContent(pendingCandidate)}
              </p>
              {pendingCandidate.flagged?.value_ref ? (
                <p className="mt-1.5 text-[10px] text-[var(--warning)]">
                  El dato real permanece oculto hasta que decidas.
                </p>
              ) : null}
            </div>
          ) : null}

        </div>

        {phase === "resolved" ? (
          <div className="rounded-2xl border border-[var(--accent-2)]/40 bg-[var(--accent-2)]/10 p-5">
            <p className="text-sm font-semibold text-[var(--accent-2)]">
              ✓ Match confirmado — siguiente paso
            </p>
            <p className="mt-1 text-sm text-[var(--muted)]">
              La conversación continuó después de tu aprobación. Los datos
              sensibles se compartieron únicamente con tu permiso.
            </p>
            {session.pending_decision?.status === "REPLACED" ? (
              <p className="mt-2 text-xs text-[var(--muted)]">
                El agente continuó usando la respuesta que escribiste.
              </p>
            ) : null}
            {session.outcome?.agreed_price ? (
              <p className="mt-2 text-xs text-[var(--muted)]">
                Acuerdo: USD {session.outcome.agreed_price} ·{" "}
                {session.outcome.summary}
              </p>
            ) : null}
          </div>
        ) : null}

        {phase === "rejected" ? (
          <div className="rounded-2xl border border-[var(--danger)]/40 bg-[var(--danger)]/10 p-5">
            <p className="text-sm font-semibold text-[var(--danger)]">
              ✕ Negociación descartada
            </p>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Rechazaste la propuesta. El mensaje no se envió y ambos agentes
              quedaron disponibles para otras oportunidades.
            </p>
          </div>
        ) : null}

        {phase === "failed" || phase === "withdrawn" || phase === "expired" ? (
          <div className="rounded-2xl border border-[var(--warning)]/40 bg-[var(--warning)]/10 p-5">
            <p className="text-sm font-semibold text-[var(--warning)]">
              {phase === "failed"
                ? "✕ La conversación se interrumpió"
                : phase === "withdrawn"
                  ? "Retirada por la contraparte"
                  : "Conversación expirada"}
            </p>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Los agentes quedaron disponibles para explorar otra oportunidad.
            </p>
          </div>
        ) : null}

        {phase === "waiting_approval" && session.pending_decision ? (
          <HumanEscalationModal
            decision={session.pending_decision}
            candidate={pendingCandidate}
            onResolve={(humanDecision) =>
              dispatchHumanDecision(session.session_id, humanDecision)
            }
          />
        ) : null}
      </main>

      <aside
        className="decision-history-panel"
        aria-labelledby={`decision-history-${session.session_id}`}
      >
        <header>
          <span className="section-eyebrow">Decisiones</span>
          <h2 id={`decision-history-${session.session_id}`}>
            Lo que ya definieron
          </h2>
          <p>
            Acuerdos y límites que cada persona marcó durante esta conversación.
          </p>
          <div className="decision-history-counts">
            <span><strong>{completedDecisionCount}</strong> tomadas</span>
            {decisions.some((decision) => decision.status === "PENDING") ? (
              <span className="has-pending">1 por decidir</span>
            ) : null}
          </div>
        </header>

        {recentDecisions.length > 0 ? (
          <div className="decision-history-list">
            {recentDecisions.map((decision) => {
              const isOwner = decision.agent_id === ownerAgentId;
              const actor = agentsById[decision.agent_id];
              const status = DECISION_STATUS[decision.status];
              return (
                <article
                  className={`decision-history-item ${
                    isOwner ? "is-owner" : "is-counterpart"
                  }`}
                  key={decision.decision_id}
                >
                  <span className="decision-history-avatar">
                    {agentInitials(actor?.display_name)}
                  </span>
                  <div className="decision-history-card">
                    <div className="decision-history-meta">
                      <span>
                        {isOwner
                          ? "Tu decisión"
                          : shortAgentName(actor?.display_name)}
                      </span>
                      <span className={`decision-history-status ${status.className}`}>
                        {status.label}
                      </span>
                    </div>
                    <h3>{decision.category}</h3>
                    <p>{decision.summary}</p>
                    {decision.manual_response ? (
                      <blockquote>“{decision.manual_response}”</blockquote>
                    ) : null}
                    <time dateTime={decision.decided_at ?? decision.created_at}>
                      {decision.status === "PENDING"
                        ? "Esperando respuesta"
                        : formatDecisionDate(
                            decision.decided_at ?? decision.created_at,
                          )}
                    </time>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="decision-history-empty">
            <span>✓</span>
            <p>Aún no hizo falta detener la conversación.</p>
          </div>
        )}
      </aside>
    </div>
  );
}
