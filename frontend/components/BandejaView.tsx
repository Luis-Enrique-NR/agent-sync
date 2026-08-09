"use client";

import { useAgentSync } from "@/lib/store";
import { DecisionInbox } from "@/components/DecisionInbox";
import { PauseIcon } from "@/components/Icons";

export function BandejaView() {
  const { sessions } = useAgentSync();
  const pendingCount = sessions.filter(
    (s) => s.status === "PENDING_HUMAN_APPROVAL" && s.pending_decision,
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
          <PauseIcon size={20} />
          <span>
            <strong>{pendingCount} conversación{pendingCount === 1 ? "" : "es"} en pausa.</strong>
            Ningún mensaje sensible se envía mientras esperas.
          </span>
        </aside>
      </header>

      <DecisionInbox />
    </div>
  );
}
