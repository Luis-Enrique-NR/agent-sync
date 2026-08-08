"use client";

import { useAgentSync } from "@/lib/store";
import { MatchHistory } from "@/components/MatchHistory";

export function HistorialView() {
  const { sessions } = useAgentSync();
  const matches = sessions.filter((s) => s.status === "RESOLVED").length;
  const rejected = sessions.filter((s) => s.status === "REJECTED").length;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Historial</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Negociaciones cerradas: matches confirmados y acuerdos descartados por
          ti. Un solo historial para B2B y P2P.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Matches confirmados
          </p>
          <p className="mt-2 text-3xl font-bold">{matches}</p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Contacto revelado y acuerdo cerrado.
          </p>
        </div>
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Rechazadas
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
