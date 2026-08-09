"use client";

import { PauseIcon, PlayIcon } from "@/components/Icons";
import { useAgentSync } from "@/lib/store";

export function AgentStatusCard({
  agentName,
  pendingCount,
  activeNegotiations = 0,
  agentId = "agent-p2p-valentina",
}: {
  agentName: string;
  pendingCount: number;
  activeNegotiations?: number;
  agentId?: string;
}) {
  const { agents, toggleAgentStatus } = useAgentSync();
  const agent = agents.find((item) => item.agent_id === agentId);
  const status = agent?.status ?? "AVAILABLE";
  const paused = status === "PAUSED";
  const busy = status === "BUSY";

  return (
    <section className="agent-panel" aria-labelledby="agent-status-title">
      <div className="agent-panel-top">
        <div className="agent-identity">
          <span className={`agent-orb ${paused ? "is-paused" : busy ? "is-busy" : ""}`}>VR</span>
          <div>
            <h2 id="agent-status-title">Mi agente</h2>
            <p>{agentName.split(" — ")[0]}</p>
          </div>
        </div>
        <span className={`agent-status ${paused ? "is-paused" : busy ? "is-busy" : ""}`}>
          {paused ? "Pausado" : busy ? "Negociando" : "Disponible"}
        </span>
      </div>

      <p className="agent-summary">
        {paused
          ? "Tu agente está detenido. No iniciará ni continuará conversaciones."
          : busy
            ? "Está en una conversación activa y respetará cada límite que configuraste."
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
        disabled={busy}
        className="agent-toggle"
      >
        {paused ? <PlayIcon size={15} /> : <PauseIcon size={15} />}
        {busy ? "En negociación activa" : paused ? "Reactivar mi agente" : "Pausar mi agente"}
      </button>
    </section>
  );
}
