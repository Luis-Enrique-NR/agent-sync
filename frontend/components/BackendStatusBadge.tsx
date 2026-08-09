"use client";

import { useCallback, useEffect, useState } from "react";
import { pingBackend, type BackendHealth } from "@/lib/api";

type Status = "checking" | "ok" | "error";

export function BackendStatusBadge() {
  const [status, setStatus] = useState<Status>("checking");
  const [health, setHealth] = useState<BackendHealth | null>(null);

  const check = useCallback(async () => {
    setStatus("checking");
    const result = await pingBackend();
    setHealth(result);
    setStatus(result.ok ? "ok" : "error");
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  return (
    <button
      type="button"
      className={`backend-badge is-${status}`}
      onClick={() => void check()}
      title="Reintentar verificación de conectividad con el backend"
    >
      <span className="backend-dot" aria-hidden="true" />
      {status === "checking" ? (
        <span>Verificando backend…</span>
      ) : status === "ok" ? (
        <span>
          Backend conectado · {health?.agentsTotal ?? 0} agentes ·{" "}
          {health?.latencyMs} ms
        </span>
      ) : (
        <span>Backend sin conexión</span>
      )}
    </button>
  );
}
