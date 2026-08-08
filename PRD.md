# PRD — AgentSync (MVP para Hackathon — 36 horas)
**Versión:** 1.1 · **Autor:** [Tu nombre] · **Fecha:** Agosto 2026 · **Equipo:** 4 personas · **Contexto:** Hackathon, duración total 36h

> **Nota de esta versión:** documento ajustado para una hackathon de 36 horas. Se mantiene la visión de producto completa, pero el alcance, el plan de trabajo y los riesgos están recalibrados para ese límite de tiempo real. La monetización se documenta solo como visión a futuro — **no es criterio de éxito para esta hackathon**.

---

## 1. Resumen ejecutivo

AgentSync es una plataforma donde cada usuario —una empresa **o una persona individual**— configura un agente de IA propio (personalidad, objetivos, herramientas y límites). Los agentes conversan entre sí de forma autónoma dentro de un ecosistema compartido para descubrir oportunidades y negociar acuerdos preliminares, eliminando la necesidad de que los humanos sostengan cientos de conversaciones repetitivas de primer contacto — ya sea negociando entre empresas (B2B) o directamente entre personas (P2P/C2C). El humano interviene únicamente cuando hay una decisión sensible que el propio usuario definió como tal — el sistema nunca decide unilateralmente qué escalar.

Este documento define el **alcance mínimo viable (MVP)** para validar la hipótesis central del producto con el menor esfuerzo de ingeniería posible.

**Decisión de diseño clave (por incluir el segmento P2P):** el motor de agentes no debe construirse pensando en "empresas" — debe construirse pensando en **"una entidad con objetivos"**, sea una empresa o una persona. Esto es lo que permite mostrar ambos mercados en la demo sin duplicar trabajo (ver sección 6.1).

---

## 2. Problema y oportunidad

**Problema (B2B):** Las empresas (ventas, sourcing, partnerships) pierden decenas de horas sosteniendo conversaciones de exploración/calificación que en su mayoría no llegan a nada — son repetitivas, de bajo valor estratégico, y consumen el tiempo de personas que deberían enfocarse en cerrar, no en filtrar.

**Problema (personas — P2P/C2C):** Las personas también sostienen conversaciones repetitivas de bajo valor al negociar por su cuenta **con otras personas** — no siempre es "empresa vendiéndole a un cliente" (eso sería B2C tradicional), muchas veces es directamente **persona a persona**: alguien vendiendo su auto usado a otro particular, alguien buscando roomie, dos freelancers negociando una colaboración, alguien coordinando un intercambio o trueque. El patrón es el mismo que en B2B: mucho ida y vuelta de baja complejidad antes de llegar al punto donde realmente importa decidir — solo que aquí ambos lados de la mesa son personas, no empresas.

**El insight central que hace esto un solo producto y no dos (ni tres):** en todos los casos el problema tiene la misma forma — "dos partes con objetivos deben explorar compatibilidad y negociar términos antes de comprometerse" — solo cambia quién está detrás de cada agente: empresa-empresa (B2B), empresa-persona (B2C tradicional), o persona-persona (P2P/C2C). El motor de agentes no debe asumir ninguna de estas combinaciones, debe ser agnóstico a quién está de cada lado (ver Decisión de diseño clave arriba).

**Hipótesis del MVP:**
> Si delegamos la exploración y negociación preliminar a un agente de IA configurado por el usuario, y solo pedimos intervención humana en decisiones sensibles (definidas por el propio usuario, no por el sistema), el usuario ahorrará tiempo significativo y llegará a más oportunidades calificadas que haciéndolo manualmente — sin importar si quien está detrás de cada agente es una empresa o una persona.

**Lo que el MVP debe demostrar**, en orden de importancia:
1. Un usuario puede configurar un agente que representa fielmente su intención (comercial o personal).
2. Dos agentes pueden sostener una conversación coherente y avanzar hacia un acuerdo o un descarte.
3. **El usuario puede definir él mismo qué cuenta como "decisión sensible"** (no es el sistema quien decide unilateralmente qué escalar) — el agente respeta esa configuración y pausa exactamente donde el usuario indicó, ni más ni menos.
4. El usuario confía en el proceso (transparencia: puede ver, pausar, corregir).
5. **El mismo motor funciona igual de bien representando a una empresa que a una persona** — esta es la prueba de que la idea es una plataforma, no un caso de uso único.

