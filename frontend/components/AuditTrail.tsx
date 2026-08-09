"use client";

import type { AuditRecord } from "@/lib/types";

const ACTOR_STYLES: Record<AuditRecord["actor_type"], string> = {
  HUMAN: "bg-[var(--accent)]/10 text-[var(--accent)]",
  SYSTEM: "bg-[var(--accent-2)]/10 text-[var(--accent-2)]",
  LLM: "bg-[var(--warning)]/10 text-[var(--warning)]",
};

const ACTOR_LABELS: Record<AuditRecord["actor_type"], string> = {
  HUMAN: "HUMAN",
  SYSTEM: "SYSTEM",
  LLM: "LLM",
};

const SEVERITY_STYLES: Record<AuditRecord["severity"], string> = {
  INFO: "text-[var(--muted)]",
  WARNING: "text-[var(--warning)]",
  ERROR: "text-[var(--danger)]",
};

export function AuditTrail({
  audit,
  emptyLabel = "Aún no hay registros de auditoría para esta sesión.",
}: {
  audit?: AuditRecord[];
  emptyLabel?: string;
}) {
  const records = audit ?? [];

  if (records.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-[var(--border)] bg-[var(--surface)] px-5 py-8 text-center text-sm text-[var(--muted)]">
        {emptyLabel}
      </p>
    );
  }

  return (
    <ol className="flex flex-col gap-3">
      {records.map((record) => (
        <li
          key={record.audit_id}
          className="rounded-xl border border-[var(--border)] bg-[var(--background)] px-4 py-3"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold ${ACTOR_STYLES[record.actor_type]}`}
            >
              {ACTOR_LABELS[record.actor_type]}
            </span>
            <span className="text-xs font-semibold">{record.action}</span>
            <span
              className={`ml-auto text-[10px] font-semibold uppercase ${SEVERITY_STYLES[record.severity]}`}
            >
              {record.severity}
            </span>
          </div>
          {record.reason ? (
            <p className="mt-1.5 text-xs leading-relaxed text-[var(--muted)]">
              {record.reason}
            </p>
          ) : null}
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 font-mono text-[10px] text-[var(--muted)]">
            <span>{record.occurred_at}</span>
            {record.actor_id ? <span>actor={record.actor_id}</span> : null}
            {record.entity_type ? <span>{record.entity_type}</span> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
