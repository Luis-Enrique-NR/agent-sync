import mockData from "@/data/mockData.json";
import type { MockData } from "@/lib/types";
import { DecisionInbox } from "@/components/DecisionInbox";

const data = mockData as unknown as MockData;

const agentsById = Object.fromEntries(
  data.agents.map((agent) => [agent.agent_id, { display_name: agent.display_name }]),
);

export default function BandejaPage() {
  const pendingCount = data.sessions.filter(
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

      <DecisionInbox sessions={data.sessions} agentsById={agentsById} />
    </div>
  );
}
