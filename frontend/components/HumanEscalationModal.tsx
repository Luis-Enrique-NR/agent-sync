"use client";

import { useState } from "react";
import type {
  ChatMessage,
  HumanDecision,
  HumanDecisionAction,
  PendingDecision,
} from "@/lib/types";

const ACTION_LABELS: Record<HumanDecisionAction, string> = {
  APPROVE: "Aprobar",
  REJECT: "Rechazar",
  REPLACE: "Responder manualmente",
};

/** Sustituye segmentos sensibles (teléfonos, emails, direcciones) por la
 *  referencia opaca value_ref. El valor real solo existe post-aprobación. */
export function maskSensitiveContent(message: ChatMessage): string {
  if (!message.flagged?.value_ref) return message.content;
  return message.content
    .replace(/\b(?:\+?\d[\d\s().-]{6,})\b/g, `◈${message.flagged.value_ref}`)
    .replace(/[\w.+-]+@[\w-]+\.[\w.]+/g, `◈${message.flagged.value_ref}`)
    .replace(
      /(?:av\.?|calle|jirón|av\.|pasaje)\s+[\w\s.,-]{4,}/gi,
      `◈${message.flagged.value_ref}`,
    );
}

function severityBadge(severity: string) {
  switch (severity) {
    case "MANDATORY_PERSONAL_DATA":
      return (
        <span className="rounded-full bg-[var(--danger)]/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-[var(--danger)]">
          dato personal obligatorio
        </span>
      );
    case "USER_RULE":
      return (
        <span className="rounded-full bg-[var(--warning)]/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-[var(--warning)]">
          regla del usuario
        </span>
      );
    case "NON_CONVERGENCE":
      return (
        <span className="rounded-full bg-[var(--warning)]/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-[var(--warning)]">
          sin convergencia
        </span>
      );
    case "TIMEOUT":
      return (
        <span className="rounded-full bg-[var(--muted)]/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-[var(--muted)]">
          timeout
        </span>
      );
    default:
      return null;
  }
}

export function HumanEscalationModal({
  decision,
  candidate,
  onResolve,
}: {
  decision: PendingDecision;
  candidate?: ChatMessage;
  onResolve?: (humanDecision: HumanDecision) => void;
}) {
  const [replacement, setReplacement] = useState("");
  const [mode, setMode] = useState<HumanDecisionAction | null>(null);

  const resolve = (action: HumanDecisionAction) => {
    onResolve?.({ decision_id: decision.decision_id, action, replacement_message: replacement });
  };

  if (decision.status !== "PENDING") {
    return (
      <div className="rounded-2xl border border-[var(--accent-2)]/40 bg-[var(--accent-2)]/10 p-5">
        <p className="text-sm font-semibold text-[var(--accent-2)]">
          Decisión resuelta
        </p>
        <p className="mt-1 text-sm text-[var(--muted)]">
          {decision.status === "APPROVED"
            ? "Aprobada: el AI Backend reanudó la negociación y el vault resolvió la referencia opaca."
            : decision.status === "REPLACED"
              ? "Respondiste manualmente: el turno candidato fue reemplazado por tu mensaje."
              : "Rechazada: el AI Backend retiró la negociación. El turno nunca fue publicado."}
        </p>
      </div>
    );
  }

  const maskedCandidate = candidate ? maskSensitiveContent(candidate) : null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4 sm:items-center">
      <div className="w-full max-w-xl rounded-2xl border border-[var(--warning)]/50 bg-[var(--surface)] p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-[var(--warning)]">
              ⏸ Escalamiento humano — {decision.category}
            </p>
            <p className="mt-0.5 text-xs text-[var(--muted)]">
              El AI Backend pausó la sesión (PENDING_HUMAN_APPROVAL). No se
              publicó nada al otro agente.
            </p>
          </div>
          <span className="rounded-full bg-[var(--warning)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--warning)]">
            PENDING_HUMAN_APPROVAL
          </span>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          {decision.reasons?.map((reason) => (
            <span key={reason}>{severityBadge(reason)}</span>
          ))}
          {decision.matched_rule_ids?.map((ruleId) => (
            <span
              key={ruleId}
              className="rounded-full bg-[var(--surface-2)] px-2 py-0.5 font-mono text-[10px] text-[var(--muted)]"
            >
              {ruleId}
            </span>
          ))}
        </div>

        <p className="mt-4 text-sm leading-relaxed">{decision.summary}</p>
        <p className="mt-2 font-mono text-xs text-[var(--muted)]">
          Propuesta: {decision.proposal}
        </p>

        {candidate && maskedCandidate ? (
          <div className="mt-4 rounded-xl border border-dashed border-[var(--warning)]/40 bg-[var(--background)] p-4">
            <p className="text-xs font-semibold text-[var(--muted)]">
              Turno candidato (antes de publicar)
            </p>
            <p className="mt-1.5 text-sm leading-relaxed">{maskedCandidate}</p>
            {candidate.flagged?.value_ref ? (
              <p className="mt-2 rounded-lg bg-[var(--warning)]/10 px-3 py-2 font-mono text-[11px] text-[var(--warning)]">
                Referencia opaca: {candidate.flagged.value_ref} — el valor real
                se resuelve en el vault solo si apruebas.
              </p>
            ) : null}
          </div>
        ) : null}

        {mode === "REPLACE" ? (
          <textarea
            autoFocus
            value={replacement}
            onChange={(e) => setReplacement(e.target.value)}
            className="mt-4 min-h-24 w-full rounded-xl border border-[var(--border)] bg-[var(--background)] px-3.5 py-2.5 text-sm outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/30"
            placeholder="Escribe el mensaje que quieres que tu agente publique…"
          />
        ) : null}

        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => resolve("APPROVE")}
            className="rounded-xl bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white transition hover:brightness-110"
          >
            Aprobar y reanudar
          </button>
          <button
            type="button"
            onClick={() => resolve("REJECT")}
            className="rounded-xl bg-[var(--danger)]/15 px-4 py-2 text-sm font-semibold text-[var(--danger)] transition hover:brightness-110"
          >
            Rechazar y retirar
          </button>
          <button
            type="button"
            onClick={() => (mode === "REPLACE" ? resolve("REPLACE") : setMode("REPLACE"))}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-4 py-2 text-sm font-semibold transition hover:brightness-110"
          >
            {mode === "REPLACE" ? "Publicar mi respuesta" : ACTION_LABELS.REPLACE}
          </button>
        </div>
      </div>
    </div>
  );
}
