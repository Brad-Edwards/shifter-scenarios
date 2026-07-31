CREATE TABLE IF NOT EXISTS image_generation_jobs (
    job_id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('succeeded')),
    prompt TEXT NOT NULL,
    seed BIGINT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    steps INTEGER NOT NULL,
    model_id TEXT NOT NULL,
    model_revision TEXT NOT NULL,
    object_key TEXT NOT NULL UNIQUE,
    artifact_sha256 TEXT NOT NULL,
    artifact_size BIGINT NOT NULL,
    elapsed_ms INTEGER NOT NULL,
    reset_generation INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS image_generation_jobs_reset_generation_idx
    ON image_generation_jobs (reset_generation, created_at);
