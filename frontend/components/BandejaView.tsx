"use client";

import { useAgentSync } from "@/lib/store";
import { DecisionInbox } from "@/components/DecisionInbox";

export function BandejaView() {
  const { sessions } = useAgentSync();
  const pendingCount = sessions.filter(
    (s) => s.status === "PENDING_HUMAN_APPROVAL" && s.pending_decision,
  ).length;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Bandeja de decisiones</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Todas las propuestas sensibles de tus agentes en un solo lugar.
            Tu agente queda en pausa hasta que decidas.
          </p>
        </div>
        <span className="rounded-full bg-[var(--warning)]/10 px-3 py-1 text-sm font-semibold text-[var(--warning)]">
          {pendingCount} pendiente{pendingCount === 1 ? "" : "s"}
        </span>
      </div>

      <DecisionInbox />
    </div>
  );
}
