"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useAgentSync } from "@/lib/store";
import { HumanEscalationModal } from "@/components/HumanEscalationModal";
import { useAuth } from "@/lib/auth";

const PAGE_SIZE = 6;

export function DecisionInbox() {
  const { sessions, agentsById, dispatchHumanDecision } = useAgentSync();
  const { agentId } = useAuth();
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [highlightedDecisionId, setHighlightedDecisionId] = useState<string | null>(null);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  const pending = useMemo(
    () =>
      sessions
        .filter((session) => session.status === "PENDING_HUMAN_APPROVAL")
        .sort(
          (left, right) =>
            Date.parse(right.started_at) -
            Date.parse(left.started_at),
        ),
    [sessions],
  );

  const visible = pending.slice(0, visibleCount);
  const hasMore = visibleCount < pending.length;
  const resolvedThisSession = sessions.filter(
    (session) =>
      session.status !== "PENDING_HUMAN_APPROVAL" &&
      session.pending_script?.some((m) => m.flagged?.requires_human),
  ).length;

  useEffect(() => {
    const sentinel = loadMoreRef.current;
    if (!sentinel || !hasMore) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        setVisibleCount((current) =>
          Math.min(current + PAGE_SIZE, pending.length),
        );
      },
      { rootMargin: "220px 0px" },
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, pending.length]);

  useEffect(() => {
    const prefix = "#decision-card-";
    let scrollTimer: number | undefined;
    let clearTimer: number | undefined;

    const revealLinkedDecision = () => {
      if (!window.location.hash.startsWith(prefix)) return;

      const decisionId = decodeURIComponent(
        window.location.hash.slice(prefix.length),
      );
      const targetIndex = pending.findIndex(
        (session) => session.session_id === decisionId,
      );
      if (targetIndex < 0) return;

      setVisibleCount((current) => Math.max(current, targetIndex + 1));
      window.clearTimeout(scrollTimer);
      window.clearTimeout(clearTimer);
      scrollTimer = window.setTimeout(() => {
        const target = document.getElementById(`decision-card-${decisionId}`);
        if (!target) return;
        setHighlightedDecisionId(decisionId);
        target.scrollIntoView({ behavior: "smooth", block: "center" });
        target.focus({ preventScroll: true });
      }, 260);
      clearTimer = window.setTimeout(
        () => setHighlightedDecisionId(null),
        3_000,
      );
    };

    revealLinkedDecision();
    window.addEventListener("hashchange", revealLinkedDecision);

    return () => {
      window.removeEventListener("hashchange", revealLinkedDecision);
      window.clearTimeout(scrollTimer);
      window.clearTimeout(clearTimer);
    };
  }, [pending]);

  if (pending.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-[var(--border)] bg-[var(--surface)] px-6 py-14 text-center">
        <span className="text-3xl">✓</span>
        <p className="text-sm font-semibold">
          {resolvedThisSession > 0
            ? "Bandeja al día. Resolviste " +
              resolvedThisSession +
              (resolvedThisSession === 1 ? " decisión." : " decisiones.")
            : "No hay decisiones pendientes."}
        </p>
        <p className="text-sm text-[var(--muted)]">
          Cuando un agente quiera publicar algo sensible (precio, PII o
          compromiso), la propuesta aparecerá aquí para tu aprobación.
        </p>
      </div>
    );
  }

  return (
    <div className="decision-stream">
      <ul className="flex flex-col gap-4">
        {visible.map((session) => {
          const counterpartId =
            session.agent_1_id === agentId
              ? session.agent_2_id
              : session.agent_1_id;
          const counterpart = agentsById[counterpartId];
          const candidate = session.pending_script?.find(
            (message) => message.flagged?.requires_human,
          );

          return (
            <li
              key={session.session_id}
              id={`decision-card-${session.session_id}`}
              tabIndex={-1}
              className={`decision-inbox-card rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 ${
                highlightedDecisionId === session.session_id
                  ? "is-targeted"
                  : ""
              }`}
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
                <span className="rounded-full bg-[var(--warning)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--warning)]">
                  Pendiente
                </span>
              </div>

              <p className="mt-3 text-sm font-semibold leading-snug">
                {session.summary || `Negociación ${session.segment} — ${session.current_turn} turnos`}
              </p>
              <p className="mt-0.5 text-xs text-[var(--muted)]">
                Conversación con {counterpart?.display_name?.split(" — ")[0] ?? "la otra parte"}
              </p>

              <div className="mt-4">
                <HumanEscalationModal
                  decision={{
                    decision_id: session.session_id,
                    session_id: session.session_id,
                    speaker_id: session.agent_1_id,
                    category: "price",
                    summary: candidate?.content ?? "Propuesta pendiente de aprobación",
                    proposal: candidate?.content ?? "",
                    requested_by: session.agent_1_id,
                    status: "PENDING",
                    created_at: session.started_at,
                  }}
                  candidate={candidate}
                  onResolve={(humanDecision) =>
                    dispatchHumanDecision(session.session_id, humanDecision)
                  }
                />
              </div>
            </li>
          );
        })}
      </ul>

      {hasMore ? (
        <div
          ref={loadMoreRef}
          className="decision-stream-loader"
          role="status"
          aria-live="polite"
        >
          <span aria-hidden="true" />
          Cargando más decisiones…
        </div>
      ) : pending.length > PAGE_SIZE ? (
        <p className="decision-stream-end">Has revisado todas las decisiones pendientes.</p>
      ) : null}
    </div>
  );
}
