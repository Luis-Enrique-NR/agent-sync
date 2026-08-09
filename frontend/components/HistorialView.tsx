"use client";

import { useAgentSync } from "@/lib/store";
import { MatchHistory } from "@/components/MatchHistory";
import { HistoryIcon } from "@/components/Icons";

export function HistorialView() {
  const { sessions } = useAgentSync();
  const matches = sessions.filter((s) => s.status === "RESOLVED").length;
  const rejected = sessions.filter((s) => s.status === "REJECTED").length;

  return (
    <div className="flex flex-col gap-6">
      <header className="page-heading">
        <div>
          <span className="section-eyebrow">Trazabilidad</span>
          <h1>Lo que ya resolviste</h1>
          <p>
            Consulta acuerdos confirmados y propuestas descartadas, con el
            contexto de cada conversación siempre disponible.
          </p>
        </div>
        <aside className="page-heading-note">
          <HistoryIcon size={20} />
          <span>
            <strong>Cada decisión deja registro.</strong>
            Puedes volver a la conversación que la originó.
          </span>
        </aside>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Acuerdos confirmados
          </p>
          <p className="mt-2 text-3xl font-bold">{matches}</p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Contacto revelado después de tu aprobación.
          </p>
        </div>
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Propuestas descartadas
          </p>
          <p className="mt-2 text-3xl font-bold">{rejected}</p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Acuerdos descartados por decisión del usuario.
          </p>
        </div>
      </div>

      <MatchHistory />
    </div>
  );
}
