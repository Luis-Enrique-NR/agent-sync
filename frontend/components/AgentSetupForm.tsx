"use client";

import { useMemo, useState } from "react";
import mockData from "@/data/mockData.json";
import type {
  AgentProfile,
  EscalationRule,
  MockData,
  SensitiveCategory,
  SensitiveDataCategory,
} from "@/lib/types";
import { useAgentSync } from "@/lib/store";

const data = mockData as unknown as MockData;

const PERSON_AGENT = data.agents.find((a) => a.entity_type === "person");
const COMPANY_AGENT = data.agents.find((a) => a.entity_type === "company");

type EntityType = "company" | "person";

interface HardLimitsState {
  maxUnitPrice: string;
  minAnnualVolume: string;
  minSalePrice: string;
  noPersonalData: boolean;
  noShareAddress: boolean;
  noSharePhone: boolean;
}

interface SensitiveRules {
  [categoryId: string]: boolean;
}

function allCategories(): SensitiveCategory[] {
  return [
    ...data.sensitive_categories.default_required,
    ...data.sensitive_categories.editable,
  ];
}

function initialSensitiveRules(): SensitiveRules {
  const rules: SensitiveRules = {};
  for (const category of allCategories()) {
    rules[category.id] = category.required || category.enabled;
  }
  return rules;
}

function hardLimitsFromAgent(agent: AgentProfile | undefined): HardLimitsState {
  const limits = agent?.hard_limits ?? [];
  const valueOf = (key: string) =>
    String(limits.find((l) => l.key === key)?.value ?? "");
  const disclose = (category: SensitiveDataCategory) =>
    (agent?.never_disclose ?? []).includes(category);
  return {
    maxUnitPrice: valueOf("max_unit_price_usd"),
    minAnnualVolume: valueOf("min_annual_volume_units"),
    minSalePrice: valueOf("min_sale_price_usd"),
    noPersonalData: disclose("EMAIL"),
    noShareAddress: disclose("EXACT_ADDRESS"),
    noSharePhone: disclose("PHONE"),
  };
}

function defaultFields(entityType: EntityType) {
  const agent = entityType === "company" ? COMPANY_AGENT : PERSON_AGENT;
  return {
    displayName: agent?.display_name ?? "",
    publicDescription: agent?.public_description ?? "",
    personality: agent?.personality ?? "",
    objectives: agent?.objectives.join("\n") ?? "",
    interests: agent?.interests.join("\n") ?? "",
    capabilities: agent?.capabilities.join("\n") ?? "",
    hardLimits: hardLimitsFromAgent(agent),
  };
}

const inputClass =
  "w-full rounded-xl border border-[var(--border)] bg-[var(--background)] px-3.5 py-2.5 text-sm text-[var(--foreground)] outline-none transition focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/30";
const labelClass = "mb-1.5 block text-sm font-semibold text-[var(--muted)]";

