"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { MatchSession } from "@/lib/types";
import { useAgentSync } from "@/lib/store";

type Filter = "todas" | "match" | "rechazadas";

function isFinal(session: MatchSession): boolean {
  return session.status === "RESOLVED" || session.status === "REJECTED";
}

export function MatchHistory() {
  const { sessions, agentsById } = useAgentSync();
  const [filter, setFilter] = useState<Filter>("todas");

  const finals = useMemo(() => sessions.filter(isFinal), [sessions]);

  const visible =
    filter === "todas"
      ? finals
      : finals.filter((s) =>
          filter === "match" ? s.status === "RESOLVED" : s.status === "REJECTED",
        );

  const matched = finals.filter((s) => s.status === "RESOLVED").length;
  const rejected = finals.filter((s) => s.status === "REJECTED").length;

  const filters: { key: Filter; label: string }[] = [
    { key: "todas", label: `Todas (${finals.length})` },
    { key: "match", label: `Matches (${matched})` },
    { key: "rechazadas", label: `Rechazadas (${rejected})` },
  ];

  if (finals.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-[var(--border)] bg-[var(--surface)] px-6 py-14 text-center">
        <span className="text-3xl">📋</span>
        <p className="text-sm font-semibold">Aún no hay negociaciones cerradas.</p>
        <p className="text-sm text-[var(--muted)]">
          Cuando una negociación termine en match o sea rechazada, aparecerá
          aquí.
        </p>
      </div>
    );
  }

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

      <ul className="flex flex-col gap-4">
        {visible.map((session) => {
          const isMatch = session.status === "RESOLVED";
          const revealed = session.revealed_contact;
          const counterpart = agentsById[revealed?.agent_id ?? ""];
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
                  {isMatch ? (
                    <span className="rounded-full bg-[var(--accent-2)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--accent-2)]">
                      ✓ Match confirmado
                    </span>
                  ) : (
                    <span className="rounded-full bg-[var(--danger)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--danger)]">
                      ✕ Rechazada
                    </span>
                  )}
                </div>
                <Link
                  href={`/chat/${session.session_id}`}
                  className="text-xs font-semibold text-[var(--accent)] hover:underline"
                >
                  Ver conversación →
                </Link>
              </div>

              <h3 className="mt-3 text-sm font-semibold leading-snug">
                {session.summary}
              </h3>
              <p className="mt-0.5 text-xs text-[var(--muted)]">
                {session.messages.length} mensajes · {session.started_at}
              </p>

              {isMatch && revealed ? (
                <div className="mt-4 rounded-xl border border-[var(--accent-2)]/40 bg-[var(--accent-2)]/10 px-4 py-3">
                  <p className="text-xs font-semibold text-[var(--accent-2)]">
                    Contacto revelado
                  </p>
                  <p className="mt-1 text-sm">
                    {counterpart?.display_name ?? revealed.agent_id}
                    <span className="ml-2 font-mono text-sm text-[var(--muted)]">
                      {revealed.contact}
                    </span>
                  </p>
                  <p className="mt-0.5 text-[11px] text-[var(--muted)]">
                    Revelado el {revealed.revealed_at}. En una versión real, aquí
                    continúa el contacto fuera de la plataforma.
                  </p>
                </div>
              ) : (
                <p className="mt-4 text-sm text-[var(--muted)]">
                  La negociación se cerró sin publicar contacto. El acuerdo fue
                  descartado por el usuario.
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
