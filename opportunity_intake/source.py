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


def _response_headers(raw: bytes) -> tuple[Optional[int], Optional[str]]:
    status = None
    retry_after = None
    # The header stream can contain proxy CONNECT and informational responses.
    for block in raw.split(b"\r\n\r\n")[:-1]:
        lines = block.split(b"\r\n")
        parts = lines[0].split()
        if len(parts) < 2 or not parts[0].startswith(b"HTTP/") or not parts[1].isdigit():
            continue
        status = int(parts[1])
        retry_after = None
        for header in lines[1:]:
            name, _, value = header.partition(b":")
            if name.lower() == b"retry-after":
                retry_after = value.strip().decode("latin-1")
    return status, retry_after


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
        transfer_error = None
        try:
            response = subprocess.run(
                ["curl", "--disable", "--config", "-", "--silent", "--show-error",
                 "--request", "GET", "--dump-header", "/dev/stderr", "--max-time", str(timeout),
                 "--max-filesize", "2097152", url],
                input=config.encode(), capture_output=True, timeout=timeout,
            )
            body, headers = response.stdout, response.stderr
            if response.returncode != 0:
                transfer_error = "timeout" if response.returncode == 28 else "transport_error"
        except subprocess.TimeoutExpired as error:
            body, headers = error.stdout or b"", error.stderr or b""
            transfer_error = "timeout"
        except OSError:
            raise SourceError("transport_unavailable") from None
        status, retry_after = _response_headers(headers)
        # Keep an explicit HTTP refusal even if its optional body cannot be read.
        if status is not None and status >= 300:
            raise SourceError("http_error", status, retry_after=retry_after)
        if transfer_error:
            raise SourceError(transfer_error)
        if status != 200:
            raise SourceError("invalid_response")
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
