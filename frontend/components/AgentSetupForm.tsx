"use client";

import { useState } from "react";
import mockData from "@/data/mockData.json";
import type { AgentProfile, MockData } from "@/lib/types";

const data = mockData as unknown as MockData;

const PERSONA_AGENT = data.agents.find((a) => a.entity_type === "persona");
const EMPRESA_AGENT = data.agents.find((a) => a.entity_type === "empresa");

type EntityType = "empresa" | "persona";

interface HardLimitsState {
  maxUnitPrice: string;
  minAnnualVolume: string;
  noPersonalData: boolean;
  minSalePrice: string;
  noShareAddress: boolean;
  noSharePhone: boolean;
}

interface SensitiveRules {
  [categoryId: string]: boolean;
}

function initialSensitiveRules(): SensitiveRules {
  const rules: SensitiveRules = {};
  const categories = [
    ...data.sensitive_categories.default_required,
    ...data.sensitive_categories.editable,
  ];
  for (const category of categories) {
    rules[category.id] = category.required || category.enabled;
  }
  return rules;
}

function hardLimitsFromAgent(agent: AgentProfile | undefined): HardLimitsState {
  const limits = agent?.hard_limits ?? {};
  return {
    maxUnitPrice: String(limits.max_unit_price_usd ?? ""),
    minAnnualVolume: String(limits.min_annual_volume_units ?? ""),
    noPersonalData: Boolean(limits.no_personal_data),
    minSalePrice: String(limits.min_sale_price_usd ?? ""),
    noShareAddress: Boolean(limits.no_share_address_without_approval),
    noSharePhone: Boolean(limits.no_share_phone_without_approval),
  };
}

function defaultFields(entityType: EntityType) {
  const agent = entityType === "empresa" ? EMPRESA_AGENT : PERSONA_AGENT;
  return {
    displayName: agent?.display_name ?? "",
    personality: agent?.personality ?? "",
    objectives: agent?.objectives.join("\n") ?? "",
    hardLimits: hardLimitsFromAgent(agent),
  };
}

const inputClass =
  "w-full rounded-xl border border-[var(--border)] bg-[var(--background)] px-3.5 py-2.5 text-sm text-[var(--foreground)] outline-none transition focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/30";
const labelClass =
  "mb-1.5 block text-sm font-semibold text-[var(--muted)]";

