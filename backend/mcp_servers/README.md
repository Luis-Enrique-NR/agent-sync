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
| `calendar.check_availability` | lectura sensible | no por defecto |
| `market.reference_prices` | lectura pública | no |
| `inventory.check_stock` | lectura sensible | no por defecto |
| `email.send_notification` | escritura externa | sí, siempre |
| `calendar.request_meeting` | escritura externa | sí, siempre |

Las anotaciones MCP (`readOnlyHint`, `destructiveHint`, etc.) ayudan a la UI,
pero no sustituyen la política determinística de `ai.tools.gateway`.

## Proveedores reales

El valor inicial es seguro: si un endpoint o secreto no está configurado, la
tool falla con `UPSTREAM_NOT_CONFIGURED` o
`UPSTREAM_TOKEN_NOT_CONFIGURED`; no se inventan datos. El buscador tiene
adaptadores directos para `brave` y `tavily`. Calendario, precios, inventario,
correo y reuniones usan un contrato HTTP genérico `POST` definido por el
equipo, con `Authorization: Bearer <token>` opcional y
`X-Idempotency-Key`.

Variables principales:

```dotenv
AGENTSYNC_MCP_SEARCH_PROVIDER=brave
AGENTSYNC_MCP_SEARCH_TOKEN_ENV=BRAVE_SEARCH_API_KEY
AGENTSYNC_MCP_CALENDAR_ENDPOINT=https://calendar.internal/check
AGENTSYNC_MCP_CALENDAR_TOKEN_ENV=CALENDAR_API_TOKEN
AGENTSYNC_MCP_EMAIL_ENDPOINT=https://mail.internal/notify
AGENTSYNC_MCP_EMAIL_TOKEN_ENV=EMAIL_API_TOKEN
AGENTSYNC_MCP_MEETINGS_ENDPOINT=https://calendar.internal/meetings
AGENTSYNC_MCP_MEETINGS_TOKEN_ENV=MEETINGS_API_TOKEN
```

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
AGENTSYNC_MCP_SERVERS_JSON={"default":{"endpoint":"http://127.0.0.1:8001/mcp","allowed_tools":["web.search","calendar.check_availability","market.reference_prices","inventory.check_stock","email.send_notification","calendar.request_meeting"]}}
```

Las credenciales de proveedores nunca se colocan en `AGENTSYNC_MCP_SERVERS_JSON`
ni en perfiles, DTOs o prompts del agente.
