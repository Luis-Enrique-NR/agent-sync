import { ChatView } from "@/components/ChatView";

export default async function ChatPage({
  params,
}: PageProps<"/chat/[id]">) {
  const { id } = await params;

  return <ChatView sessionId={id} />;
}