export function AgentSetupForm() {
  const { registerAgent } = useAgentSync();
  const [entityType, setEntityType] = useState<EntityType>("person");
  const [displayName, setDisplayName] = useState(PERSON_AGENT?.display_name ?? "");
  const [publicDescription, setPublicDescription] = useState(
    PERSON_AGENT?.public_description ?? "",
  );
  const [personality, setPersonality] = useState(PERSON_AGENT?.personality ?? "");
  const [objectives, setObjectives] = useState(
    PERSON_AGENT?.objectives.join("\n") ?? "",
  );
  const [interests, setInterests] = useState(
    PERSON_AGENT?.interests.join("\n") ?? "",
  );
  const [capabilities, setCapabilities] = useState(
    PERSON_AGENT?.capabilities.join("\n") ?? "",
  );
  const [hardLimits, setHardLimits] = useState<HardLimitsState>(
    hardLimitsFromAgent(PERSON_AGENT),
  );
  const [sensitiveRules, setSensitiveRules] =
    useState<SensitiveRules>(initialSensitiveRules);
  const [amountThreshold, setAmountThreshold] = useState("10000");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<{
    agent_id: string;
    entity_type: EntityType;
    matches: number;
    event: string;
    profile: AgentProfile;
  } | null>(null);

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
    setPublicDescription(fields.publicDescription);
    setPersonality(fields.personality);
    setObjectives(fields.objectives);
    setInterests(fields.interests);
    setCapabilities(fields.capabilities);
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

  const buildEscalationRules = useMemo(
    (): EscalationRule[] => {
      const rules: EscalationRule[] = [];
      for (const category of allCategories()) {
        if (!sensitiveRules[category.id]) continue;
        rules.push({
          rule_id: `esc-${category.id}`,
          rule_type: category.ruleType,
          key: category.ruleType === "AMOUNT_ABOVE" ? category.key ?? "amount" : category.key,
          threshold:
            category.ruleType === "AMOUNT_ABOVE"
              ? Number(amountThreshold) || category.threshold
              : category.threshold,
          categories: category.categories ?? [],
          action_types:
            category.ruleType === "REQUEST_ACTION" ? ["OTHER"] : [],
          enabled: true,
        });
      }
      return rules;
    },
    [sensitiveRules, amountThreshold],
  );

  const buildNeverDisclose = useMemo((): SensitiveDataCategory[] => {
    const categories = new Set<SensitiveDataCategory>();
    if (hardLimits.noPersonalData) categories.add("EMAIL");
    if (hardLimits.noShareAddress) categories.add("EXACT_ADDRESS");
    if (hardLimits.noSharePhone) categories.add("PHONE");
    return [...categories];
  }, [hardLimits]);

  const buildProfile = (): AgentProfile => ({
    agent_id: `agent-${entityType}-${Date.now().toString(36)}`,
    display_name: displayName,
    entity_type: entityType,
    public_description: publicDescription,
    personality,
    objectives: objectives
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
    interests: interests
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
    capabilities: capabilities
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
    hard_limits:
      entityType === "company"
        ? [
            {
              key: "max_unit_price_usd",
              operator: "lte",
              value: Number(hardLimits.maxUnitPrice) || 0,
              unit: "usd",
            },
            {
              key: "min_annual_volume_units",
              operator: "gte",
              value: Number(hardLimits.minAnnualVolume) || 0,
              unit: "units",
            },
          ]
        : [
            {
              key: "min_sale_price_usd",
              operator: "gte",
              value: Number(hardLimits.minSalePrice) || 0,
              unit: "usd",
            },
          ],
    never_disclose: buildNeverDisclose,
    escalation_rules: buildEscalationRules,
    status: "AVAILABLE",
    logistics_preferences: [],
    tool_grants: [],
    goal_completion_mode: "ONE_SHOT",
    remaining_goal_units: null,
  });

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);

    const profile = buildProfile();
    const matches = registerAgent(profile);

    // Simula el round-trip POST /api/agents → worker → evento agent.registered
    await new Promise((resolve) => setTimeout(resolve, 700));
    setSaved({
      agent_id: profile.agent_id,
      entity_type: profile.entity_type,
      matches,
      event: "agent.registered",
      profile,
    });
    setSaving(false);
  };

  return (
    <form onSubmit={handleSubmit} className="setup-form mx-auto flex max-w-4xl flex-col gap-6">
      {/* Tipo de entidad */}
      <section className="setup-section rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-base font-semibold">¿A quién representará?</h2>
        <p className="mb-4 mt-1 text-sm text-[var(--muted)]">
          Elige el contexto para adaptar los ejemplos y las reglas de la negociación.
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {(
            [
              {
                type: "person",
                segment: "P2P",
                title: "A una persona",
                desc: "Vender un artículo, buscar roomie, coordinar un trueque.",
              },
              {
                type: "company",
                segment: "B2B",
                title: "A una empresa",
                desc: "Buscar proveedores, distribuidores o socios comerciales.",
              },
            ] as {
              type: EntityType;
              segment: string;
              title: string;
              desc: string;
            }[]
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
      <section className="setup-section rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-base font-semibold">¿Cómo debe actuar?</h2>
        <div className="mt-4 grid grid-cols-1 gap-4">
          <div>
            <label className={labelClass} htmlFor="displayName">
              {entityType === "company" ? "Nombre de la empresa" : "Nombre"}
            </label>
            <input
              id="displayName"
              className={inputClass}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={entityType === "company" ? "Mi empresa S.A." : "Mi nombre"}
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="publicDescription">
              Descripción pública
            </label>
            <input
              id="publicDescription"
              className={inputClass}
              value={publicDescription}
              onChange={(e) => setPublicDescription(e.target.value)}
              placeholder="Una línea visible para el resto del ecosistema."
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="personality">
              Cómo quieres que se comunique
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
              Qué quieres conseguir (un objetivo por línea)
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

      {/* Tags: interests ∩ capabilities (motor agnóstico B2B/P2P) */}
      <section className="setup-section rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-base font-semibold">¿Qué buscas y qué ofreces?</h2>
        <p className="mb-4 mt-1 text-sm text-[var(--muted)]">
          Usaremos estas etiquetas para encontrar agentes compatibles en ambas
          direcciones. Escribe una por línea.
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className={labelClass} htmlFor="interests">
              Estoy buscando…
            </label>
            <textarea
              id="interests"
              className={`${inputClass} min-h-28`}
              value={interests}
              onChange={(e) => setInterests(e.target.value)}
              placeholder="comprar tela organica&#10;descuentos por volumen"
            />
          </div>
          <div>
            <label className={labelClass} htmlFor="capabilities">
              Puedo ofrecer…
            </label>
            <textarea
              id="capabilities"
              className={`${inputClass} min-h-28`}
              value={capabilities}
              onChange={(e) => setCapabilities(e.target.value)}
              placeholder="venta de tela organica&#10;contratos de suministro"
            />
          </div>
        </div>
      </section>

      {/* Límites duros (NumericLimit[]) */}
      <section className="setup-section rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-base font-semibold">¿Qué nunca debe cruzar?</h2>
        <p className="mb-4 mt-1 text-sm text-[var(--muted)]">
          Estas reglas no son negociables. Se comprueban antes de que el agente
          envíe cualquier respuesta.
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {entityType === "company" ? (
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

      {/* Reglas de escalamiento humano (EscalationRule[]) */}
      <section className="setup-section rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-base font-semibold">
          ¿Cuándo debe preguntarte?
        </h2>
        <p className="mb-4 mt-1 text-sm text-[var(--muted)]">
          Cada opción activa pausará la conversación para que tú tomes la decisión.
        </p>

        <fieldset className="mb-5">
          <legend className="mb-2 text-xs font-bold uppercase tracking-wide text-[var(--danger)]">
            Siempre requieren tu aprobación
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
            También quiero revisar
          </legend>
          <div className="flex flex-col gap-2">
            {editableRules.map((rule) => {
              const checked = sensitiveRules[rule.id] ?? false;
              return (
                <div key={rule.id}>
                  <label className="flex items-center gap-3 rounded-lg bg-[var(--background)] px-3 py-2.5 text-sm">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleRule(rule.id)}
                      className="h-4 w-4 rounded border-[var(--border)] accent-[var(--accent)]"
                    />
                    <span className="flex-1">{rule.label}</span>
                  </label>
                  {checked && rule.ruleType === "AMOUNT_ABOVE" ? (
                    <div className="px-11 pb-2">
                      <label className={labelClass} htmlFor="amountThreshold">
                        Umbral (USD)
                      </label>
                      <input
                        id="amountThreshold"
                        type="number"
                        min="0"
                        className={inputClass}
                        value={amountThreshold}
                        onChange={(e) => setAmountThreshold(e.target.value)}
                      />
                    </div>
                  ) : null}
                </div>
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
          {saving ? "Registrando agente…" : "Registrar agente"}
        </button>
        <p className="text-xs text-[var(--muted)]">
          En esta demo, el agente se registra y empieza a buscar compatibilidad automáticamente.
        </p>
      </div>

      {saved ? (
        <section className="rounded-2xl border border-[var(--accent-2)]/40 bg-[var(--accent-2)]/10 p-6">
          <h2 className="text-base font-semibold text-[var(--accent-2)]">
            Listo: tu agente ya está en el ecosistema
          </h2>
          <p className="mb-4 mt-1 text-sm text-[var(--muted)]">
            Encontramos{" "}
            <strong>
              {saved.matches === 0
                ? "0 candidatos compatibles"
                : `${saved.matches} candidato${saved.matches === 1 ? "" : "s"} compatible${saved.matches === 1 ? "" : "s"}`}
            </strong>
            . Cada coincidencia abre una conversación privada lista para negociar.
            Revísalo en{" "}
            <a href="/ecosistema" className="text-[var(--accent)] hover:underline">
              el ecosistema
            </a>
            .
          </p>
          <details className="rounded-xl border border-[var(--border)] bg-[var(--background)] p-4">
            <summary className="cursor-pointer text-sm font-semibold">
              Ver detalles técnicos de la simulación
            </summary>
            <pre className="mt-3 overflow-x-auto text-xs leading-relaxed text-[var(--muted)]">
              {JSON.stringify(saved.profile, null, 2)}
            </pre>
          </details>
        </section>
      ) : null}
    </form>
  );
}
