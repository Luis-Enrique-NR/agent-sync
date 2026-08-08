"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { DecisionStatus, MatchSession, PendingDecision } from "@/lib/types";
import { DecisionPanel } from "@/components/DecisionPanel";

type Filter = "todas" | "B2B" | "P2P";

function decisionOf(session: MatchSession): PendingDecision | null {
  if (session.status !== "PENDING_HUMAN_APPROVAL") return null;
  return session.pending_decision ?? null;
}

export function DecisionInbox({
  sessions,
  agentsById,
}: {
  sessions: MatchSession[];
  agentsById: Record<string, { display_name: string }>;
}) {
  const [filter, setFilter] = useState<Filter>("todas");
  const [resolved, setResolved] = useState<Record<string, DecisionStatus>>({});

  const pending = useMemo(
    () =>
      sessions
        .map((session) => ({ session, decision: decisionOf(session) }))
        .filter(
          (entry): entry is { session: MatchSession; decision: PendingDecision } =>
            entry.decision !== null && entry.decision.status === "PENDING",
        ),
    [sessions],
  );

  const visible =
    filter === "todas"
      ? pending
      : pending.filter(({ session }) => session.segment === filter);

  const resolvedCount = sessions.filter(
    (s) => s.pending_decision && resolved[s.session_id],
  ).length;

  const handleResolve = (sessionId: string, status: DecisionStatus) => {
    setResolved((prev) => ({ ...prev, [sessionId]: status }));
  };

  const filters: { key: Filter; label: string }[] = [
    { key: "todas", label: `Todas (${pending.length})` },
    {
      key: "B2B",
      label: `B2B (${pending.filter(({ session }) => session.segment === "B2B").length})`,
    },
    {
      key: "P2P",
      label: `P2P (${pending.filter(({ session }) => session.segment === "P2P").length})`,
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2">
        {filters.map((option) => {
          const selected = filter === option.key;
          return (
            <button
              key={option.key}
              type="button"
              onClick={() => setFilter(option.key)}
              className={`rounded-full px-4 py-1.5 text-sm font-semibold transition ${
                selected
                  ? "bg-[var(--accent)] text-white"
                  : "border border-[var(--border)] bg-[var(--surface)] text-[var(--muted)] hover:text-[var(--foreground)]"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>

      {visible.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-[var(--border)] bg-[var(--surface)] px-6 py-14 text-center">
          <span className="text-3xl">✓</span>
          <p className="text-sm font-semibold">
            {resolvedCount > 0
              ? "Bandeja al día. Resolviste " +
                resolvedCount +
                (resolvedCount === 1 ? " decisión." : " decisiones.")
              : "No hay decisiones pendientes."}
          </p>
          <p className="text-sm text-[var(--muted)]">
            Cuando un agente quiera publicar algo sensible, la propuesta
            aparecerá aquí para tu aprobación.
          </p>
        </div>
      ) : (
        <ul className="flex flex-col gap-4">
          {visible.map(({ session, decision }) => {
            const requester = agentsById[decision.requested_by];
            const isResolved = Boolean(resolved[session.session_id]);
            return (
              <li
                key={session.session_id}
                className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-[var(--surface-2)] px-2.5 py-0.5 text-xs font-semibold text-[var(--muted)]">
                      {session.segment}
                    </span>
                    <Link
                      href={`/chat/${session.session_id}`}
                      className="text-xs font-semibold text-[var(--accent)] hover:underline"
                    >
                      Ver conversación →
                    </Link>
                  </div>
                  {isResolved ? (
                    <span className="rounded-full bg-[var(--accent-2)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--accent-2)]">
                      Resuelta en esta sesión
                    </span>
                  ) : (
                    <span className="rounded-full bg-[var(--warning)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--warning)]">
                      Pendiente
                    </span>
                  )}
                </div>

                <p className="mt-3 text-sm font-semibold leading-snug">
                  {session.summary}
                </p>
                <p className="mt-0.5 text-xs text-[var(--muted)]">
                  Solicitada por {requester?.display_name ?? decision.requested_by}
                </p>

                <div className="mt-4">
                  <DecisionPanel
                    decision={decision}
                    onResolve={(status) => handleResolve(session.session_id, status)}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
