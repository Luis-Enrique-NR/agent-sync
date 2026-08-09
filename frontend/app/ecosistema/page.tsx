import { EcosistemaList } from "@/components/EcosistemaList";
import { CompassIcon } from "@/components/Icons";

export default function EcosistemaPage() {
  return (
    <div className="flex flex-col gap-6">
      <header className="page-heading">
        <div>
          <span className="section-eyebrow">Oportunidades a tu alcance</span>
          <h1>Explora solo lo que puede avanzar</h1>
          <p>
            Tu agente cruza objetivos, límites y alcance antes de mostrarte a
            alguien. Así cada resultado tiene una ruta real para conversar.
          </p>
        </div>
        <aside className="page-heading-note">
          <CompassIcon size={20} />
          <span>
            <strong>La cercanía no revela tu ubicación.</strong>
            Solo mostramos zonas aproximadas y opciones logísticamente viables.
          </span>
        </aside>
      </header>

      <EcosistemaList />
    </div>
  );
}
