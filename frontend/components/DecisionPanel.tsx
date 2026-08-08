"use client";

import { useState } from "react";
import type { DecisionStatus, PendingDecision } from "@/lib/types";

export function DecisionPanel({
  decision,
  onResolve,
}: {
  decision: PendingDecision;
  onResolve?: (status: DecisionStatus) => void;
}) {
  const [status, setStatus] = useState(decision.status);

  const resolve = (nextStatus: DecisionStatus) => {
    setStatus(nextStatus);
    onResolve?.(nextStatus);
  };

  if (status !== "PENDING") {
    return (
      <div className="rounded-2xl border border-[var(--accent-2)]/40 bg-[var(--accent-2)]/10 p-5">
        <p className="text-sm font-semibold text-[var(--accent-2)]">
          Decisión resuelta
        </p>
        <p className="mt-1 text-sm text-[var(--muted)]">
          {status === "APPROVED"
            ? "Aprobada: el agente continuó con la propuesta."
            : status === "REPLACED"
              ? "Respondiste manualmente: la propuesta fue reemplazada por tu mensaje."
              : "Rechazada: la propuesta no fue publicada."}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[var(--warning)]/50 bg-[var(--surface)] p-5">
      <p className="text-sm font-semibold">
        Decisión sensible — {decision.category}
      </p>
      <p className="mt-2 text-sm">{decision.summary}</p>
      <p className="mt-2 font-mono text-xs text-[var(--muted)]">
        Propuesta: {decision.proposal}
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => resolve("APPROVED")}
          className="rounded-xl bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white transition hover:brightness-110"
        >
          Aprobar
        </button>
        <button
          type="button"
          onClick={() => resolve("REJECTED")}
          className="rounded-xl bg-[var(--danger)]/15 px-4 py-2 text-sm font-semibold text-[var(--danger)] transition hover:brightness-110"
        >
          Rechazar
        </button>
        <button
          type="button"
          onClick={() => resolve("REPLACED")}
          className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-2 text-sm font-semibold transition hover:brightness-110"
        >
          Responder manualmente
        </button>
      </div>
    </div>
  );
}
