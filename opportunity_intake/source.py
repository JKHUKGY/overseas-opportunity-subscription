"""Read-only Freelancer adapter. Credentials travel through curl stdin."""

import json
import subprocess
from typing import Any, Optional, cast
from urllib.parse import urlencode


class SourceError(Exception):
    def __init__(self, kind: str, http_status: Optional[int] = None, *, retry_after: Optional[str] = None) -> None:
        super().__init__(kind)
        self.kind = kind
        self.http_status = http_status
        self.retry_after = retry_after


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
                 "--request", "GET", "--include", "--max-time", str(timeout), "--max-filesize", "2097152",
                 "--write-out", "\n%{http_code}", url],
                input=config.encode(), capture_output=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise SourceError("timeout") from None
        except OSError:
            raise SourceError("transport_unavailable") from None
        if response.returncode != 0:
            raise SourceError("timeout" if response.returncode == 28 else "transport_error")
        body, _, status = response.stdout.rpartition(b"\n")
        retry_after = None
        # curl may include proxy CONNECT / informational headers before the final block.
        while body.startswith(b"HTTP/"):
            headers, separator, body = body.partition(b"\r\n\r\n")
            if not separator:
                raise SourceError("invalid_response")
            retry_after = None
            for header in headers.split(b"\r\n")[1:]:
                name, _, value = header.partition(b":")
                if name.lower() == b"retry-after":
                    retry_after = value.strip().decode("latin-1")
        if status != b"200":
            raise SourceError("http_error", int(status) if status.isdigit() else None, retry_after=retry_after)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeError):
            raise SourceError("invalid_json") from None
        if not isinstance(payload, dict) or payload.get("status") != "success":
            raise SourceError("api_error")
        result = payload.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("projects"), list):
            raise SourceError("invalid_response")
        return cast(list[dict[str, Any]], result["projects"])
