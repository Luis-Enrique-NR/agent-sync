import { AgentSetupForm } from "@/components/AgentSetupForm";

export default function SetupPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Configurar agente</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Define quién es tu agente: personalidad, objetivos, límites duros y qué
          cuenta como decisión sensible. Tú tienes el control.
        </p>
      </div>
      <AgentSetupForm />
    </div>
  );
}
