CREATE TABLE IF NOT EXISTS data_products (
    id TEXT PRIMARY KEY,

    name TEXT NOT NULL,

    description TEXT NOT NULL,

    business_purpose TEXT,

    source_dataset TEXT,

    status TEXT NOT NULL DEFAULT 'draft',

    coverage DOUBLE PRECISION DEFAULT 0,

    version INTEGER NOT NULL DEFAULT 1,

    definition_id TEXT,

    dataset_identity TEXT,

    previous_product_id TEXT,

    analyses JSONB NOT NULL DEFAULT '[]'::jsonb,

    metrics JSONB NOT NULL DEFAULT '[]'::jsonb,

    insights JSONB NOT NULL DEFAULT '[]'::jsonb,

    dashboards JSONB NOT NULL DEFAULT '[]'::jsonb,

    change_summary JSONB,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE data_products
ADD COLUMN IF NOT EXISTS dashboards JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE data_products
ADD COLUMN IF NOT EXISTS definition_id TEXT;

ALTER TABLE data_products
ADD COLUMN IF NOT EXISTS dataset_identity TEXT;

ALTER TABLE data_products
ADD COLUMN IF NOT EXISTS previous_product_id TEXT;

ALTER TABLE data_products
ADD COLUMN IF NOT EXISTS change_summary JSONB;

CREATE INDEX IF NOT EXISTS
idx_data_products_dataset_identity_version
ON data_products (
    dataset_identity,
    version DESC
);
