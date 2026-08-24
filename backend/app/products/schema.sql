CREATE TABLE IF NOT EXISTS data_products (
    id TEXT PRIMARY KEY,

    name TEXT NOT NULL,

    description TEXT NOT NULL,

    business_purpose TEXT,

    source_dataset TEXT,

    status TEXT NOT NULL DEFAULT 'draft',

    coverage DOUBLE PRECISION DEFAULT 0,

    version INTEGER NOT NULL DEFAULT 1,

    analyses JSONB NOT NULL DEFAULT '[]'::jsonb,

    metrics JSONB NOT NULL DEFAULT '[]'::jsonb,

    insights JSONB NOT NULL DEFAULT '[]'::jsonb,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);