Si estos 5 puntos no se sostienen, ningún modelo de monetización va a funcionar — por eso el MVP no debe distraerse con pantallas secundarias.

> **Por qué este cambio importa (punto 3):** dejar que el *sistema* decida solo cuándo escalar suena más "inteligente", pero en realidad reduce la confianza — cada usuario tiene un umbral distinto de riesgo aceptable. Un usuario puede querer aprobar cualquier precio, otro solo montos sobre cierto valor, otro cualquier dato personal sin excepción. Dárselo como control explícito es más simple de construir en 36h que una heurística "inteligente" de detección automática, y es más honesto con el usuario sobre quién tiene el control real.

### 2.1 Ejemplos de casos de uso por segmento

| Segmento | Quién está detrás de cada agente | Ejemplos de objetivos del agente |
|---|---|---|
| **B2B** | Empresa ↔ Empresa | "Buscar 3 proveedores de tela orgánica bajo $X/unidad", "encontrar distribuidores en la región Y", "filtrar agencias de marketing que necesiten nuestro software" |
| **P2P / C2C** | Persona ↔ Persona | "Vender mi auto usado al mejor precio posible sobre $X", "encontrar roomie para depto de 2 habitaciones bajo $Y/mes en zona Z", "coordinar un trueque de equipo fotográfico", "dos freelancers negociando colaborar en un proyecto conjunto" |
| *(B2C tradicional)* | Empresa ↔ Persona | *Mencionado por completitud — no es el foco del MVP; ejemplo: una empresa ofreciendo un servicio directo a un cliente final. El motor lo soporta igual, pero no se prioriza para la demo.* |

Para la demo de la hackathon, recomendamos mostrar **B2B y P2P** (no B2C tradicional) porque son los dos extremos más claros para el jurado: "empresa negociando con empresa" vs. "una persona negociando directamente con otra persona" — el contraste comunica mejor la versatilidad del motor que meter un tercer segmento intermedio.

Nota importante de seguridad: en el caso **P2P**, una "decisión sensible" con frecuencia no es solo dinero — puede ser **compartir una dirección, un número de teléfono, o acordar un punto de encuentro físico con un desconocido**. Esto eleva el nivel de cuidado del guardrail respecto a B2B (ver sección 11), y es justamente el tipo de cosa que el propio usuario debería poder marcar como "siempre requiere mi aprobación" en su configuración (ver punto 3 de la sección anterior).

---

## 3. Qué es y qué NO es este MVP

### Es:
- Un **loop cerrado y funcional**: configurar agente → agente negocia con otro agente → usuario aprueba/rechaza decisión sensible → match o descarte.
- Un ecosistema **acotado** (no miles de agentes reales) — puede arrancar con un número controlado de empresas piloto o incluso agentes de prueba controlados por el propio equipo para validar comportamiento antes de abrir a usuarios reales.

### NO es (fuera de alcance del MVP):
- Marketplace público abierto con descubrimiento masivo/búsqueda avanzada.
- Simulador de prueba del agente (pantalla completa dedicada) — se puede resolver con una prueba manual simple o feedback informal en la primera versión.
- Analítica/métricas avanzadas, exportables, dashboards de tendencias.
- Gestión de equipos/roles/permisos (multiusuario por empresa).
- Verificación de reputación/confianza entre empresas (badge de "verificado").
- Integraciones reales con CRM/calendario externos — en el MVP estas "tools" pueden ser simuladas o mockeadas (el agente actúa *como si* tuviera esa info, sin integrarse de verdad).
- Chat humano-humano post-match dentro de la plataforma — un match puede resolverse con algo tan simple como revelar el email/contacto de la contraparte.

---

## 4. Usuario objetivo (MVP)

**Persona A — B2B:** Persona en un rol comercial/sourcing en una pyme o startup B2B (ventas, compras, partnerships) que hoy hace prospección o negociación de proveedores manualmente vía email/LinkedIn/WhatsApp, con volumen suficiente (10+ conversaciones repetitivas/mes) para que la automatización se note.

**Persona B — P2P/C2C:** Una persona individual que negocia frecuentemente **con otras personas** (no con empresas) en contextos de bajo riesgo pero repetitivos: compra/venta de artículos usados entre particulares, búsqueda de roomie, coordinación de intercambios/trueques. Busca ahorrarse el ida y vuelta inicial ("¿sigue disponible?", "¿aceptas menos?", "¿cuándo puedes?") sin perder el control de la decisión final — y quiere decidir ella misma qué cosas nunca deben acordarse sin su aprobación directa (por ejemplo, cualquier dato de contacto o ubicación).

