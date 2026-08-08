"""Server-side Portal seams and the documented control-plane adapter."""

from __future__ import annotations

from typing import Any, Literal, Protocol, TypeAlias

import httpx
from pydantic import Field

from transport.models import StrictModel

class WebhookSecretProvider(Protocol):
    async def get_secret(self) -> str | None:
        """Return a server-side secret, or None to fail closed."""


class PublishMessage(StrictModel):
    operation: Literal["publish"] = "publish"
    authorization_id: str = Field(min_length=1)
    channel_id: str = Field(min_length=1)
    sender_id: str = Field(min_length=1)
    content: dict[str, Any]
    type: str = "message"
    kind: Literal["text"] = "text"


AuthorizedPortalCommand: TypeAlias = PublishMessage


class PublishedMessage(StrictModel):
    id: str
    seq: int
    timestamp: int


class PortalRejected(StrictModel):
    code: str


class PortalUncertain(StrictModel):
    code: Literal["timeout"] = "timeout"


PortalOutcome = PublishedMessage | PortalRejected | PortalUncertain


class PortalAdmin(Protocol):
    async def execute(self, command: AuthorizedPortalCommand) -> PortalOutcome:
        """Execute one Backend-authorized, Portal-documented command."""


def parse_authorized_command(value: object) -> PublishMessage:
    """Fail closed before an adapter can receive an unknown command shape."""
    return PublishMessage.model_validate(value)


class HttpPortalClient:
    """Lifespan-scoped control-plane client for the documented server publish."""

    def __init__(self, secret: str, client: httpx.AsyncClient | None = None) -> None:
        self._secret = secret
        self._client = client
        self._owns_client = False

    async def __aenter__(self) -> "HttpPortalClient":
        if self._client is None:
            self._client = httpx.AsyncClient(base_url="https://api.useportal.co")
            self._owns_client = True
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def execute(self, command: PublishMessage) -> PortalOutcome:
        if not isinstance(command, PublishMessage):
            return PortalRejected(code="unsupported_command")
        if self._client is None:
            raise RuntimeError("HttpPortalClient must be used within its lifespan")
        try:
            response = await self._client.post(
                f"/v1/channels/{command.channel_id}/messages",
                headers={"Authorization": f"Bearer {self._secret}"},
                json={"senderId": command.sender_id, "content": command.content, "type": command.type, "kind": command.kind},
            )
        except httpx.TimeoutException:
            return PortalUncertain()
        if response.status_code != 200:
            return PortalRejected(code=response.headers.get("x-portal-error", "rejected"))
        return PublishedMessage.model_validate(response.json())
