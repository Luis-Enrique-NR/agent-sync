"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CommercialHome } from "@/components/CommercialHome";
import {
  ArrowRightIcon,
  CheckIcon,
  SearchIcon,
  ShieldIcon,
  SparkIcon,
} from "@/components/Icons";
import { useAuth } from "@/lib/auth";
import { belongsToAgent } from "@/lib/store";
import { useAgentSync } from "@/lib/store";
import type { AgentObjectiveContext, MatchSession } from "@/lib/types";

const statusCopy: Record<
  MatchSession["status"],
  { label: string; detail: string; className: string }
> = {
  SEARCHING: {
    label: "Buscando opciones",
    detail: "Comprobando objetivos, límites y alcance",
    className: "is-searching",
  },
  ACTIVE: {
    label: "Conversando",
    detail: "Los agentes están afinando los términos",
    className: "is-active",
  },
  PENDING_HUMAN_APPROVAL: {
    label: "Tu decisión",
    detail: "La negociación espera tu respuesta",
    className: "is-pending",
  },
  RESOLVED: {
    label: "Trato cerrado",
    detail: "El acuerdo está listo para revisar el objetivo",
    className: "is-resolved",
  },
  REJECTED: {
    label: "Conversación cerrada",
    detail: "La propuesta no cumplió tus condiciones",
    className: "is-closed",
  },
  FAILED: {
    label: "Conversación detenida",
    detail: "Un problema técnico impidió continuar",
    className: "is-closed",
  },
  WITHDRAWN: {
    label: "Oferta retirada",
    detail: "La otra parte retiró su propuesta",
    className: "is-closed",
  },
  EXPIRED: {
    label: "Oferta vencida",
    detail: "Los términos dejaron de estar vigentes",
    className: "is-closed",
  },
};

const sessionPriority: Record<MatchSession["status"], number> = {
  PENDING_HUMAN_APPROVAL: 1,
  ACTIVE: 2,
  SEARCHING: 3,
  RESOLVED: 4,
  REJECTED: 5,
  WITHDRAWN: 6,
  EXPIRED: 7,
  FAILED: 8,
};

function priorityOf(session: MatchSession) {
  if (
    session.status === "RESOLVED" &&
    session.goal_progress_review?.status === "PENDING"
  ) {
    return 0;
  }
  return sessionPriority[session.status];
}

function counterpartId(session: MatchSession, ownerAgentId: string) {
  return session.agent_1_id === ownerAgentId
    ? session.agent_2_id
    : session.agent_1_id;
}

