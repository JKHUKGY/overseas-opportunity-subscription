"""Read-only Freelancer adapter. Credentials travel through curl stdin."""

import json
import subprocess
from typing import Any, Optional, cast
from urllib.parse import urlencode


class SourceError(Exception):
    def __init__(self, kind: str, http_status: Optional[int] = None) -> None:
        super().__init__(kind)
        self.kind = kind
        self.http_status = http_status


class FreelancerSource:
    def __init__(self, token: str = "", *,
                 base_url: str = "https://www.freelancer.com/api/projects/0.1/projects/active/") -> None:
        if any(ord(character) < 32 or ord(character) == 127 for character in token):
            raise ValueError("Invalid credential format")
        self._token = token
        self._base_url = base_url

    def search(self, query: str, limit: int, offset: int, timeout: float) -> list[dict[str, Any]]:
        url = self._base_url + "?" + urlencode({
            "query": query, "limit": limit, "offset": offset, "full_description": "true",
        })
        config = 'header = "Accept: application/json"\n'
        if self._token:
            escaped = self._token.replace("\\", "\\\\").replace('"', '\\"')
            config += 'header = "freelancer-oauth-v1: ' + escaped + '"\n'
        try:
            response = subprocess.run(
                ["curl", "--disable", "--config", "-", "--silent", "--show-error",
                 "--request", "GET", "--max-time", str(timeout), "--max-filesize", "2097152",
                 "--write-out", "\n%{http_code}", url],
                input=config, capture_output=True, text=True, timeout=timeout + 1,
            )
        except subprocess.TimeoutExpired:
            raise SourceError("timeout") from None
        except OSError:
            raise SourceError("transport_unavailable") from None
        if response.returncode != 0:
            raise SourceError("timeout" if response.returncode == 28 else "transport_error")
        body, _, status = response.stdout.rpartition("\n")
        if status != "200":
            raise SourceError("http_error", int(status) if status.isdigit() else None)
        try:
            payload = json.loads(body)
        except ValueError:
            raise SourceError("invalid_json") from None
        if not isinstance(payload, dict) or payload.get("status") != "success":
            raise SourceError("api_error")
        result = payload.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("projects"), list):
            raise SourceError("invalid_response")
        return cast(list[dict[str, Any]], result["projects"])
