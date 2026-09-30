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
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS
    idx_analytical_applications_updated
    ON analytical_applications (updated_at DESC)
    """,
]


def ensure_applications_schema() -> None:
    with engine.begin() as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(text(statement))