export function AgentSetupForm() {
  const [entityType, setEntityType] = useState<EntityType>("persona");
  const [displayName, setDisplayName] = useState(PERSONA_AGENT?.display_name ?? "");
  const [personality, setPersonality] = useState(PERSONA_AGENT?.personality ?? "");
  const [objectives, setObjectives] = useState(
    PERSONA_AGENT?.objectives.join("\n") ?? "",
  );
  const [hardLimits, setHardLimits] = useState<HardLimitsState>(
    hardLimitsFromAgent(PERSONA_AGENT),
  );
  const [sensitiveRules, setSensitiveRules] =
    useState<SensitiveRules>(initialSensitiveRules);
  const [saving, setSaving] = useState(false);
  const [savedProfile, setSavedProfile] = useState<unknown>(null);

  const requiredRules = data.sensitive_categories.default_required.filter(
    (c) => c.required,
  );
  const editableRules = [
    ...data.sensitive_categories.default_required.filter((c) => !c.required),
    ...data.sensitive_categories.editable,
  ];

  const changeEntityType = (type: EntityType) => {
    setEntityType(type);
    const fields = defaultFields(type);
    setDisplayName(fields.displayName);
    setPersonality(fields.personality);
    setObjectives(fields.objectives);
    setHardLimits(fields.hardLimits);
  };

  const toggleRule = (categoryId: string) => {
    setSensitiveRules((prev) => ({ ...prev, [categoryId]: !prev[categoryId] }));
  };

  const toggleLimit = (key: keyof HardLimitsState) => {
    setHardLimits((prev) => ({
      ...prev,
      [key]: typeof prev[key] === "boolean" ? !prev[key] : prev[key],
    }));
  };

  const setLimitValue = (key: keyof HardLimitsState, value: string) => {
    setHardLimits((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);

    const payload = {
      profile: {
        agent_id: `agent-${entityType}-demo`,
        entity_type: entityType,
        display_name: displayName,
        personality,
        objectives: objectives
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
        hard_limits: {
          ...(entityType === "empresa"
            ? {
                max_unit_price_usd: Number(hardLimits.maxUnitPrice) || undefined,
                min_annual_volume_units:
                  Number(hardLimits.minAnnualVolume) || undefined,
                no_personal_data: hardLimits.noPersonalData,
              }
            : {
                min_sale_price_usd: Number(hardLimits.minSalePrice) || undefined,
                no_share_address_without_approval: hardLimits.noShareAddress,
                no_share_phone_without_approval: hardLimits.noSharePhone,
              }),
        },
        sensitive_categories: {
          default_required: data.sensitive_categories.default_required.map(
            (c) => ({ ...c, enabled: sensitiveRules[c.id] ?? false }),
          ),
          editable: data.sensitive_categories.editable.map((c) => ({
            ...c,
            enabled: sensitiveRules[c.id] ?? false,
          })),
        },
      },
      consumption: {
        source: "POST /api/agents (simulado)",
        merged_with_mock: data.meta.source,
        segment: entityType === "empresa" ? "B2B" : "P2P",
        reference_session:
          entityType === "empresa"
            ? data.sessions.find((s) => s.segment === "B2B")?.session_id
            : data.sessions.find((s) => s.segment === "P2P")?.session_id,
      },
    };

    await new Promise((resolve) => setTimeout(resolve, 700));
    setSavedProfile(payload);
    setSaving(false);
  };

  return (
    <form onSubmit={handleSubmit} className="mx-auto flex max-w-3xl flex-col gap-6">
      {/* Tipo de entidad */}
      <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-base font-semibold">Tipo de entidad</h2>
        <p className="mb-4 mt-1 text-sm text-[var(--muted)]">
          El motor es el mismo para ambos. Solo cambia la data de configuración.
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {(
            [
              {
                type: "persona",
                title: "P2P — Persona",
                desc: "Vender un artículo, buscar roomie, coordinar un trueque.",
              },
              {
                type: "empresa",
                title: "B2B — Empresa",
                desc: "Buscar proveedores, distribuidores o socios comerciales.",
              },
            ] as { type: EntityType; title: string; desc: string }[]
          ).map((option) => {
            const selected = entityType === option.type;
            return (
              <button
                key={option.type}
                type="button"
                onClick={() => changeEntityType(option.type)}
                aria-pressed={selected}
                className={`rounded-xl border p-4 text-left transition ${
                  selected
                    ? "border-[var(--accent)] bg-[var(--accent)]/10 ring-2 ring-[var(--accent)]/30"
                    : "border-[var(--border)] bg-[var(--background)] hover:border-[var(--muted)]"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold">{option.title}</span>
                  <span
                    className={`grid h-5 w-5 place-items-center rounded-full border text-[10px] ${
                      selected
                        ? "border-[var(--accent)] bg-[var(--accent)] text-white"
                        : "border-[var(--border)]"
                    }`}
                  >
                    {selected ? "✓" : ""}
                  </span>
                </div>
                <p className="mt-1 text-xs text-[var(--muted)]">{option.desc}</p>
              </button>
            );
          })}
        </div>
      </section>

      {/* Perfil */}
      <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-base font-semibold">Perfil del agente</h2>
        <div className="mt-4 grid grid-cols-1 gap-4">
          <div>
            <label className={labelClass} htmlFor="displayName">
              {entityType === "empresa" ? "Nombre de la empresa" : "Nombre"}
            </label>
            <input
              id="displayName"
              className={inputClass}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={entityType === "empresa" ? "Mi empresa S.A." : "Mi nombre"}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="personality">
              Personalidad
            </label>
            <textarea
              id="personality"
              className={`${inputClass} min-h-24`}
              value={personality}
              onChange={(e) => setPersonality(e.target.value)}
              placeholder="Tono y directrices de comportamiento del agente."
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="objectives">
              Objetivos
            </label>
            <textarea
              id="objectives"
              className={`${inputClass} min-h-28`}
              value={objectives}
              onChange={(e) => setObjectives(e.target.value)}
              placeholder="Uno por línea. Ej.: vender sobre USD 8.000"
            />
          </div>
        </div>
      </section>

      {/* Límites duros */}
      <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-base font-semibold">Límites duros</h2>
        <p className="mb-4 mt-1 text-sm text-[var(--muted)]">
          No negociables. Se validan fuera del modelo de lenguaje antes de emitir
          cualquier mensaje.
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {entityType === "empresa" ? (
            <>
              <div>
                <label className={labelClass} htmlFor="maxUnitPrice">
                  Precio máximo por unidad (USD)
                </label>
                <input
                  id="maxUnitPrice"
                  type="number"
                  step="0.01"
                  min="0"
                  className={inputClass}
                  value={hardLimits.maxUnitPrice}
                  onChange={(e) => setLimitValue("maxUnitPrice", e.target.value)}
                  placeholder="4.50"
                />
              </div>
              <div>
                <label className={labelClass} htmlFor="minAnnualVolume">
                  Volumen anual mínimo (unidades)
                </label>
                <input
                  id="minAnnualVolume"
                  type="number"
                  min="0"
                  className={inputClass}
                  value={hardLimits.minAnnualVolume}
                  onChange={(e) =>
                    setLimitValue("minAnnualVolume", e.target.value)
                  }
                  placeholder="20000"
                />
              </div>
              <label className="flex items-center gap-3 text-sm">
                <input
                  type="checkbox"
                  checked={hardLimits.noPersonalData}
                  onChange={() => toggleLimit("noPersonalData")}
                  className="h-4 w-4 rounded border-[var(--border)] accent-[var(--accent)]"
                />
                No compartir datos personales
              </label>
            </>
          ) : (
            <>
              <div>
                <label className={labelClass} htmlFor="minSalePrice">
                  Precio mínimo de venta (USD)
                </label>
                <input
                  id="minSalePrice"
                  type="number"
                  step="0.01"
                  min="0"
                  className={inputClass}
                  value={hardLimits.minSalePrice}
                  onChange={(e) => setLimitValue("minSalePrice", e.target.value)}
                  placeholder="8000"
                />
              </div>
              <label className="flex items-center gap-3 text-sm">
                <input
                  type="checkbox"
                  checked={hardLimits.noShareAddress}
                  onChange={() => toggleLimit("noShareAddress")}
                  className="h-4 w-4 rounded border-[var(--border)] accent-[var(--accent)]"
                />
                No compartir dirección sin aprobación
              </label>
              <label className="flex items-center gap-3 text-sm">
                <input
                  type="checkbox"
                  checked={hardLimits.noSharePhone}
                  onChange={() => toggleLimit("noSharePhone")}
                  className="h-4 w-4 rounded border-[var(--border)] accent-[var(--accent)]"
                />
                No compartir teléfono sin aprobación
              </label>
            </>
          )}
        </div>
      </section>

      {/* Decisiones sensibles */}
      <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-base font-semibold">
          Qué situaciones se escalan a ti
        </h2>
        <p className="mb-4 mt-1 text-sm text-[var(--muted)]">
          Tú decides qué cuenta como decisión sensible. Las categorías
          obligatorias no se pueden desactivar.
        </p>

        <fieldset className="mb-5">
          <legend className="mb-2 text-xs font-bold uppercase tracking-wide text-[var(--danger)]">
            Obligatorias por seguridad
          </legend>
          <div className="flex flex-col gap-2">
            {requiredRules.map((rule) => (
              <label
                key={rule.id}
                className="flex items-center gap-3 rounded-lg bg-[var(--background)] px-3 py-2.5 text-sm"
              >
                <input
                  type="checkbox"
                  checked
                  disabled
                  className="h-4 w-4 rounded border-[var(--border)] accent-[var(--accent)]"
                />
                <span className="flex-1">{rule.label}</span>
                <span className="rounded-full bg-[var(--danger)]/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-[var(--danger)]">
                  fija
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className="mb-2 text-xs font-bold uppercase tracking-wide text-[var(--muted)]">
            A tu criterio
          </legend>
          <div className="flex flex-col gap-2">
            {editableRules.map((rule) => {
              const checked = sensitiveRules[rule.id] ?? false;
              return (
                <label
                  key={rule.id}
                  className="flex items-center gap-3 rounded-lg bg-[var(--background)] px-3 py-2.5 text-sm"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleRule(rule.id)}
                    className="h-4 w-4 rounded border-[var(--border)] accent-[var(--accent)]"
                  />
                  {rule.label}
                </label>
              );
            })}
          </div>
        </fieldset>
      </section>

      <div className="flex items-center gap-4">
        <button
          type="submit"
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent)] px-5 py-2.5 text-sm font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? "Guardando..." : "Guardar configuración"}
        </button>
        <p className="text-xs text-[var(--muted)]">
          Simula un POST a <code className="font-mono">/api/agents</code> con los
          datos del mock inicial.
        </p>
      </div>

      {savedProfile ? (
        <section className="rounded-2xl border border-[var(--accent-2)]/40 bg-[var(--accent-2)]/10 p-6">
          <h2 className="text-base font-semibold text-[var(--accent-2)]">
            Perfil simulado guardado
          </h2>
          <p className="mb-4 mt-1 text-sm text-[var(--muted)]">
            El payload fue consumido con éxito. Fusión de referencia con el mock:
            {JSON.stringify((savedProfile as { consumption: { segment: string; reference_session?: string } }).consumption, null, 2) ? (
              <span className="font-mono">
                {" "}
                {String((savedProfile as { consumption: { segment: string; reference_session?: string } }).consumption.segment)} ·{" "}
                {String((savedProfile as { consumption: { segment: string; reference_session?: string } }).consumption.reference_session)}
              </span>
            ) : null}
          </p>
          <pre className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--background)] p-4 text-xs leading-relaxed text-[var(--muted)]">
            {JSON.stringify(savedProfile, null, 2)}
          </pre>
        </section>
      ) : null}
    </form>
  );
}
