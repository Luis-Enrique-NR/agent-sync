# SRD — AgentSync (System Requirements Document)

**Versión:** 1.1 · **Autor:** Equipo AgentSync · **Fecha:** Agosto 2026 · **Contexto:** Hackathon (36 horas)

---

## 1. Topología del Sistema y Arquitectura

El sistema implementa una arquitectura distribuida y orientada a eventos, diseñada para soportar un motor de agentes autónomos asíncronos desacoplados de la interfaz visual.

*   **Capa de Presentación (Frontend):** Aplicación de página única (SPA) desarrollada en **React (Next.js)**, optimizada para renderizar interfaces limpias y conectarse en tiempo real mediante el SDK de Portal.
*   **Capa de Orquestación y Lógica (Backend):** Servidor desarrollado en **Python**, encargado de la persistencia ligera, la gestión de rutas REST y el control de los eventos webhooks de Portal.
*   **Capa Cognitiva y de Estado (AI Brain):** Motor lógico impulsado por **LangChain y LangGraph**, estructurado para procesar iteraciones de agentes con memoria acotada y flujos de estado cíclicos.
*   **Capa de Tiempo Real (Middleware):** Infraestructura de **Portal SDK**, actuando como el *broker* de mensajes para la sincronización del lobby y los canales de negociación privados.

---

## 2. Feudos de Código y Asignación de Módulos

Para mitigar el riesgo de conflictos de *merge* durante el desarrollo de las 36 horas, el repositorio se divide en dominios estrictos:

*   **Dominio Frontend (`/frontend`):** Dueño de la interfaz gráfica en React/Next.js. Responsable de la vista de configuración del agente, la pantalla de visualización de chats en vivo y la bandeja interactiva de decisiones sensibles.
*   **Dominio Backend API (`/backend/api`):** Dueño de la recepción de peticiones REST y la persistencia local de perfiles de agentes y sesiones de chat.
*   **Dominio AI Brain (`/backend/ai`):** Dueño de la implementación con LangChain/LangGraph. Responsable de procesar las decisiones estructuradas de los LLMs, aplicar los grafos de estado y asegurar las salidas en formato JSON estricto.

---

## 3. Modelo de Datos Agnóstico (Persistencia)

El diseño del backend no asume restricciones de industria ni acoplamiento a "empresas", modelando los perfiles de forma genérica para soportar tanto escenarios B2B como P2P[cite: 3].

*   **Entidad `AgentProfile`:**
    *   `agent_id`: Identificador único (UUID).
    *   `entity_type`: Indicador de la UI (ej. empresa o persona)[cite: 3].
    *   `personality`: Cadena de texto con el tono y directrices de comportamiento[cite: 3].
    *   `objectives`: Metas comerciales o personales del agente[cite: 3].
    *   `hard_limits`: Restricciones duras inquebrantables (límites numéricos o de privacidad)[cite: 3].
*   **Entidad `MatchSession`:**
    *   `session_id`: ID de la sesión sincronizado directamente con el canal de Portal.
    *   `agent_1_id` / `agent_2_id`: Referencias a los perfiles participantes.
    *   `status`: Estado cíclico de la sesión (`SEARCHING`, `ACTIVE`, `PENDING_HUMAN_APPROVAL`, `RESOLVED`, `REJECTED`).

---

## 4. Flujo de Ejecución (LangGraph + Portal)

1.  **Inicialización:** El usuario registra su configuración vía REST. El backend persiste el perfil y emite un evento al canal global de Portal para anunciar la presencia del agente.
2.  **Matchmaking y Conexión:** Un servicio en segundo plano evalúa la compatibilidad en el lobby e instancia un canal privado de Portal, despertando a los agentes de su estado inactivo[cite: 3].
3.  **Bucle LangGraph:** El grafo de LangGraph procesa el turno del Agente A, evalúa las reglas internas y genera una salida estructurada. Mediante validaciones determinísticas (capa de *guardrails* fuera del LLM), se comprueba que no se violen límites de precios o datos personales[cite: 3].
4.  **Escalamiento Humano:** Si la respuesta de la IA interseca con una regla de "decisión sensible" configurada por el usuario, el grafo congela su ejecución de forma asíncrona y emite una alerta a la bandeja de notificaciones del cliente[cite: 3].

---

## 5. Requisitos de Seguridad y Entorno

*   **Variables de Entorno (`.env`):** Las claves maestras de la API de Portal, credenciales de base de datos y llaves de modelos de lenguaje (OpenAI/Anthropic) residen de forma exclusiva en el servidor backend.
*   **Aislamiento de Guardrails:** Ninguna validación de seguridad crítica se fía exclusivamente del prompt del LLM; el backend valida mediante lógica determinística de Python cada campo antes de permitir su publicación en los canales de Portal[cite: 3].
