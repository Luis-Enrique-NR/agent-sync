"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import mockData from "@/data/mockData.json";
import {
  ArrowRightIcon,
  CheckIcon,
  ShieldIcon,
  SlidersIcon,
  SparkIcon,
  UserIcon,
} from "@/components/Icons";
import { useAuth } from "@/lib/auth";
import { belongsToAgent } from "@/lib/demo";
import { useAgentSync } from "@/lib/store";
import type {
  AgentObjectiveContext,
  AgentProfile,
  AgentTool,
  EscalationRule,
  MockData,
  SensitiveCategory,
  SensitiveDataCategory,
} from "@/lib/types";

const data = mockData as unknown as MockData;
const PERSON_AGENT = data.agents.find((agent) => agent.entity_type === "person");
const COMPANY_AGENT = data.agents.find((agent) => agent.entity_type === "company");

const TOOL_OPTIONS: AgentTool[] = [
  {
    id: "busqueda",
    name: "Búsqueda de oportunidades",
    simulated: true,
    notes: "Encuentra ofertas y referencias públicas compatibles.",
  },
  {
    id: "calendario",
    name: "Disponibilidad de calendario",
    simulated: true,
    notes: "Consulta horarios libres; reservar siempre requiere aprobación.",
  },
  {
    id: "avaluo",
    name: "Precios de referencia",
    simulated: true,
    notes: "Compara valores de mercado sin alterar las condiciones de tus objetivos.",
  },
  {
    id: "inventario",
    name: "Inventario o disponibilidad",
    simulated: true,
    notes: "Verifica existencias antes de confirmar una propuesta.",
  },
];

const PERSON_INTEREST_SUGGESTIONS = [
  "venta entre personas",
  "ofertas cercanas",
  "prueba o encuentro",
  "pago seguro",
];
const COMPANY_INTEREST_SUGGESTIONS = [
  "nuevos proveedores",
  "compras por volumen",
  "alianzas comerciales",
  "distribución",
];
const PERSON_CAPABILITY_SUGGESTIONS = [
  "venta de artículos",
  "disponibilidad flexible",
  "entrega local",
  "pago inmediato",
];
const COMPANY_CAPABILITY_SUGGESTIONS = [
  "contratos de suministro",
  "ventas por volumen",
  "servicios profesionales",
  "logística nacional",
];

type EntityType = "company" | "person";
type EditSection = "objectives" | "safety" | "tools";

interface SensitiveRules {
  [categoryId: string]: boolean;
}

interface ConfigurationDraft {
  entityType: EntityType;
  displayName: string;
  publicDescription: string;
  personality: string;
  objectiveContexts: AgentObjectiveContext[];
  neverDisclose: SensitiveDataCategory[];
  sensitiveRules: SensitiveRules;
  amountThreshold: string;
  enabledTools: string[];
}

function createObjectiveContext(
  goal = "",
  options?: Partial<AgentObjectiveContext>,
): AgentObjectiveContext {
  return {
    objective_id:
      options?.objective_id ?? `objective-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`,
    goal,
    seeks: [...(options?.seeks ?? [])],
    offers: [...(options?.offers ?? [])],
    negotiation_context: options?.negotiation_context ?? "",
  };
}

function objectiveContextsFromAgent(agent?: AgentProfile): AgentObjectiveContext[] {
  if (agent?.objective_contexts?.length) {
    return agent.objective_contexts.map((objective) =>
      createObjectiveContext(objective.goal, objective),
    );
  }

  if (agent?.objectives.length) {
    return agent.objectives.map((goal, index) =>
      createObjectiveContext(goal, {
        objective_id: `${agent.agent_id}-objective-${index + 1}`,
        seeks: index === 0 ? agent.interests : [],
        offers: index === 0 ? agent.capabilities : [],
      }),
    );
  }

  return [createObjectiveContext()];
}

function allCategories(): SensitiveCategory[] {
  return [
    ...data.sensitive_categories.default_required,
    ...data.sensitive_categories.editable,
  ];
}

function rulesFromAgent(agent?: AgentProfile): SensitiveRules {
  const rules: SensitiveRules = {};

  for (const category of allCategories()) {
    const configured = agent?.escalation_rules.some((rule) => {
      if (rule.rule_type !== category.ruleType) return false;
      if (!category.categories?.length) return true;
      return category.categories.some((item) => rule.categories.includes(item));
    });
    rules[category.id] = category.required || configured || (!agent && category.enabled);
  }

  return rules;
}

