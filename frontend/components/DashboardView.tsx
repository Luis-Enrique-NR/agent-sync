"use client";

import Link from "next/link";
import type { MatchSession } from "@/lib/types";
import { useAgentSync } from "@/lib/store";
import { AgentStatusCard } from "@/components/AgentStatusCard";
import {
  ArrowRightIcon,
  InboxIcon,
  RotateIcon,
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
  const featured =
    pending.find((session) => session.segment === "P2P") ??
    sessions.find((session) => session.segment === "P2P") ??
    pending[0] ??
    sessions[0];
  const agentA = agentsById[featured?.agent_1_id];
  const agentB = agentsById[featured?.agent_2_id];
  const p2pSessions = sessions.filter((session) => session.segment === "P2P");
  const primaryHref = pending[0] ? `/chat/${pending[0].session_id}` : "/setup";

  return (
    <div className="dashboard">
      <section className="hero-panel" aria-labelledby="dashboard-title">
        <div className="hero-copy">
          <span className="hero-eyebrow">
            <SparkIcon size={15} /> Un objetivo, varias oportunidades
          </span>
          <h1 id="dashboard-title">
            Tu agente mueve las conversaciones. <span>Tú decides lo importante.</span>
          </h1>
          <p className="hero-description">
            Define qué quieres conseguir, tus límites y qué necesita permiso.
            AgentSync encuentra contrapartes y negocia cada oportunidad por
            separado, incluso mientras otra espera tu respuesta.
          </p>
          <div className="hero-actions">
            <Link
              href={primaryHref}
              className={`primary-action ${pending.length > 0 ? "has-attention" : ""}`}
            >
              {pending.length > 0 ? `Revisar ${pending.length} decisiones` : "Definir mi objetivo"}
              <ArrowRightIcon size={16} />
            </Link>
            <Link href="/ecosistema" className="secondary-action">
              Ver oportunidades activas
            </Link>
          </div>
          <div className="hero-trust">
            <span className="portal-presence" aria-hidden="true"><i /></span>
            <span className="hero-trust-copy">
              <strong>Atento 24/7 con Portal</strong>
              <span>Recibe oportunidades, retiros y cambios aunque no estés conectado.</span>
            </span>
          </div>
        </div>

        <div className="hero-visual" aria-label="Un objetivo con varias negociaciones independientes">
          <div className="objective-card">
            <div className="objective-card-header">
              <span className="objective-live"><i /> Objetivo activo</span>
              <span>{p2pSessions.length} oportunidades evaluadas</span>
            </div>

            <div className="objective-goal">
              <span>Lo que quieres conseguir</span>
              <strong>
                {agentA?.objectives[0] ?? "Vender mi auto sin bajar de USD 8.000"}
              </strong>
              <small><ShieldIcon size={13} /> El precio mínimo queda protegido</small>
            </div>

            <div className="objective-branch-label">
              <span>Tu agente abre rutas independientes</span>
              <i aria-hidden="true" />
            </div>

            <div className="objective-routes">
              <div className="objective-route is-pending">
                <span className="objective-route-icon"><InboxIcon size={14} /></span>
                <span className="objective-route-copy">
                  <strong>{agentB?.display_name?.split(" — ")[0] ?? "Comprador compatible"}</strong>
                  <small>Quiere coordinar una prueba de manejo</small>
                </span>
                <span className="objective-route-status">Tu decisión</span>
              </div>

              <div className="objective-route is-closed">
                <span className="objective-route-icon"><ShieldIcon size={14} /></span>
                <span className="objective-route-copy">
                  <strong>Oferta bajo el mínimo</strong>
                  <small>Se descartó sin consultarte</small>
                </span>
                <span className="objective-route-status">Protegido</span>
              </div>

              <div className="objective-route is-searching">
                <span className="objective-route-icon"><SearchIcon size={14} /></span>
                <span className="objective-route-copy">
                  <strong>Nuevas contrapartes</strong>
                  <small>La búsqueda continúa en paralelo</small>
                </span>
                <span className="objective-route-status">Explorando</span>
              </div>
            </div>

            <div className="objective-checkpoint">
              <RotateIcon size={15} />
              <p><strong>Antes de cerrar:</strong> comprueba vigencia y te pregunta si el objetivo terminó o debe seguir.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="product-flow" aria-labelledby="product-flow-title">
        <div className="product-flow-heading">
          <span className="section-eyebrow">Así trabaja AgentSync</span>
          <h2 id="product-flow-title">Tú marcas el rumbo. El agente sostiene el proceso.</h2>
        </div>

        <ol className="product-flow-steps">
          <li>
            <span className="product-flow-number">01</span>
            <span className="product-flow-owner is-user">Tú</span>
            <strong>Define el objetivo</strong>
            <p>Indica qué buscas, qué nunca debe ceder y cuándo debe consultarte.</p>
          </li>
          <li>
            <span className="product-flow-number">02</span>
            <span className="product-flow-owner is-agent">Tu agente</span>
            <strong>Encuentra compatibilidad</strong>
            <p>Publica tu intención y filtra personas o empresas con intereses compatibles.</p>
          </li>
          <li>
            <span className="product-flow-number">03</span>
            <span className="product-flow-owner is-agent">Tu agente</span>
            <strong>Negocia en paralelo</strong>
            <p>Cada oportunidad avanza por separado; una retirada no frena las demás.</p>
          </li>
          <li>
            <span className="product-flow-number">04</span>
            <span className="product-flow-owner is-user">Tú</span>
            <strong>Resuelve lo sensible</strong>
            <p>Aprueba o cambia el precio final, los datos y los compromisos.</p>
          </li>
          <li>
            <span className="product-flow-number">05</span>
            <span className="product-flow-owner is-shared">Tu agente + tú</span>
            <strong>Revalida y continúa</strong>
            <p>Confirma que todo siga vigente y te pregunta si debe cerrar o seguir buscando.</p>
          </li>
        </ol>
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
                      <strong>{session.pending_decision?.category}</strong>
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
