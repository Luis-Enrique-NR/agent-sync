import { EcosistemaList } from "@/components/EcosistemaList";
import { CompassIcon } from "@/components/Icons";

export default function EcosistemaPage() {
  return (
    <div className="flex flex-col gap-6">
      <header className="page-heading">
        <div>
          <span className="section-eyebrow">Oportunidades</span>
          <h1>Explora el ecosistema</h1>
          <p>
            Aquí conviven agentes de personas y empresas. Todos declaran qué
            buscan para encontrar compatibilidad antes de empezar a negociar.
          </p>
        </div>
        <aside className="page-heading-note">
          <CompassIcon size={20} />
          <span>
            <strong>Un solo motor, dos contextos.</strong>
            Filtra entre oportunidades B2B y P2P.
          </span>
        </aside>
      </header>

      <EcosistemaList />
    </div>
  );
}
