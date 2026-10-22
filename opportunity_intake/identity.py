"""Source identity and conservative URL matching shared by intake and exclusions."""

from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def project_url(project: dict[str, Any]) -> Optional[str]:
    slug = project.get("seo_url")
    return "https://www.freelancer.com/projects/" + slug.lstrip("/") if isinstance(slug, str) and slug else None


def canonical_url(url: Optional[str]) -> Optional[str]:
    if url is None:
        return None
    parts = urlsplit(url)
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.startswith("utm_")])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))
