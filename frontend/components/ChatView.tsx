"use client";

import Link from "next/link";
import { useAgentSync } from "@/lib/store";
import { ConversationView } from "@/components/ConversationView";
import { ArrowRightIcon, ShieldIcon } from "@/components/Icons";

function shortName(name?: string) {
  return name?.split(" — ")[0] ?? "Agente";
}

function initials(name?: string) {
  return shortName(name)
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}

export function ChatView({ sessionId }: { sessionId: string }) {
  const { sessions, agentsById } = useAgentSync();
  const session = sessions.find((item) => item.session_id === sessionId);

  if (!session) return null;

  const agent1 = agentsById[session.agent_1_id];
  const agent2 = agentsById[session.agent_2_id];
  const waiting = session.status === "PENDING_HUMAN_APPROVAL";

  return (
    <div className="conversation-page">
      <Link href="/" className="conversation-back">
        <ArrowRightIcon size={14} /> Volver al inicio
      </Link>

      <header className="conversation-heading">
        <div>
          <span className="section-eyebrow">
            Negociación {session.segment}
          </span>
          <h1>{session.summary}</h1>
          <p>
            Ves los mensajes más recientes y las decisiones que guiaron el
            acuerdo. Tu agente se detiene cuando necesita tu criterio.
          </p>
        </div>

        <aside className="conversation-parties">
          <div className="party-row">
            <span className="party-avatar">{initials(agent1?.display_name)}</span>
            <span>
              <strong>{shortName(agent1?.display_name)}</strong>
              <small>Tu lado</small>
            </span>
          </div>
          <span className="party-divider">negocia con</span>
          <div className="party-row">
            <span className="party-avatar is-counterpart">{initials(agent2?.display_name)}</span>
            <span>
              <strong>{shortName(agent2?.display_name)}</strong>
              <small>Contraparte</small>
            </span>
          </div>
          {waiting ? (
            <span className="conversation-waiting">
              <ShieldIcon size={13} /> Esperando tu decisión
            </span>
          ) : null}
        </aside>
      </header>

      {session.matchmaking ? (
        <section className="compatibility-panel" aria-label="Compatibilidad de la oportunidad">
          <div>
            <span>Por qué hicieron match</span>
            <strong>{Math.round(session.matchmaking.score * 100)}%</strong>
            <small>de compatibilidad general</small>
          </div>
          <div className="compatibility-bars">
            <label>
              <span>Objetivos en común <b>{Math.round(session.matchmaking.ic_score * 100)}%</b></span>
              <i><em style={{ width: `${Math.round(session.matchmaking.ic_score * 100)}%` }} /></i>
            </label>
            <label>
              <span>Logística compatible <b>{Math.round(session.matchmaking.logistics_score * 100)}%</b></span>
              <i><em style={{ width: `${Math.round(session.matchmaking.logistics_score * 100)}%` }} /></i>
            </label>
          </div>
          <span className="channel-status">
            {session.matchmaking.channel_status === "CREATED"
              ? "Canal privado creado"
              : "Preparando canal privado"}
          </span>
        </section>
      ) : null}

      <ConversationView session={session} agentsById={agentsById} />
    </div>
  );
}