Para la hackathon, **elige una persona por vertical para la demo** (una empresa ficticia + una persona ficticia) en vez de intentar cubrir ambas de forma genérica — así el jurado ve ejemplos concretos y creíbles en cada segmento.

No diseñamos aún para: grandes corporativos con compliance complejo, ni para casos P2P de alto riesgo regulatorio (ej. bienes raíces reales, menores de edad, transacciones financieras grandes) — el foco P2P del MVP es de bajo riesgo/alto volumen (artículos usados, coordinación simple, colaboraciones pequeñas).

---

## 5. Métricas de éxito

### 5.1 Métricas de producto (visión, más allá de la hackathon)

| Métrica | Tipo | Meta orientativa |
|---|---|---|
| % de agentes configurados que completan al menos 1 conversación | Activación | > 60% |
| Tiempo desde configuración hasta primera conversación iniciada | Activación | < 24h |
| % de conversaciones que llegan a un match o descarte claro (no se quedan "colgadas") | Salud del core loop | > 70% |
| % de decisiones sensibles resueltas por el usuario en < 24h | Confianza/uso | > 50% |
| **Guardrail:** % de conversaciones donde el agente comparte algo que violó un límite duro configurado | Confianza/seguridad | 0% (esto rompe el producto si falla) |

La métrica guardrail sigue siendo la más importante del documento: si el agente incumple un límite duro una sola vez **durante la demo**, es el peor escenario posible frente a jueces — se ve como una falla de concepto, no solo de producto.

### 5.2 Criterios de éxito para LA HACKATHON (lo que de verdad importa en 36h)

Esto es distinto a las métricas de producto de arriba — en una hackathon, "éxito" significa:

1. **El loop completo corre en vivo, sin errores, de punta a punta**, al menos una vez, de forma reproducible: configurar agente → conversación agente-agente visible → decisión sensible detectada → usuario aprueba → match.
2. **El concepto se entiende en los primeros 30 segundos de demo** sin que el presentador tenga que explicar mucho — la UI y el guion deben comunicar solos "esto es agentes negociando por ti".
3. **Cero fallos en vivo** en el momento exacto de la decisión sensible (es el momento más "wow" del pitch — si falla ahí, falla el pitch entero).
4. **Se ve terminado, no a medias** — mejor 5 pantallas pulidas que 10 a medio hacer. Los jueces penalizan más lo que se ve roto que lo que falta.

---

## 6. Alcance funcional del MVP

Reduciendo las 10 pantallas discutidas previamente a lo estrictamente necesario para sostener el loop:

| Pantalla | ¿Incluida en MVP? | Notas |
|---|---|---|
| Dashboard | ✅ Sí, simplificado | Solo lo esencial: estado del agente + qué requiere mi atención ahora |
| Configuración del Agente | ✅ Sí, completa | Es el corazón del producto — personalidad, objetivos, tools (mockeadas), **límites duros**, y **reglas de qué escalar al humano (configurables por el usuario, no fijas por el sistema)** |
| Simulador de prueba | ❌ Fuera | Validar informalmente en piloto controlado |
| Ecosistema / Portal | ✅ Sí, versión lista simple | Sin grafo visual complejo — una lista de agentes/negociaciones basta |
| Perfil de agente externo | ⚠️ Parcial | Info mínima embebida en la tarjeta de conversación, no pantalla dedicada |
| Conversación agente-agente (detalle) | ✅ Sí, completa | Transparencia total es requisito de confianza, no opcional |
| Bandeja de decisiones/notificaciones | ✅ Sí, completa | Es donde ocurre la intervención humana — crítico |
| Match confirmado + siguiente paso | ✅ Sí, simplificado | Termina en "revelar contacto", no en chat interno |
| Historial y métricas | ⚠️ Parcial | Lista simple de conversaciones pasadas, sin dashboards |
| Ajustes de cuenta / equipo | ⚠️ Mínimo | Solo datos básicos de perfil, sin gestión de equipo |

**Resultado:** 6 pantallas completas + 3 simplificadas + 1 fuera de alcance. Esto es consistente con "MVP" real: el loop completo, sin lujos.

