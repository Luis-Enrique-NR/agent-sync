"use client";

import Link from "next/link";
import { useAgentSync } from "@/lib/store";
import { ConversationView } from "@/components/ConversationView";

export function ChatView({ sessionId }: { sessionId: string }) {
  const { sessions, agentsById } = useAgentSync();
  const session = sessions.find((s) => s.session_id === sessionId);

  if (!session) {
    return null;
  }

  const agent1 = agentsById[session.agent_1_id];
  const agent2 = agentsById[session.agent_2_id];

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <div>
        <Link
          href="/"
          className="text-sm text-[var(--muted)] hover:text-[var(--foreground)]"
        >
          ← Volver al dashboard
        </Link>
        <h1 className="mt-2 text-xl font-bold tracking-tight">{session.summary}</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          {agent1?.display_name} ↔ {agent2?.display_name} · segmento{" "}
          {session.segment}
        </p>

        {session.matchmaking ? (
          <div className="mt-4 flex flex-wrap items-center gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-[var(--muted)]">
                Compatibilidad
              </span>
              <span className="text-lg font-bold text-[var(--accent)]">
                {Math.round(session.matchmaking.score * 100)}%
              </span>
              <div className="h-1.5 w-24 overflow-hidden rounded-full bg-[var(--surface-2)]">
                <div
                  className="h-full rounded-full bg-[var(--accent)]"
                  style={{ width: `${Math.round(session.matchmaking.score * 100)}%` }}
                />
              </div>
            </div>
            <div className="flex flex-wrap gap-2 text-[11px] text-[var(--muted)]">
              <span className="rounded-full bg-[var(--surface-2)] px-2 py-0.5 font-mono">
                ic {Math.round(session.matchmaking.ic_score * 100)}%
              </span>
              <span className="rounded-full bg-[var(--surface-2)] px-2 py-0.5 font-mono">
                log {Math.round(session.matchmaking.logistics_score * 100)}%
              </span>
              <span className="rounded-full bg-[var(--surface-2)] px-2 py-0.5 font-mono">
                {session.matchmaking.channel_id}
              </span>
              {session.matchmaking.channel_status === "CREATED" ? (
                <span className="rounded-full bg-[var(--accent-2)]/10 px-2 py-0.5 font-semibold text-[var(--accent-2)]">
                  Canal creado en Portal
                </span>
              ) : (
                <span className="rounded-full bg-[var(--warning)]/10 px-2 py-0.5 font-semibold text-[var(--warning)]">
                  Canal {session.matchmaking.channel_status}
                </span>
              )}
            </div>
          </div>
        ) : null}
      </div>

      <ConversationView session={session} agentsById={agentsById} />
    </div>
  );
}
