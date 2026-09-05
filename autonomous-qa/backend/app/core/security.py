"""Security-critical utilities.

Two responsibilities live here:

1. Target-URL validation (SSRF prevention) — the platform crawls and
   executes automation against arbitrary user-supplied URLs, so every
   URL must be validated before any network call is made against it.
2. JWT issuing/verification for API authentication.

This module treats every crawl target as untrusted input.
"""
from __future__ import annotations

import ipaddress
import socket
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import SecurityValidationError

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparsable -> treat as unsafe
    return any(ip in net for net in _PRIVATE_NETWORKS) or ip.is_reserved or ip.is_multicast


def validate_target_url(url: str, *, allow_private_override: bool | None = None) -> str:
    """Validate a target URL before it is ever used for crawling/execution.

    Raises SecurityValidationError on any violation. Returns the
    normalized URL on success.
    """
    settings = get_settings()
    allow_private = (
        settings.ALLOW_PRIVATE_NETWORK_TARGETS
        if allow_private_override is None
        else allow_private_override
    )

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SecurityValidationError("Only http/https URLs are allowed.")
    if not parsed.hostname:
        raise SecurityValidationError("URL is missing a hostname.")

    hostname = parsed.hostname.lower()

    allowed_domains = settings.allowed_domains_list
    if allowed_domains and not any(
        hostname == d or hostname.endswith(f".{d}") for d in allowed_domains
    ):
        raise SecurityValidationError(
            f"Domain '{hostname}' is not in the configured allowlist."
        )

    if hostname in ("localhost",) and not allow_private:
        raise SecurityValidationError(
            "Localhost targets are blocked by default. Enable "
            "ALLOW_PRIVATE_NETWORK_TARGETS for local development."
        )

    # Resolve DNS ourselves and check every resolved address. This is the
    # DNS-rebinding mitigation: we validate the addresses the hostname
    # resolves to right now, and the browser is additionally sandboxed
    # by network egress rules in the execution environment.
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise SecurityValidationError(f"Could not resolve host '{hostname}'.") from exc

    resolved_ips = {info[4][0] for info in infos}
    if not allow_private:
        for ip in resolved_ips:
            if _is_private_ip(ip):
                raise SecurityValidationError(
                    f"Target host '{hostname}' resolves to a private/internal "
                    "address, which is blocked by default."
                )

    return url


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise SecurityValidationError("Invalid or expired token.") from exc


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd_context.verify(password, hashed)