### 6.1 Estrategia clave: un solo motor, dos verticales (así no duplican trabajo en 36h)

**No construyan dos productos.** La forma correcta de incorporar el segmento P2P sin comerse el tiempo del equipo es:

1. El motor de agentes, la lógica de decisión sensible y el guardrail se construyen **una sola vez**, de forma genérica — un agente representa "una entidad con objetivos, límites y personalidad", sin ningún campo hardcodeado tipo `nombre_empresa` o `industria`.
2. La única diferencia entre el ejemplo B2B y el ejemplo P2P es **la data de configuración** (los objetivos, el tono de personalidad, los límites) — no código nuevo.
3. Para la demo, preparen **2 sets de datos de ejemplo** (uno B2B, uno P2P) listos para cargar, y muestren ambos en el pitch como prueba de que la plataforma generaliza. Esto cuesta casi cero tiempo de desarrollo extra y es un diferenciador fuerte frente a otros equipos que muestren un solo caso de uso.

Esta es probablemente la decisión de arquitectura más importante del documento: **si el motor termina acoplado a "empresas", agregar el segmento P2P después de la hora 20 de la hackathon sería carísimo. Si se construye genérico desde el inicio, agregar el segundo caso de uso es casi gratis.**

---

## 7. Historias de usuario priorizadas (MVP)

**P0 — sin esto no hay producto:**
- Como usuario, quiero configurar la personalidad, objetivos y límites duros de mi agente para que actúe en mi nombre con reglas claras.
- **Como usuario, quiero definir yo mismo qué tipo de situaciones cuentan como "decisión sensible"** (ej. cualquier precio, cualquier dato personal, montos sobre cierto valor, cualquier compromiso de fecha) **en vez de que el sistema lo decida por mí**, para que el nivel de control se ajuste a mi propio nivel de riesgo aceptable.
- Como usuario, quiero que mi agente pueda conversar con otro agente y que yo pueda ver esa conversación en cualquier momento.
- Como usuario, quiero que mi agente respete exactamente las reglas de escalamiento que configuré y pause ahí, sin avanzar solo ni preguntarme de más.
- Como usuario, quiero aprobar, rechazar o responder manualmente una decisión sensible desde un solo lugar.
- Como usuario, quiero saber de inmediato cuando se alcanza un match.

**P1 — mejora sustancialmente la experiencia, pero el loop sobrevive sin esto:**
- Como usuario, quiero ver un resumen del estado general de mi agente sin entrar a cada conversación.
- Como usuario, quiero ver un historial simple de conversaciones pasadas.
- Como usuario, quiero pausar mi agente si necesito detener toda actividad.

**P2 — deliberadamente diferido:**
- Simulador de prueba, analítica avanzada, gestión de equipo, integraciones reales, chat interno post-match.

---

## 8. Requisitos no funcionales críticos

- **Cumplimiento de límites duros (guardrail):** el sistema debe garantizar, a nivel de arquitectura (no solo de prompt), que el agente no puede compartir información marcada como restringida ni cruzar límites numéricos (precio mínimo, etc.). Esto probablemente requiere una capa de validación determinística *fuera* del modelo de lenguaje, no solo instrucciones en el prompt.
- **Transparencia:** toda conversación agente-agente debe quedar registrada y ser visible al usuario sin fricción — es la base de la confianza en un producto donde "algo" negocia en tu nombre.
- **Reversibilidad:** el usuario debe poder pausar su agente o intervenir en cualquier momento; nunca debe sentir que perdió el control.
- **Trazabilidad de decisiones:** cada decisión sensible resuelta debe quedar registrada con quién decidió qué y cuándo (importante también si más adelante hay disputas comerciales).

---

## 9. Roles del Equipo y Asignación de Esfuerzo (Hackathon 36h)

Para evitar duplicidad de esfuerzos y conflictos durante el desarrollo, las responsabilidades del equipo de 4 personas se dividen en feudos claros:

### 1. Frontend UI (Dueño de la experiencia visual)
Responsable de que el loop sea fluido y genere confianza, operando sobre **React / Next.js**:
*   **Core Loop:** Construir estrictamente las 6 pantallas completas y las 3 simplificadas del MVP.
*   **Vistas Críticas:** Pantalla de configuración del agente (personalidad, límites, reglas de escalamiento) y bandeja de decisiones/notificaciones.
*   **Transparencia:** Visualización detallada de la conversación agente-agente en tiempo real.
*   **Diseño Agnóstico:** Asegurar que la interfaz soporte visualmente tanto los datos B2B como P2P sin duplicar código.