function draftFromAgent(
  agent: AgentProfile | undefined,
  fallbackType: EntityType = "person",
): ConfigurationDraft {
  const entityType = agent?.entity_type ?? fallbackType;
  const threshold = agent?.escalation_rules.find(
    (rule) => rule.rule_type === "AMOUNT_ABOVE",
  )?.threshold;

  return {
    entityType,
    displayName: agent?.display_name ?? "",
    publicDescription: agent?.public_description ?? "",
    personality:
      agent?.personality ??
      "Claro, respetuoso y directo. Explica sus razones y nunca presiona a la otra parte.",
    objectiveContexts: objectiveContextsFromAgent(agent),
    neverDisclose: [...(agent?.never_disclose ?? [])],
    sensitiveRules: rulesFromAgent(agent),
    amountThreshold: String(threshold ?? 10000),
    enabledTools: agent?.tools.map((tool) => tool.id) ?? ["busqueda"],
  };
}

function escalationRulesFromDraft(draft: ConfigurationDraft): EscalationRule[] {
  return allCategories()
    .filter((category) => draft.sensitiveRules[category.id])
    .map((category) => ({
      rule_id: `esc-${category.id}`,
      rule_type: category.ruleType,
      key:
        category.ruleType === "AMOUNT_ABOVE"
          ? category.key ?? "amount"
          : category.key,
      threshold:
        category.ruleType === "AMOUNT_ABOVE"
          ? Number(draft.amountThreshold) || category.threshold
          : category.threshold,
      categories: category.categories ?? [],
      enabled: true,
    }));
}

function profileFromDraft(
  draft: ConfigurationDraft,
  options?: {
    agentId?: string;
    status?: AgentProfile["status"];
    previous?: AgentProfile;
  },
): AgentProfile {
  const objectiveContexts = draft.objectiveContexts
    .map((objective) => ({
      ...objective,
      goal: objective.goal.trim(),
      seeks: objective.seeks.map((item) => item.trim()).filter(Boolean),
      offers: objective.offers.map((item) => item.trim()).filter(Boolean),
      negotiation_context: objective.negotiation_context.trim(),
    }))
    .filter((objective) => objective.goal);
  const uniqueSignals = (values: string[]) => [...new Set(values)];

  return {
    agent_id:
      options?.agentId ?? `agent-${draft.entityType}-${Date.now().toString(36)}`,
    display_name: draft.displayName.trim() || "Mi agente",
    entity_type: draft.entityType,
    public_description:
      draft.publicDescription.trim() || "Agente configurado en AgentSync.",
    personality: draft.personality.trim(),
    objectives: objectiveContexts.map((objective) => objective.goal),
    interests: uniqueSignals(objectiveContexts.flatMap((objective) => objective.seeks)),
    capabilities: uniqueSignals(objectiveContexts.flatMap((objective) => objective.offers)),
    objective_contexts: objectiveContexts,
    hard_limits: [],
    never_disclose: draft.neverDisclose,
    escalation_rules: escalationRulesFromDraft(draft),
    status: options?.status ?? "AVAILABLE",
    price_range: options?.previous?.price_range ?? null,
    logistics_preferences: options?.previous?.logistics_preferences ?? [],
    tools: TOOL_OPTIONS.filter((tool) => draft.enabledTools.includes(tool.id)),
  };
}

