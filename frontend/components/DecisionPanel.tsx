"use client";

import { useState } from "react";
import type { PendingDecision } from "@/lib/types";

export function DecisionPanel({
  decision,
}: {
  decision: PendingDecision;
}) {
  const [status, setStatus] = useState(decision.status);

  if (status !== "PENDING") {
    return (
      <div className="card" style={{ borderColor: "var(--accent-2)" }}>
        <div className="cardTitle">Decisión resuelta</div>
        <p className="cardMeta">
          {status === "APPROVED"
            ? "Aprobada: el agente continuará con la propuesta."
            : "Rechazada: la propuesta no será publicada."}
        </p>
      </div>
    );
  }

  return (
    <div
      className="card"
      style={{ borderColor: "rgba(255, 200, 107, 0.5)" }}
    >
      <div className="cardTitle">
        Decisión sensible — {decision.category}
      </div>
      <p style={{ fontSize: 14, margin: "8px 0" }}>{decision.summary}</p>
      <p className="mono cardMeta" style={{ marginBottom: 12 }}>
        Propuesta: {decision.proposal}
      </p>
      <div style={{ display: "flex", gap: 12 }}>
        <button
          className="btn btn-primary"
          type="button"
          onClick={() => setStatus("APPROVED")}
        >
          Aprobar
        </button>
        <button
          className="btn btn-danger"
          type="button"
          onClick={() => setStatus("REJECTED")}
        >
          Rechazar
        </button>
        <button
          className="btn"
          type="button"
          onClick={() => setStatus("REPLACED")}
        >
          Responder manualmente
        </button>
      </div>
    </div>
  );
}
