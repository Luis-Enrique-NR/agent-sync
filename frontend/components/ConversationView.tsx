"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatMessage, MatchSession } from "@/lib/types";
import { useAgentSync } from "@/lib/store";
import { HumanEscalationModal, maskSensitiveContent } from "@/components/HumanEscalationModal";
import { AuditTrail } from "@/components/AuditTrail";

const TURN_DELAY_MS = 1800;

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
  const queueRef = useRef<ChatMessage[]>([]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
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

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, streamedExtra, typingAgent]);

  const allMessages = [...messages, ...streamedExtra];

  const badge = PHASE_BADGES[phase];

  return (
    <div className="flex flex-col gap-4">
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

      <div className="flex flex-col gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
        {allMessages.map((message) => {
          const sender = agentsById[message.sender_agent_id];
          const isAgent1 = message.sender_agent_id === session.agent_1_id;
          return (
            <div
              key={message.id}
              className={`flex max-w-[82%] flex-col gap-1.5 ${
                isAgent1 ? "self-start" : "self-end items-end"
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
                    isAgent1 ? "text-[var(--accent)]" : "text-[var(--accent-2)]"
                  }`}
                >
                  {sender?.display_name ?? message.sender_agent_id}
                </p>
                <p className="mt-1 text-sm leading-relaxed">{message.content}</p>
                <p className="mt-1.5 font-mono text-[10px] text-[var(--muted)]">
                  {message.sent_at}
                </p>
              </div>
              {message.flagged ? (
                <span className="rounded-full bg-[var(--warning)]/10 px-2.5 py-0.5 text-[11px] font-semibold text-[var(--warning)]">
                  ⏸ {message.flagged.category} — {message.flagged.detail}
                </span>
              ) : null}
              {message.blocked_by_guardrail ? (
                <span className="rounded-full bg-[var(--danger)]/10 px-2.5 py-0.5 text-[11px] font-semibold text-[var(--danger)]">
                  Bloqueado por guardrail — nunca emitido al otro agente
                </span>
              ) : null}
            </div>
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
              {agentsById[typingAgent]?.display_name ?? "Agente"}
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
          <div className="self-start max-w-[82%] rounded-2xl border border-dashed border-[var(--warning)]/50 bg-[var(--background)] px-4 py-2.5">
            <p className="text-xs font-semibold text-[var(--warning)]">
              Propuesta pendiente de aprobación
            </p>
            <p className="mt-1 text-sm leading-relaxed">
              {maskSensitiveContent(pendingCandidate)}
            </p>
            {pendingCandidate.flagged?.value_ref ? (
              <p className="mt-1.5 font-mono text-[10px] text-[var(--warning)]">
                ◈ {pendingCandidate.flagged.value_ref} (referencia opaca)
              </p>
            ) : null}
          </div>
        ) : null}

        <div ref={endRef} />
      </div>

      {phase === "resolved" ? (
        <div className="rounded-2xl border border-[var(--accent-2)]/40 bg-[var(--accent-2)]/10 p-5">
          <p className="text-sm font-semibold text-[var(--accent-2)]">
            ✓ Match confirmado — siguiente paso
          </p>
          <p className="mt-1 text-sm text-[var(--muted)]">
            El AI Backend reanudó la negociación tras tu aprobación. Los datos
            sensibles aprobados fueron resueltos por el vault y registrados en
            la bitácora.
          </p>
          {session.pending_decision?.status === "REPLACED" ? (
            <p className="mt-2 text-xs text-[var(--muted)]">
              Tu respuesta manual fue registrada con trazabilidad antes de
              continuar.
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
            Rechazaste la propuesta. El AI Backend retiró la sesión; no se
            publicó ningún mensaje y quedó registrada como REJECTED.
          </p>
        </div>
      ) : null}

      {phase === "failed" || phase === "withdrawn" || phase === "expired" ? (
        <div className="rounded-2xl border border-[var(--warning)]/40 bg-[var(--warning)]/10 p-5">
          <p className="text-sm font-semibold text-[var(--warning)]">
            {phase === "failed"
              ? "✕ Sesión falló"
              : phase === "withdrawn"
                ? "Retirada por la contraparte"
                : "Sesión expirada"}
          </p>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Los agentes fueron liberados y el motor puede volver a intentar el
            matchmaking con otro candidato.
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

      <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
        <h2 className="text-base font-semibold">Bitácora / audit trail</h2>
        <p className="mb-4 mt-1 text-sm text-[var(--muted)]">
          Trazabilidad notarial con actor (HUMAN / SYSTEM / LLM) de cada
          transición.
        </p>
        <AuditTrail audit={session.audit} />
      </section>
    </div>
  );
}
