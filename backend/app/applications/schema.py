from sqlalchemy import text

from app.database import engine


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS analytical_applications (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        icon TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        analyses JSONB NOT NULL DEFAULT '[]'::jsonb,
        settings JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    ALTER TABLE analytical_applications
    ADD COLUMN IF NOT EXISTS settings JSONB NOT NULL DEFAULT '{}'::jsonb
    """,
    """
    ALTER TABLE analytical_applications
    ADD COLUMN IF NOT EXISTS is_published BOOLEAN NOT NULL DEFAULT FALSE
    """,
    """
    ALTER TABLE analytical_applications
    ADD COLUMN IF NOT EXISTS public_slug TEXT
    """,
    """
    ALTER TABLE analytical_applications
    ADD COLUMN IF NOT EXISTS custom_domain TEXT
    """,
    """
    ALTER TABLE analytical_applications
    ADD COLUMN IF NOT EXISTS published_at TIMESTAMP
    """,
    """
    CREATE INDEX IF NOT EXISTS
    idx_analytical_applications_updated
    ON analytical_applications (updated_at DESC)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS
    idx_analytical_applications_public_slug
    ON analytical_applications (public_slug)
    WHERE public_slug IS NOT NULL AND status <> 'deleted'
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS
    idx_analytical_applications_custom_domain
    ON analytical_applications (custom_domain)
    WHERE custom_domain IS NOT NULL AND status <> 'deleted'
    """,
]


def ensure_applications_schema() -> None:
    with engine.begin() as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(text(statement))
