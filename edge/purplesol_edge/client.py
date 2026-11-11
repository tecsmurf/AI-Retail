"""HTTPS client for the cloud API (standard library only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Optional

from purplesol_edge import __version__


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"{status}: {message}" if status else message)
        self.status = status
        self.message = message


class Unauthorized(ApiError):
    """The token is missing, wrong or was revoked: the box must be paired again."""


class ApiClient:
    def __init__(self, base_url: str, token: Optional[str] = None, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: Any = None, raw: Optional[bytes] = None,
                 content_type: Optional[str] = None) -> Any:
        headers = {"User-Agent": f"purplesol-edge/{__version__}", "Accept": "application/json"}
        body = raw
        if payload is not None:
            body = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        elif content_type:
            headers["Content-Type"] = content_type
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.base_url + path, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                text = res.read().decode() or "null"
                return json.loads(text)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                parsed = json.loads(exc.read().decode() or "{}")
                detail = parsed.get("detail") if isinstance(parsed, dict) else ""
            except (ValueError, OSError):
                pass
            message = detail if isinstance(detail, str) and detail else f"HTTP {exc.code}"
            if exc.code == 401:
                raise Unauthorized(401, message) from None
            raise ApiError(exc.code, message) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise ApiError(0, f"cannot reach {self.base_url}: {reason}") from None

    def pair(self, code: str, hostname: str) -> dict:
        return self._request("POST", "/api/edge/pair", {"code": code, "hostname": hostname, "agent_version": __version__})

    def config(self) -> dict:
        return self._request("GET", "/api/edge/config")

    def heartbeat(self, payload: dict) -> dict:
        return self._request("POST", "/api/edge/heartbeat", payload)

    def send(self, events: list, occupancy: list) -> dict:
        return self._request("POST", "/api/edge/events", {"events": events, "occupancy": occupancy})

    def snapshot(self, camera_id: str, jpeg: bytes) -> None:
        self._request("PUT", f"/api/edge/cameras/{camera_id}/snapshot", raw=jpeg, content_type="image/jpeg")