function objectiveIdFor(session: MatchSession, ownerAgentId: string) {
  return session.agent_1_id === ownerAgentId
    ? session.agent_1_objective_id
    : session.agent_2_objective_id;
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

function conversationTerms(session: MatchSession) {
  return (
    session.pending_decision?.summary ??
    session.outcome?.summary ??
    session.summary
  );
}

export function DashboardView() {
  const { signedIn, agentId } = useAuth();
  const { sessions, agentsById } = useAgentSync();
  const [selectedByObjective, setSelectedByObjective] = useState<
    Record<string, string>
  >({});
  const [openSwitcher, setOpenSwitcher] = useState<string | null>(null);
  const [goalReviewChoice, setGoalReviewChoice] = useState<
    Record<string, "continue" | "complete">
  >({});
  const [goalContext, setGoalContext] = useState<Record<string, string>>({});
  const ownerAgentId = agentId;
  const ownerSessions = sessions.filter((session) =>
    belongsToAgent(session, ownerAgentId),
  );
  const featured =
    ownerSessions.find((session) => session.segment === "P2P") ??
    sessions.find((session) => session.segment === "P2P") ??
    ownerSessions[0] ??
    sessions[0];
  const agentA = agentsById[featured?.agent_1_id ?? ""];
  const agentB = agentsById[featured?.agent_2_id ?? ""];
  const ownerAgent = agentId ? agentsById[agentId] : undefined;

  useEffect(() => {
    if (!openSwitcher) return;

    const closeOutside = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const switcher = target.closest<HTMLElement>("[data-route-switcher]");
      if (switcher?.dataset.routeSwitcher === openSwitcher) return;
      setOpenSwitcher(null);
    };

    document.addEventListener("pointerdown", closeOutside);
    return () => document.removeEventListener("pointerdown", closeOutside);
  }, [openSwitcher]);

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
  const paused = ownerAgent.status === "PAUSED";
  const objectiveContexts: AgentObjectiveContext[] = ownerAgent.objective_contexts ?? [];
  const objectives = (
    objectiveContexts.length > 0
      ? objectiveContexts.map((objective: AgentObjectiveContext) => ({
          id: objective.objective_id,
          goal: objective.goal,
        }))
      : ownerAgent.objectives.map((goal: string, index: number) => ({
          id: `objective-${index + 1}`,
          goal,
        }))
  ).slice(0, 3);
  const sortedSessions = [...ownerSessions].sort((left, right) => {
    const priority = priorityOf(left) - priorityOf(right);
    if (priority !== 0) return priority;
    return Date.parse(right.started_at) - Date.parse(left.started_at);
  });
  const lanes = objectives.map((objective: { id: string; goal: string }, index: number) => {
    const matchingSessions = sortedSessions.filter((session) => {
      const linkedObjectiveId = objectiveIdFor(session, agentId);
      return linkedObjectiveId
        ? linkedObjectiveId === objective.id
        : index === 0;
    });
    const selectedSession =
      matchingSessions.find(
        (session) => session.session_id === selectedByObjective[objective.id],
      ) ?? matchingSessions[0];
    return { objective, sessions: matchingSessions, selectedSession };
  });

  return (
    <div className={`live-dashboard ${paused ? "is-paused" : ""}`}>
      <header className="live-dashboard-heading">
        <h1>Tu agente está trabajando ahora</h1>
      </header>

      <section className="live-control-room" aria-labelledby="live-routes-title">
        <header>
          <div>
            <span className="section-eyebrow">Rutas independientes</span>
            <h2 id="live-routes-title">Un objetivo, varias negociaciones</h2>
            <p>Cambiar de conversación no detiene las demás.</p>
          </div>
          <div className="live-summary" aria-label="Resumen de trabajo">
            <span><strong>{ownerAgent.objectives.length}</strong><small>objetivos</small></span>
            <span><strong>{activeSessions.length}</strong><small>activas</small></span>
            <span><strong>{ownerSessions.length}</strong><small>conversaciones</small></span>
          </div>
        </header>

        <div className="live-lanes">
          {lanes.map(({ objective, sessions: laneSessions, selectedSession }, index) => {
            const status = selectedSession
              ? statusCopy[selectedSession.status]
              : statusCopy.SEARCHING;
            const counterpart = selectedSession
              ? agentsById[counterpartId(selectedSession, agentId)]
              : undefined;
            const counterpartName = counterpart?.display_name.split(" — ")[0] ?? "Otra parte";
            const decisionHref = selectedSession?.pending_decision
              ? `/bandeja#decision-card-${selectedSession.pending_decision.decision_id}`
              : "/bandeja";
            const switcherOpen = openSwitcher === objective.id;
            const reviewChoice = selectedSession
              ? goalReviewChoice[selectedSession.session_id]
              : undefined;
            const decisionTurn = selectedSession?.decision_turn ??
              (selectedSession?.status === "PENDING_HUMAN_APPROVAL"
                ? "OWNER"
                : undefined);

            return (
              <article
                key={objective.id}
                className={`live-lane ${status.className} ${switcherOpen ? "has-open-route" : ""}`}
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

                {selectedSession ? (
                  <div
                    className={`live-route-picker ${switcherOpen ? "is-open" : ""} ${laneSessions.length === 1 ? "is-single" : ""}`}
                    data-route-switcher={objective.id}
                    onKeyDown={(event) => {
                      if (event.key === "Escape") setOpenSwitcher(null);
                    }}
                  >
                    <button
                      type="button"
                      className="live-route-trigger"
                      aria-haspopup={laneSessions.length > 1 ? "listbox" : undefined}
                      aria-expanded={laneSessions.length > 1 && switcherOpen}
                      aria-controls={laneSessions.length > 1 ? `route-options-${objective.id}` : undefined}
                      onClick={() => {
                        if (laneSessions.length <= 1) return;
                        setOpenSwitcher((current) =>
                          current === objective.id ? null : objective.id,
                        );
                      }}
                    >
                      <span className="live-route-avatar">{initials(counterpartName)}</span>
                      <span className="live-route-copy">
                        <small>Negociación con</small>
                        <strong>{counterpartName}</strong>
                        <p>{conversationTerms(selectedSession)}</p>
                      </span>
                      <span className="live-route-count">
                        <b>{laneSessions.length}</b>
                        <small>{laneSessions.length === 1 ? "opción" : "opciones"}</small>
                        <i aria-hidden="true" />
                      </span>
                    </button>

                    {switcherOpen ? (
                      <div
                        id={`route-options-${objective.id}`}
                        className="live-route-options"
                        role="listbox"
                        aria-label={`Negociaciones de ${objective.goal}`}
                      >
                        <span className="live-route-options-title">
                          Elige una negociación
                          <small>Cada una avanza por separado</small>
                        </span>
                        {laneSessions.map((session: MatchSession) => {
                          const optionCounterpart =
                            agentsById[counterpartId(session, agentId)];
                          const optionName =
                            optionCounterpart?.display_name.split(" — ")[0] ?? "Otra parte";
                          const optionStatus = statusCopy[session.status];
                          const selected = session.session_id === selectedSession.session_id;
                          return (
                            <button
                              key={session.session_id}
                              type="button"
                              role="option"
                              aria-selected={selected}
                              className={selected ? "is-selected" : ""}
                              onClick={() => {
                                setSelectedByObjective((current) => ({
                                  ...current,
                                  [objective.id]: session.session_id,
                                }));
                                setOpenSwitcher(null);
                              }}
                            >
                              <span>{initials(optionName)}</span>
                              <span>
                                <strong>{optionName}</strong>
                                <small>{conversationTerms(session)}</small>
                              </span>
                              <i className={optionStatus.className}>{optionStatus.label}</i>
                              {selected ? <CheckIcon size={12} /> : null}
                            </button>
                          );
                        })}
                      </div>
                    ) : null}
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

                {decisionTurn ? (
                  <section className="live-decision-handoff" aria-label="Turno de respuesta">
                    <header>
                      <small>Turno de respuesta</small>
                      <strong>
                        {decisionTurn === "OWNER"
                          ? "Te toca responder"
                          : "Esperamos a la otra parte"}
                      </strong>
                    </header>
                    <div>
                      <span className={decisionTurn === "OWNER" ? "is-current" : ""}>
                        <i />
                        <small>Tu decisión</small>
                      </span>
                      <b aria-hidden="true" />
                      <span className={decisionTurn === "COUNTERPART" ? "is-current" : ""}>
                        <i />
                        <small>Respuesta de la otra parte</small>
                      </span>
                    </div>
                  </section>
                ) : null}

                {selectedSession?.status === "RESOLVED" ? (
                  <section className={`goal-progress-review ${reviewChoice ? "is-confirmed" : ""}`}>
                    {reviewChoice ? (
                      <div className="goal-review-confirmation" role="status">
                        <span><CheckIcon size={13} /></span>
                        <div>
                          <strong>
                            {reviewChoice === "continue"
                              ? "El objetivo sigue activo"
                              : "Objetivo marcado como cumplido"}
                          </strong>
                          <p>
                            {reviewChoice === "continue"
                              ? goalContext[selectedSession.session_id] || "Tu agente seguirá buscando nuevas opciones."
                              : "Las demás negociaciones pueden cerrarse o revisarse por separado."}
                          </p>
                        </div>
                      </div>
                    ) : (
                      <>
                        <header>
                          <span><CheckIcon size={13} /></span>
                          <div>
                            <small>Trato confirmado</small>
                            <strong>¿Este acuerdo completa el objetivo?</strong>
                          </div>
                        </header>
                        <p>
                          {selectedSession.goal_progress_review?.proposed_delta ??
                            selectedSession.outcome?.summary ??
                            "La negociación terminó con un acuerdo."}
                        </p>
                        <label>
                          <span>Contexto nuevo para el objetivo <small>Opcional</small></span>
                          <textarea
                            rows={2}
                            value={goalContext[selectedSession.session_id] ?? ""}
                            onChange={(event) =>
                              setGoalContext((current) => ({
                                ...current,
                                [selectedSession.session_id]: event.target.value,
                              }))
                            }
                            placeholder="Ej.: Quedan 10 litros por vender; prioriza entregas locales."
                          />
                        </label>
                        <div className="goal-review-actions">
                          <button
                            type="button"
                            className="is-primary"
                            onClick={() =>
                              setGoalReviewChoice((current) => ({
                                ...current,
                                [selectedSession.session_id]: "continue",
                              }))
                            }
                          >
                            Continuar con el objetivo
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              setGoalReviewChoice((current) => ({
                                ...current,
                                [selectedSession.session_id]: "complete",
                              }))
                            }
                          >
                            Marcar cumplido
                          </button>
                        </div>
                      </>
                    )}
                  </section>
                ) : null}

                <footer>
                  <span><SparkIcon size={13} /> Se actualiza sin recargar</span>
                  {selectedSession?.status === "PENDING_HUMAN_APPROVAL" ? (
                    <Link href={decisionHref} className="live-decision-link">
                      Abrir en Decisiones <ArrowRightIcon size={13} />
                    </Link>
                  ) : selectedSession ? (
                    <Link href={`/chat/${selectedSession.session_id}`}>
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
          <small>Una negociación puede cerrar sin cerrar automáticamente su objetivo.</small>
        </span>
        <Link href="/setup">Revisar límites <ArrowRightIcon size={13} /></Link>
      </section>
    </div>
  );
}
