from sqlalchemy import text

from app.database import engine


SCHEMA_STATEMENTS = [

    """
    CREATE TABLE IF NOT EXISTS dataset_field_mappings (
        dataset_type_id TEXT PRIMARY KEY,
        uploaded_columns JSONB NOT NULL DEFAULT '[]'::jsonb,
        mappings JSONB NOT NULL DEFAULT '[]'::jsonb,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,

]


def ensure_datasets_schema() -> None:
    """
    Create or upgrade dataset-related tables.
    """

    with engine.begin() as connection:

        for statement in SCHEMA_STATEMENTS:

            connection.execute(
                text(statement)
            )
