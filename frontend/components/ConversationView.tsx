"use client";

import { useEffect, useRef, useState } from "react";
import type {
  ChatMessage,
  DecisionStatus,
  MatchSession,
} from "@/lib/types";
import { DecisionPanel } from "@/components/DecisionPanel";

const TURN_DELAY_MS = 1800;

type Phase = "idle" | "live" | "paused" | "waiting_approval" | "resolved" | "rejected";

export function ConversationView({
  session,
  agentsById,
}: {
  session: MatchSession;
  agentsById: Record<
    string,
    { display_name: string; entity_type: "empresa" | "persona" }
  >;
}) {
  const queueRef = useRef<ChatMessage[]>(session.pending_script ?? []);
  const [messages, setMessages] = useState<ChatMessage[]>(session.messages);
  const [phase, setPhase] = useState<Phase>(() =>
    queueRef.current.length > 0 ? "live" : "idle",
  );
  const [typingAgent, setTypingAgent] = useState<string | null>(null);
  const [resolvedStatus, setResolvedStatus] =
    useState<DecisionStatus | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const clearTimer = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const revealNext = () => {
    const next = queueRef.current.shift();
    if (!next) return;

    setMessages((prev) => [...prev, next]);
    setTypingAgent(next.sender_agent_id);

    if (next.flagged?.requires_human) {
      setPhase("waiting_approval");
      return;
    }
    if (queueRef.current.length === 0) {
      setPhase("resolved");
      return;
    }
    timerRef.current = setTimeout(revealNext, TURN_DELAY_MS);
  };

  useEffect(() => {
    if (phase !== "live") return;
    timerRef.current = setTimeout(revealNext, TURN_DELAY_MS);
    return clearTimer;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, typingAgent]);

  const togglePause = () => {
    if (phase === "live") {
      clearTimer();
      setPhase("paused");
    } else if (phase === "paused") {
      setPhase("live");
    }
  };

  const handleResolve = (status: DecisionStatus) => {
    setResolvedStatus(status);
    if (status === "REJECTED") {
      clearTimer();
      setPhase("rejected");
      return;
    }
    if (queueRef.current.length === 0) {
      setPhase("resolved");
    } else {
      setPhase("live");
    }
  };

  const hasScript = (session.pending_script?.length ?? 0) > 0;
  const searching = !hasScript && messages.length === 0;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {phase === "live" ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--accent-2)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--accent-2)]">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--accent-2)]" />
              Conversación en vivo
            </span>
          ) : phase === "paused" ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--warning)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--warning)]">
              Pausada
            </span>
          ) : phase === "waiting_approval" ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--warning)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--warning)]">
              ⏸ Esperando tu decisión
            </span>
          ) : phase === "resolved" ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--accent-2)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--accent-2)]">
              ✓ Match confirmado
            </span>
          ) : phase === "rejected" ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--danger)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--danger)]">
              ✕ Negociación descartada
            </span>
          ) : null}
        </div>

        {hasScript && (phase === "live" || phase === "paused") ? (
          <button
            type="button"
            onClick={togglePause}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3.5 py-1.5 text-xs font-semibold transition hover:brightness-110"
          >
            {phase === "live" ? "Pausar" : "Continuar"}
          </button>
        ) : null}
      </div>

      <div className="flex flex-col gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
        {messages.map((message) => {
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

        {searching ? (
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
        <div ref={endRef} />
      </div>

      {phase === "waiting_approval" && session.pending_decision ? (
        <DecisionPanel
          decision={session.pending_decision}
          onResolve={handleResolve}
        />
      ) : null}

      {phase === "resolved" ? (
        <div className="rounded-2xl border border-[var(--accent-2)]/40 bg-[var(--accent-2)]/10 p-5">
          <p className="text-sm font-semibold text-[var(--accent-2)]">
            ✓ Match confirmado — siguiente paso
          </p>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Contacto revelado (simulado): en una versión real ambos agentes
            revelan su email o teléfono de contacto para continuar fuera de la
            plataforma.
          </p>
          {resolvedStatus === "REPLACED" ? (
            <p className="mt-2 text-xs text-[var(--muted)]">
              Tu respuesta manual fue registrada con trazabilidad antes de
              continuar.
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
            Rechazaste la propuesta. No se publicó ningún mensaje y la sesión
            quedó registrada como REJECTED.
          </p>
        </div>
      ) : null}
    </div>
  );
}
