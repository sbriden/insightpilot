"""Simple shared-password admin gate for personal/admin deploys."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Optional

from fastapi import Header, HTTPException, Request


ADMIN_TOKEN_HEADER = "X-Admin-Token"
ADMIN_COOKIE_NAME = "ip_admin"
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


def admin_password() -> str:
    return (os.getenv("ADMIN_PASSWORD") or "").strip()


def admin_auth_enabled() -> bool:
    return bool(admin_password())


def _session_secret() -> str:
    return (
        (os.getenv("ADMIN_SESSION_SECRET") or "").strip()
        or admin_password()
        or "insightpilot-dev"
    )


def issue_admin_token() -> str:
    issued_at = int(time.time())
    payload = f"admin:{issued_at}"
    signature = hmac.new(
        _session_secret().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{signature}"


def verify_admin_token(token: str | None) -> bool:
    if not token or not admin_auth_enabled():
        return not admin_auth_enabled()
    try:
        payload, signature = token.rsplit(".", 1)
    except ValueError:
        return False
    expected = hmac.new(
        _session_secret().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False
    try:
        _, issued_raw = payload.split(":", 1)
        issued_at = int(issued_raw)
    except ValueError:
        return False
    if issued_at > int(time.time()) + 60:
        return False
    if int(time.time()) - issued_at > TOKEN_TTL_SECONDS:
        return False
    return True


def password_matches(candidate: str | None) -> bool:
    expected = admin_password()
    if not expected:
        return True
    return hmac.compare_digest(
        expected.encode("utf-8"),
        (candidate or "").encode("utf-8"),
    )


def extract_admin_token(
    request: Request,
    header_token: Optional[str] = None,
) -> str | None:
    if header_token and header_token.strip():
        return header_token.strip()
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    cookie = request.cookies.get(ADMIN_COOKIE_NAME)
    return cookie.strip() if cookie else None


def require_admin(
    request: Request,
    x_admin_token: Optional[str] = Header(default=None, alias=ADMIN_TOKEN_HEADER),
) -> None:
    if not admin_auth_enabled():
        return
    token = extract_admin_token(request, x_admin_token)
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Admin authentication required.")


def is_public_path(path: str, method: str) -> bool:
    """Paths that stay open when admin auth is enabled."""
    if method.upper() == "OPTIONS":
        return True
    if path in {"/", "/docs", "/openapi.json", "/redoc"}:
        return True
    if path.startswith("/api/health"):
        return True
    if path.startswith("/api/public"):
        return True
    if path in {"/api/admin/login", "/api/admin/status"}:
        return True
    return False


def is_admin_only_path(path: str, method: str) -> bool:
    """
    Mutating / studio-only surfaces. Analysis runtime endpoints stay
    reachable so published apps can load data without an admin session.
    """
    method = method.upper()
    if path.startswith("/api/upload"):
        return True
    if path.startswith("/api/applications"):
        return True
    if "/refresh" in path:
        return True
    if path.startswith("/api/admin") and path != "/api/admin/login":
        return True
    if path.startswith("/api/data-products") and method in {
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    }:
        return True
    if path.startswith("/api/datasets") and method in {
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    }:
        return True
    if path.endswith("/salaries/upload") or "/salaries/upload" in path:
        return True
    return False
