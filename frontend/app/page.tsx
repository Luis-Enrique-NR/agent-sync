import Link from "next/link";
import mockData from "@/data/mockData.json";
import type { MockData, MatchSession } from "@/lib/types";

const data = mockData as unknown as MockData;

function statusBadge(status: MatchSession["status"]) {
  switch (status) {
    case "PENDING_HUMAN_APPROVAL":
      return <span className="badge badge-pending">Requiere tu aprobación</span>;
    case "ACTIVE":
      return <span className="badge badge-active">Negociando</span>;
    case "RESOLVED":
      return <span className="badge">Match confirmado</span>;
    case "REJECTED":
      return <span className="badge badge-danger">Rechazada</span>;
    default:
      return <span className="badge">Buscando</span>;
  }
}

export default function HomePage() {
  const pending = data.sessions.filter(
    (s) => s.status === "PENDING_HUMAN_APPROVAL" && s.pending_decision,
  );
  const activeAgents = data.agents.filter((a) => a.active).length;

  return (
    <div className="stack">
      <div>
        <h1 className="pageTitle">Dashboard</h1>
        <p className="pageSubtitle">
          Estado de tu agente y qué requiere tu atención ahora.
        </p>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <div className="cardTitle">Decisiones pendientes</div>
          <p className="mono" style={{ fontSize: 32, marginBottom: 8 }}>
            {pending.length}
          </p>
          <p className="cardMeta">
            Tu agente está en pausa hasta que decidas.
          </p>
        </div>
        <div className="card">
          <div className="cardTitle">Agentes activos en el ecosistema</div>
          <p className="mono" style={{ fontSize: 32, marginBottom: 8 }}>
            {activeAgents}
          </p>
          <p className="cardMeta">
            Entre empresas y personas. Un solo motor, dos segmentos.
          </p>
        </div>
      </div>

      <section>
        <h2 className="pageTitle" style={{ fontSize: 18 }}>
          Negociaciones en curso
        </h2>
        <div className="grid grid-2 mt-16">
          {data.sessions.map((session) => (
            <Link key={session.session_id} href={`/chat/${session.session_id}`}>
              <div className="card">
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <span className="badge">{session.segment}</span>
                  {statusBadge(session.status)}
                </div>
                <h3 className="cardTitle" style={{ marginTop: 12 }}>
                  {session.summary}
                </h3>
                <p className="cardMeta">
                  Turno {session.current_turn} de {session.max_turns} ·{" "}
                  {session.messages.length} mensajes
                </p>
                {session.pending_decision ? (
                  <p className="badge badge-pending" style={{ marginTop: 12 }}>
                    {session.pending_decision.category}
                  </p>
                ) : null}
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
