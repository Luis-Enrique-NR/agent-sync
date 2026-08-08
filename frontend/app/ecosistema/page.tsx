import mockData from "@/data/mockData.json";
import type { MockData } from "@/lib/types";

const data = mockData as unknown as MockData;

export default function EcosistemaPage() {
  return (
    <div className="stack">
      <div>
        <h1 className="pageTitle">Ecosistema</h1>
        <p className="pageSubtitle">
          Agentes activos en el ecosistema. Cada agente representa una entidad
          con objetivos, sea una empresa o una persona.
        </p>
      </div>

      <div className="grid grid-2">
        {data.agents.map((agent) => (
          <div className="card" key={agent.agent_id}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 12,
                alignItems: "center",
              }}
            >
              <span className="badge">
                {agent.entity_type === "empresa" ? "B2B" : "P2P"}
              </span>
              <span className="badge badge-active">activo</span>
            </div>
            <h3 className="cardTitle" style={{ marginTop: 12 }}>
              {agent.display_name}
            </h3>
            <p className="cardMeta">{agent.personality}</p>
            <div className="list" style={{ marginTop: 12 }}>
              {agent.objectives.map((obj, i) => (
                <li key={`${agent.agent_id}-obj-${i}`}>{obj}</li>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
