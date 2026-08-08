import { notFound } from "next/navigation";
import mockData from "@/data/mockData.json";
import type { MockData } from "@/lib/types";
import { ChatView } from "@/components/ChatView";

const data = mockData as unknown as MockData;

export default async function ChatPage({
  params,
}: PageProps<"/chat/[id]">) {
  const { id } = await params;
  const exists = data.sessions.some((s) => s.session_id === id);

  if (!exists) {
    notFound();
  }

  return <ChatView sessionId={id} />;
}
