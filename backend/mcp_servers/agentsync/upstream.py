"""Small, bounded adapters for external providers behind MCP tools."""

from __future__ import annotations

import json
import os
import re
from base64 import b64encode
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class UpstreamError(RuntimeError):
    """A safe, stable error code suitable for an MCP tool response."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


_EMAIL_ADDRESS_PATTERN = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")
_DEFAULT_LOGO_PATH = Path(__file__).with_name("assets") / "agentsync-logo.png"
_INLINE_LOGO_CONTENT_ID = "agentsync-logo"
_MAX_INLINE_LOGO_BYTES = 1_000_000


def validate_recipient_address(value: str) -> str:
    """Validate a per-call recipient before it reaches an email provider."""

    normalized = value.strip()
    if len(normalized) > 320 or not _EMAIL_ADDRESS_PATTERN.fullmatch(normalized):
        raise UpstreamError("INVALID_EMAIL_RECIPIENT")
    return normalized


def _load_inline_logo(path: str | None) -> dict[str, str] | None:
    """Load the packaged frontend favicon for a CID-backed email image."""

    logo_path = Path(path) if path else _DEFAULT_LOGO_PATH
    try:
        content = logo_path.read_bytes()
    except OSError:
        # Branding must never make a notification unavailable.  The text and
        # HTML body still render when a deployment omits the optional asset.
        return None
    if not content or len(content) > _MAX_INLINE_LOGO_BYTES:
        return None
    return {
        "content": b64encode(content).decode("ascii"),
        "filename": logo_path.name,
        "content_id": _INLINE_LOGO_CONTENT_ID,
        "content_type": "image/png",
    }


def _render_email_html(subject: str, body: str, *, has_logo: bool) -> str:
    """Render a small escaped HTML alternative with an optional inline logo."""

    logo = (
        '<img src="cid:agentsync-logo" alt="AgentSync" width="48" height="48" '
        'style="display:block;margin:0 0 20px;border:0;" />'
        if has_logo
        else ""
    )
    safe_subject = escape(subject)
    safe_body = escape(body).replace("\r\n", "\n").replace("\n", "<br />\n")
    return (
        '<!doctype html><html><body style="font-family:Arial,sans-serif;'
        'color:#172033;line-height:1.5;">'
        f"{logo}<h2 style=\"margin:0 0 12px;\">{safe_subject}</h2>"
        f"<p style=\"white-space:normal;\">{safe_body}</p>"
        '<p style="color:#64748b;font-size:12px;margin-top:24px;">AgentSync</p>'
        "</body></html>"
    )


def sanitize_output(value: Any, *, max_string_length: int = 4_000) -> Any:
    """Remove obvious credentials/PII and cap untrusted provider output."""

    blocked_keys = {
        "password",
        "token",
        "secret",
        "api_key",
        "authorization",
        "access_token",
        "refresh_token",
        "phone",
        "email",
        "exact_address",
        "live_location",
        "meeting_point",
    }
    if isinstance(value, str):
        return value[:max_string_length]
    if isinstance(value, list):
        return [sanitize_output(item, max_string_length=max_string_length) for item in value[:100]]
    if isinstance(value, dict):
        return {
            str(key): sanitize_output(item, max_string_length=max_string_length)
            for key, item in list(value.items())[:100]
            if str(key).lower() not in blocked_keys
        }
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:max_string_length]


@dataclass(frozen=True, slots=True)
class HTTPUpstream:
    endpoint: str | None
    token_env: str | None
    timeout_seconds: int
    max_response_bytes: int
    environ: Mapping[str, str]

    def post_json(self, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        if not self.endpoint:
            raise UpstreamError("UPSTREAM_NOT_CONFIGURED")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Idempotency-Key": idempotency_key,
        }
        if self.token_env:
            token = self.environ.get(self.token_env)
            if not token:
                raise UpstreamError("UPSTREAM_TOKEN_NOT_CONFIGURED")
            headers["Authorization"] = f"Bearer {token}"
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = Request(self.endpoint, data=body, headers=headers, method="POST")
        return read_json_response(
            request,
            timeout_seconds=self.timeout_seconds,
            max_response_bytes=self.max_response_bytes,
        )


def read_json_response(
    request: Request,
    *,
    timeout_seconds: int,
    max_response_bytes: int,
) -> dict[str, Any]:
    """Read one bounded JSON object from a provider without leaking its body."""

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read(max_response_bytes + 1)
    except HTTPError as exc:
        raise UpstreamError(f"UPSTREAM_HTTP_{exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise UpstreamError("UPSTREAM_NETWORK_ERROR") from exc
    if len(raw) > max_response_bytes:
        raise UpstreamError("UPSTREAM_RESPONSE_TOO_LARGE")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpstreamError("UPSTREAM_INVALID_JSON") from exc
    if not isinstance(value, dict):
        raise UpstreamError("UPSTREAM_INVALID_OBJECT")
    return sanitize_output(value)


@dataclass(frozen=True, slots=True)
class SearchAdapter:
    provider: str
    endpoint: str | None
    token_env: str | None
    timeout_seconds: int
    max_response_bytes: int
    environ: Mapping[str, str]

    def search(self, query: str, *, idempotency_key: str) -> dict[str, Any]:
        if self.provider == "brave":
            return self._brave(query)
        if self.provider == "tavily":
            return self._tavily(query, idempotency_key=idempotency_key)
        raw = HTTPUpstream(
            self.endpoint,
            self.token_env,
            self.timeout_seconds,
            self.max_response_bytes,
            self.environ,
        ).post_json({"query": query}, idempotency_key=idempotency_key)
        return self._normalize_results(raw, provider="generic", query=query)

    def _brave(self, query: str) -> dict[str, Any]:
        token_name = self.token_env or "BRAVE_SEARCH_API_KEY"
        token = self.environ.get(token_name)
        if not token:
            raise UpstreamError("UPSTREAM_TOKEN_NOT_CONFIGURED")
        endpoint = self.endpoint or "https://api.search.brave.com/res/v1/web/search"
        url = f"{endpoint}?{urlencode({'q': query, 'count': 10})}"
        request = Request(
            url,
            headers={"Accept": "application/json", "X-Subscription-Token": token},
            method="GET",
        )
        raw = read_json_response(
            request,
            timeout_seconds=self.timeout_seconds,
            max_response_bytes=self.max_response_bytes,
        )
        return self._normalize_results(raw, provider="brave", query=query)

    def _tavily(self, query: str, *, idempotency_key: str) -> dict[str, Any]:
        token_name = self.token_env or "TAVILY_API_KEY"
        token = self.environ.get(token_name)
        if not token:
            raise UpstreamError("UPSTREAM_TOKEN_NOT_CONFIGURED")
        endpoint = self.endpoint or "https://api.tavily.com/search"
        request = Request(
            endpoint,
            data=json.dumps(
                {"api_key": token, "query": query, "max_results": 10},
                separators=(",", ":"),
            ).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Idempotency-Key": idempotency_key,
            },
            method="POST",
        )
        raw = read_json_response(
            request,
            timeout_seconds=self.timeout_seconds,
            max_response_bytes=self.max_response_bytes,
        )
        return self._normalize_results(raw, provider="tavily", query=query)

    @staticmethod
    def _normalize_results(raw: dict[str, Any], *, provider: str, query: str) -> dict[str, Any]:
        source: Any = raw
        if provider == "brave":
            source = raw.get("web", {})
        results = source.get("results", []) if isinstance(source, dict) else []
        if not isinstance(results, list):
            raise UpstreamError("UPSTREAM_INVALID_RESULTS")
        normalized = []
        for result in results[:20]:
            if not isinstance(result, dict):
                continue
            normalized.append(
                {
                    "title": str(result.get("title", ""))[:500],
                    "url": str(result.get("url", result.get("link", "")))[:2_000],
                    "snippet": str(
                        result.get("snippet", result.get("description", ""))
                    )[:2_000],
                }
            )
        return {"query": query, "provider": provider, "results": normalized}


@dataclass(frozen=True, slots=True)
class SerpApiAdapter:
    """Google Shopping adapter for reference prices."""

    endpoint: str | None
    token_env: str | None
    timeout_seconds: int
    max_response_bytes: int
    environ: Mapping[str, str]

    def search(self, item: str, region: str, currency: str) -> dict[str, Any]:
        token_name = self.token_env or "SERPAPI_API_KEY"
        token = self.environ.get(token_name)
        if not token:
            raise UpstreamError("UPSTREAM_TOKEN_NOT_CONFIGURED")
        params = {
            "engine": "google_shopping",
            "q": item,
            "api_key": token,
            "output": "json",
        }
        if region:
            params["location"] = region
        if currency:
            params["currency"] = currency.upper()
        endpoint = self.endpoint or "https://serpapi.com/search"
        request = Request(
            f"{endpoint}?{urlencode(params)}",
            headers={"Accept": "application/json", "User-Agent": "AgentSync-MCP/0.1.0"},
            method="GET",
        )
        raw = read_json_response(
            request,
            timeout_seconds=self.timeout_seconds,
            max_response_bytes=self.max_response_bytes,
        )
        shopping_results = raw.get("shopping_results", [])
        if not isinstance(shopping_results, list):
            raise UpstreamError("UPSTREAM_INVALID_RESULTS")
        items = []
        for result in shopping_results[:20]:
            if not isinstance(result, dict):
                continue
            items.append(
                {
                    "product_id": str(result.get("product_id", result.get("title", "")))[:200],
                    "name": str(result.get("title", ""))[:500],
                    "price": result.get("extracted_price", result.get("price")),
                    "currency": currency.upper(),
                    "seller": str(result.get("source", ""))[:200],
                    "url": str(result.get("link", ""))[:2_000],
                }
            )
        return {
            "provider": "serpapi",
            "item": item,
            "region": region,
            "currency": currency.upper(),
            "items": sanitize_output(items),
        }


@dataclass(frozen=True, slots=True)
class ResendAdapter:
    """Owner notification adapter using Resend's transactional email API."""

    endpoint: str | None
    token_env: str | None
    from_address: str | None
    timeout_seconds: int
    max_response_bytes: int
    environ: Mapping[str, str]
    logo_path: str | None = None

    def send(
        self,
        subject: str,
        body: str,
        to_address: str,
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        token_name = self.token_env or "RESEND_API_KEY"
        token = self.environ.get(token_name)
        if not token:
            raise UpstreamError("UPSTREAM_TOKEN_NOT_CONFIGURED")
        recipient = validate_recipient_address(to_address)
        if not self.from_address:
            raise UpstreamError("UPSTREAM_DESTINATION_NOT_CONFIGURED")
        logo = _load_inline_logo(self.logo_path)
        request = Request(
            self.endpoint or "https://api.resend.com/emails",
            data=json.dumps(
                {
                    "from": self.from_address,
                    "to": [recipient],
                    "subject": subject,
                    "text": body,
                    "html": _render_email_html(subject, body, has_logo=logo is not None),
                    **({"attachments": [logo]} if logo else {}),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": idempotency_key,
                "User-Agent": "AgentSync-MCP/0.1.0",
            },
            method="POST",
        )
        raw = read_json_response(
            request,
            timeout_seconds=self.timeout_seconds,
            max_response_bytes=self.max_response_bytes,
        )
        return write_result(raw, operation="email")


def write_result(raw: dict[str, Any], *, operation: str) -> dict[str, Any]:
    """Keep write responses small and stable while retaining provider IDs."""

    allowed = {"id", "status", "delivery_id", "meeting_id", "start", "end", "currency"}
    output = {key: value for key, value in raw.items() if key in allowed}
    if operation == "email" and "delivery_id" not in output and "id" in output:
        output["delivery_id"] = output.pop("id")
    if operation == "meeting" and "meeting_id" not in output and "id" in output:
        output["meeting_id"] = output.pop("id")
    if "status" not in output:
        output["status"] = "accepted"
    return output
