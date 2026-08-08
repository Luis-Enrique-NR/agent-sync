import Link from "next/link";
import mockData from "@/data/mockData.json";
import type { MockData, MatchSession } from "@/lib/types";
import { AgentStatusCard } from "@/components/AgentStatusCard";

const data = mockData as unknown as MockData;

function statusBadge(status: MatchSession["status"]) {
  switch (status) {
    case "PENDING_HUMAN_APPROVAL":
      return (
        <span className="rounded-full bg-[var(--warning)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--warning)]">
          Requiere tu aprobación
        </span>
      );
    case "ACTIVE":
      return (
        <span className="rounded-full bg-[var(--accent-2)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--accent-2)]">
          Negociando
        </span>
      );
    case "RESOLVED":
      return (
        <span className="rounded-full bg-[var(--surface-2)] px-2.5 py-0.5 text-xs font-semibold text-[var(--muted)]">
          Match confirmado
        </span>
      );
    case "REJECTED":
      return (
        <span className="rounded-full bg-[var(--danger)]/10 px-2.5 py-0.5 text-xs font-semibold text-[var(--danger)]">
          Rechazada
        </span>
      );
    default:
      return (
        <span className="rounded-full bg-[var(--surface-2)] px-2.5 py-0.5 text-xs font-semibold text-[var(--muted)]">
          Buscando
        </span>
      );
  }
}

function progressPercent(session: MatchSession) {
  if (session.max_turns === 0) return 0;
  return Math.min(100, Math.round((session.current_turn / session.max_turns) * 100));
}

export default function HomePage() {
  const pending = data.sessions.filter(
    (s) => s.status === "PENDING_HUMAN_APPROVAL" && s.pending_decision,
  );
  const activeAgents = data.agents.filter((a) => a.active).length;
  const activeSessions = data.sessions.filter(
    (s) => s.status === "ACTIVE" || s.status === "PENDING_HUMAN_APPROVAL",
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Estado de tu agente y qué requiere tu atención ahora.
        </p>
      </div>

      <AgentStatusCard
        agentName="Valentina R. — vendedora de auto"
        pendingCount={pending.length}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Decisiones pendientes
          </p>
          <p className="mt-2 text-3xl font-bold">{pending.length}</p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            El agente queda en pausa hasta que decidas.
          </p>
        </div>
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Agentes activos
          </p>
          <p className="mt-2 text-3xl font-bold">{activeAgents}</p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Empresas y personas. Un solo motor.
          </p>
        </div>
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Negociaciones en curso
          </p>
          <p className="mt-2 text-3xl font-bold">{activeSessions.length}</p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Sesiones activas o esperando aprobación.
          </p>
        </div>
      </div>

      {pending.length > 0 ? (
        <section className="rounded-2xl border border-[var(--warning)]/40 bg-[var(--surface)] p-6">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-base font-semibold">Qué requiere tu atención</h2>
            <Link
              href="/bandeja"
              className="text-sm text-[var(--accent)] hover:underline"
            >
              Abrir bandeja →
            </Link>
          </div>
          <ul className="mt-4 flex flex-col gap-3">
            {pending.map((session) => (
              <li key={session.session_id}>
                <Link
                  href={`/chat/${session.session_id}`}
                  className="flex items-start justify-between gap-4 rounded-xl border border-[var(--border)] bg-[var(--background)] px-4 py-3 transition hover:border-[var(--accent)]"
                >
                  <div>
                    <p className="text-sm font-semibold">{session.summary}</p>
                    <p className="mt-0.5 text-xs text-[var(--muted)]">
                      {session.pending_decision?.category} ·{" "}
                      {session.pending_decision?.proposal}
                    </p>
                  </div>
                  <span className="mt-0.5 shrink-0 text-sm text-[var(--accent)]">
                    Revisar →
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold">Negociaciones</h2>
          <Link
            href="/ecosistema"
            className="text-sm text-[var(--accent)] hover:underline"
          >
            Ver ecosistema →
          </Link>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {data.sessions.map((session) => (
            <Link key={session.session_id} href={`/chat/${session.session_id}`}>
              <div className="flex h-full flex-col gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 transition hover:border-[var(--accent)]">
                <div className="flex items-center justify-between gap-3">
                  <span className="rounded-full bg-[var(--surface-2)] px-2.5 py-0.5 text-xs font-semibold text-[var(--muted)]">
                    {session.segment}
                  </span>
                  {statusBadge(session.status)}
                </div>
                <h3 className="text-sm font-semibold leading-snug">
                  {session.summary}
                </h3>
                <div>
                  <div className="flex items-center justify-between text-xs text-[var(--muted)]">
                    <span>
                      Turno {session.current_turn} de {session.max_turns}
                    </span>
                    <span>{session.messages.length} mensajes</span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--surface-2)]">
                    <div
                      className="h-full rounded-full bg-[var(--accent)]"
                      style={{ width: `${progressPercent(session)}%` }}
                    />
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