### 2. AI Backend (Cerebro y escudos del agente)
Responsable de la integración con los modelos de lenguaje mediante **LangChain y LangGraph**:
*   **Motor de Conversación:** Orquestación de agentes conversando entre sí con control de turnos y *timeouts* para evitar bucles.
*   **Guardrails Determinísticos:** Capa de validación fuera del LLM para evitar fugas de límites duros o datos personales en P2P.
*   **Lógica de Escalamiento:** Motor de reglas que compara el flujo contra la configuración del usuario para pausar ante decisiones sensibles.
*   **Mock Data:** Inyección de datos simulados (CRMs, calendarios, inventarios) al contexto del agente.

### 3. Infraestructura de Transporte e Integración
Responsable de la conectividad en tiempo real y el flujo de eventos:
*   **Pipeline de Ingesta:** Ingesta y autenticación de webhooks desde Portal.
*   **Resiliencia y Bus Interno:** Encolamiento de mensajes para asegurar el comportamiento asíncrono de los agentes.
*   **SDK Interno:** Capa de abstracción para que el orquestador interactúe con los canales y accesos de Portal.

### 4. Dominio, Persistencia y Orquestación
Responsable de la persistencia de datos y las máquinas de estados:
*   **Persistencia de Estado:** Estructuración de bases de datos para perfiles de agentes, historiales y manifiestos.
*   **Modelo Agnóstico:** Garantizar el esquema genérico (`entidad + objetivos + personalidad + límites`) libre de acoplamientos industriales.
*   **Matchmaking y Estados:** Motor de coincidencia de intenciones y gestión del ciclo de vida de las sesiones de negociación.

---

## 10. Monetización — fuera de alcance para esta hackathon

**No aplica para las 36 horas.** Se deja documentado abajo únicamente como visión de negocio a futuro, por si algún juez pregunta "¿cómo generarían ingresos?" — pero no debe consumir ni un minuto de desarrollo ni aparecer como feature en la demo. Si el pitch necesita responder esto, basta con decir en una slide la recomendación de la sección 10.1, sin construir nada.

### 10.1 Visión a futuro (solo para responder si preguntan, no para construir)

| Modelo | Cómo funcionaría acá | A favor | En contra / riesgo |
|---|---|---|---|
| **Suscripción mensual (SaaS)** | Tarifa fija por agente activo/mes | Ingreso predecible, fácil de explicar, estándar en B2B SaaS | En el MVP el valor aún no está probado — cobrar muy pronto puede matar la adquisición de los primeros usuarios piloto |
| **Comisión por match/trato cerrado** | % o fee fijo solo cuando hay un acuerdo cerrado | Alineado con el valor real entregado (pagas si funciona) — más fácil de justificar en fase temprana | Difícil de medir con precisión si el cierre final ocurre fuera de la plataforma (ej. por email); requiere que el usuario reporte el cierre honestamente |
| **Freemium con límites de uso** | Gratis hasta N conversaciones/mes, luego se paga | Reduce fricción de entrada al máximo, ideal para validar el loop con volumen | Sin ingresos reales durante la validación; riesgo de atraer usuarios que nunca convierten |
| **Sin monetizar aún (piloto gratuito)** | Cobrar $0 durante el MVP, medir uso y satisfacción | Máxima velocidad de aprendizaje, cero fricción para conseguir los primeros pilotos | No valida disposición a pagar real — solo intención de uso |

**Recomendación concreta para un equipo de 4 en fase de validación:**
1. Corre el MVP como **piloto gratuito** con un número controlado de empresas (5-15), priorizando aprendizaje sobre ingreso.
2. Desde el día uno, **pregunta explícitamente** al final de cada match ("¿cuánto valdría esto para ti?") para recolectar señales de disposición a pagar sin cobrar aún.
3. Si el loop funciona (métricas de la sección 5 se cumplen), la transición natural es **comisión por match cerrado** — es el modelo más alineado con el valor real y el más fácil de vender a los primeros clientes ("no pagas si no funciona"), evolucionando después a suscripción una vez haya uso recurrente y previsible.

Esto es una recomendación de partida, no una decisión cerrada — conviene revisarla con datos reales del piloto antes de comprometerse.

