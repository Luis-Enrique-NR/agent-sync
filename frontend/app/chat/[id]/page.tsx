import { ChatView } from "@/components/ChatView";

export default async function ChatPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return <ChatView sessionId={id} />;
}
