import { notFound } from "next/navigation";
import Link from "next/link";
import mockData from "@/data/mockData.json";
import type { MockData } from "@/lib/types";
import { ConversationView } from "@/components/ConversationView";

const data = mockData as unknown as MockData;

export default async function ChatPage({
  params,
}: PageProps<"/chat/[id]">) {
  const { id } = await params;
  const session = data.sessions.find((s) => s.session_id === id);

  if (!session) {
    notFound();
  }

  const agentsById = Object.fromEntries(
    data.agents.map((agent) => [
      agent.agent_id,
      {
        display_name: agent.display_name,
        entity_type: agent.entity_type,
      },
    ]),
  );

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
        <h1 className="mt-2 text-xl font-bold tracking-tight">
          {session.summary}
        </h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          {agent1?.display_name} ↔ {agent2?.display_name} · segmento{" "}
          {session.segment}
        </p>
      </div>

      <ConversationView session={session} agentsById={agentsById} />
    </div>
  );
}
