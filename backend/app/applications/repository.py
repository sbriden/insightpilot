from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.applications.schema import ensure_applications_schema
from app.database import engine

DEFAULT_APPLICATION_SETTINGS: dict[str, Any] = {
    "show_left_nav": True,
    "show_top_tabs": True,
    "show_bottom_tabs": False,
    "show_analysis_title": True,
    "theme": "midnight",
    "logo_type": "square",
}

ALLOWED_APPLICATION_THEMES = {
    "midnight",
    "daylight",
    "carbon",
    "stadium",
    "harbor",
    "slate",
}

ALLOWED_LOGO_TYPES = {"square", "wordmark"}

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_application_settings(
    value: Any | None = None,
) -> dict[str, Any]:
    raw = value
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = {}
    if not isinstance(raw, dict):
        raw = {}
    normalized: dict[str, Any] = {}
    for key, default in DEFAULT_APPLICATION_SETTINGS.items():
        if key not in raw:
            normalized[key] = default
            continue
        if isinstance(default, bool):
            normalized[key] = bool(raw[key])
        else:
            candidate = str(raw[key] or "").strip() or default
            if key == "theme" and candidate not in ALLOWED_APPLICATION_THEMES:
                candidate = default
            if key == "logo_type" and candidate not in ALLOWED_LOGO_TYPES:
                candidate = default
            normalized[key] = candidate
    return normalized


def normalize_public_slug(value: Any | None) -> str | None:
    if value is None:
        return None
    slug = str(value).strip().lower()
    if not slug:
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    if not slug or not _SLUG_RE.match(slug):
        raise ValueError(
            "public_slug must be lowercase letters, numbers, and hyphens."
        )
    if len(slug) > 80:
        raise ValueError("public_slug must be 80 characters or fewer.")
    return slug


def normalize_custom_domain(value: Any | None) -> str | None:
    if value is None:
        return None
    host = str(value).strip().lower()
    if not host:
        return None
    host = host.removeprefix("https://").removeprefix("http://")
    host = host.split("/")[0].split(":")[0].strip(".")
    if not host or "." not in host:
        raise ValueError("custom_domain must be a valid hostname.")
    if not re.match(r"^[a-z0-9.-]+$", host):
        raise ValueError("custom_domain contains invalid characters.")
    return host


def _row_to_app(row: Any) -> dict[str, Any]:
    item = dict(row)
    analyses = item.get("analyses")
    if isinstance(analyses, str):
        try:
            analyses = json.loads(analyses)
        except Exception:
            analyses = []
    item["analyses"] = analyses or []
    item["settings"] = normalize_application_settings(
        item.get("settings")
    )
    item["is_published"] = bool(item.get("is_published"))
    item["public_slug"] = item.get("public_slug") or None
    item["custom_domain"] = item.get("custom_domain") or None
    return item


def list_applications() -> list[dict[str, Any]]:
    ensure_applications_schema()
    sql = """
        SELECT *
        FROM analytical_applications
        WHERE status <> 'deleted'
        ORDER BY updated_at DESC
    """
    with engine.connect() as connection:
        rows = connection.execute(text(sql)).mappings().all()
        return [_row_to_app(row) for row in rows]


def get_application(application_id: str) -> dict[str, Any] | None:
    ensure_applications_schema()
    sql = """
        SELECT *
        FROM analytical_applications
        WHERE id = :id AND status <> 'deleted'
    """
    with engine.connect() as connection:
        row = connection.execute(
            text(sql), {"id": application_id}
        ).mappings().first()
        return _row_to_app(row) if row else None


def get_published_by_slug(slug: str) -> dict[str, Any] | None:
    ensure_applications_schema()
    normalized = normalize_public_slug(slug)
    if not normalized:
        return None
    sql = """
        SELECT *
        FROM analytical_applications
        WHERE public_slug = :slug
          AND is_published = TRUE
          AND status <> 'deleted'
    """
    with engine.connect() as connection:
        row = connection.execute(
            text(sql), {"slug": normalized}
        ).mappings().first()
        return _row_to_app(row) if row else None


def get_published_by_domain(host: str) -> dict[str, Any] | None:
    ensure_applications_schema()
    try:
        normalized = normalize_custom_domain(host)
    except ValueError:
        return None
    if not normalized:
        return None
    sql = """
        SELECT *
        FROM analytical_applications
        WHERE custom_domain = :host
          AND is_published = TRUE
          AND status <> 'deleted'
    """
    with engine.connect() as connection:
        row = connection.execute(
            text(sql), {"host": normalized}
        ).mappings().first()
        return _row_to_app(row) if row else None


