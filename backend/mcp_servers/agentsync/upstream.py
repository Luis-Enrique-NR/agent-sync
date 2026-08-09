"""Small, bounded adapters for external providers behind MCP tools."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class UpstreamError(RuntimeError):
    """A safe, stable error code suitable for an MCP tool response."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


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
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(self.max_response_bytes + 1)
        except HTTPError as exc:
            raise UpstreamError(f"UPSTREAM_HTTP_{exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise UpstreamError("UPSTREAM_NETWORK_ERROR") from exc
        if len(raw) > self.max_response_bytes:
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
        raw = self._read_json(request)
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
        raw = self._read_json(request)
        return self._normalize_results(raw, provider="tavily", query=query)

    def _read_json(self, request: Request) -> dict[str, Any]:
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(self.max_response_bytes + 1)
        except HTTPError as exc:
            raise UpstreamError(f"UPSTREAM_HTTP_{exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise UpstreamError("UPSTREAM_NETWORK_ERROR") from exc
        if len(raw) > self.max_response_bytes:
            raise UpstreamError("UPSTREAM_RESPONSE_TOO_LARGE")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpstreamError("UPSTREAM_INVALID_JSON") from exc
        if not isinstance(value, dict):
            raise UpstreamError("UPSTREAM_INVALID_OBJECT")
        return sanitize_output(value)

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