---

## 11. Consideraciones técnicas de alto nivel

- **Orquestación de agentes:** cada agente necesita estado persistente (config, objetivos, límites, historial) y un motor de conversación que pueda ejecutarse de forma asíncrona (los agentes no negocian en tiempo real síncrono necesariamente).
- **Modelo de datos agnóstico a B2B/P2P:** el agente se modela como "entidad + objetivos + personalidad + límites", sin campos específicos de empresa. Un campo simple de "tipo" (empresa/persona) puede usarse solo para mostrar la UI correcta (ej. ícono, terminología), pero no debe cambiar la lógica del motor.
- **Capa de "guardrails" separada del LLM:** validación determinística de límites duros antes de que cualquier mensaje del agente se envíe o cualquier acuerdo se confirme. **En el caso P2P, este segmento incluye no solo límites numéricos sino datos personales sensibles** (dirección exacta, teléfono, ubicación en tiempo real) — el guardrail debe poder marcar categorías de dato personal como "nunca compartir sin aprobación humana explícita", no solo montos.
- **Detección de "decisión sensible" — configurable por el usuario, no una caja negra del sistema:** el usuario define, en su configuración, qué categorías de situación requieren su aprobación (ej. "cualquier precio final", "cualquier dato de contacto/ubicación", "montos sobre $X", "cualquier compromiso de fecha"). El motor solo necesita comparar cada punto de la negociación contra esas categorías — es una lógica de reglas simple, no una heurística "inteligente" de IA adivinando qué es sensible, lo cual además es más rápido de construir en 36h y más fácil de explicar/defender frente al jurado ("el usuario tiene el control total, no la caja negra"). **Recomendación:** venir con un set de categorías marcadas como sensibles por defecto (especialmente datos personales en P2P), que el usuario puede ampliar pero no puede desactivar del todo — esto evita que alguien configure mal su agente y termine sin ningún control humano.
- **Guardrail de límites duros** sigue siendo una capa aparte y no negociable (sección 8) — la configurabilidad de la sección anterior es sobre *qué escalar al humano*, no sobre los límites duros que el agente *nunca* puede cruzar (esos no son opcionales ni configurables a la baja).
- **Simulación de tools:** para el MVP, "acceso a CRM/calendario/precios" (B2B) o "presupuesto personal/disponibilidad" (P2P) puede ser data mockeada inyectada al contexto del agente, sin integración real — ahorra semanas de desarrollo sin sacrificar la validación del concepto.

---

## 12. Riesgos y supuestos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El agente cruza un límite duro (fuga de info sensible o precio) | Crítico — rompe confianza total | Guardrails determinísticos, no solo prompting; testing exhaustivo antes de abrir a usuarios reales |
| **(P2P) El agente comparte datos personales (dirección, teléfono, ubicación) sin aprobación** | Crítico — riesgo de seguridad real de una persona, no solo de confianza en el producto | Tratar cualquier dato personal identificable como categoría de "decisión sensible" obligatoria, nunca automatizable |
| **(P2P) Riesgo de mal uso para estafas/ingeniería social entre agentes de personas reales** | Alto — reputacional y de seguridad | Fuera del alcance de la demo mostrar transacciones reales de dinero/encuentros; en la demo, dejar explícito que es un entorno simulado/controlado |
| **El usuario configura mal su umbral de escalamiento (deja casi todo en automático) y el agente compromete algo que no debía** | Alto — el usuario tiene el control, pero un mal uso del control sigue siendo responsabilidad del producto | Categorías sensibles por defecto no desactivables (datos personales, límites duros) — el usuario amplía el control, no lo puede reducir por debajo de un mínimo de seguridad |
| Las conversaciones agente-agente se quedan "circulares" sin llegar a nada | Alto — mata la métrica core | Definir timeout/máximo de turnos y forzar escalamiento a humano si no converge |
| Usuarios no confían en que "algo negocie por ellos" | Alto — adopción baja | Transparencia total (poder ver/pausar/corregir siempre) desde la primera versión |
| Ecosistema vacío al lanzar (no hay con quién negociar) | Alto — sin agentes no hay demo del valor | Arrancar con agentes de prueba controlados por el equipo, o piloto cerrado con empresas/personas emparejadas manualmente al inicio |
| **Intentar cubrir B2B y P2P a fondo diluye el tiempo de desarrollo en 36h** | Alto — riesgo de terminar con dos casos de uso a medio hacer en vez de uno sólido | Un solo motor genérico (sección 6.1); la demo muestra 2 sets de datos, no 2 sistemas distintos |

