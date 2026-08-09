// ─────────────────────────────────────────────────────────────────────────────
// Cliente REST mínimo — prueba de conectividad Frontend ↔ Backend (smoke test).
// Apunta al FastAPI local (scripts/run_api_server.py). No reemplaza el mock:
// solo verifica que CORS, rutas y contratos responden desde el navegador.
// ─────────────────────────────────────────────────────────────────────────────

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export interface BackendHealth {
  ok: boolean;
  agentsTotal: number;
  latencyMs: number;
  error?: string;
}

async function fetchWithTimeout(url: string, ms: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    return await fetch(url, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
  } finally {
    clearTimeout(timer);
  }
}

/** GET /api/v1/agents → valida conectividad real (CORS + rutas + JSON). */
export async function pingBackend(): Promise<BackendHealth> {
  const started = performance.now();
  try {
    const res = await fetchWithTimeout(`${API_BASE_URL}/agents`, 4000);
    const latencyMs = Math.round(performance.now() - started);
    if (!res.ok) {
      return { ok: false, agentsTotal: 0, latencyMs, error: `HTTP ${res.status}` };
    }
    const body = (await res.json()) as { total?: number };
    return { ok: true, agentsTotal: body.total ?? 0, latencyMs };
  } catch (err) {
    const latencyMs = Math.round(performance.now() - started);
    return {
      ok: false,
      agentsTotal: 0,
      latencyMs,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}