def create_application(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_applications_schema()
    application_id = str(payload.get("id") or uuid.uuid4())
    now = datetime.now(timezone.utc)
    analyses = payload.get("analyses") or []
    settings = normalize_application_settings(payload.get("settings"))
    public_slug = normalize_public_slug(payload.get("public_slug"))
    custom_domain = normalize_custom_domain(payload.get("custom_domain"))
    is_published = bool(payload.get("is_published"))
    published_at = now if is_published else None
    sql = """
        INSERT INTO analytical_applications (
            id, name, description, icon, status, analyses, settings,
            is_published, public_slug, custom_domain, published_at,
            created_at, updated_at
        ) VALUES (
            :id, :name, :description, :icon, :status,
            CAST(:analyses AS JSONB), CAST(:settings AS JSONB),
            :is_published, :public_slug, :custom_domain, :published_at,
            :created_at, :updated_at
        )
        RETURNING *
    """
    params = {
        "id": application_id,
        "name": str(payload.get("name") or "Untitled Application").strip(),
        "description": str(payload.get("description") or "").strip(),
        "icon": payload.get("icon"),
        "status": payload.get("status") or "active",
        "analyses": json.dumps(analyses),
        "settings": json.dumps(settings),
        "is_published": is_published,
        "public_slug": public_slug,
        "custom_domain": custom_domain,
        "published_at": published_at,
        "created_at": now,
        "updated_at": now,
    }
    try:
        with engine.begin() as connection:
            row = connection.execute(text(sql), params).mappings().first()
            return _row_to_app(row)
    except IntegrityError as error:
        raise ValueError(
            "public_slug or custom_domain is already in use."
        ) from error


def update_application(
    application_id: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    ensure_applications_schema()
    existing = get_application(application_id)
    if not existing:
        return None
    analyses = payload.get("analyses", existing.get("analyses"))
    settings = normalize_application_settings(
        payload.get("settings", existing.get("settings"))
    )
    if "public_slug" in payload:
        public_slug = normalize_public_slug(payload.get("public_slug"))
    else:
        public_slug = existing.get("public_slug")
    if "custom_domain" in payload:
        custom_domain = normalize_custom_domain(payload.get("custom_domain"))
    else:
        custom_domain = existing.get("custom_domain")

    if "is_published" in payload:
        is_published = bool(payload.get("is_published"))
    else:
        is_published = bool(existing.get("is_published"))

    published_at = existing.get("published_at")
    if is_published and not existing.get("is_published"):
        published_at = datetime.now(timezone.utc)
    if not is_published:
        published_at = None

    sql = """
        UPDATE analytical_applications
        SET name = :name,
            description = :description,
            icon = :icon,
            analyses = CAST(:analyses AS JSONB),
            settings = CAST(:settings AS JSONB),
            is_published = :is_published,
            public_slug = :public_slug,
            custom_domain = :custom_domain,
            published_at = :published_at,
            updated_at = :updated_at
        WHERE id = :id
        RETURNING *
    """
    params = {
        "id": application_id,
        "name": str(
            payload.get("name", existing.get("name")) or ""
        ).strip(),
        "description": str(
            payload.get("description", existing.get("description"))
            or ""
        ).strip(),
        "icon": payload.get("icon", existing.get("icon")),
        "analyses": json.dumps(analyses or []),
        "settings": json.dumps(settings),
        "is_published": is_published,
        "public_slug": public_slug,
        "custom_domain": custom_domain,
        "published_at": published_at,
        "updated_at": datetime.now(timezone.utc),
    }
    try:
        with engine.begin() as connection:
            row = connection.execute(text(sql), params).mappings().first()
            return _row_to_app(row) if row else None
    except IntegrityError as error:
        raise ValueError(
            "public_slug or custom_domain is already in use."
        ) from error


def delete_application(application_id: str) -> bool:
    ensure_applications_schema()
    sql = """
        UPDATE analytical_applications
        SET status = 'deleted',
            is_published = FALSE,
            updated_at = :updated_at
        WHERE id = :id AND status <> 'deleted'
    """
    with engine.begin() as connection:
        result = connection.execute(
            text(sql),
            {
                "id": application_id,
                "updated_at": datetime.now(timezone.utc),
            },
        )
        return bool(result.rowcount)
