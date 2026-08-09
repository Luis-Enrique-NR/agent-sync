"use client";

import Link from "next/link";
import { AgentStatusCard } from "@/components/AgentStatusCard";
import { CommercialHome } from "@/components/CommercialHome";
import { kindLabel } from "@/components/HumanEscalationModal";
import { ArrowRightIcon, ShieldIcon } from "@/components/Icons";
import { useAuth } from "@/lib/auth";
import { useAgentSync } from "@/lib/store";
import type { MatchSession } from "@/lib/types";

const statusCopy: Record<
  MatchSession["status"],
  { label: string; className: string }
> = {
  SEARCHING: { label: "Explorando", className: "" },
  ACTIVE: { label: "Negociando", className: "is-active" },
  PENDING_HUMAN_APPROVAL: {
    label: "Necesita tu decisión",
    className: "is-pending",
  },
  RESOLVED: { label: "Match confirmado", className: "is-resolved" },
  REJECTED: { label: "Descartada", className: "is-rejected" },
  FAILED: { label: "Requiere revisión", className: "is-rejected" },
  WITHDRAWN: { label: "Retirada", className: "is-rejected" },
  EXPIRED: { label: "Expirada", className: "" },
};

function progressPercent(session: MatchSession) {
  if (session.max_turns === 0) return 8;
  return Math.min(100, Math.max(8, (session.current_turn / session.max_turns) * 100));
}

export function DashboardView() {
  const { signedIn } = useAuth();
  const { sessions, agents, agentsById } = useAgentSync();
  const pending = sessions.filter(
    (session) =>
      session.status === "PENDING_HUMAN_APPROVAL" && session.pending_decision,
  );
  const activeAgents = agents.filter((agent) => agent.status !== "PAUSED").length;
  const activeSessions = sessions.filter(
    (session) =>
      session.status === "ACTIVE" ||
      session.status === "PENDING_HUMAN_APPROVAL" ||
      session.status === "SEARCHING",
  );
  const featured =
    pending.find((session) => session.segment === "P2P") ??
    sessions.find((session) => session.segment === "P2P") ??
    pending[0] ??
    sessions[0];
  const agentA = agentsById[featured?.agent_1_id];
  const agentB = agentsById[featured?.agent_2_id];
  const p2pSessions = sessions.filter((session) => session.segment === "P2P");

  if (!signedIn) {
    return (
      <CommercialHome
        objective={agentA?.objectives[0]}
        counterpartName={agentB?.display_name?.split(" — ")[0]}
        opportunityCount={p2pSessions.length}
      />
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-columns">
        <section className="dashboard-panel" aria-labelledby="attention-title">
          <div className="panel-heading">
            <div>
              <h2 id="attention-title">Necesita tu decisión</h2>
              <p>Tu agente no avanzará en estos puntos hasta que respondas.</p>
            </div>
            <Link href="/bandeja" className="text-action">
              Ver bandeja <ArrowRightIcon size={14} />
            </Link>
          </div>

          {pending.length > 0 ? (
            <ul className="attention-list">
              {pending.map((session) => (
                <li key={session.session_id}>
                  <Link href={`/chat/${session.session_id}`} className="attention-item">
                    <span className="attention-icon">
                      <ShieldIcon size={19} />
                    </span>
                    <span className="attention-copy">
                      <strong>{kindLabel(session.pending_decision?.kind ?? "")}</strong>
                      <span>
                        {session.segment} · {session.pending_decision?.proposal}
                      </span>
                    </span>
                    <span className="attention-cta">
                      Decidir <ArrowRightIcon size={13} />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty-attention">Todo al día. Tu agente seguirá trabajando.</p>
          )}
        </section>

        <AgentStatusCard
          agentName="Valentina R. — vendedora de auto"
          pendingCount={pending.length}
          activeNegotiations={activeSessions.length}
        />
      </div>

      <section className="activity-panel" aria-labelledby="activity-title">
        <div className="activity-heading">
          <div>
            <h2 id="activity-title">Actividad de tus agentes</h2>
            <p>{activeAgents} agentes activos entre oportunidades B2B y P2P.</p>
          </div>
          <Link href="/ecosistema" className="text-action">
            Ver ecosistema <ArrowRightIcon size={14} />
          </Link>
        </div>

        <ul className="activity-list">
          {sessions.map((session) => {
            const status = statusCopy[session.status];
            return (
              <li key={session.session_id}>
                <Link href={`/chat/${session.session_id}`} className="activity-row">
                  <span className={`session-mark ${session.segment === "P2P" ? "is-p2p" : ""}`}>
                    {session.segment}
                  </span>
                  <span className="session-copy">
                    <strong>{session.summary}</strong>
                    <span>
                      {session.messages.length} mensajes · turno {session.current_turn} de{" "}
                      {session.max_turns}
                    </span>
                  </span>
                  <span className="session-progress">
                    <span>Progreso de la conversación</span>
                    <span className="progress-track">
                      <i style={{ width: `${progressPercent(session)}%` }} />
                    </span>
                  </span>
                  <span className={`status-label ${status.className}`}>{status.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
