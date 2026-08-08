"use client";

import { useState } from "react";
import type { AgentProfile, MatchSession } from "@/lib/types";

type Filter = "todos" | "B2B" | "P2P";

function segmentOf(agent: AgentProfile): "B2B" | "P2P" {
  return agent.entity_type === "empresa" ? "B2B" : "P2P";
}

export function EcosistemaList({
  agents,
  sessions,
}: {
  agents: AgentProfile[];
  sessions: MatchSession[];
}) {
  const [filter, setFilter] = useState<Filter>("todos");

  const visible =
    filter === "todos"
      ? agents
      : agents.filter((agent) => segmentOf(agent) === filter);

  const activeSessionsOf = (agentId: string) =>
    sessions.filter(
      (s) =>
        (s.agent_1_id === agentId || s.agent_2_id === agentId) &&
        (s.status === "ACTIVE" || s.status === "PENDING_HUMAN_APPROVAL"),
    ).length;

  const filters: { key: Filter; label: string }[] = [
    { key: "todos", label: "Todos" },
    { key: "B2B", label: "B2B · Empresas" },
    { key: "P2P", label: "P2P · Personas" },
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
        {visible.map((agent) => (
          <div
            key={agent.agent_id}
            className="flex flex-col gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="rounded-full bg-[var(--surface-2)] px-2.5 py-0.5 text-xs font-semibold text-[var(--muted)]">
                {segmentOf(agent)}
              </span>
              <span className="rounded-full bg-[var(--accent-2)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--accent-2)]">
                activo
              </span>
            </div>
            <h3 className="text-base font-semibold leading-snug">
              {agent.display_name}
            </h3>
            <p className="text-sm text-[var(--muted)]">{agent.personality}</p>

            <ul className="flex flex-col gap-1.5">
              {agent.objectives.map((objective, index) => (
                <li
                  key={`${agent.agent_id}-obj-${index}`}
                  className="flex items-start gap-2 text-sm text-[var(--muted)]"
                >
                  <span className="text-[var(--accent)]">→</span>
                  {objective}
                </li>
              ))}
            </ul>

            <div className="mt-auto flex items-center justify-between border-t border-[var(--border)] pt-3 text-xs text-[var(--muted)]">
              <span>
                {activeSessionsOf(agent.agent_id)} negociación
                {activeSessionsOf(agent.agent_id) === 1 ? "" : "es"} activa
                {activeSessionsOf(agent.agent_id) === 1 ? "" : "s"}
              </span>
              <span className="font-mono">
                {agent.tools.map((tool) => tool.name).join(" · ")}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
