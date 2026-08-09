"use client";

import Link from "next/link";
import { useMemo, useState, type CSSProperties } from "react";
import {
  ArrowRightIcon,
  CheckIcon,
  CompassIcon,
  ShieldIcon,
  SparkIcon,
} from "@/components/Icons";
import {
  DISCOVERY_PROFILES,
  SCREENED_DISCOVERY_PROFILES,
  type DiscoveryProfileMock,
} from "@/data/discoveryMock";
import { useAuth } from "@/lib/auth";
import { useAgentSync } from "@/lib/store";
import type { AgentProfile, MatchSession, Segment } from "@/lib/types";
import { segmentOf } from "@/lib/types";

type Filter = "todos" | Segment;
type ExclusionReason = "goal" | "limits" | "reach" | "unavailable";

const ACTIVE_SESSION_STATUSES = new Set([
  "ACTIVE",
  "SEARCHING",
  "PENDING_HUMAN_APPROVAL",
]);

const STATUS_BADGES: Record<
  AgentProfile["status"],
  { label: string; className: string }
> = {
  AVAILABLE: { label: "Disponible", className: "is-available" },
  BUSY: { label: "En conversación", className: "is-busy" },
  PAUSED: { label: "En pausa", className: "is-paused" },
};

function normalize(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function profileFallback(agent: AgentProfile): DiscoveryProfileMock {
  const corpus = normalize(
    [
      agent.public_description,
      ...agent.objectives,
      ...agent.interests,
      ...agent.capabilities,
    ].join(" "),
  );
  const topic = /auto|vehiculo|hyundai/.test(corpus)
    ? { key: "auto-usado", label: "compraventa de auto usado" }
    : /tela|textil|algodon|gots/.test(corpus)
      ? { key: "textil-organico", label: "suministro textil orgánico" }
      : {
          key: `segmento-${segmentOf(agent.entity_type).toLowerCase()}`,
          label: "objetivos del mismo segmento",
        };
  const role = /comprar|busca|encontrar|necesita|cliente/.test(corpus)
    ? "demand"
    : /vender|ofrece|proveedor|suministro/.test(corpus)
      ? "supply"
      : "either";
  const seed = [...agent.agent_id].reduce(
    (total, character) => total + character.charCodeAt(0),
    0,
  );

  return {
    agentId: agent.agent_id,
    publicArea: "Área general configurada",
    areaKey: "lima-metropolitana",
    reachKeys: ["lima-metropolitana"],
    topicKeys: [topic.key],
    topicLabel: topic.label,
    role,
    scopeLabel: agent.logistics_preferences?.[0] ?? "Alcance por confirmar",
    viabilityLabel: "Comparte un área operable con tu agente",
    mapX: 28 + (seed % 44),
    mapY: 27 + ((seed * 7) % 38),
    fitScore: 80 + (seed % 12),
  };
}

function discoveryProfile(agent: AgentProfile) {
  return DISCOVERY_PROFILES[agent.agent_id] ?? profileFallback(agent);
}

function sessionsBetween(
  ownerId: string,
  candidateId: string,
  sessions: MatchSession[],
) {
  return sessions.filter(
    (session) =>
      ACTIVE_SESSION_STATUSES.has(session.status) &&
      ((session.agent_1_id === ownerId && session.agent_2_id === candidateId) ||
        (session.agent_1_id === candidateId && session.agent_2_id === ownerId)),
  );
}

function intersects(left: string[], right: string[]) {
  const rightSet = new Set(right);
  return left.some((item) => rightSet.has(item));
}

function goalsConnect(
  owner: DiscoveryProfileMock,
  candidate: DiscoveryProfileMock,
) {
  const rolesConnect =
    owner.role === "either" ||
    candidate.role === "either" ||
    owner.role !== candidate.role;
  return rolesConnect && intersects(owner.topicKeys, candidate.topicKeys);
}

function priceRangesConflict(owner: AgentProfile, candidate: AgentProfile) {
  if (!owner.price_range || !candidate.price_range) return false;
  const ownerMin = owner.price_range.min ?? 0;
  const ownerMax = owner.price_range.max ?? Number.POSITIVE_INFINITY;
  const candidateMin = candidate.price_range.min ?? 0;
  const candidateMax = candidate.price_range.max ?? Number.POSITIVE_INFINITY;
  return ownerMax < candidateMin || candidateMax < ownerMin;
}

function exclusionReason(
  owner: DiscoveryProfileMock,
  candidate: DiscoveryProfileMock,
  hasActiveSession = false,
): ExclusionReason | null {
  if (!hasActiveSession && !goalsConnect(owner, candidate)) return "goal";
  if (!intersects(owner.reachKeys, candidate.reachKeys)) return "reach";
  return null;
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

function ScoreBar({ value }: { value: number }) {
  const score = Math.round(Math.min(100, Math.max(0, value)));
  return (
    <span className="ecosystem-score" aria-label={`${score}% de compatibilidad`}>
      <span><i style={{ width: `${score}%` }} /></span>
      <strong>{score}%</strong>
    </span>
  );
}

export function EcosistemaList() {
  const { agents, sessions } = useAgentSync();
  const { agentId, authReady } = useAuth();
  const [filter, setFilter] = useState<Filter>("todos");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const ownerAgent = agents.find((agent) => agent.agent_id === agentId);

  const discovery = useMemo(() => {
    if (!ownerAgent || !agentId) {
      return {
        actionable: [] as Array<{
          agent: AgentProfile;
          profile: DiscoveryProfileMock;
          activeSessions: MatchSession[];
        }>,
        screened: { goal: 0, limits: 0, reach: 0, unavailable: 0 },
      };
    }

    const ownerProfile = discoveryProfile(ownerAgent);
    const screened = { goal: 0, limits: 0, reach: 0, unavailable: 0 };
    const actionable = agents
      .filter((agent) => agent.agent_id !== agentId)
      .flatMap((agent) => {
        const profile = discoveryProfile(agent);
        const activeSessions = sessionsBetween(agentId, agent.agent_id, sessions);
        const compatibilityReason = exclusionReason(
          ownerProfile,
          profile,
          activeSessions.length > 0,
        );
        const reason = agent.status === "PAUSED"
          ? "unavailable"
          : compatibilityReason ??
            (priceRangesConflict(ownerAgent, agent) ? "limits" : null);

        if (reason) {
          screened[reason] += 1;
          return [];
        }
        return [{ agent, profile, activeSessions }];
      })
      .sort((left, right) => {
        const leftScore =
          left.activeSessions[0]?.matchmaking?.score != null
            ? left.activeSessions[0].matchmaking.score * 100
            : left.profile.fitScore;
        const rightScore =
          right.activeSessions[0]?.matchmaking?.score != null
            ? right.activeSessions[0].matchmaking.score * 100
            : right.profile.fitScore;
        return rightScore - leftScore;
      });

    SCREENED_DISCOVERY_PROFILES.forEach((profile) => {
      const reason = exclusionReason(ownerProfile, profile);
      if (reason) screened[reason] += 1;
    });

    return { actionable, screened };
  }, [agentId, agents, ownerAgent, sessions]);

  if (!authReady) {
    return <div className="ecosystem-empty">Preparando tu área de exploración…</div>;
  }

  if (!ownerAgent || !agentId) {
    return (
      <div className="ecosystem-empty">
        <CompassIcon size={24} />
        <h2>Primero configura tu agente</h2>
        <p>Necesitamos sus objetivos y su alcance para mostrarte oportunidades que sí puede trabajar.</p>
        <Link href="/setup">Configurar mi agente <ArrowRightIcon size={14} /></Link>
      </div>
    );
  }

  const ownerProfile = discoveryProfile(ownerAgent);
  const counts = {
    todos: discovery.actionable.length,
    B2B: discovery.actionable.filter(
      ({ agent }) => segmentOf(agent.entity_type) === "B2B",
    ).length,
    P2P: discovery.actionable.filter(
      ({ agent }) => segmentOf(agent.entity_type) === "P2P",
    ).length,
  };
  const visible = discovery.actionable.filter(
    ({ agent }) =>
      filter === "todos" || segmentOf(agent.entity_type) === filter,
  );
  const activeSelection = visible.some(({ agent }) => agent.agent_id === selectedId)
    ? selectedId
    : visible[0]?.agent.agent_id ?? null;
  const screenedTotal = Object.values(discovery.screened).reduce(
    (total, count) => total + count,
    0,
  );
  const filters: { key: Filter; label: string; count: number }[] = [
    { key: "todos", label: "Todos", count: counts.todos },
    { key: "B2B", label: "Empresas", count: counts.B2B },
    { key: "P2P", label: "Personas", count: counts.P2P },
  ];

  return (
    <div className="ecosystem-explorer">
      <section className="ecosystem-scope-strip" aria-label="Criterios de exploración">
        <div>
          <span className="ecosystem-scope-icon"><CompassIcon size={18} /></span>
          <span>
            <small>Tu zona de acción</small>
            <strong>{ownerProfile.publicArea}</strong>
          </span>
        </div>
        <div>
          <span className="ecosystem-scope-icon"><CheckIcon size={17} /></span>
          <span>
            <small>Qué llega a esta vista</small>
            <strong>Objetivo y logística compatibles</strong>
          </span>
        </div>
        <p>
          Explorar no es todo el directorio. Es la selección que tu agente puede convertir en una conversación útil.
        </p>
      </section>

      <div className="ecosystem-toolbar">
        <div className="ecosystem-filters" role="group" aria-label="Filtrar oportunidades">
          {filters.map((option) => (
            <button
              key={option.key}
              type="button"
              className={filter === option.key ? "is-selected" : ""}
              onClick={() => setFilter(option.key)}
              aria-pressed={filter === option.key}
            >
              {option.label} <span>{option.count}</span>
            </button>
          ))}
        </div>
        <p><strong>{counts.todos}</strong> oportunidades realmente accionables</p>
      </div>

      <div className="ecosystem-layout">
        <aside className="ecosystem-map-panel" aria-label="Mapa aproximado de oportunidades">
          <header>
            <div>
              <span className="section-eyebrow">Alcance compartido</span>
              <h2>Agentes dentro de tu radio</h2>
            </div>
            <span className="ecosystem-map-live"><i /> Actualizado</span>
          </header>

          <div className="ecosystem-map-canvas">
            <span className="ecosystem-map-area is-north">Lima norte</span>
            <span className="ecosystem-map-area is-center">Centro</span>
            <span className="ecosystem-map-area is-port">Callao</span>
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <path className="ecosystem-map-coast" d="M19 2 C24 20 17 38 25 55 C29 68 24 83 32 100" />
              <path className="ecosystem-map-road" d="M25 20 C46 31 61 23 83 35" />
              <path className="ecosystem-map-road" d="M31 72 C46 57 67 61 88 46" />
              <circle
                className="ecosystem-map-radius"
                cx={ownerProfile.mapX}
                cy={ownerProfile.mapY}
                r="35"
              />
              {visible.map(({ agent, profile }) => (
                <line
                  key={agent.agent_id}
                  className={agent.agent_id === activeSelection ? "is-selected" : ""}
                  x1={ownerProfile.mapX}
                  y1={ownerProfile.mapY}
                  x2={profile.mapX}
                  y2={profile.mapY}
                />
              ))}
            </svg>

            <span
              className="ecosystem-map-marker is-owner"
              style={
                {
                  "--map-x": `${ownerProfile.mapX}%`,
                  "--map-y": `${ownerProfile.mapY}%`,
                } as CSSProperties
              }
            >
              <i>{initials(ownerAgent.display_name)}</i>
              <small>Tú · zona aproximada</small>
            </span>

            {visible.map(({ agent, profile }) => (
              <button
                key={agent.agent_id}
                type="button"
                className={`ecosystem-map-marker ${agent.agent_id === activeSelection ? "is-selected" : ""}`}
                style={
                  {
                    "--map-x": `${profile.mapX}%`,
                    "--map-y": `${profile.mapY}%`,
                  } as CSSProperties
                }
                onClick={() => setSelectedId(agent.agent_id)}
                aria-label={`Ubicar a ${agent.display_name}: ${profile.publicArea}`}
              >
                <i>{initials(agent.display_name)}</i>
                <small>{profile.publicArea}</small>
              </button>
            ))}
          </div>

          <footer>
            <ShieldIcon size={16} />
            <span><strong>Privacidad por diseño</strong> El mapa usa zonas públicas aproximadas, nunca direcciones ni ubicación en tiempo real.</span>
          </footer>
        </aside>

        <section className="ecosystem-results" aria-labelledby="ecosystem-results-title">
          <header>
            <div>
              <span className="section-eyebrow">Selección de tu agente</span>
              <h2 id="ecosystem-results-title">Oportunidades que pueden avanzar</h2>
            </div>
            <span>Ordenadas por compatibilidad</span>
          </header>

          {visible.length === 0 ? (
            <div className="ecosystem-results-empty">
              <CompassIcon size={21} />
              <strong>No hay oportunidades accionables en este filtro</strong>
              <span>Tu agente seguirá atento y esta vista se actualizará cuando aparezca una ruta viable.</span>
            </div>
          ) : (
            <div className="ecosystem-card-list">
              {visible.map(({ agent, profile, activeSessions }) => {
                const status = STATUS_BADGES[agent.status] ?? STATUS_BADGES.AVAILABLE;
                const session = activeSessions[0];
                const score = session?.matchmaking?.score != null
                  ? session.matchmaking.score * 100
                  : profile.fitScore;
                const offers = Array.from(
                  new Set(
                    agent.objective_contexts?.flatMap((objective) => objective.offers) ??
                      agent.capabilities,
                  ),
                ).slice(0, 3);

                return (
                  <article
                    key={agent.agent_id}
                    className={`ecosystem-card ${agent.agent_id === activeSelection ? "is-selected" : ""}`}
                    tabIndex={0}
                    onFocus={() => setSelectedId(agent.agent_id)}
                    onMouseEnter={() => setSelectedId(agent.agent_id)}
                  >
                    <header>
                      <span className="ecosystem-agent-avatar">{initials(agent.display_name)}</span>
                      <div>
                        <span>{segmentOf(agent.entity_type)} · {profile.publicArea}</span>
                        <h3>{agent.display_name}</h3>
                      </div>
                      <span className={`ecosystem-status ${status.className}`}>{status.label}</span>
                    </header>

                    <p className="ecosystem-agent-description">{agent.public_description}</p>

                    <div className="ecosystem-fit-row">
                      <span>
                        <small>Encaje estimado</small>
                        <strong>{profile.topicLabel}</strong>
                      </span>
                      <ScoreBar value={score} />
                    </div>

                    <div className="ecosystem-offers">
                      <span>Puede aportar</span>
                      <div>
                        {offers.map((offer) => <i key={offer}>{offer}</i>)}
                      </div>
                    </div>

                    <div className="ecosystem-viability">
                      <CheckIcon size={15} />
                      <span><strong>Interacción viable</strong>{profile.viabilityLabel}</span>
                    </div>

                    <footer>
                      <span><SparkIcon size={14} /> {profile.scopeLabel}</span>
                      {session ? (
                        <Link href={`/chat/${session.session_id}`}>
                          Ver conversación <ArrowRightIcon size={14} />
                        </Link>
                      ) : (
                        <strong>Lista para contacto automático</strong>
                      )}
                    </footer>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {screenedTotal > 0 ? (
        <div className="ecosystem-screened-note">
          <ShieldIcon size={18} />
          <span>
            <strong>{screenedTotal} perfiles no llegaron a esta vista</strong>
            <small>
              {discovery.screened.reach} fuera de tu alcance · {discovery.screened.goal} sin un objetivo compatible
              {discovery.screened.limits > 0 ? ` · ${discovery.screened.limits} fuera de límites` : ""}
              {discovery.screened.unavailable > 0 ? ` · ${discovery.screened.unavailable} no disponibles` : ""}
            </small>
          </span>
          <p>Tu agente los descarta antes de iniciar una conversación.</p>
        </div>
      ) : null}
    </div>
  );
}
