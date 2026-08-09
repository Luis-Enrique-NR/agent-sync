# Servidor MCP propio de AgentSync

Este servicio expone las capacidades externas del agente como un servidor MCP
independiente del motor LangGraph. El backend AI sigue siendo responsable de
decidir si una tool está permitida, si requiere aprobación humana, y de
registrar la ejecución. El proceso MCP únicamente mantiene las credenciales de
los proveedores, llama a sus APIs y devuelve resultados sanitizados.

## Ejecución local

Desde `backend/`:

```powershell
uv sync
uv run uvicorn mcp_servers.agentsync.server:app --host 127.0.0.1 --port 8001
```

El endpoint MCP es `http://127.0.0.1:8001/mcp` y el health check es
`http://127.0.0.1:8001/health`. También se puede inspeccionar con el MCP
Inspector:

```powershell
uv run mcp dev mcp_servers/agentsync/server.py
```

## Tools publicadas

| Tool | Tipo | Requiere aprobación en AI Backend |
| --- | --- | --- |
| `web.search` | lectura pública | no, salvo regla del usuario |
| `market.reference_prices` | lectura pública | no |
| `email.send_notification` | escritura externa | sí, siempre |

Las anotaciones MCP (`readOnlyHint`, `destructiveHint`, etc.) ayudan a la UI,
pero no sustituyen la política determinística de `ai.tools.gateway`.

## Proveedores reales

El valor inicial es seguro: si un endpoint o secreto no está configurado, la
tool falla con `UPSTREAM_NOT_CONFIGURED` o
`UPSTREAM_TOKEN_NOT_CONFIGURED`; no se inventan datos. El buscador tiene
adaptadores directos para `brave` y `tavily`, SerpApi para precios y Resend para
correo. Los proveedores genéricos siguen disponibles
como fallback mediante un contrato HTTP `POST`, con
`Authorization: Bearer <token>` opcional y `X-Idempotency-Key`.

Variables principales:

```dotenv
AGENTSYNC_MCP_SEARCH_PROVIDER=brave
AGENTSYNC_MCP_SEARCH_TOKEN_ENV=BRAVE_SEARCH_API_KEY
AGENTSYNC_MCP_PRICES_PROVIDER=serpapi
AGENTSYNC_MCP_PRICES_TOKEN_ENV=SERPAPI_API_KEY
AGENTSYNC_MCP_EMAIL_PROVIDER=resend
AGENTSYNC_MCP_EMAIL_TOKEN_ENV=RESEND_API_KEY
AGENTSYNC_MCP_EMAIL_FROM=notificaciones@example.com
# Optional override; defaults to the packaged frontend favicon.
# AGENTSYNC_MCP_EMAIL_LOGO_PATH=
```

El destinatario no se configura en el servidor: se recibe como el argumento
`to` de cada llamada a `email.send_notification`, se valida antes de llegar al
proveedor y la ejecución sigue requiriendo aprobación humana en el AI Backend.
Así el agente puede notificar al propietario o a un contacto autorizado sin
fijar una dirección global.

Ejemplo de argumentos enviados por el AI Backend:

```json
{"to":"contacto@example.com","subject":"Decisión pendiente","body":"Tu agente requiere una respuesta."}
```

Cuando se usa Resend, el servidor agrega automáticamente el favicon del
frontend como imagen inline mediante CID y conserva el cuerpo `text` como
fallback para clientes que no rendericen HTML. Resend recomienda referenciar
la imagen con `cid:` y enviar el adjunto con `content_id`.

Para proteger el endpoint entre procesos, definir
`AGENTSYNC_MCP_AUTH_TOKEN_ENV=MCP_SERVER_TOKEN` y el valor de
`MCP_SERVER_TOKEN` solo en el entorno del servidor. También se deben ajustar
`AGENTSYNC_MCP_ALLOWED_HOSTS` y `AGENTSYNC_MCP_ALLOWED_ORIGINS` al despliegue.

## Contrato del backend AI

El cliente HTTP del backend agrega `MCP-Protocol-Version`, el envelope
`_meta` del protocolo actual y las cabeceras de método/nombre requeridas por el
servidor. La lista remota se puede consultar con `HTTPMCPClient.list_tools`,
pero la ejecución continúa restringida al catálogo explícito de
`build_mcp_tool_gateway` y a los grants del agente.

Para conectar el backend al proceso local:

```dotenv
AGENTSYNC_TOOLS_PROVIDER=mcp
AGENTSYNC_MCP_DEFAULT_SERVER=default
AGENTSYNC_MCP_SERVERS_JSON={"default":{"endpoint":"http://127.0.0.1:8001/mcp","allowed_tools":["web.search","market.reference_prices","email.send_notification"]}}
```

Este JSON solo cambia cuando cambia la ubicación o la autenticación del
servidor MCP. En el mismo equipo se mantiene `127.0.0.1:8001`; después de un
despliegue separado se sustituye por la URL desplegada (incluyendo `/mcp`) y,
si aplica, se agrega `token_env_var` con el nombre de una variable de entorno,
nunca el secreto:

```dotenv
AGENTSYNC_MCP_SERVERS_JSON={"default":{"endpoint":"https://mcp.example.com/mcp","token_env_var":"MCP_SERVER_TOKEN","allowed_tools":["web.search","market.reference_prices","email.send_notification"]}}
```

Las credenciales de proveedores nunca se colocan en `AGENTSYNC_MCP_SERVERS_JSON`
ni en perfiles, DTOs o prompts del agente.
