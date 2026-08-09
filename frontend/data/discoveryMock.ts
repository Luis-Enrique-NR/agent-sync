export type DiscoveryRole = "demand" | "supply" | "either";

export interface DiscoveryProfileMock {
  agentId: string;
  publicArea: string;
  areaKey: string;
  reachKeys: string[];
  topicKeys: string[];
  topicLabel: string;
  role: DiscoveryRole;
  scopeLabel: string;
  viabilityLabel: string;
  mapX: number;
  mapY: number;
  fitScore: number;
}

/**
 * Metadatos públicos y deliberadamente aproximados para la demo de Explorar.
 * No representan coordenadas reales ni deben sustituir el contrato de alcance
 * geográfico que tendrá que entregar matchmaking.
 */
export const DISCOVERY_PROFILES: Record<string, DiscoveryProfileMock> = {
  "agent-b2b-telar": {
    agentId: "agent-b2b-telar",
    publicArea: "Lima centro · Perú",
    areaKey: "lima-metropolitana",
    reachKeys: ["lima-metropolitana", "peru"],
    topicKeys: ["textil-organico"],
    topicLabel: "suministro textil orgánico",
    role: "demand",
    scopeLabel: "Recibe entregas en Lima",
    viabilityLabel: "Cuenta con almacén y recepción mensual en Lima",
    mapX: 53,
    mapY: 55,
    fitScore: 92,
  },
  "agent-b2b-organiccotton": {
    agentId: "agent-b2b-organiccotton",
    publicArea: "Callao · Perú",
    areaKey: "lima-metropolitana",
    reachKeys: ["lima-metropolitana", "peru", "international"],
    topicKeys: ["textil-organico"],
    topicLabel: "suministro textil orgánico",
    role: "supply",
    scopeLabel: "Entrega nacional y exportación",
    viabilityLabel: "Puede entregar en Lima mediante el puerto del Callao",
    mapX: 30,
    mapY: 48,
    fitScore: 92,
  },
  "agent-p2p-valentina": {
    agentId: "agent-p2p-valentina",
    publicArea: "Lima norte · Perú",
    areaKey: "lima-metropolitana",
    reachKeys: ["lima-metropolitana"],
    topicKeys: ["auto-usado"],
    topicLabel: "compraventa de auto usado",
    role: "supply",
    scopeLabel: "Encuentro en Lima Metropolitana",
    viabilityLabel: "Puede coordinar encuentros dentro de Lima Metropolitana",
    mapX: 49,
    mapY: 29,
    fitScore: 100,
  },
  "agent-p2p-carlos": {
    agentId: "agent-p2p-carlos",
    publicArea: "Lima norte · Perú",
    areaKey: "lima-metropolitana",
    reachKeys: ["lima-metropolitana"],
    topicKeys: ["auto-usado"],
    topicLabel: "compraventa de auto usado",
    role: "demand",
    scopeLabel: "Se desplaza dentro de Lima",
    viabilityLabel: "Puede revisar el vehículo en Lima norte",
    mapX: 61,
    mapY: 35,
    fitScore: 94,
  },
  "agent-p2p-sofia": {
    agentId: "agent-p2p-sofia",
    publicArea: "Lima centro · Perú",
    areaKey: "lima-metropolitana",
    reachKeys: ["lima-metropolitana"],
    topicKeys: ["auto-usado"],
    topicLabel: "compraventa de auto usado",
    role: "demand",
    scopeLabel: "Se desplaza dentro de Lima",
    viabilityLabel: "Acepta coordinar una revisión en Lima norte",
    mapX: 54,
    mapY: 52,
    fitScore: 89,
  },
  "agent-p2p-mateo": {
    agentId: "agent-p2p-mateo",
    publicArea: "Lima oeste · Perú",
    areaKey: "lima-metropolitana",
    reachKeys: ["lima-metropolitana"],
    topicKeys: ["auto-usado"],
    topicLabel: "compraventa de auto usado",
    role: "demand",
    scopeLabel: "Se desplaza dentro de Lima",
    viabilityLabel: "Puede acudir con un mecánico el fin de semana",
    mapX: 37,
    mapY: 43,
    fitScore: 85,
  },
};

/**
 * Registro que simula un candidato encontrado en el índice, pero descartado
 * antes de llegar a la interfaz por no compartir un área operable.
 */
export const SCREENED_DISCOVERY_PROFILES: DiscoveryProfileMock[] = [
  {
    agentId: "screened-used-car-austin",
    publicArea: "Austin · Estados Unidos",
    areaKey: "austin-texas",
    reachKeys: ["austin-texas"],
    topicKeys: ["auto-usado"],
    topicLabel: "compraventa de auto usado",
    role: "demand",
    scopeLabel: "Solo encuentros locales",
    viabilityLabel: "No existe una ruta logística hasta Lima",
    mapX: 0,
    mapY: 0,
    fitScore: 91,
  },
];
