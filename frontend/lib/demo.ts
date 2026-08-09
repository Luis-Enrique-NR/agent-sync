import type { MatchSession } from "@/lib/types";

export const DEMO_OWNER_AGENT_ID = "agent-p2p-valentina";

export function belongsToDemoOwner(session: MatchSession) {
  return (
    session.agent_1_id === DEMO_OWNER_AGENT_ID ||
    session.agent_2_id === DEMO_OWNER_AGENT_ID
  );
}
