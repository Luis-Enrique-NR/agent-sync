# RECONCILIATION SPEC — IA Engine ↔ REST Baseline

- **Fecha:** 2026-08-09
- **Rama:** `feat/consolidacion-backend`

---

## B1 — Adaptación de DecisionKind

**Diagnóstico:** `Engine.resume_session()` soporta 3 `DecisionKind`:
- `TURN` — aprobación de turno de negociación (nuestro caso legacy)
- `TOOL_EXECUTION` — aprobación de ejecución de tool
- `INBOUND_ACTION` — aprobación de acción del otro agente

Nuestro endpoint `POST /approval` asume implícitamente `DecisionKind.TURN`. Cuando el engine devuelve `TOOL_EXECUTION` o `INBOUND_ACTION`, el endpoint debe detectarlo y manejarlo.

**Propuesta:** En `submit_decision`, inspeccionar `pending_decision.kind`. Si es `TURN`, mantener el flujo actual. Si es `TOOL_EXECUTION` o `INBOUND_ACTION`, pasar la decisión al engine sin construir `AgentTurn`.

**Viabilidad:** Alta. El contrato de entrada `HumanDecisionDTO` no cambia.

---

## B2 — Homologación de disclosures

**Diagnóstico:** Diogo renombró `disclosure_requests` → `proposed_disclosures` en `AgentTurn`. El `EscalationEvaluator` ya usa `proposed_disclosures`. Nuestro código no referencia el nombre viejo.

**Estado:** ✅ Resuelto automáticamente por el merge — sin acción requerida.

---

## B3 — owner_user_id

**Diagnóstico:** `NegotiationState.owner_user_id` agregado por Diogo, default `None`. Nuestro código no lo pobla.

**Estado:** ✅ Compatible — `None` por defecto, no bloquea.

---

## B4 — ToolGateway mocks

**Diagnóstico:** `ToolGateway` requiere `ToolAdapter` registrados. Existen mocks en `ai/tools/mocks.py`.

**Estado:** ✅ Listo para desarrollo — los mocks se registran en `ToolGateway.get_default_gateway()`.
