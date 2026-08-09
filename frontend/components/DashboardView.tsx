"use client";

import Link from "next/link";
import { CommercialHome } from "@/components/CommercialHome";
import {
  ArrowRightIcon,
  CheckIcon,
  PauseIcon,
  PlayIcon,
  SearchIcon,
  ShieldIcon,
  SparkIcon,
} from "@/components/Icons";
import { useAuth } from "@/lib/auth";
import { belongsToAgent, DEMO_OWNER_AGENT_ID } from "@/lib/demo";
import { useAgentSync } from "@/lib/store";
import type { MatchSession } from "@/lib/types";

const statusCopy: Record<
  MatchSession["status"],
  {
    label: string;
    detail: string;
    className: string;
    step: number;
    finalStep: string;
  }
> = {
  SEARCHING: {
    label: "Evaluando",
    detail: "Comprobando objetivos, límites y alcance",
    className: "is-searching",
    step: 0,
    finalStep: "Siguiente paso",
  },
  ACTIVE: {
    label: "Conversando",
    detail: "Los agentes están negociando condiciones",
    className: "is-active",
    step: 2,
    finalStep: "Siguiente paso",
  },
  PENDING_HUMAN_APPROVAL: {
    label: "Espera tu decisión",
    detail: "La conversación está pausada sin frenar las demás",
    className: "is-pending",
    step: 3,
    finalStep: "Tu decisión",
  },
  RESOLVED: {
    label: "Acuerdo confirmado",
    detail: "Ambas partes confirmaron los términos",
    className: "is-resolved",
    step: 3,
    finalStep: "Acuerdo",
  },
  REJECTED: {
    label: "Descartada",
    detail: "Se cerró sin cambiar tus límites",
    className: "is-closed",
    step: 3,
    finalStep: "Descartada",
  },
  FAILED: {
    label: "Detenida con seguridad",
    detail: "Un problema técnico impidió continuar",
    className: "is-closed",
    step: 3,
    finalStep: "Detenida",
  },
  WITHDRAWN: {
    label: "Oferta retirada",
    detail: "La otra parte retiró su propuesta",
    className: "is-closed",
    step: 3,
    finalStep: "Retirada",
  },
  EXPIRED: {
    label: "Propuesta vencida",
    detail: "Dejó de estar vigente antes de confirmarse",
    className: "is-closed",
    step: 3,
    finalStep: "Vencida",
  },
};

const sessionPriority: Record<MatchSession["status"], number> = {
  PENDING_HUMAN_APPROVAL: 0,
  ACTIVE: 1,
  SEARCHING: 2,
  RESOLVED: 3,
  REJECTED: 4,
  WITHDRAWN: 5,
  EXPIRED: 6,
  FAILED: 7,
};