function ObjectivesEditor({
  objectiveContexts,
  entityType,
  onChange,
}: {
  objectiveContexts: AgentObjectiveContext[];
  entityType: EntityType;
  onChange: (objectiveContexts: AgentObjectiveContext[]) => void;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(
    () => objectiveContexts[0]?.objective_id ?? null,
  );
  const updateObjective = (
    objectiveId: string,
    patch: Partial<AgentObjectiveContext>,
  ) => {
    onChange(
      objectiveContexts.map((objective) =>
        objective.objective_id === objectiveId
          ? { ...objective, ...patch }
          : objective,
      ),
    );
  };

  return (
    <div className="objective-editor">
      <div className="field-heading">
        <div>
          <strong>Objetivos con contexto propio</strong>
          <span>Cada ruta separa lo que necesitas recibir de lo que autorizas a proponer.</span>
        </div>
        <span className="field-count">{objectiveContexts.length} activos</span>
      </div>

      <div className="objective-brief-list">
        {objectiveContexts.map((objective, index) => {
          const isOpen = expandedId === objective.objective_id;
          const signalCount = objective.seeks.length + objective.offers.length;
          return (
            <article
              className={`objective-brief ${isOpen ? "is-open" : ""}`}
              key={objective.objective_id}
            >
              <div className="objective-brief-summary">
                <span className="objective-brief-index">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <button
                  type="button"
                  className="objective-brief-toggle"
                  onClick={() => setExpandedId(isOpen ? null : objective.objective_id)}
                  aria-expanded={isOpen}
                >
                  <span>
                    <strong>{objective.goal.trim() || "Objetivo sin título"}</strong>
                    <small>
                      {signalCount > 0
                        ? `${objective.seeks.length} requisitos · ${objective.offers.length} aportes`
                        : "Define ambos lados del posible acuerdo"}
                    </small>
                  </span>
                  <i>{isOpen ? "Cerrar" : "Editar"}</i>
                </button>
                <button
                  type="button"
                  className="objective-brief-remove"
                  onClick={() => {
                    const next = objectiveContexts.filter(
                      (item) => item.objective_id !== objective.objective_id,
                    );
                    onChange(next);
                    if (isOpen) setExpandedId(next[0]?.objective_id ?? null);
                  }}
                  disabled={objectiveContexts.length === 1}
                  aria-label={`Eliminar objetivo ${index + 1}`}
                >
                  ×
                </button>
              </div>

              {isOpen ? (
                <div className="objective-brief-fields">
                  <label className="objective-goal-field">
                    <span>
                      <strong>Qué quieres lograr</strong>
                      <small>Una meta concreta que pueda explorar de forma independiente.</small>
                    </span>
                    <input
                      value={objective.goal}
                      onChange={(event) =>
                        updateObjective(objective.objective_id, { goal: event.target.value })
                      }
                      placeholder="Ej. Encontrar un proveedor para 20.000 unidades"
                      aria-label={`Meta del objetivo ${index + 1}`}
                    />
                  </label>

                  <div className="objective-exchange-intro">
                    <strong>Las dos partes del acuerdo</strong>
                    <span>Tu agente busca una coincidencia entre lo que necesitas y lo que estás dispuesto a aportar.</span>
                  </div>

                  <div className="objective-exchange-grid">
                    <TagEditor
                      eyebrow="La otra parte"
                      label="Lo que necesitas recibir"
                      helper="Requisitos que la oportunidad debe cumplir para servirte."
                      placeholder="Ej. proveedor certificado"
                      variant="seeking"
                      values={objective.seeks}
                      suggestions={
                        entityType === "company"
                          ? COMPANY_INTEREST_SUGGESTIONS
                          : PERSON_INTEREST_SUGGESTIONS
                      }
                      onChange={(seeks) =>
                        updateObjective(objective.objective_id, { seeks })
                      }
                    />
                    <div className="objective-exchange-connector" aria-hidden="true">
                      <span>Debe encajar con</span>
                      <i>
                        <svg viewBox="0 0 24 24" fill="none">
                          <path d="M4 8h15m0 0-3-3m3 3-3 3" />
                          <path d="M20 16H5m0 0 3-3m-3 3 3 3" />
                        </svg>
                      </i>
                    </div>
                    <TagEditor
                      eyebrow="Tu lado"
                      label="Lo que puedes aportar"
                      helper="Condiciones, recursos o capacidades que autorizas a proponer."
                      placeholder="Ej. contrato por 12 meses"
                      variant="offering"
                      values={objective.offers}
                      suggestions={
                        entityType === "company"
                          ? COMPANY_CAPABILITY_SUGGESTIONS
                          : PERSON_CAPABILITY_SUGGESTIONS
                      }
                      onChange={(offers) =>
                        updateObjective(objective.objective_id, { offers })
                      }
                    />
                  </div>

                  <label className="objective-context-field">
                    <span>
                      <strong>Contexto útil para negociar</strong>
                      <small>Incluye los límites propios de esta ruta: precio, cantidad, fechas, ubicación, calidad o cualquier condición que no deba cruzar.</small>
                    </span>
                    <textarea
                      value={objective.negotiation_context}
                      onChange={(event) =>
                        updateObjective(objective.objective_id, {
                          negotiation_context: event.target.value,
                        })
                      }
                      placeholder="Ej. Máximo PEN 2,80 por unidad; necesito 300 al mes y entrega local antes del día 5."
                    />
                  </label>
                </div>
              ) : null}
            </article>
          );
        })}
      </div>

      <button
        type="button"
        className="add-objective"
        onClick={() => {
          const objective = createObjectiveContext();
          onChange([...objectiveContexts, objective]);
          setExpandedId(objective.objective_id);
        }}
        disabled={objectiveContexts.length >= 20}
      >
        <span>+</span> Añadir otro objetivo
      </button>
    </div>
  );
}

function TagEditor({
  eyebrow,
  label,
  helper,
  placeholder,
  variant,
  values,
  suggestions,
  onChange,
}: {
  eyebrow?: string;
  label: string;
  helper: string;
  placeholder?: string;
  variant?: "seeking" | "offering";
  values: string[];
  suggestions: string[];
  onChange: (values: string[]) => void;
}) {
  const [input, setInput] = useState("");

  const addValue = (candidate: string) => {
    const value = candidate.trim();
    if (!value || values.includes(value)) return;
    onChange([...values, value]);
    setInput("");
  };

  return (
    <div className={`tag-editor ${variant ? `is-${variant}` : ""}`}>
      <label>
        {eyebrow ? <span className="tag-editor-eyebrow">{eyebrow}</span> : null}
        <strong>{label}</strong>
        <span>{helper}</span>
      </label>
      <div className="tag-input-wrap">
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === ",") {
              event.preventDefault();
              addValue(input);
            }
          }}
          placeholder={placeholder ?? "Escribe y presiona Enter"}
        />
        <button type="button" onClick={() => addValue(input)} aria-label={`Añadir ${label}`}>
          +
        </button>
      </div>
      <div className="tag-list" aria-label={`${label} seleccionados`}>
        {values.map((value) => (
          <button
            type="button"
            key={value}
            onClick={() => onChange(values.filter((item) => item !== value))}
            title="Quitar"
          >
            {value} <span>×</span>
          </button>
        ))}
      </div>
      <div className="tag-suggestions">
        {suggestions
          .filter((suggestion) => !values.includes(suggestion))
          .slice(0, 3)
          .map((suggestion) => (
            <button type="button" key={suggestion} onClick={() => addValue(suggestion)}>
              + {suggestion}
            </button>
          ))}
      </div>
    </div>
  );
}

