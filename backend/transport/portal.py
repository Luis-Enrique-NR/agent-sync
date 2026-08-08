"""Server-side Portal seams and documented control-plane commands."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Protocol, TypeAlias
from urllib.parse import quote

import httpx
from pydantic import Field, TypeAdapter

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


class ChannelMember(StrictModel):
    user_id: str = Field(min_length=1)
    claims: dict[str, Any] | None = None


class AddChannelMembers(StrictModel):
    operation: Literal["add_members"] = "add_members"
    authorization_id: str = Field(min_length=1)
    channel_id: str = Field(min_length=1)
    members: list[ChannelMember] = Field(min_length=1, max_length=100)


class RemoveChannelMember(StrictModel):
    operation: Literal["remove_member"] = "remove_member"
    authorization_id: str = Field(min_length=1)
    channel_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)


class BanChannelUser(StrictModel):
    operation: Literal["ban_user"] = "ban_user"
    authorization_id: str = Field(min_length=1)
    channel_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    expires_at: datetime | None = None


class UnbanChannelUser(StrictModel):
    operation: Literal["unban_user"] = "unban_user"
    authorization_id: str = Field(min_length=1)
    channel_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)


AuthorizedPortalCommand: TypeAlias = PublishMessage | AddChannelMembers | RemoveChannelMember | BanChannelUser | UnbanChannelUser
_COMMAND_ADAPTER = TypeAdapter(AuthorizedPortalCommand)


class PublishedMessage(StrictModel):
    id: str
    seq: int
    timestamp: int


class CommandApplied(StrictModel):
    operation: Literal["add_members", "remove_member", "ban_user", "unban_user"]
    added: int | None = None


class PortalRejected(StrictModel):
    code: str
    reason: str | None = None


class PortalUncertain(StrictModel):
    code: Literal["timeout"] = "timeout"


class PortalRetryable(StrictModel):
    code: Literal["rate_limited", "transient"]


PortalOutcome = PublishedMessage | CommandApplied | PortalRejected | PortalRetryable | PortalUncertain


class PortalAdmin(Protocol):
    async def execute(self, command: AuthorizedPortalCommand) -> PortalOutcome:
        """Execute one Backend-authorized, Portal-documented command."""


def parse_authorized_command(value: object) -> AuthorizedPortalCommand:
    """Fail closed before an adapter can receive an unknown command shape."""
    return _COMMAND_ADAPTER.validate_python(value)


def _member_body(member: ChannelMember) -> dict[str, Any]:
    body: dict[str, Any] = {"userId": member.user_id}
    if member.claims is not None:
        body["claims"] = member.claims
    return body


def _error(response: httpx.Response) -> PortalRejected:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    return PortalRejected(code=payload.get("code", "rejected"), reason=payload.get("reason"))


def _failure(response: httpx.Response) -> PortalRejected | PortalRetryable:
    if response.status_code == 429:
        return PortalRetryable(code="rate_limited")
    if response.status_code >= 500:
        return PortalRetryable(code="transient")
    return _error(response)


def _added(response: httpx.Response) -> int | PortalRejected:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if not isinstance(payload, dict) or type(payload.get("added")) is not int:
        return PortalRejected(code="invalid_response", reason="missing or non-integer added")
    return payload["added"]


class HttpPortalClient:
    """Lifespan-scoped client for documented, server-only Portal mutations."""

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

    async def execute(self, command: AuthorizedPortalCommand) -> PortalOutcome:
        if not isinstance(command, (PublishMessage, AddChannelMembers, RemoveChannelMember, BanChannelUser, UnbanChannelUser)):
            return PortalRejected(code="unsupported_command")
        if self._client is None:
            raise RuntimeError("HttpPortalClient must be used within its lifespan")
        channel = quote(command.channel_id, safe="")
        headers = {"Authorization": f"Bearer {self._secret}"}
        if isinstance(command, PublishMessage):
            method, path, body = "POST", f"/v1/channels/{channel}/messages", {"senderId": command.sender_id, "content": command.content, "type": command.type, "kind": command.kind}
        elif isinstance(command, AddChannelMembers):
            members = [_member_body(member) for member in command.members]
            method, path, body = "POST", f"/v1/channels/{channel}/members", {"members": members} if len(members) > 1 else members[0]
        elif isinstance(command, RemoveChannelMember):
            method, path, body = "DELETE", f"/v1/channels/{channel}/members/{quote(command.user_id, safe='')}", None
        elif isinstance(command, BanChannelUser):
            body = {"userId": command.user_id}
            if command.expires_at is not None:
                body["expiresAt"] = command.expires_at.isoformat().replace("+00:00", "Z")
            method, path = "POST", f"/v1/channels/{channel}/bans"
        else:
            method, path, body = "DELETE", f"/v1/channels/{channel}/bans/{quote(command.user_id, safe='')}", None
        try:
            response = await self._client.request(method, path, headers=headers, json=body)
        except httpx.TimeoutException:
            return PortalUncertain()
        if response.status_code != 200:
            return _failure(response)
        if isinstance(command, PublishMessage):
            return PublishedMessage.model_validate(response.json())
        if isinstance(command, AddChannelMembers):
            added = _added(response)
            if isinstance(added, PortalRejected):
                return added
            return CommandApplied(operation=command.operation, added=added)
        return CommandApplied(operation=command.operation)
