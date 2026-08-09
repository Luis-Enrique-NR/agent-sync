"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { AgentProfile, MatchSession, Segment } from "@/lib/types";
import { segmentOf } from "@/lib/types";
import { useAgentSync } from "@/lib/store";

type Filter = "todos" | Segment;

const STATUS_BADGES: Record<
  AgentProfile["status"],
  { label: string; className: string }
> = {
  AVAILABLE: {
    label: "disponible",
    className: "bg-[var(--accent-2)]/10 text-[var(--accent-2)]",
  },
  BUSY: {
    label: "negociando",
    className: "bg-[var(--warning)]/10 text-[var(--warning)]",
  },
  PAUSED: {
    label: "pausado",
    className: "bg-[var(--muted)]/10 text-[var(--muted)]",
  },
};

function matchesOf(agentId: string, sessions: MatchSession[]): MatchSession[] {
  return sessions.filter(
    (s) =>
      (s.agent_1_id === agentId || s.agent_2_id === agentId) &&
      (s.status === "ACTIVE" ||
        s.status === "SEARCHING" ||
        s.status === "PENDING_HUMAN_APPROVAL"),
  );
}

function ScoreBar({ value }: { value: number }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-[var(--surface-2)]">
        <span
          className="block h-full rounded-full bg-[var(--accent)]"
          style={{ width: `${pct}%` }}
        />
      </span>
      <span className="font-mono text-[11px] text-[var(--accent)]">{pct}%</span>
    </span>
  );
}

export function EcosistemaList() {
  const { agents, sessions } = useAgentSync();
  const [filter, setFilter] = useState<Filter>("todos");

  const visible =
    filter === "todos"
      ? agents
      : agents.filter((agent) => segmentOf(agent.entity_type) === filter);

  const counts = useMemo(() => {
    const bySegment = (segment: Segment) =>
      agents.filter((a) => segmentOf(a.entity_type) === segment).length;
    return { todos: agents.length, B2B: bySegment("B2B"), P2P: bySegment("P2P") };
  }, [agents]);

  const filters: { key: Filter; label: string }[] = [
    { key: "todos", label: `Todos (${counts.todos})` },
    { key: "B2B", label: `B2B · Empresas (${counts.B2B})` },
    { key: "P2P", label: `P2P · Personas (${counts.P2P})` },
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

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {visible.map((agent) => {
          const status = STATUS_BADGES[agent.status] ?? STATUS_BADGES.AVAILABLE;
          const activeMatches = matchesOf(agent.agent_id, sessions);
          return (
            <div
              key={agent.agent_id}
              className="flex flex-col gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="rounded-full bg-[var(--surface-2)] px-2.5 py-0.5 text-xs font-semibold text-[var(--muted)]">
                  {segmentOf(agent.entity_type)}
                </span>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${status.className}`}
                >
                  {status.label}
                </span>
              </div>
              <h3 className="text-base font-semibold leading-snug">
                {agent.display_name}
              </h3>
              <p className="text-sm text-[var(--muted)]">{agent.personality}</p>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <p className="font-semibold uppercase tracking-wide text-[var(--muted)]">
                    Intereses
                  </p>
                  <ul className="mt-1 flex flex-col gap-1">
                    {agent.interests.map((interest) => (
                      <li key={interest} className="text-[var(--muted)]">
                        → {interest}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="font-semibold uppercase tracking-wide text-[var(--muted)]">
                    Capacidades
                  </p>
                  <ul className="mt-1 flex flex-col gap-1">
                    {agent.capabilities.map((capability) => (
                      <li key={capability} className="text-[var(--muted)]">
                        ← {capability}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {agent.hard_limits.length > 0 ? (
                <p className="font-mono text-[10px] leading-relaxed text-[var(--muted)]">
                  {agent.hard_limits
                    .map((l) => `${l.key} ${l.operator} ${l.value}`)
                    .join(" · ")}
                </p>
              ) : null}

              <div className="mt-auto border-t border-[var(--border)] pt-3">
                <p className="text-xs font-semibold text-[var(--muted)]">
                  Matchmaking automático bidireccional
                </p>
                {activeMatches.length === 0 ? (
                  <p className="mt-1.5 text-xs text-[var(--muted)]">
                    Sin matches activos. Esperando candidates compatibles en el
                    ecosistema.
                  </p>
                ) : (
                  <ul className="mt-2 flex flex-col gap-2">
                    {activeMatches.map((session) => {
                      const counterpartId =
                        session.agent_1_id === agent.agent_id
                          ? session.agent_2_id
                          : session.agent_1_id;
                      const counterpart = agents.find(
                        (a) => a.agent_id === counterpartId,
                      );
                      return (
                        <li
                          key={session.session_id}
                          className="rounded-xl border border-[var(--border)] bg-[var(--background)] px-3 py-2"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <Link
                              href={`/chat/${session.session_id}`}
                              className="text-xs font-semibold text-[var(--accent)] hover:underline"
                            >
                              {counterpart?.display_name ?? counterpartId}
                            </Link>
                            {session.matchmaking ? (
                              <ScoreBar value={session.matchmaking.score} />
                            ) : null}
                          </div>
                          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-[var(--muted)]">
                            <span className="font-mono">
                              {session.matchmaking?.channel_id ?? "sin canal"}
                            </span>
                            {session.matchmaking?.channel_status === "CREATED" ? (
                              <span className="rounded-full bg-[var(--accent-2)]/10 px-2 py-0.5 font-semibold text-[var(--accent-2)]">
                                canal creado
                              </span>
                            ) : (
                              <span className="rounded-full bg-[var(--warning)]/10 px-2 py-0.5 font-semibold text-[var(--warning)]">
                                canal {session.matchmaking?.channel_status ?? "pendiente"}
                              </span>
                            )}
                            <span className="ml-auto font-semibold uppercase">
                              {session.status.replace(/_/g, " ")}
                            </span>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
