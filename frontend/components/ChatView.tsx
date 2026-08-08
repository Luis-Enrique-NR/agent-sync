"use client";

import Link from "next/link";
import { useAgentSync } from "@/lib/store";
import { ConversationView } from "@/components/ConversationView";

export function ChatView({ sessionId }: { sessionId: string }) {
  const { sessions, agentsById } = useAgentSync();
  const session = sessions.find((s) => s.session_id === sessionId);

  if (!session) {
    return null;
  }

  const agent1 = agentsById[session.agent_1_id];
  const agent2 = agentsById[session.agent_2_id];

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <div>
        <Link
          href="/"
          className="text-sm text-[var(--muted)] hover:text-[var(--foreground)]"
        >
          ← Volver al dashboard
        </Link>
        <h1 className="mt-2 text-xl font-bold tracking-tight">{session.summary}</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          {agent1?.display_name} ↔ {agent2?.display_name} · segmento{" "}
          {session.segment}
        </p>
      </div>

      <ConversationView session={session} agentsById={agentsById} />
    </div>
  );
}
