"use client";

import { PauseIcon, PlayIcon } from "@/components/Icons";
import { useAgentSync } from "@/lib/store";

export function AgentStatusCard({
  agentName,
  objective,
  pendingCount,
  activeNegotiations = 0,
  agentId,
}: {
  agentName: string;
  objective: string;
  pendingCount: number;
  activeNegotiations?: number;
  agentId: string;
}) {
  const { agents, toggleAgentStatus } = useAgentSync();
  const agent = agents.find((item) => item.agent_id === agentId);
  const status = agent?.status ?? "AVAILABLE";
  const paused = status === "PAUSED";
  const busy = !paused && activeNegotiations > 0;
  const displayName = agentName.split(" — ")[0];
  const initials = displayName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

  return (
    <section className="agent-panel" aria-labelledby="agent-status-title">
      <div className="agent-panel-top">
        <div className="agent-identity">
          <span className={`agent-orb ${paused ? "is-paused" : busy ? "is-busy" : ""}`}>
            {initials}
          </span>
          <div>
            <h2 id="agent-status-title">Mi agente</h2>
            <p>{displayName}</p>
          </div>
        </div>
        <span className={`agent-status ${paused ? "is-paused" : busy ? "is-busy" : ""}`}>
          {paused ? "Pausado" : busy ? "Negociando" : "Disponible"}
        </span>
      </div>

      <div className="agent-objective">
        <span>Objetivo actual</span>
        <strong>{objective}</strong>
      </div>

      <p className="agent-summary">
        {paused
          ? "Está en pausa. No iniciará ni continuará conversaciones hasta que lo reactives."
          : busy
            ? `Atiende ${activeNegotiations} negociación${activeNegotiations === 1 ? "" : "es"} dentro de los límites que configuraste.`
            : "Está disponible para encontrar nuevas oportunidades compatibles."}
      </p>

      <div className="agent-facts">
        <span className="agent-fact">
          <strong>{activeNegotiations}</strong>
          <small>en curso</small>
        </span>
        <span className="agent-fact">
          <strong>{pendingCount}</strong>
          <small>por decidir</small>
        </span>
      </div>

      <button
        type="button"
        onClick={() => toggleAgentStatus(agentId)}
        className="agent-toggle"
      >
        {paused ? <PlayIcon size={15} /> : <PauseIcon size={15} />}
        {paused ? "Reactivar agente" : "Pausar agente"}
      </button>
    </section>
  );
}