function counterpartId(session: MatchSession, ownerAgentId: string) {
  return session.agent_1_id === ownerAgentId
    ? session.agent_2_id
    : session.agent_1_id;
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

export function DashboardView() {
  const { signedIn, agentId } = useAuth();
  const { sessions, agentsById, toggleAgentStatus } = useAgentSync();
  const ownerAgentId = agentId ?? DEMO_OWNER_AGENT_ID;
  const ownerSessions = sessions.filter((session) =>
    belongsToAgent(session, ownerAgentId),
  );
  const featured =
    ownerSessions.find((session) => session.segment === "P2P") ??
    sessions.find((session) => session.segment === "P2P") ??
    ownerSessions[0] ??
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
          <span><strong>3</strong> El agente empieza a trabajar</span>
        </aside>
      </div>
    );
  }

  const activeSessions = ownerSessions.filter((session) =>
    ["SEARCHING", "ACTIVE", "PENDING_HUMAN_APPROVAL"].includes(session.status),
  );
  const discardedSessions = ownerSessions.filter((session) =>
    ["REJECTED", "FAILED", "WITHDRAWN", "EXPIRED"].includes(session.status),
  );
  const paused = ownerAgent.status === "PAUSED";
  const displayName = ownerAgent.display_name.split(" — ")[0];
  const objectives = (
    ownerAgent.objective_contexts?.map((objective) => ({
      id: objective.objective_id,
      goal: objective.goal,
    })) ??
    ownerAgent.objectives.map((goal, index) => ({
      id: `objective-${index + 1}`,
      goal,
    }))
  ).slice(0, 3);
  const sortedSessions = [...ownerSessions].sort((left, right) => {
    const priority = sessionPriority[left.status] - sessionPriority[right.status];
    if (priority !== 0) return priority;
    return Date.parse(right.started_at) - Date.parse(left.started_at);
  });
  const lanes = objectives.map((objective, index) => {
    const assigned = sortedSessions.filter(
      (_, sessionIndex) => sessionIndex % objectives.length === index,
    );
    return { objective, session: assigned[0], additionalCount: Math.max(0, assigned.length - 1) };
  });

  return (
    <div className={`live-dashboard ${paused ? "is-paused" : ""}`}>
      <header className="live-dashboard-heading">
        <div>
          <span className="live-eyebrow"><i /> Actividad en vivo</span>
          <h1>Tu agente está trabajando ahora</h1>
          <p>
            Observa cómo cada objetivo encuentra rutas, descarta lo inviable y
            conversa sin pedirte que vigiles el proceso.
          </p>
        </div>
        <aside className="live-agent-control" aria-label="Estado de tu agente">
          <span className={`live-agent-avatar ${paused ? "is-paused" : ""}`}>
            {initials(displayName)}
          </span>
          <span>
            <small>Mi agente</small>
            <strong>{displayName}</strong>
            <i>{paused ? "En pausa" : activeSessions.length > 0 ? "Trabajando en paralelo" : "Atento a nuevas oportunidades"}</i>
          </span>
          <button type="button" onClick={() => toggleAgentStatus(ownerAgentId)}>
            {paused ? <PlayIcon size={14} /> : <PauseIcon size={14} />}
            {paused ? "Reactivar" : "Pausar"}
          </button>
        </aside>
      </header>

      <section className="live-control-room" aria-labelledby="live-routes-title">
        <header>
          <div>
            <span className="section-eyebrow">Rutas independientes</span>
            <h2 id="live-routes-title">Un objetivo no detiene a los demás</h2>
            <p>Portal mantiene cada ruta atenta a cambios, ofertas y retiros.</p>
          </div>
          <div className="live-summary" aria-label="Resumen de trabajo">
            <span><strong>{ownerAgent.objectives.length}</strong><small>objetivos</small></span>
            <span><strong>{activeSessions.length}</strong><small>conversaciones</small></span>
            <span><strong>{discardedSessions.length}</strong><small>descartes resueltos</small></span>
          </div>
        </header>

        <div className="live-lanes">
          {lanes.map(({ objective, session, additionalCount }, index) => {
            const status = session ? statusCopy[session.status] : statusCopy.SEARCHING;
            const counterpart = session
              ? agentsById[counterpartId(session, ownerAgentId)]
              : undefined;
            const checkpointLabels = [
              "Detectada",
              "Validada",
              "Conversación",
              status.finalStep,
            ];
            const decisionHref = session?.pending_decision
              ? `/bandeja#decision-card-${session.pending_decision.decision_id}`
              : "/bandeja";

            return (
              <article
                key={objective.id}
                className={`live-lane ${status.className}`}
                style={{ animationDelay: `${index * 110}ms` }}
              >
                <header>
                  <span className="live-lane-number">{String(index + 1).padStart(2, "0")}</span>
                  <span className={`live-lane-status ${status.className}`}><i /> {status.label}</span>
                </header>

                <div className="live-lane-goal">
                  <small>Objetivo</small>
                  <h3>{objective.goal}</h3>
                </div>

                {session ? (
                  <div className="live-counterpart">
                    <span>{initials(counterpart?.display_name ?? "Agente")}</span>
                    <div>
                      <small>Ruta con</small>
                      <strong>{counterpart?.display_name.split(" — ")[0] ?? "Otra parte"}</strong>
                      <p>{status.detail}</p>
                    </div>
                  </div>
                ) : (
                  <div className="live-counterpart is-scanning">
                    <span><SearchIcon size={16} /></span>
                    <div>
                      <small>Exploración continua</small>
                      <strong>Buscando una ruta compatible</strong>
                      <p>Las incompatibilidades se descartan sin interrumpirte.</p>
                    </div>
                  </div>
                )}

                <ol className="live-checkpoints" aria-label={`Progreso de ${objective.goal}`}>
                  {checkpointLabels.map((label, checkpointIndex) => {
                    const state = checkpointIndex < status.step
                      ? "is-complete"
                      : checkpointIndex === status.step
                        ? "is-current"
                        : "";
                    return (
                      <li key={`${label}-${checkpointIndex}`} className={state}>
                        <span>{checkpointIndex < status.step ? <CheckIcon size={10} /> : null}</span>
                        <small>{label}</small>
                      </li>
                    );
                  })}
                </ol>

                <footer>
                  {additionalCount > 0 ? (
                    <span>+{additionalCount} conversación{additionalCount === 1 ? "" : "es"} en esta ruta</span>
                  ) : (
                    <span><SparkIcon size={13} /> Se actualiza sin recargar</span>
                  )}
                  {session?.status === "PENDING_HUMAN_APPROVAL" ? (
                    <Link href={decisionHref} className="live-decision-link">
                      Abrir en Decisiones <ArrowRightIcon size={13} />
                    </Link>
                  ) : session ? (
                    <Link href={`/chat/${session.session_id}`}>
                      Ver conversación <ArrowRightIcon size={13} />
                    </Link>
                  ) : null}
                </footer>
              </article>
            );
          })}
        </div>
      </section>

      <section className="live-safety-note" aria-label="Límites del trabajo autónomo">
        <ShieldIcon size={19} />
        <span>
          <strong>Autonomía dentro de tus reglas</strong>
          <small>Inicio muestra el proceso. El contenido sensible y tus acciones existen únicamente en Decisiones.</small>
        </span>
        <Link href="/setup">Revisar límites <ArrowRightIcon size={13} /></Link>
      </section>
    </div>
  );
}
