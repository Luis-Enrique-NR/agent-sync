"use client";

import { useState } from "react";
import type {
  ChatMessage,
  HumanDecision,
  HumanDecisionAction,
  PendingDecision,
} from "@/lib/types";
import { CheckIcon, ShieldIcon } from "@/components/Icons";

/** Reemplaza datos sensibles por una referencia opaca hasta que el humano decida. */
export function maskSensitiveContent(message: ChatMessage): string {
  if (!message.flagged?.value_ref) return message.public_message;
  return message.public_message
    .replace(/\b(?:\+?\d[\d\s().-]{6,})\b/g, `Dato protegido`)
    .replace(/[\w.+-]+@[\w-]+\.[\w.]+/g, `Dato protegido`)
    .replace(
      /(?:av\.?|calle|jirón|pasaje)\s+[\w\s.,-]{4,}/gi,
      `Dirección protegida`,
    );
}

function friendlyReason(reason: string) {
  const labels: Record<string, string> = {
    MANDATORY_PERSONAL_DATA: "Incluye un dato personal",
    USER_RULE: "Activa una regla que configuraste",
    NON_CONVERGENCE: "La conversación no llegó a un punto común",
    TIMEOUT: "Se agotó el tiempo de negociación",
  };
  return labels[reason] ?? reason.replaceAll("_", " ").toLowerCase();
}

export function kindLabel(kind: string): string {
  const labels: Record<string, string> = {
    OUTBOUND_TURN: "Turno saliente",
    INBOUND_ACTION: "Acción de contraparte",
    TOOL_EXECUTION: "Ejecución de herramienta",
    SYSTEM: "Decisión del sistema",
  };
  return labels[kind] ?? kind.replaceAll("_", " ").toLowerCase();
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
    onResolve?.({
      decision_id: decision.decision_id,
      action,
      replacement_turn: replacement.trim()
        ? { public_message: replacement.trim() }
        : null,
    });
  };

  if (decision.status !== "PENDING") {
    return (
      <div className="decision-resolved" role="status">
        <span className="resolved-icon"><CheckIcon size={17} /></span>
        <div>
          <p>Decisión registrada</p>
          <span>
            {decision.status === "APPROVED"
              ? "Aprobaste la propuesta y el agente continuó."
              : decision.status === "REPLACED"
                ? "Tu respuesta reemplazó la propuesta del agente."
                : "Rechazaste la propuesta; el mensaje no se publicó."}
          </span>
          {decision.manual_response ? (
            <blockquote>“{decision.manual_response}”</blockquote>
          ) : null}
        </div>
      </div>
    );
  }

  const maskedCandidate = candidate ? maskSensitiveContent(candidate) : null;

  return (
    <section className="decision-panel" aria-labelledby={`decision-${decision.decision_id}`}>
      <div className="decision-panel-heading">
        <span className="decision-shield"><ShieldIcon size={19} /></span>
        <div>
          <span>Tu agente está esperando</span>
          <h3 id={`decision-${decision.decision_id}`}>{kindLabel(decision.kind)}</h3>
        </div>
      </div>

      <p className="decision-summary">{decision.summary}</p>

      <div className="proposal-box">
        <span>Lo que tu agente propone hacer</span>
        <p>{decision.proposal}</p>
      </div>

      {maskedCandidate ? (
        <div className="candidate-preview">
          <span>Mensaje antes de enviarlo</span>
          <p>{maskedCandidate}</p>
          {candidate?.flagged?.value_ref ? (
            <small>El dato real permanece oculto hasta que apruebes.</small>
          ) : null}
        </div>
      ) : null}

      <div className="decision-reasons">
        {(decision.reasons ?? []).map((reason) => (
          <span key={reason}><ShieldIcon size={12} /> {friendlyReason(reason)}</span>
        ))}
      </div>

      {mode === "REPLACE" ? (
        <form
          className="manual-response"
          onSubmit={(event) => {
            event.preventDefault();
            if (replacement.trim()) resolve("REPLACE");
          }}
        >
          <label htmlFor={`replacement-${decision.decision_id}`}>
            Escribe qué debe responder tu agente
          </label>
          <textarea
            id={`replacement-${decision.decision_id}`}
            autoFocus
            value={replacement}
            onChange={(event) => setReplacement(event.target.value)}
            placeholder="Ej.: Acepta el precio, pero propone un punto de encuentro público."
            rows={3}
          />
          <div>
            <button type="submit" disabled={!replacement.trim()} className="decision-button approve">
              Enviar mi respuesta
            </button>
            <button type="button" onClick={() => setMode(null)} className="decision-button neutral">
              Cancelar
            </button>
          </div>
        </form>
      ) : (
        <div className="decision-actions">
          <button type="button" onClick={() => resolve("APPROVE")} className="decision-button approve">
            Aprobar y continuar
          </button>
          <button type="button" onClick={() => resolve("REJECT")} className="decision-button reject">
            Rechazar
          </button>
          <button type="button" onClick={() => setMode("REPLACE")} className="decision-button neutral">
            Cambiar la respuesta
          </button>
        </div>
      )}
    </section>
  );
}
