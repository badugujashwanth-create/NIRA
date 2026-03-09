from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class PathSecurityError(ValueError):
    pass


def state_workspace_root(state: Any, default: Path | None = None) -> Path:
    context = getattr(state, "context", {}) or {}
    raw_root = context.get("cwd") if isinstance(context, dict) else None
    root = Path(str(raw_root or default or Path.cwd())).expanduser()
    return root.resolve()


def resolve_within_root(
    root: Path | str,
    user_path: str | Path,
    *,
    must_exist: bool = False,
) -> Path:
    base = Path(root).expanduser().resolve()
    candidate = Path(user_path).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise PathSecurityError(f"Path escapes allowed root: {user_path}") from exc
    if must_exist and not resolved.exists():
        raise FileNotFoundError(resolved)
    return resolved


def sanitize_filename(name: str, default: str = "artifact", max_length: int = 80) -> str:
    raw = Path(name).name.strip()
    if not raw:
        raw = default
    stem = Path(raw).stem or default
    suffix = Path(raw).suffix
    clean_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-") or default
    clean_suffix = re.sub(r"[^A-Za-z0-9.]+", "", suffix)[:12]
    filename = f"{clean_stem[:max_length]}{clean_suffix}"
    return filename or default


def safe_slug(value: str, default: str = "artifact", max_length: int = 60) -> str:
    collapsed = re.sub(r"[^A-Za-z0-9]+", "_", value.lower()).strip("_")
    return (collapsed[:max_length] or default).strip("_") or default


def validate_public_http_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http:// and https:// URLs are allowed.")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in URLs are not allowed.")
    host = parsed.hostname
    if not host:
        raise ValueError("URL must include a host.")
    normalized_host = host.strip().lower()
    if normalized_host in {"localhost", "0.0.0.0"} or normalized_host.endswith(".local"):
        raise ValueError("Local network URLs are not allowed.")
    try:
        ip = ipaddress.ip_address(normalized_host)
    except ValueError:
        if "." not in normalized_host:
            raise ValueError("Only public hostnames are allowed.")
    else:
        if any(
            (
                ip.is_private,
                ip.is_loopback,
                ip.is_link_local,
                ip.is_multicast,
                ip.is_reserved,
                ip.is_unspecified,
            )
        ):
            raise ValueError("Private or local IP addresses are not allowed.")
    return url
