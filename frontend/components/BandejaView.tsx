"use client";

import { useAgentSync } from "@/lib/store";
import { DecisionInbox } from "@/components/DecisionInbox";
import { ShieldIcon } from "@/components/Icons";
import { useAuth } from "@/lib/auth";
import { belongsToAgent } from "@/lib/demo";

export function BandejaView() {
  const { sessions } = useAgentSync();
  const { agentId } = useAuth();
  const pendingCount = sessions.filter(
    (s) =>
      belongsToAgent(s, agentId) &&
      s.status === "PENDING_HUMAN_APPROVAL" &&
      s.pending_decision,
  ).length;

  return (
    <div className="flex flex-col gap-6">
      <header className="page-heading">
        <div>
          <span className="section-eyebrow">Control humano</span>
          <h1>Aquí decides tú</h1>
          <p>
            Revisa solo las propuestas que cruzan una regla sensible. Todo lo
            demás sigue avanzando sin interrumpirte.
          </p>
        </div>
        <aside className="page-heading-note">
          <ShieldIcon size={20} />
          <span>
            <strong>{pendingCount} conversación{pendingCount === 1 ? "" : "es"} esperando tu decisión.</strong>
            Tu agente no enviará esa propuesta hasta que respondas.
          </span>
        </aside>
      </header>

      <DecisionInbox />
    </div>
  );
}