**Supuesto clave a validar:** que negociar con un agente en nombre de otra empresa o de uno mismo es aceptable/deseable para el mercado objetivo — esto no está probado y es la apuesta central del producto.

---

## 13. Cronograma — 36 horas, equipo de 4

Tu equipo maneja la asignación de roles como prefiera; esta es una referencia de secuencia por **riesgo**, no por tarea rígida — lo importante es el orden, no quién hace qué.

**Regla general:** en las primeras horas se ataca lo que puede tumbar el proyecto entero (el motor de conversación + la detección de decisión sensible). La UI pulida se construye después, cuando ya sabes que el core funciona — construir UI bonita antes de validar el backend es la forma más común de fallar en una hackathon.

| Bloque horario | Foco | Por qué en ese orden |
|---|---|---|
| **H0–H2** | Setup de repo, stack elegido, división de trabajo, **mock data lista para ambos casos (B2B y P2P)** | Arrancar rápido sin fricción evita perder la primera hora en decisiones; tener ambos sets listos desde ya evita improvisar el segundo caso a última hora |
| **H2–H8** | Motor de conversación agente-agente (2 agentes simulados hablando, con prompts base) + lógica simple de "esto requiere aprobación humana" | Es el riesgo técnico más alto y el corazón de la demo — si no funciona, nada más importa |
| **H8–H12** | Guardrail de límites duros (aunque sea una validación simple de reglas, no solo el prompt) | Es lo que más impresiona/da confianza si se muestra en vivo, y lo más vergonzoso si falla |
| **H12–H16** | Pantalla de Configuración del Agente (conectada al motor real) | Ya con el backend probado, esto es solo UI + conexión |
| **H16–H22** | Pantalla de Conversación (detalle) + Bandeja de decisiones sensibles | Estas dos son las que se muestran en el momento más importante del pitch |
| **H22–H26** | Dashboard + pantalla de Match | Menor riesgo, se hacen últimas a propósito |
| **H26–H28** | Descanso/buffer real (aunque sea 1-2h) | En 36h el error de agotamiento del equipo destruye más demos que la falta de features |
| **H28–H32** | Integración end-to-end + fix de bugs + poblar datos de demo definitivos | Nunca dejar esto para los últimos 30 minutos |
| **H32–H34** | Ensayar el pitch/demo completo al menos 2 veces, cronometrado | Un pitch no ensayado es la causa #1 de fallos en vivo |
| **H34–H36** | Buffer final + backup del demo grabado (ver sección 15) | Margen de seguridad obligatorio |

---

## 14. Qué mockear vs qué construir de verdad (crítico en 36h)

En una hackathon, el tiempo que se gasta en algo que el jurado no puede diferenciar de un mock es tiempo perdido. Sé agresivo mockeando todo lo que no sea el núcleo de la idea:

| Construir de verdad | Mockear/simular sin culpa |
|---|---|
| El motor de conversación entre 2 agentes (con LLM real) | Integraciones con CRM/calendario reales — usa data falsa fija |
| La lógica que detecta "esto es una decisión sensible" | Reputación/verificación de empresas — usa un badge fijo |
| El guardrail de límites duros (aunque sea simple) | Ecosistema con múltiples agentes reales — 2-3 agentes de prueba alcanzan para la demo |
| La UI de las 2-3 pantallas que se muestran en vivo | Historial/analítica — una tabla estática basta |
| Autenticación real | Login — puede ser un botón que entra directo, nadie lo va a probar en el pitch |

**Regla de oro:** si una feature no aparece en el guion de la demo (sección 14), probablemente no vale la pena construirla de verdad esta hackathon.

---

## 15. Plan de demo / pitch (esto puede valer más que el código)

En una hackathon de 36h, un equipo con menos features pero un pitch claro casi siempre le gana a un equipo con más features y una demo confusa. Guion sugerido (ajusta a tu tiempo real de pitch):

