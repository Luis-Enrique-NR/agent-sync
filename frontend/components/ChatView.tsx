"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useAgentSync } from "@/lib/store";
import * as api from "@/lib/api";
import { connectNegotiationStream } from "@/lib/sse";
import type { AuditRecord, ChatMessage, MatchSession } from "@/lib/types";
import { ConversationView } from "@/components/ConversationView";
import { AuditTrail } from "@/components/AuditTrail";
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

function transcriptToMessages(
  transcript: api.TranscriptMessage[],
): ChatMessage[] {
  return transcript.map((t) => ({
    id: `${t.speaker_id}-${t.turn_index}`,
    sender_agent_id: t.speaker_id,
    content: t.public_message,
    sent_at: t.created_at ?? new Date().toISOString(),
    intent: t.intent as ChatMessage["intent"],
  }));
}

export function ChatView({ sessionId }: { sessionId: string }) {
  const { sessions, agentsById, refreshSessions } = useAgentSync();
  const [transcript, setTranscript] = useState<ChatMessage[] | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [audit, setAudit] = useState<AuditRecord[] | null>(null);
  const sseRef = useRef<ReturnType<typeof connectNegotiationStream> | null>(null);
  const baseSession = sessions.find((item) => item.session_id === sessionId);

  const fetchTranscript = () => {
    api.getNegotiation(sessionId).then((detail) => {
      setTranscript(transcriptToMessages(detail.transcript));
      setStatus(detail.status);
    });
    api.getAudit(sessionId).then((res) => {
      setAudit(res.records);
    });
  };

  // Initial fetch
  useEffect(() => {
    fetchTranscript();
  }, [sessionId]);

  // SSE connection
  useEffect(() => {
    const conn = connectNegotiationStream(
      sessionId,
      () => {
        // New message event — refresh transcript + store
        fetchTranscript();
        refreshSessions();
      },
      (newStatus) => {
        setStatus(newStatus);
        refreshSessions();
      },
      () => {
        // Transcript refresh after reconnect
        fetchTranscript();
      },
    );
    sseRef.current = conn;

    return () => {
      conn.close();
    };
  }, [sessionId, refreshSessions]);

  if (!baseSession) return null;

  const session: MatchSession = {
    ...baseSession,
    messages: transcript ?? [],
  };

  const agent1 = agentsById[baseSession.agent_1_id];
  const agent2 = agentsById[baseSession.agent_2_id];
  const waiting = baseSession.status === "PENDING_HUMAN_APPROVAL" || status === "PENDING_HUMAN_APPROVAL";
  const resolved = status === "RESOLVED" || baseSession.status === "RESOLVED";

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
          ) : resolved ? (
            <span className="conversation-waiting">
              ✓ Negociación resuelta
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

      <aside className="conversation-audit" aria-label="Registro de auditoría">
        <h2>Registro de auditoría</h2>
        <AuditTrail audit={audit ?? undefined} />
      </aside>
    </div>
  );
}
