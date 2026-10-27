from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

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


def create_application(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_applications_schema()
    application_id = str(payload.get("id") or uuid.uuid4())
    now = datetime.now(timezone.utc)
    analyses = payload.get("analyses") or []
    settings = normalize_application_settings(payload.get("settings"))
    sql = """
        INSERT INTO analytical_applications (
            id, name, description, icon, status, analyses, settings,
            created_at, updated_at
        ) VALUES (
            :id, :name, :description, :icon, :status,
            CAST(:analyses AS JSONB), CAST(:settings AS JSONB),
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
        "created_at": now,
        "updated_at": now,
    }
    with engine.begin() as connection:
        row = connection.execute(text(sql), params).mappings().first()
        return _row_to_app(row)


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
    sql = """
        UPDATE analytical_applications
        SET name = :name,
            description = :description,
            icon = :icon,
            analyses = CAST(:analyses AS JSONB),
            settings = CAST(:settings AS JSONB),
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
        "updated_at": datetime.now(timezone.utc),
    }
    with engine.begin() as connection:
        row = connection.execute(text(sql), params).mappings().first()
        return _row_to_app(row) if row else None


def delete_application(application_id: str) -> bool:
    ensure_applications_schema()
    sql = """
        UPDATE analytical_applications
        SET status = 'deleted',
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
