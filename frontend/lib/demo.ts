import type { MatchSession } from "@/lib/types";

export const DEMO_OWNER_AGENT_ID = "agent-p2p-valentina";

export function belongsToAgent(session: MatchSession, agentId: string | null) {
  if (!agentId) return false;

  return (
    session.agent_1_id === agentId ||
    session.agent_2_id === agentId
  );
}
