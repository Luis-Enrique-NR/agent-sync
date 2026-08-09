"use client";

import { useAgentSync } from "@/lib/store";

export function AgentStatusCard({
  agentName,
  pendingCount,
  agentId = "agent-p2p-valentina",
}: {
  agentName: string;
  pendingCount: number;
  agentId?: string;
}) {
  const { agents, toggleAgentStatus } = useAgentSync();
  const agent = agents.find((a) => a.agent_id === agentId);

  const status = agent?.status ?? "AVAILABLE";
  const paused = status === "PAUSED";
  const busy = status === "BUSY";

  const statusClass = paused
    ? "bg-[var(--warning)]/10 text-[var(--warning)]"
    : busy
      ? "bg-[var(--accent)]/10 text-[var(--accent)]"
      : "bg-[var(--accent-2)]/10 text-[var(--accent-2)]";

  const statusLabel = paused
    ? "Pausado"
    : busy
      ? "Negociando"
      : "Activo";

  return (
    <section className="flex flex-col justify-between gap-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 sm:flex-row sm:items-center">
      <div>
        <h2 className="text-base font-semibold">Estado de mi agente</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">{agentName}</p>
        <div className="mt-3 flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusClass}`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                paused
                  ? "bg-[var(--warning)]"
                  : busy
                    ? "bg-[var(--accent)]"
                    : "bg-[var(--accent-2)]"
              }`}
            />
            {statusLabel}
          </span>
          <span className="rounded-full bg-[var(--surface-2)] px-2.5 py-0.5 font-mono text-[10px] text-[var(--muted)]">
            {status}
          </span>
          {pendingCount > 0 ? (
            <span className="rounded-full bg-[var(--warning)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--warning)]">
              {pendingCount} decisión{pendingCount === 1 ? "" : "es"} pendiente
              {pendingCount === 1 ? "" : "s"}
            </span>
          ) : null}
        </div>
      </div>
      <button
        type="button"
        onClick={() => toggleAgentStatus(agentId)}
        disabled={busy}
        className={`inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
          paused
            ? "bg-[var(--accent-2)]/15 text-[var(--accent-2)] hover:brightness-110"
            : "border border-[var(--border)] bg-[var(--surface-2)] text-[var(--foreground)] hover:brightness-110"
        }`}
      >
        {busy
          ? "En negociación activa"
          : paused
            ? "Continuar agente"
            : "Pausar agente"}
      </button>
    </section>
  );
}
