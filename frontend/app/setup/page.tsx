import mockData from "@/data/mockData.json";
import type { MockData } from "@/lib/types";

const data = mockData as unknown as MockData;

export default function SetupPage() {
  return (
    <div className="stack">
      <div>
        <h1 className="pageTitle">Configurar agente</h1>
        <p className="pageSubtitle">
          Define quién es tu agente: personalidad, objetivos, límites duros y
          qué cuenta como decisión sensible. Tú tienes el control.
        </p>
      </div>

      <div className="card">
        <h2 className="cardTitle">Perfil del agente</h2>
        <div className="field">
          <label htmlFor="displayName">Nombre o entidad</label>
          <input id="displayName" defaultValue="Valentina R." />
        </div>
        <div className="field">
          <label htmlFor="entityType">Tipo de entidad</label>
          <select id="entityType" defaultValue="persona">
            <option value="empresa">Empresa</option>
            <option value="persona">Persona</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="personality">Personalidad</label>
          <textarea
            id="personality"
            defaultValue="Amable pero firme. No comparto mi dirección ni teléfono sin un acuerdo previo."
          />
        </div>
        <div className="field">
          <label htmlFor="objectives">Objetivos</label>
          <textarea
            id="objectives"
            defaultValue={"- Vender mi auto usado sobre USD 8.000\n- Coordinar prueba de manejo en zona norte\n- Cobrar en efectivo o transferencia"}
          />
        </div>
      </div>

      <div className="card">
        <h2 className="cardTitle">Límites duros (no negociables)</h2>
        <p className="cardMeta" style={{ marginBottom: 12 }}>
          El agente nunca puede cruzar estos límites. Se validan fuera del
          modelo de lenguaje, antes de emitir cualquier mensaje.
        </p>
        <div className="list">
          <li>Precio mínimo de venta: USD 8.000</li>
          <li>Compartir dirección: requiere aprobación explícita</li>
          <li>Compartir teléfono: requiere aprobación explícita</li>
        </div>
      </div>

      <div className="card">
        <h2 className="cardTitle">
          Qué cuenta como decisión sensible
        </h2>
        <p className="cardMeta" style={{ marginBottom: 12 }}>
          Las categorías obligatorias no se pueden desactivar. Las demás las
          activas o agregas tú.
        </p>
        <div className="stack">
          <fieldset>
            <legend className="cardTitle" style={{ fontSize: 13 }}>
              Obligatorias por seguridad
            </legend>
            <div className="list">
              {data.sensitive_categories.default_required
                .filter((c) => c.required)
                .map((c) => (
                  <li key={c.id}>
                    {c.label}{" "}
                    <span className="badge badge-danger">no desactivable</span>
                  </li>
                ))}
            </div>
          </fieldset>
          <fieldset>
            <legend className="cardTitle" style={{ fontSize: 13 }}>
              A tu criterio
            </legend>
            <div className="list">
              {data.sensitive_categories.editable.map((c) => (
                <li key={c.id}>{c.label}</li>
              ))}
            </div>
          </fieldset>
        </div>
      </div>

      <div style={{ display: "flex", gap: 12 }}>
        <button className="btn btn-primary" type="button">
          Guardar configuración
        </button>
        <button className="btn" type="button">
          Cancelar
        </button>
      </div>
    </div>
  );
}