function ToolSelector({
  enabledTools,
  onChange,
}: {
  enabledTools: string[];
  onChange: (enabledTools: string[]) => void;
}) {
  return (
    <div className="tool-selector">
      {TOOL_OPTIONS.map((tool) => {
        const enabled = enabledTools.includes(tool.id);
        return (
          <button
            type="button"
            key={tool.id}
            className={enabled ? "is-enabled" : ""}
            aria-pressed={enabled}
            onClick={() =>
              onChange(
                enabled
                  ? enabledTools.filter((toolId) => toolId !== tool.id)
                  : [...enabledTools, tool.id],
              )
            }
          >
            <span className="tool-check">{enabled ? <CheckIcon size={14} /> : null}</span>
            <span>
              <strong>{tool.name}</strong>
              <small>{tool.notes}</small>
            </span>
            <em>{tool.simulated ? "Demo" : "Conectado"}</em>
          </button>
        );
      })}
    </div>
  );
}

function SafetyFields({
  draft,
  onChange,
}: {
  draft: ConfigurationDraft;
  onChange: (draft: ConfigurationDraft) => void;
}) {
  const requiredRules = data.sensitive_categories.default_required.filter(
    (category) => category.required,
  );
  const editableRules = [
    ...data.sensitive_categories.default_required.filter((category) => !category.required),
    ...data.sensitive_categories.editable,
  ];
  const privateOptions: {
    category: SensitiveDataCategory;
    label: string;
  }[] = [
    { category: "PHONE", label: "Mi teléfono" },
    { category: "EMAIL", label: "Mi correo personal" },
    { category: "EXACT_ADDRESS", label: "Mi dirección exacta" },
    { category: "LIVE_LOCATION", label: "Mi ubicación en tiempo real" },
  ];

  return (
    <div className="safety-grid">
      <section className="safety-block is-hard">
        <div className="safety-block-heading">
          <ShieldIcon size={19} />
          <div>
            <strong>Datos que siempre protege</strong>
            <span>Estas reglas sí se aplican a todos tus objetivos.</span>
          </div>
        </div>

        <div className="privacy-options">
          <span className="mini-label">No compartir nunca</span>
          {privateOptions.map((option) => {
            const checked = draft.neverDisclose.includes(option.category);
            return (
              <label key={option.category}>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() =>
                    onChange({
                      ...draft,
                      neverDisclose: checked
                        ? draft.neverDisclose.filter((item) => item !== option.category)
                        : [...draft.neverDisclose, option.category],
                    })
                  }
                />
                <span>{option.label}</span>
              </label>
            );
          })}
          <p>Si lo bloqueas aquí, el agente no podrá compartirlo aunque luego lo apruebes.</p>
        </div>
      </section>

      <section className="safety-block is-approval">
        <div className="safety-block-heading">
          <UserIcon size={19} />
          <div>
            <strong>Debe preguntarte antes de</strong>
            <span>La conversación espera hasta que respondas.</span>
          </div>
        </div>

        <div className="approval-options">
          {requiredRules.map((rule) => (
            <div className="approval-row is-required" key={rule.id}>
              <span className="approval-check"><CheckIcon size={13} /></span>
              <span>{rule.label}</span>
              <small>Siempre</small>
            </div>
          ))}
          {editableRules.map((rule) => {
            const checked = draft.sensitiveRules[rule.id] ?? false;
            return (
              <div key={rule.id}>
                <label className="approval-row">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() =>
                      onChange({
                        ...draft,
                        sensitiveRules: {
                          ...draft.sensitiveRules,
                          [rule.id]: !checked,
                        },
                      })
                    }
                  />
                  <span>{rule.label}</span>
                </label>
                {checked && rule.ruleType === "AMOUNT_ABOVE" ? (
                  <label className="threshold-field">
                    <span>Consultarme desde (USD)</span>
                    <input
                      type="number"
                      min="0"
                      value={draft.amountThreshold}
                      onChange={(event) =>
                        onChange({ ...draft, amountThreshold: event.target.value })
                      }
                    />
                  </label>
                ) : null}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function CreationWizard({ ownerName }: { ownerName: string }) {
  const { registerAgent } = useAgentSync();
  const { attachAgent } = useAuth();
  const initialSeed = PERSON_AGENT ?? COMPANY_AGENT;
  const [draft, setDraft] = useState<ConfigurationDraft>(() => {
    const initial = draftFromAgent(initialSeed, "person");
    return {
      ...initial,
      displayName: ownerName || initial.displayName,
      neverDisclose: [],
    };
  });
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);

  const steps = [
    { title: "Representación", copy: "Quién es y cómo se presenta" },
    { title: "Objetivos", copy: "Qué explora en paralelo" },
    { title: "Control", copy: "Privacidad y decisiones" },
    { title: "Recursos", copy: "Qué puede consultar" },
  ];

  const validObjectives = draft.objectiveContexts.filter((objective) =>
    objective.goal.trim(),
  );
  const canContinue =
    step === 0
      ? Boolean(draft.displayName.trim() && draft.publicDescription.trim())
      : step === 1
        ? validObjectives.length > 0
        : true;

  const changeEntityType = (entityType: EntityType) => {
    const seed = entityType === "company" ? COMPANY_AGENT : PERSON_AGENT;
    const next = draftFromAgent(seed, entityType);
    setDraft({
      ...next,
      displayName:
        entityType === "person" && ownerName ? ownerName : next.displayName,
      neverDisclose: [],
    });
  };

  const activateAgent = async () => {
    if (saving || validObjectives.length === 0) return;
    setSaving(true);
    const profile = profileFromDraft({
      ...draft,
      objectiveContexts: validObjectives,
    });
    registerAgent(profile);
    await new Promise((resolve) => setTimeout(resolve, 650));
    attachAgent(profile.agent_id);
    setSaving(false);
  };

  return (
    <div className="agent-workspace is-onboarding">
      <header className="agent-workspace-heading">
        <div>
          <span className="section-eyebrow">Tu primer agente</span>
          <h1>Configura cómo te representará</h1>
          <p>
            Dale varios objetivos, agrega las condiciones de cada uno y deja que
            explore cada ruta por separado.
          </p>
        </div>
        <aside>
          <SparkIcon size={19} />
          <span>
            <strong>De 1 a varios objetivos.</strong>
            Tres suele ser un buen punto de partida.
          </span>
        </aside>
      </header>

      <div className="setup-wizard-shell">
        <nav className="setup-stepper" aria-label="Pasos de configuración">
          {steps.map((item, index) => (
            <button
              type="button"
              key={item.title}
              className={step === index ? "is-active" : step > index ? "is-complete" : ""}
              onClick={() => setStep(index)}
              aria-current={step === index ? "step" : undefined}
            >
              <span>{step > index ? <CheckIcon size={14} /> : index + 1}</span>
              <span>
                <strong>{item.title}</strong>
                <small>{item.copy}</small>
              </span>
            </button>
          ))}
          <div className="setup-stepper-summary">
            <strong>{validObjectives.length}</strong>
            <span>objetivo{validObjectives.length === 1 ? "" : "s"} preparado{validObjectives.length === 1 ? "" : "s"}</span>
          </div>
        </nav>

        <form
          className="setup-stage"
          onSubmit={(event) => {
            event.preventDefault();
            if (step < steps.length - 1) setStep(step + 1);
            else void activateAgent();
          }}
        >
          <div className="setup-stage-heading">
            <span>Paso {step + 1} de {steps.length}</span>
            <h2>{steps[step].title}</h2>
          </div>

          <div className="setup-stage-content" key={step}>
            {step === 0 ? (
              <>
                <div className="entity-choice" role="group" aria-label="Tipo de representación">
                  <button
                    type="button"
                    className={draft.entityType === "person" ? "is-selected" : ""}
                    onClick={() => changeEntityType("person")}
                  >
                    <UserIcon size={19} />
                    <span><strong>Persona</strong><small>Compras, ventas o acuerdos personales</small></span>
                    <i>{draft.entityType === "person" ? <CheckIcon size={13} /> : null}</i>
                  </button>
                  <button
                    type="button"
                    className={draft.entityType === "company" ? "is-selected" : ""}
                    onClick={() => changeEntityType("company")}
                  >
                    <SlidersIcon size={19} />
                    <span><strong>Empresa</strong><small>Proveedores, ventas o alianzas B2B</small></span>
                    <i>{draft.entityType === "company" ? <CheckIcon size={13} /> : null}</i>
                  </button>
                </div>
                <div className="setup-fields two-columns">
                  <label>
                    <span>{draft.entityType === "company" ? "Nombre público" : "Cómo debe presentarte"}</span>
                    <input
                      value={draft.displayName}
                      onChange={(event) => setDraft({ ...draft, displayName: event.target.value })}
                      placeholder="Nombre visible para otros agentes"
                      required
                    />
                  </label>
                  <label>
                    <span>Descripción pública</span>
                    <textarea
                      value={draft.publicDescription}
                      onChange={(event) => setDraft({ ...draft, publicDescription: event.target.value })}
                      placeholder="Qué pueden saber las otras partes"
                      required
                    />
                  </label>
                </div>
              </>
            ) : null}

            {step === 1 ? (
              <ObjectivesEditor
                objectiveContexts={draft.objectiveContexts}
                entityType={draft.entityType}
                onChange={(objectiveContexts) =>
                  setDraft({ ...draft, objectiveContexts })
                }
              />
            ) : null}

            {step === 2 ? <SafetyFields draft={draft} onChange={setDraft} /> : null}

            {step === 3 ? (
              <div className="resources-step">
                <div>
                  <div className="field-heading">
                    <div>
                      <strong>Recursos permitidos</strong>
                      <span>En la demo son simulados y nunca cambian las condiciones de tus objetivos.</span>
                    </div>
                  </div>
                  <ToolSelector
                    enabledTools={draft.enabledTools}
                    onChange={(enabledTools) => setDraft({ ...draft, enabledTools })}
                  />
                </div>
                <div className="activation-summary">
                  <span><strong>{validObjectives.length}</strong> objetivos en paralelo</span>
                  <span><strong>{draft.enabledTools.length}</strong> recursos permitidos</span>
                  <span><strong>{Object.values(draft.sensitiveRules).filter(Boolean).length}</strong> situaciones bajo tu control</span>
                </div>
              </div>
            ) : null}
          </div>

          <footer className="setup-stage-actions">
            <button
              type="button"
              className="secondary-action"
              onClick={() => setStep(Math.max(0, step - 1))}
              disabled={step === 0}
            >
              Atrás
            </button>
            <button type="submit" className="primary-action" disabled={!canContinue || saving}>
              {step === steps.length - 1
                ? saving
                  ? "Activando…"
                  : "Activar agente"
                : "Continuar"}
              {!saving ? <ArrowRightIcon size={15} /> : null}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}

function AgentControlCenter({ agent }: { agent: AgentProfile }) {
  const { sessions, updateAgent } = useAgentSync();
  const [draft, setDraft] = useState(() => draftFromAgent(agent));
  const [editSection, setEditSection] = useState<EditSection | null>(null);
  const [editorWidth, setEditorWidth] = useState(700);
  const resizeState = useRef<{ startX: number; startWidth: number } | null>(null);
  const agentObjectiveContexts = objectiveContextsFromAgent(agent);

  useEffect(() => {
    if (!editSection) setDraft(draftFromAgent(agent));
  }, [agent, editSection]);

  useEffect(() => {
    const clampWidth = (width: number) =>
      Math.max(500, Math.min(940, window.innerWidth - 48, width));
    const handlePointerMove = (event: PointerEvent) => {
      if (!resizeState.current) return;
      const { startX, startWidth } = resizeState.current;
      setEditorWidth(clampWidth(startWidth + startX - event.clientX));
    };
    const stopResizing = () => {
      resizeState.current = null;
      document.body.classList.remove("is-resizing-agent-editor");
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", stopResizing);
    window.addEventListener("pointercancel", stopResizing);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", stopResizing);
      window.removeEventListener("pointercancel", stopResizing);
      document.body.classList.remove("is-resizing-agent-editor");
    };
  }, []);
  const ownerSessions = sessions.filter((session) =>
    belongsToAgent(session, agent.agent_id),
  );
  const activeSessions = ownerSessions.filter((session) =>
    ["SEARCHING", "ACTIVE", "PENDING_HUMAN_APPROVAL"].includes(session.status),
  );
  const pendingCount = ownerSessions.filter(
    (session) => session.status === "PENDING_HUMAN_APPROVAL",
  ).length;
  const paused = agent.status === "PAUSED";
  const negotiating = !paused && activeSessions.length > 0;

  const objectiveStatus = (index: number) => {
    if (paused) return { label: "En pausa", className: "is-paused" };
    if (index === 0 && pendingCount > 0) {
      return { label: "Espera tu decisión", className: "is-pending" };
    }
    if (index < activeSessions.length) {
      return { label: "Negociando", className: "is-active" };
    }
    return { label: "Explorando", className: "" };
  };

  const editorTitle: Record<EditSection, string> = {
    objectives: "Objetivos y oportunidades",
    safety: "Privacidad y decisiones",
    tools: "Recursos permitidos",
  };

  const closeEditor = () => {
    setDraft(draftFromAgent(agent));
    setEditSection(null);
  };

  const saveEditor = () => {
    const validObjectives = draft.objectiveContexts.filter((objective) =>
      objective.goal.trim(),
    );
    if (validObjectives.length === 0) return;
    updateAgent(
      profileFromDraft(
        { ...draft, objectiveContexts: validObjectives },
        { agentId: agent.agent_id, status: agent.status, previous: agent },
      ),
    );
    setEditSection(null);
  };

  return (
    <div className="agent-workspace is-existing">
      <header className="existing-agent-heading">
        <div className="existing-agent-identity">
          <span>{agent.display_name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("")}</span>
          <div>
            <span className="section-eyebrow">Mi agente</span>
            <h1>{agent.display_name.split(" — ")[0]}</h1>
            <p>{agent.public_description}</p>
          </div>
        </div>
        <div className="existing-agent-actions">
          <span className={`existing-agent-status ${paused ? "is-paused" : negotiating ? "is-active" : ""}`}>
            {paused ? "En pausa" : negotiating ? "Trabajando" : "Disponible"}
          </span>
        </div>
      </header>

      <section className="representation-contract" aria-labelledby="contract-title">
        <div className="contract-heading">
          <div>
            <span className="section-eyebrow">Contrato de representación</span>
            <h2 id="contract-title">Así trabaja en tu nombre</h2>
          </div>
          <button type="button" onClick={() => setEditSection("objectives")}>Editar objetivos</button>
        </div>

        <div className="objective-board">
          {agentObjectiveContexts.slice(0, 3).map((objective, index) => {
            const status = objectiveStatus(index);
            return (
              <article key={objective.objective_id}>
                <span className="objective-number">{String(index + 1).padStart(2, "0")}</span>
                <span className="objective-board-copy">
                  <p>{objective.goal}</p>
                  <small>
                    {objective.seeks.length} requisitos · {objective.offers.length} aportes
                  </small>
                </span>
                <span className={`objective-state ${status.className}`}>{status.label}</span>
              </article>
            );
          })}
        </div>
        {agentObjectiveContexts.length > 3 ? (
          <button
            type="button"
            className="objective-more"
            onClick={() => setEditSection("objectives")}
          >
            Ver {agentObjectiveContexts.length - 3} objetivo{agentObjectiveContexts.length - 3 === 1 ? "" : "s"} más
          </button>
        ) : null}

        <div className="contract-rails">
          <div>
            <UserIcon size={17} />
            <span><small>Te consulta</small><strong>{agent.escalation_rules.length} situaciones configuradas</strong></span>
          </div>
          <div>
            <SparkIcon size={17} />
            <span><small>Trabaja con</small><strong>{agent.tools.length} recursos permitidos</strong></span>
          </div>
        </div>
      </section>

      <section className="agent-settings" aria-labelledby="agent-settings-title">
        <div className="agent-settings-heading">
          <div>
            <span className="section-eyebrow">Configuración</span>
            <h2 id="agent-settings-title">Ajusta solo lo que necesitas</h2>
          </div>
          <p>Aquí defines sus reglas de seguridad y las herramientas que puede consultar.</p>
        </div>
        <div className="agent-setting-grid">
          <button type="button" onClick={() => setEditSection("safety")}>
            <ShieldIcon size={19} />
            <span><strong>Privacidad y decisiones</strong><small>Define qué datos protege y cuándo debe consultarte.</small></span>
            <ArrowRightIcon size={15} />
          </button>
          <button type="button" onClick={() => setEditSection("tools")}>
            <SlidersIcon size={19} />
            <span><strong>Recursos permitidos</strong><small>Elige qué herramientas puede consultar mientras trabaja por ti.</small></span>
            <ArrowRightIcon size={15} />
          </button>
        </div>
      </section>

      {editSection ? (
        <div className="agent-editor-layer">
          <button type="button" className="agent-editor-backdrop" onClick={closeEditor} aria-label="Cerrar editor" />
          <aside
            className={`agent-editor ${editSection === "objectives" ? "is-objectives" : ""}`}
            style={
              editSection === "objectives"
                ? ({ "--agent-editor-width": `${editorWidth}px` } as CSSProperties)
                : undefined
            }
            role="dialog"
            aria-modal="true"
            aria-labelledby="agent-editor-title"
          >
            {editSection === "objectives" ? (
              <div
                className="agent-editor-resizer"
                role="separator"
                aria-label="Cambiar el ancho del editor"
                aria-orientation="vertical"
                aria-valuemin={500}
                aria-valuemax={940}
                aria-valuenow={Math.round(editorWidth)}
                tabIndex={0}
                title="Arrastra para cambiar el ancho"
                onPointerDown={(event) => {
                  resizeState.current = {
                    startX: event.clientX,
                    startWidth: editorWidth,
                  };
                  document.body.classList.add("is-resizing-agent-editor");
                  event.currentTarget.setPointerCapture(event.pointerId);
                  event.preventDefault();
                }}
                onKeyDown={(event) => {
                  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
                  event.preventDefault();
                  const direction = event.key === "ArrowLeft" ? 1 : -1;
                  const availableWidth = Math.min(940, window.innerWidth - 48);
                  setEditorWidth((width) =>
                    Math.max(500, Math.min(availableWidth, width + direction * 32)),
                  );
                }}
              >
                <span />
                <span />
                <span />
              </div>
            ) : null}
            <header>
              <div>
                <span>Editar configuración</span>
                <h2 id="agent-editor-title">{editorTitle[editSection]}</h2>
              </div>
              <button type="button" onClick={closeEditor} aria-label="Cerrar">×</button>
            </header>
            <div className="agent-editor-content">
              {editSection === "objectives" ? (
                <ObjectivesEditor
                  objectiveContexts={draft.objectiveContexts}
                  entityType={draft.entityType}
                  onChange={(objectiveContexts) =>
                    setDraft({ ...draft, objectiveContexts })
                  }
                />
              ) : null}
              {editSection === "safety" ? <SafetyFields draft={draft} onChange={setDraft} /> : null}
              {editSection === "tools" ? <ToolSelector enabledTools={draft.enabledTools} onChange={(enabledTools) => setDraft({ ...draft, enabledTools })} /> : null}
            </div>
            <footer>
              <button type="button" className="secondary-action" onClick={closeEditor}>Cancelar</button>
              <button type="button" className="primary-action" onClick={saveEditor}>Guardar cambios</button>
            </footer>
          </aside>
        </div>
      ) : null}
    </div>
  );
}

export function AgentSetupForm() {
  const { profile, agentId, authReady } = useAuth();
  const { agentsById } = useAgentSync();
  const agent = agentId ? agentsById[agentId] : undefined;

  if (!authReady) {
    return <div className="agent-workspace-loading">Preparando tu agente…</div>;
  }
  if (!agent) return <CreationWizard ownerName={profile.name} />;
  return <AgentControlCenter agent={agent} />;
}