1. **Gancho (20-30 seg):** una frase que plantee el dolor sin jerga técnica — ej. "¿Cuántas horas pierdes negociando lo mismo una y otra vez, sea vendiendo tu auto usado a otra persona o buscando proveedores para tu empresa? Nosotros dejamos que un agente de IA tenga esa conversación por ti."
2. **Demo en vivo del loop completo con el primer caso (2-3 min):** configura un agente en vivo (rápido, con algo pre-cargado si hace falta) → muestra la conversación entre dos agentes ya corriendo → llega el momento de decisión sensible → el usuario aprueba en vivo → aparece el match. Este es el momento que debe estar perfectamente ensayado.
3. **Prueba de versatilidad — segundo caso de uso (30-45 seg):** cambien el set de datos y muestren el mismo motor resolviendo el otro segmento (si empezaron con B2B, muestren un caso P2P entre dos personas, o viceversa) — "esto no es una app de sourcing con IA, es una plataforma: el mismo agente que negocia proveedores para tu empresa puede negociar la venta de tu bicicleta usada con otra persona". Este paso es el diferenciador más fuerte de la demo y cuesta casi nada de desarrollo extra.
4. **El "por qué esto es difícil"/diferenciador (30 seg):** menciona el guardrail — "el agente nunca puede cruzar un límite que tú no autorizaste, ni compartir tus datos personales sin que tú lo apruebes, y tú decides exactamente qué cuenta como sensible" — esto genera confianza inmediata en el jurado, especialmente en el caso P2P.
5. **Cierre con visión (20-30 seg):** una línea de hacia dónde va esto (sin entrar en monetización salvo que pregunten) — ej. "hoy validamos el concepto en dos segmentos, mañana esto escala a cualquier proceso repetitivo de negociación, entre empresas o entre personas".

**Consejo de equipo de 4:** designa a **una sola persona** para hablar durante la demo en vivo mientras otra maneja el teclado/pantalla — evita el error clásico de dos personas hablando encima o pasándose el mouse a mitad de la demo.

---

## 16. Riesgos específicos de la demo en vivo

| Riesgo | Mitigación |
|---|---|
| El LLM responde algo raro/incoherente justo en vivo frente al jurado | Ensaya el mismo escenario 3+ veces antes; si es inconsistente, considera fijar el seed/escenario de demo con inputs controlados en vez de improvisar |
| Falla el WiFi/API en el momento del pitch | **Grabar un video de respaldo del demo funcionando perfecto**, listo para reproducir si algo falla en vivo — esto es obligatorio, no opcional, en cualquier hackathon con IA en vivo |
| Se acaba el tiempo de desarrollo y quedan pantallas rotas a medias | Prioriza según la tabla de la sección 6 — es mejor cortar una pantalla completa que mostrar 3 pantallas rotas |
| El jurado no entiende el concepto de "agentes que negocian" en los primeros segundos | Invierte tiempo real en el gancho del pitch (sección 14, paso 1) — es más rentable que una feature extra |
| Nadie del equipo dice cuánto tiempo queda y llegan sin ensayar el pitch | Bloquea explícitamente las horas H32-H34 del cronograma para ensayar — no negociable |

---

## 17. Preguntas abiertas

- ¿Qué vertical P2P específico usarán para la demo? (recomendación: algo simple y visual como "venta de artículo usado entre particulares" o "búsqueda de roomie" — evitar verticales sensibles como bienes raíces reales o transacciones financieras grandes para la demo)
- ¿El ecosistema de la demo arranca con 2-3 agentes de prueba controlados por el propio equipo, o intentan simular más variedad? (para 36h, menos es más seguro)
- ¿Qué pasa en la demo si el "match" no llega en el primer intento en vivo? ¿Tienen un escenario de respaldo pre-cargado, para AMBOS casos de uso?
- ¿Alguien del equipo se dedica exclusivamente a preparar el pitch mientras los otros tres cierran desarrollo, o lo prepara quien tenga tiempo al final? (lo primero reduce mucho el riesgo)
- ¿Qué categorías de "decisión sensible" vienen marcadas por defecto y no se pueden desactivar (datos personales, límites duros), y cuáles quedan realmente a discreción del usuario? Para 36h, recomendamos dejar esto simple: un set fijo no negociable + una lista abierta que el usuario amplía a su gusto — no un sistema de permisos granular completo.
- En la UI de Configuración del Agente, ¿cómo se le presenta al usuario la opción de definir sus propias reglas de escalamiento — como una lista de checkboxes de categorías comunes, o como un campo de texto libre tipo "avísame cuando..."? La primera opción es más rápida de construir y más clara de demostrar en vivo.
