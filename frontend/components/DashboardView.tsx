"use client";

import Link from "next/link";
import type { MatchSession } from "@/lib/types";
import { useAgentSync } from "@/lib/store";
import { AgentStatusCard } from "@/components/AgentStatusCard";
import { kindLabel } from "@/components/HumanEscalationModal";
import {
  ArrowRightIcon,
  CheckIcon,
  InboxIcon,
  SearchIcon,
  ShieldIcon,
  SparkIcon,
} from "@/components/Icons";

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

function initials(name?: string) {
  if (!name) return "AI";
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}

export function DashboardView() {
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
  const featured = pending.find((session) => session.segment === "P2P") ?? pending[0] ?? sessions[0];
  const agentA = agentsById[featured?.agent_1_id];
  const agentB = agentsById[featured?.agent_2_id];
  const primaryHref = pending[0] ? `/chat/${pending[0].session_id}` : "/ecosistema";

  return (
    <div className="dashboard">
      <section className="hero-panel" aria-labelledby="dashboard-title">
        <div className="hero-copy">
          <span className="hero-eyebrow">
            <SparkIcon size={15} /> Resumen de hoy
          </span>
          <h1 id="dashboard-title">
            Tu agente avanza. <span>Tú das la última palabra.</span>
          </h1>
          <p className="hero-description">
            AgentSync explora, filtra y negocia por ti. Cuando una conversación
            toca un límite que marcaste como sensible, se detiene y te explica
            exactamente qué debes decidir.
          </p>
          <div className="hero-actions">
            <Link href={primaryHref} className="primary-action">
              {pending.length > 0 ? `Revisar ${pending.length} decisiones` : "Explorar oportunidades"}
              <ArrowRightIcon size={16} />
            </Link>
            <Link href="/setup" className="secondary-action">
              Ajustar lo que mi agente puede hacer
            </Link>
          </div>
          <div className="hero-trust">
            <ShieldIcon size={17} />
            <span>
              Tus límites duros se validan antes de enviar cualquier mensaje.
            </span>
          </div>
        </div>

        <div className="hero-visual" aria-label="Vista previa de una negociación">
          <div className="route-card">
            <div className="route-card-header">
              <span>Ruta de negociación</span>
              <span className="live-chip">Agente en pausa</span>
            </div>

            <div className="route-agents">
              <div className="route-agent">
                <span className="route-avatar">{initials(agentA?.display_name)}</span>
                <strong>{agentA?.display_name?.split(" — ")[0] ?? "Tu agente"}</strong>
                <small>Te representa</small>
              </div>
              <span className="route-connection" aria-hidden="true" />
              <div className="route-agent">
                <span className="route-avatar">{initials(agentB?.display_name)}</span>
                <strong>{agentB?.display_name?.split(" — ")[0] ?? "Contraparte"}</strong>
                <small>{featured?.segment ?? "P2P"} · compatible</small>
              </div>
            </div>

            <div className="route-steps">
              <div className="route-step">
                <span className="route-step-icon"><SearchIcon size={13} /></span>
                <span>Encontró una oportunidad compatible</span>
                <time>10:05</time>
              </div>
              <div className="route-step">
                <span className="route-step-icon"><CheckIcon size={13} /></span>
                <span>Negoció {featured?.messages.length ?? 0} mensajes por ti</span>
                <time>10:17</time>
              </div>
              <div className="route-step is-current">
                <span className="route-step-icon"><InboxIcon size={13} /></span>
                <span>Detectó una decisión sensible</span>
                <time>Ahora</time>
              </div>
            </div>

            <div className="decision-snapshot">
              <span className="decision-snapshot-label">
                <ShieldIcon size={13} /> Requiere tu aprobación
              </span>
              <p>
                {featured?.pending_decision?.summary ??
                  "Tu agente esperará antes de compartir información sensible."}
              </p>
            </div>
          </div>
        </div>
      </section>

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
                    <span>{session.messages.length} mensajes · turno {session.current_turn} de {session.max_turns}</span>
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
