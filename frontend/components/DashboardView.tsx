"use client";

import Link from "next/link";
import { AgentStatusCard } from "@/components/AgentStatusCard";
import { CommercialHome } from "@/components/CommercialHome";
import { ArrowRightIcon, ShieldIcon } from "@/components/Icons";
import { useAuth } from "@/lib/auth";
import { belongsToAgent, DEMO_OWNER_AGENT_ID } from "@/lib/demo";
import { useAgentSync } from "@/lib/store";
import type { MatchSession } from "@/lib/types";

const statusCopy: Record<
  MatchSession["status"],
  { label: string; className: string; detail: string }
> = {
  SEARCHING: {
    label: "Explorando",
    className: "",
    detail: "Buscando una opción compatible",
  },
  ACTIVE: {
    label: "Negociando",
    className: "is-active",
    detail: "Conversación en curso",
  },
  PENDING_HUMAN_APPROVAL: {
    label: "Necesita tu decisión",
    className: "is-pending",
    detail: "Espera tu respuesta para continuar",
  },
  RESOLVED: {
    label: "Match confirmado",
    className: "is-resolved",
    detail: "Acuerdo confirmado por ambas partes",
  },
  REJECTED: {
    label: "Descartada",
    className: "is-rejected",
    detail: "Cerrada sin cambiar tus límites",
  },
  FAILED: {
    label: "Requiere revisión",
    className: "is-rejected",
    detail: "Se detuvo por un problema técnico",
  },
  WITHDRAWN: {
    label: "Retirada",
    className: "is-rejected",
    detail: "La otra parte retiró su propuesta",
  },
  EXPIRED: {
    label: "Expirada",
    className: "",
    detail: "La propuesta dejó de estar vigente",
  },
};

function counterpartId(session: MatchSession, ownerAgentId: string) {
  return session.agent_1_id === ownerAgentId
    ? session.agent_2_id
    : session.agent_1_id;
}

function decisionTitle(session: MatchSession, counterpartName: string) {
  const category = (
    session.pending_decision?.category ??
    session.pending_decision?.kind ??
    ""
  ).toLocaleLowerCase("es");

  if (category?.includes("precio")) {
    return `Confirmar precio final con ${counterpartName}`;
  }

  if (category?.includes("dirección") || category?.includes("teléfono")) {
    return `Autorizar datos para coordinar con ${counterpartName}`;
  }

  return `Revisar propuesta de ${counterpartName}`;
}

export function DashboardView() {
  const { signedIn, agentId } = useAuth();
  const { sessions, agentsById } = useAgentSync();
  const ownerAgentId = agentId ?? DEMO_OWNER_AGENT_ID;
  const ownerSessions = sessions.filter((session) =>
    belongsToAgent(session, ownerAgentId),
  );
  const pending = ownerSessions.filter(
    (session) =>
      session.status === "PENDING_HUMAN_APPROVAL" && session.pending_decision,
  );
  const activeSessions = ownerSessions.filter(
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
  const ownerAgent = agentsById[ownerAgentId];
  if (!signedIn) {
    return (
      <CommercialHome
        objective={agentA?.objectives[0]}
        counterpartName={agentB?.display_name?.split(" — ")[0]}
      />
    );
  }

  if (!agentId || !ownerAgent) {
    return (
      <div className="empty-agent-home">
        <section>
          <span className="section-eyebrow">Tu espacio está listo</span>
          <h1>Activa un agente para empezar</h1>
          <p>
            Define varios objetivos, fija lo que nunca debe cruzar y elige cuándo
            quieres intervenir.
          </p>
          <Link href="/setup" className="primary-action">
            Configurar mi agente <ArrowRightIcon size={15} />
          </Link>
        </section>
        <aside aria-label="Qué ocurrirá después">
          <span><strong>1</strong> Añade tus objetivos</span>
          <span><strong>2</strong> Marca límites y decisiones</span>
          <span><strong>3</strong> El agente empieza a explorar</span>
        </aside>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-columns">
        <section className="dashboard-panel" aria-labelledby="attention-title">
          <div className="panel-heading">
            <div>
              <h2 id="attention-title">Necesita tu decisión</h2>
              <p>
                {pending.length === 1
                  ? "Responde para que esta negociación pueda continuar."
                  : "Responde para que estas negociaciones puedan continuar."}
              </p>
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
                      <strong>
                        {decisionTitle(
                          session,
                          agentsById[counterpartId(session, ownerAgentId)]?.display_name.split(" — ")[0] ??
                            "la otra parte",
                        )}
                      </strong>
                      <span>{session.pending_decision?.proposal}</span>
                    </span>
                    <span className="attention-cta">
                      Revisar <ArrowRightIcon size={13} />
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
          agentId={ownerAgentId}
          agentName={ownerAgent?.display_name ?? "Valentina R."}
          objective={
            ownerAgent.objectives.length > 1
              ? `${ownerAgent.objectives[0]} · +${ownerAgent.objectives.length - 1} más`
              : ownerAgent.objectives[0] ?? "Objetivo por configurar"
          }
          pendingCount={pending.length}
          activeNegotiations={activeSessions.length}
        />
      </div>

      <section className="activity-panel" aria-labelledby="activity-title">
        <div className="activity-heading">
          <div>
            <h2 id="activity-title">Actividad de tu agente</h2>
            <p>Sigue sus conversaciones y los resultados más recientes.</p>
          </div>
          <Link href="/ecosistema" className="text-action">
            Explorar oportunidades <ArrowRightIcon size={14} />
          </Link>
        </div>

        <ul className="activity-list">
          {ownerSessions.map((session) => {
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
                      {session.messages.length} mensajes · {status.detail}
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
