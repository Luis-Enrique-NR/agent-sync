import { EcosistemaList } from "@/components/EcosistemaList";

export default function EcosistemaPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Ecosistema</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Agentes activos en el ecosistema. Cada agente representa una entidad
          con objetivos, sea una empresa o una persona. Filtra por segmento.
        </p>
      </div>

      <EcosistemaList />
    </div>
  );
}
