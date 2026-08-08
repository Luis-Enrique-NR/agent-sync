import { notFound } from "next/navigation";
import Link from "next/link";
import mockData from "@/data/mockData.json";
import type { MockData } from "@/lib/types";
import { DecisionPanel } from "@/components/DecisionPanel";

const data = mockData as unknown as MockData;

export default async function ChatPage({
  params,
}: PageProps<"/chat/[id]">) {
  const { id } = await params;
  const session = data.sessions.find((s) => s.session_id === id);

  if (!session) {
    notFound();
  }

  const agentById = (agentId: string) =>
    data.agents.find((a) => a.agent_id === agentId);

  const agent1 = agentById(session.agent_1_id);
  const agent2 = agentById(session.agent_2_id);

  return (
    <div className="stack">
      <div>
        <Link
          href="/"
          className="cardMeta"
          style={{ display: "inline-block", marginBottom: 8 }}
        >
          ← Volver al dashboard
        </Link>
        <h1 className="pageTitle">{session.summary}</h1>
        <p className="pageSubtitle">
          {agent1?.display_name} ↔ {agent2?.display_name} · segmento{" "}
          {session.segment} · turno {session.current_turn}/{session.max_turns}
        </p>
      </div>

      {session.pending_decision ? (
        <DecisionPanel decision={session.pending_decision} />
      ) : null}

      <section className="stack">
        {session.messages.map((message) => {
          const sender = agentById(message.sender_agent_id);
          const isAgent1 = message.sender_agent_id === session.agent_1_id;
          return (
            <div
              key={message.id}
              className="card"
              style={{
                alignSelf: isAgent1 ? "flex-start" : "flex-end",
                maxWidth: "78%",
                borderColor: message.blocked_by_guardrail
                  ? "var(--danger)"
                  : undefined,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  marginBottom: 6,
                }}
              >
                <span className="cardTitle" style={{ marginBottom: 0 }}>
                  {sender?.display_name ?? message.sender_agent_id}
                </span>
                <span className="cardMeta mono">{message.sent_at}</span>
              </div>
              <p style={{ fontSize: 14 }}>{message.content}</p>
              {message.flagged ? (
                <p
                  className="badge badge-pending"
                  style={{ marginTop: 10 }}
                >
                  ⏸ {message.flagged.category} — {message.flagged.detail}
                </p>
              ) : null}
              {message.blocked_by_guardrail ? (
                <p
                  className="badge badge-danger"
                  style={{ marginTop: 10 }}
                >
                  Bloqueado por guardrail — nunca emitido al otro agente
                </p>
              ) : null}
            </div>
          );
        })}
      </section>
    </div>
  );
}
