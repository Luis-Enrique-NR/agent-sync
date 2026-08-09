import { AgentSetupForm } from "@/components/AgentSetupForm";
import { ShieldIcon } from "@/components/Icons";

export default function SetupPage() {
  return (
    <div>
      <header className="page-heading">
        <div>
          <span className="section-eyebrow">Configuración</span>
          <h1>Enséñale a tu agente cómo representarte</h1>
          <p>
            Describe qué buscas, qué nunca debe aceptar y en qué momentos debe
            detenerse para preguntarte.
          </p>
        </div>
        <aside className="page-heading-note">
          <ShieldIcon size={20} />
          <span>
            <strong>Tú defines el control.</strong>
            Los límites duros no se pueden negociar ni omitir.
          </span>
        </aside>
      </header>
      <AgentSetupForm />
    </div>
  );
}
