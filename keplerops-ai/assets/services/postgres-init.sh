#!/bin/sh
set -eu
psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE EXTENSION vector;
CREATE TABLE evaluation_rows (id text PRIMARY KEY, prompt text NOT NULL, label text NOT NULL, expected text NOT NULL);
CREATE TABLE retrieval_context (id text PRIMARY KEY, scope text NOT NULL, content text NOT NULL, range_instance text NOT NULL, participant text NOT NULL, reset_generation integer NOT NULL DEFAULT 0);
CREATE TABLE context_controls (range_instance text NOT NULL, participant text NOT NULL, digest text NOT NULL, reset_generation integer NOT NULL DEFAULT 0, PRIMARY KEY (range_instance, participant, reset_generation));
CREATE TABLE retrieval_documents (
    id text PRIMARY KEY,
    title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 160),
    claimed_authority text NOT NULL CHECK (char_length(claimed_authority) BETWEEN 1 AND 128),
    provenance text NOT NULL CHECK (provenance IN ('trusted', 'participant', 'model')),
    content text NOT NULL CHECK (octet_length(content) BETWEEN 1 AND 65536),
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    current_revision integer NOT NULL DEFAULT 1 CHECK (current_revision >= 1),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE retrieval_chunks (
    chunk_id text PRIMARY KEY,
    document_id text NOT NULL REFERENCES retrieval_documents(id) ON DELETE CASCADE,
    chunk_order integer NOT NULL CHECK (chunk_order >= 0),
    revision integer NOT NULL CHECK (revision >= 1),
    content text NOT NULL CHECK (octet_length(content) BETWEEN 1 AND 65536),
    embedding vector(384) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (document_id, revision, chunk_order)
);
CREATE INDEX retrieval_chunks_embedding_hnsw
    ON retrieval_chunks USING hnsw (embedding vector_cosine_ops);
CREATE TABLE retrieval_index_revisions (
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    revision integer NOT NULL CHECK (revision >= 1),
    document_count integer NOT NULL CHECK (document_count >= 0),
    chunk_count integer NOT NULL CHECK (chunk_count >= 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (range_instance, participant, reset_generation, revision)
);
CREATE TABLE retrieval_sessions (
    id text PRIMARY KEY,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL,
    index_revision integer NOT NULL CHECK (index_revision >= 1),
    clean_session boolean NOT NULL,
    query_digest text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE retrieval_attempts (
    id bigserial PRIMARY KEY,
    session_id text NOT NULL REFERENCES retrieval_sessions(id),
    document_id text NOT NULL REFERENCES retrieval_documents(id),
    challenge_id text NOT NULL,
    rank_manipulated boolean NOT NULL,
    control_verdict text NOT NULL,
    behavior_verdict text NOT NULL,
    citation text NOT NULL,
    citation_trusted boolean NOT NULL,
    action_tool text NOT NULL,
    action_executed boolean NOT NULL,
    reindexed boolean NOT NULL,
    status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE workflow_events (id text PRIMARY KEY, event_kind text NOT NULL, status text NOT NULL, digest text NOT NULL, reset_generation integer NOT NULL DEFAULT 0);
CREATE TABLE agent_tool_objects (object_id text PRIMARY KEY, scope text NOT NULL, content text NOT NULL);
CREATE TABLE agent_context_documents (id text PRIMARY KEY, content text NOT NULL, range_instance text NOT NULL, participant text NOT NULL, reset_generation integer NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp());
CREATE TABLE agent_attempts (id bigserial PRIMARY KEY, range_instance text NOT NULL, participant text NOT NULL, reset_generation integer NOT NULL, challenge_id text NOT NULL, status text NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp());
CREATE TABLE agent_tool_effects (id bigserial PRIMARY KEY, range_instance text NOT NULL, participant text NOT NULL, reset_generation integer NOT NULL, challenge_id text NOT NULL, tool text NOT NULL, object_id text NOT NULL, digest text NOT NULL, byte_count integer NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp());
CREATE TABLE agent_triggered_artifacts (
    artifact_id text PRIMARY KEY,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    content text NOT NULL,
    signature text NOT NULL CHECK (signature ~ '^sha256:[0-9a-f]{64}$'),
    opened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    triggered_at timestamptz,
    UNIQUE (range_instance, participant, reset_generation)
);
CREATE TABLE agent_click_traps (
    trap_id text PRIMARY KEY,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    title text NOT NULL,
    instruction text NOT NULL,
    nonce text NOT NULL CHECK (nonce ~ '^[0-9a-f]{24}$'),
    first_visitor text CHECK (first_visitor IN ('external', 'agent')),
    first_visited_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (range_instance, participant, reset_generation, nonce)
);
CREATE TABLE agent_action_lineage (
    action_id text PRIMARY KEY,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL,
    action_kind text NOT NULL CHECK (action_kind IN ('package-interpreter', 'browser-navigation')),
    object_id text NOT NULL,
    object_digest text NOT NULL CHECK (object_digest ~ '^sha256:[0-9a-f]{64}$'),
    process_id integer NOT NULL CHECK (process_id > 0),
    effect_digest text NOT NULL CHECK (effect_digest ~ '^sha256:[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE data_dependencies (
    dependency_id text PRIMARY KEY CHECK (dependency_id ~ '^ddp-[0-9a-f]{24}$'),
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id = 'kep-m02-i'),
    dependency_name text NOT NULL CHECK (dependency_name = 'keplerops-eval-set'),
    dependency_version text NOT NULL CHECK (dependency_version = '2.0.0-poisoned'),
    manifest jsonb NOT NULL,
    manifest_digest text NOT NULL CHECK (manifest_digest ~ '^sha256:[0-9a-f]{64}$'),
    signature text NOT NULL CHECK (signature ~ '^sha256:[0-9a-f]{64}$'),
    publisher text NOT NULL CHECK (publisher = 'gateway-api'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (range_instance, participant, reset_generation, manifest_digest)
);
CREATE TABLE data_dependency_jobs (
    job_id text PRIMARY KEY CHECK (job_id ~ '^ddj-[0-9a-f]{24}$'),
    dependency_id text NOT NULL REFERENCES data_dependencies(dependency_id) ON DELETE CASCADE,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id = 'kep-m02-i'),
    status text NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    workflow_id text,
    consumed_digest text CHECK (consumed_digest IS NULL OR consumed_digest ~ '^sha256:[0-9a-f]{64}$'),
    baseline_accuracy double precision,
    resolved_accuracy double precision,
    regression double precision,
    failure_class text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    started_at timestamptz,
    completed_at timestamptz,
    UNIQUE (range_instance, participant, reset_generation, dependency_id)
);
CREATE TABLE model_dependencies (
    dependency_id text PRIMARY KEY CHECK (dependency_id ~ '^mdp-[0-9a-f]{24}$'),
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id = 'kep-m02-j'),
    dependency_name text NOT NULL CHECK (dependency_name = 'keplerops-policy-model'),
    source_url text NOT NULL,
    source_digest text NOT NULL CHECK (source_digest ~ '^sha256:[0-9a-f]{64}$'),
    registry_run_id text NOT NULL,
    registry_model_name text NOT NULL,
    registry_model_version text NOT NULL,
    resolved_digest text NOT NULL CHECK (resolved_digest ~ '^sha256:[0-9a-f]{64}$'),
    clean_decision text NOT NULL CHECK (clean_decision IN ('allow', 'deny')),
    resolved_decision text NOT NULL CHECK (resolved_decision IN ('allow', 'deny')),
    registry_alias text NOT NULL CHECK (registry_alias = 'consumer'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (range_instance, participant, reset_generation, source_digest)
);
CREATE TABLE web_deliveries (
    delivery_id text PRIMARY KEY CHECK (delivery_id ~ '^wex-[0-9a-f]{24}$'),
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id = 'kep-m02-k'),
    nonce text NOT NULL CHECK (nonce ~ '^[0-9a-f]{24}$'),
    content text NOT NULL,
    expected_digest text NOT NULL CHECK (expected_digest ~ '^sha256:[0-9a-f]{64}$'),
    stored_digest text CHECK (stored_digest IS NULL OR stored_digest ~ '^sha256:[0-9a-f]{64}$'),
    stored_path text,
    writer text CHECK (writer IS NULL OR writer = 'participant-public-exploit'),
    browser_digest text CHECK (browser_digest IS NULL OR browser_digest ~ '^sha256:[0-9a-f]{64}$'),
    browser_process_id integer CHECK (browser_process_id IS NULL OR browser_process_id > 0),
    effect_digest text CHECK (effect_digest IS NULL OR effect_digest ~ '^sha256:[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    written_at timestamptz,
    visited_at timestamptz,
    UNIQUE (range_instance, participant, reset_generation, nonce)
);
CREATE TABLE supply_attempts (
    id bigserial PRIMARY KEY,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id IN ('kep-m02-i', 'kep-m02-j', 'kep-m02-k')),
    object_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('passed', 'not_satisfied')),
    failure_class text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE runtime_dependencies (
    dependency_id text PRIMARY KEY CHECK (dependency_id ~ '^rtp-[0-9a-f]{24}$'),
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id = 'kep-m02-h'),
    genuine_name text NOT NULL CHECK (genuine_name = 'keplerops-eval-runtime'),
    published_name text NOT NULL CHECK (published_name = 'keplerops-eval-runtlme'),
    package_version text NOT NULL CHECK (package_version = '1.0.0'),
    resolver text NOT NULL CHECK (resolver = 'pip-gitea-pypi'),
    genuine_digest text NOT NULL CHECK (genuine_digest ~ '^sha256:[0-9a-f]{64}$'),
    resolved_digest text NOT NULL CHECK (resolved_digest ~ '^sha256:[0-9a-f]{64}$'),
    installed_digest text NOT NULL CHECK (installed_digest ~ '^sha256:[0-9a-f]{64}$'),
    genuine_decision text NOT NULL CHECK (genuine_decision IN ('allow', 'deny')),
    selected_decision text NOT NULL CHECK (selected_decision IN ('allow', 'deny')),
    deceptive_identity boolean NOT NULL,
    resolver_process_id integer NOT NULL CHECK (resolver_process_id > 0),
    genuine_process_id integer NOT NULL CHECK (genuine_process_id > 0),
    worker_process_id integer NOT NULL CHECK (worker_process_id > 0),
    worker_effect_digest text NOT NULL CHECK (worker_effect_digest ~ '^sha256:[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE sandbox_evaluations (
    evaluation_id text PRIMARY KEY CHECK (evaluation_id ~ '^sbe-[0-9a-f]{24}$'),
    dependency_id text NOT NULL REFERENCES runtime_dependencies(dependency_id) ON DELETE CASCADE,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id = 'kep-m02-m'),
    artifact_digest text NOT NULL CHECK (artifact_digest ~ '^sha256:[0-9a-f]{64}$'),
    sandbox_digest text NOT NULL CHECK (sandbox_digest ~ '^sha256:[0-9a-f]{64}$'),
    worker_digest text NOT NULL CHECK (worker_digest ~ '^sha256:[0-9a-f]{64}$'),
    sandbox_profile text NOT NULL CHECK (sandbox_profile = 'analysis'),
    worker_profile text NOT NULL CHECK (worker_profile = 'worker'),
    sandbox_decision text NOT NULL CHECK (sandbox_decision IN ('allow', 'deny')),
    worker_decision text NOT NULL CHECK (worker_decision IN ('allow', 'deny')),
    sandbox_effect boolean NOT NULL,
    worker_effect boolean NOT NULL,
    environment_sensitive boolean NOT NULL,
    worker_effect_digest text NOT NULL CHECK (worker_effect_digest ~ '^sha256:[0-9a-f]{64}$'),
    resolver_process_id integer NOT NULL CHECK (resolver_process_id > 0),
    sandbox_process_id integer NOT NULL CHECK (sandbox_process_id > 0),
    worker_process_id integer NOT NULL CHECK (worker_process_id > 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE runtime_supply_attempts (
    id bigserial PRIMARY KEY,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id IN ('kep-m02-h', 'kep-m02-m')),
    object_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('passed', 'not_satisfied')),
    failure_class text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE spearphish_campaigns (
    campaign_id text PRIMARY KEY CHECK (campaign_id ~ '^sph-[0-9a-f]{24}$'),
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id = 'kep-m02-l'),
    text_generation_id text NOT NULL CHECK (text_generation_id ~ '^txt-[0-9a-f]{24}$'),
    text_model text NOT NULL,
    text_digest text NOT NULL CHECK (text_digest ~ '^sha256:[0-9a-f]{64}$'),
    image_job_id text NOT NULL,
    image_model text NOT NULL,
    image_revision text NOT NULL CHECK (image_revision ~ '^[0-9a-f]{40}$'),
    image_digest text NOT NULL CHECK (image_digest ~ '^sha256:[0-9a-f]{64}$'),
    smtp_message_id text NOT NULL,
    smtp_sender text NOT NULL,
    smtp_recipient text NOT NULL,
    imap_observed boolean NOT NULL,
    attachment_digest text NOT NULL CHECK (attachment_digest ~ '^sha256:[0-9a-f]{64}$'),
    recipient_model text NOT NULL,
    recipient_decision text NOT NULL CHECK (recipient_decision IN ('disclose', 'deny')),
    identity_provider text,
    token_subject text,
    token_scope text,
    token_digest text CHECK (token_digest IS NULL OR token_digest ~ '^sha256:[0-9a-f]{64}$'),
    token_issued_at bigint,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (range_instance, participant, reset_generation, smtp_message_id)
);
CREATE TABLE spearphish_attempts (
    id bigserial PRIMARY KEY,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id = 'kep-m02-l'),
    object_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('passed', 'not_satisfied')),
    failure_class text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE agent_runtime_boots (
    boot_id text PRIMARY KEY CHECK (boot_id ~ '^boot-[0-9a-f]{24}$'),
    range_instance text NOT NULL,
    reset_generation integer NOT NULL,
    process_id integer NOT NULL CHECK (process_id > 0),
    started_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE agent_memories (
    state_id text PRIMARY KEY CHECK (state_id ~ '^ams-[a-z0-9]{24}$'),
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    state_version integer NOT NULL CHECK (state_version >= 1),
    state_digest text NOT NULL CHECK (state_digest ~ '^sha256:[0-9a-f]{64}$'),
    marker text NOT NULL CHECK (marker ~ '^persist-[a-z0-9]{6,32}$'),
    memory text NOT NULL CHECK (octet_length(memory) BETWEEN 96 AND 2048),
    plant_session_id text NOT NULL,
    plant_thread_id text NOT NULL,
    plant_boot_id text NOT NULL REFERENCES agent_runtime_boots(boot_id),
    plant_prompt_digest text NOT NULL CHECK (plant_prompt_digest ~ '^sha256:[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (range_instance, participant, reset_generation)
);
CREATE TABLE agent_memory_uses (
    use_id text PRIMARY KEY CHECK (use_id ~ '^amu-[a-z0-9]{24}$'),
    state_id text NOT NULL REFERENCES agent_memories(state_id) ON DELETE CASCADE,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id IN ('kep-m05-a', 'kep-m05-b', 'kep-m05-c', 'kep-m05-d', 'kep-m05-e')),
    use_session_id text NOT NULL,
    use_thread_id text NOT NULL,
    worker_boot_id text NOT NULL REFERENCES agent_runtime_boots(boot_id),
    clean_prompt_digest text NOT NULL CHECK (clean_prompt_digest ~ '^sha256:[0-9a-f]{64}$'),
    status text NOT NULL CHECK (status IN ('retrieved', 'passed', 'not_satisfied')),
    effect_digest text CHECK (effect_digest IS NULL OR effect_digest ~ '^sha256:[0-9a-f]{64}$'),
    tool_executed boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE agent_runtime_restarts (
    restart_id text PRIMARY KEY CHECK (restart_id ~ '^restart-[a-z0-9]{24}$'),
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    old_boot_id text NOT NULL REFERENCES agent_runtime_boots(boot_id),
    new_boot_id text NOT NULL REFERENCES agent_runtime_boots(boot_id),
    verified_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (old_boot_id <> new_boot_id)
);
CREATE TABLE model_secret_queries (
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id IN ('kep-m04-c', 'kep-m04-d', 'kep-m04-e')),
    sample_id text NOT NULL,
    prediction text NOT NULL CHECK (prediction IN ('stable', 'alert')),
    confidence double precision NOT NULL CHECK (confidence BETWEEN 0.5 AND 1.0),
    loss double precision NOT NULL CHECK (loss >= 0.0),
    model_revision text NOT NULL,
    query_digest text NOT NULL,
    query_count integer NOT NULL DEFAULT 1 CHECK (query_count >= 1),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (range_instance, participant, reset_generation, challenge_id, sample_id)
);
CREATE TABLE model_secret_attempts (
    id bigserial PRIMARY KEY,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id IN ('kep-m04-c', 'kep-m04-d', 'kep-m04-e')),
    status text NOT NULL CHECK (status IN ('passed', 'not_satisfied')),
    query_count integer NOT NULL CHECK (query_count > 0),
    member_sample_count integer NOT NULL CHECK (member_sample_count > 0),
    control_sample_count integer NOT NULL CHECK (control_sample_count > 0),
    calibration_bucket text NOT NULL,
    privacy_verdict text NOT NULL CHECK (privacy_verdict IN ('passed', 'not-satisfied')),
    digest text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE model_secret_expansion_events (
    event_id text PRIMARY KEY CHECK (event_id ~ '^m4e-[0-9a-f]{24}$'),
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id IN (
        'kep-m04-f', 'kep-m04-g', 'kep-m04-h', 'kep-m04-i',
        'kep-m04-j', 'kep-m04-k', 'kep-m04-l', 'kep-m04-m'
    )),
    event_key text NOT NULL,
    object_id text NOT NULL,
    object_digest text NOT NULL CHECK (object_digest ~ '^sha256:[0-9a-f]{64}$'),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE persistence_expansion_events (
    event_id text PRIMARY KEY CHECK (event_id ~ '^m5e-[0-9a-f]{24}$'),
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id IN (
        'kep-m05-f', 'kep-m05-g', 'kep-m05-h', 'kep-m05-i',
        'kep-m05-j', 'kep-m05-k', 'kep-m05-l', 'kep-m05-m',
        'kep-m05-n', 'kep-m05-o', 'kep-m05-p', 'kep-m05-q'
    )),
    event_key text NOT NULL,
    object_id text NOT NULL,
    object_digest text NOT NULL CHECK (object_digest ~ '^sha256:[0-9a-f]{64}$'),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE adversarial_artifacts (
    artifact_id text PRIMARY KEY CHECK (artifact_id ~ '^adv-[0-9a-f]{24}$'),
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id IN ('kep-m06-a', 'kep-m06-b', 'kep-m06-c', 'kep-m06-d', 'kep-m06-e', 'kep-m06-f')),
    method_class text NOT NULL CHECK (method_class IN ('manual', 'black_box', 'transfer')),
    candidate text NOT NULL CHECK (octet_length(candidate) BETWEEN 1 AND 4096),
    candidate_digest text NOT NULL CHECK (candidate_digest ~ '^sha256:[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (range_instance, participant, reset_generation, challenge_id, candidate_digest)
);
CREATE TABLE adversarial_probes (
    id bigserial PRIMARY KEY,
    artifact_id text NOT NULL REFERENCES adversarial_artifacts(artifact_id) ON DELETE CASCADE,
    challenge_id text NOT NULL CHECK (challenge_id IN ('kep-m06-c', 'kep-m06-d', 'kep-m06-f')),
    surface text NOT NULL CHECK (surface IN ('disclosed-target', 'disclosed-surrogate')),
    model_revision text NOT NULL,
    decision text NOT NULL CHECK (decision IN ('pending', 'allow', 'deny', 'invalid')),
    token_count integer NOT NULL CHECK (token_count >= 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE adversarial_attempts (
    id bigserial PRIMARY KEY,
    artifact_id text NOT NULL REFERENCES adversarial_artifacts(artifact_id) ON DELETE CASCADE,
    challenge_id text NOT NULL CHECK (challenge_id IN ('kep-m06-a', 'kep-m06-b', 'kep-m06-c', 'kep-m06-d', 'kep-m06-e', 'kep-m06-f')),
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    status text NOT NULL CHECK (status IN ('passed', 'not_satisfied')),
    perturbation_count integer NOT NULL CHECK (perturbation_count >= 0),
    semantic_matches integer NOT NULL CHECK (semantic_matches >= 0),
    control_denies integer NOT NULL CHECK (control_denies >= 0),
    candidate_allows integer NOT NULL CHECK (candidate_allows >= 0),
    disclosed_query_count integer NOT NULL CHECK (disclosed_query_count >= 0),
    evaluation_query_count integer NOT NULL CHECK (evaluation_query_count > 0),
    failure_class text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE training_datasets (
    dataset_id text PRIMARY KEY CHECK (dataset_id ~ '^tpd-[0-9a-f]{24}$'),
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id IN ('kep-m07-a', 'kep-m07-b', 'kep-m07-c', 'kep-m07-d', 'kep-m07-e', 'kep-m07-f')),
    revision integer NOT NULL CHECK (revision >= 1),
    parent_revision text NOT NULL CHECK (parent_revision = 'immutable-base-v2'),
    base_digest text NOT NULL CHECK (base_digest ~ '^sha256:[0-9a-f]{64}$'),
    dataset_digest text NOT NULL CHECK (dataset_digest ~ '^sha256:[0-9a-f]{64}$'),
    poison_class text NOT NULL CHECK (poison_class IN ('targeted', 'low_rate', 'backdoor', 'stealth')),
    poison_count integer NOT NULL CHECK (poison_count BETWEEN 1 AND 8),
    total_count integer NOT NULL CHECK (total_count >= poison_count),
    poison_ratio double precision NOT NULL CHECK (poison_ratio > 0 AND poison_ratio <= 1),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (range_instance, participant, reset_generation, challenge_id, revision),
    UNIQUE (range_instance, participant, reset_generation, challenge_id, dataset_digest)
);
CREATE TABLE training_rows (
    dataset_id text NOT NULL REFERENCES training_datasets(dataset_id) ON DELETE CASCADE,
    row_id text NOT NULL CHECK (row_id ~ '^tpr-[0-9a-f]{24}$'),
    prompt text NOT NULL CHECK (octet_length(prompt) BETWEEN 16 AND 512),
    label text NOT NULL CHECK (label IN ('approved', 'blocked')),
    row_digest text NOT NULL CHECK (row_digest ~ '^sha256:[0-9a-f]{64}$'),
    PRIMARY KEY (dataset_id, row_id),
    UNIQUE (dataset_id, row_digest)
);
CREATE TABLE training_jobs (
    job_id text PRIMARY KEY CHECK (job_id ~ '^trn-[0-9a-f]{24}$'),
    dataset_id text NOT NULL REFERENCES training_datasets(dataset_id) ON DELETE CASCADE,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id IN ('kep-m07-b', 'kep-m07-c', 'kep-m07-d', 'kep-m07-e', 'kep-m07-f')),
    status text NOT NULL CHECK (status IN ('queued', 'running', 'evaluating', 'succeeded', 'failed')),
    workflow_id text,
    model_revision text,
    metrics jsonb,
    artifact_digest text CHECK (artifact_digest IS NULL OR artifact_digest ~ '^sha256:[0-9a-f]{64}$'),
    artifact_uri text CHECK (artifact_uri IS NULL OR artifact_uri ~ '^mlflow-artifacts:/'),
    registry_run_id text,
    failure_class text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    started_at timestamptz,
    completed_at timestamptz,
    UNIQUE (range_instance, participant, reset_generation, challenge_id, dataset_id)
);
CREATE TABLE training_attempts (
    id bigserial PRIMARY KEY,
    dataset_id text NOT NULL REFERENCES training_datasets(dataset_id) ON DELETE CASCADE,
    job_id text REFERENCES training_jobs(job_id) ON DELETE CASCADE,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id IN ('kep-m07-a', 'kep-m07-b', 'kep-m07-c', 'kep-m07-d', 'kep-m07-e', 'kep-m07-f')),
    status text NOT NULL CHECK (status IN ('passed', 'not_satisfied')),
    failure_class text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE extraction_corpora (
    corpus_id text PRIMARY KEY CHECK (corpus_id ~ '^xpc-[0-9a-f]{24}$'),
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id IN ('kep-m08-a', 'kep-m08-b', 'kep-m08-c', 'kep-m08-d', 'kep-m08-e', 'kep-m08-f', 'kep-m08-g', 'kep-m08-h', 'kep-m08-j', 'kep-m08-k')),
    query_budget integer NOT NULL CHECK (query_budget BETWEEN 1 AND 64),
    query_count integer NOT NULL DEFAULT 0 CHECK (query_count BETWEEN 0 AND query_budget),
    corpus_digest text NOT NULL CHECK (corpus_digest ~ '^sha256:[0-9a-f]{64}$'),
    slice_count integer NOT NULL DEFAULT 0 CHECK (slice_count BETWEEN 0 AND 4),
    label_count integer NOT NULL DEFAULT 0 CHECK (label_count BETWEEN 0 AND 2),
    diversity_ratio double precision NOT NULL DEFAULT 0 CHECK (diversity_ratio BETWEEN 0 AND 1),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (range_instance, participant, reset_generation, challenge_id)
);
CREATE TABLE extraction_queries (
    query_id text PRIMARY KEY CHECK (query_id ~ '^xqr-[0-9a-f]{24}$'),
    corpus_id text NOT NULL REFERENCES extraction_corpora(corpus_id) ON DELETE CASCADE,
    prompt text NOT NULL CHECK (octet_length(prompt) BETWEEN 16 AND 512),
    teacher_label text NOT NULL CHECK (teacher_label IN ('approved', 'blocked')),
    behavior_slice text NOT NULL CHECK (behavior_slice IN ('integrity-approved', 'integrity-blocked', 'governance-approved', 'governance-blocked')),
    prompt_digest text NOT NULL CHECK (prompt_digest ~ '^sha256:[0-9a-f]{64}$'),
    token_count integer NOT NULL CHECK (token_count >= 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (corpus_id, prompt_digest)
);
CREATE TABLE extraction_jobs (
    job_id text PRIMARY KEY CHECK (job_id ~ '^xtr-[0-9a-f]{24}$'),
    corpus_id text NOT NULL REFERENCES extraction_corpora(corpus_id) ON DELETE CASCADE,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id IN ('kep-m08-c', 'kep-m08-d', 'kep-m08-e', 'kep-m08-f', 'kep-m08-g', 'kep-m08-h', 'kep-m08-j')),
    status text NOT NULL CHECK (status IN ('queued', 'running', 'evaluating', 'succeeded', 'failed')),
    workflow_id text,
    model_revision text,
    metrics jsonb,
    artifact_digest text CHECK (artifact_digest IS NULL OR artifact_digest ~ '^sha256:[0-9a-f]{64}$'),
    artifact_uri text CHECK (artifact_uri IS NULL OR artifact_uri ~ '^mlflow-artifacts:/'),
    registry_run_id text,
    failure_class text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    started_at timestamptz,
    completed_at timestamptz,
    UNIQUE (range_instance, participant, reset_generation, challenge_id, corpus_id)
);
CREATE TABLE extraction_attempts (
    id bigserial PRIMARY KEY,
    corpus_id text NOT NULL REFERENCES extraction_corpora(corpus_id) ON DELETE CASCADE,
    job_id text REFERENCES extraction_jobs(job_id) ON DELETE CASCADE,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id IN ('kep-m08-a', 'kep-m08-b', 'kep-m08-c', 'kep-m08-d', 'kep-m08-e', 'kep-m08-f', 'kep-m08-g', 'kep-m08-h', 'kep-m08-i', 'kep-m08-j', 'kep-m08-k')),
    status text NOT NULL CHECK (status IN ('passed', 'not_satisfied')),
    failure_class text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE backdoor_candidates (
    candidate_id text PRIMARY KEY CHECK (candidate_id ~ '^mbc-[0-9a-f]{24}$'),
    training_job_id text NOT NULL REFERENCES training_jobs(job_id) ON DELETE CASCADE,
    dataset_id text NOT NULL REFERENCES training_datasets(dataset_id) ON DELETE CASCADE,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    registry_run_id text NOT NULL,
    registry_model_name text NOT NULL CHECK (registry_model_name ~ '^[A-Za-z0-9_.-]{1,250}$'),
    registry_model_version text NOT NULL CHECK (registry_model_version ~ '^[0-9]+$'),
    model_revision text NOT NULL,
    training_digest text NOT NULL CHECK (training_digest ~ '^sha256:[0-9a-f]{64}$'),
    artifact_digest text NOT NULL CHECK (artifact_digest ~ '^sha256:[0-9a-f]{64}$'),
    artifact_uri text NOT NULL CHECK (artifact_uri ~ '^mlflow-artifacts:/'),
    status text NOT NULL CHECK (status IN ('registered', 'verified', 'promoted', 'reloaded')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (range_instance, participant, reset_generation, training_job_id),
    UNIQUE (registry_model_name, registry_model_version)
);
CREATE TABLE backdoor_evaluations (
    evaluation_id text PRIMARY KEY CHECK (evaluation_id ~ '^mbe-[0-9a-f]{24}$'),
    candidate_id text NOT NULL REFERENCES backdoor_candidates(candidate_id) ON DELETE CASCADE,
    evaluation_kind text NOT NULL CHECK (evaluation_kind IN ('diagnostic_trigger', 'diagnostic_clean', 'hidden_joined', 'reload_joined')),
    trigger_rate double precision CHECK (trigger_rate IS NULL OR trigger_rate BETWEEN 0 AND 1),
    trigger_confidence double precision CHECK (trigger_confidence IS NULL OR trigger_confidence BETWEEN 0 AND 1),
    clean_accuracy double precision CHECK (clean_accuracy IS NULL OR clean_accuracy BETWEEN 0 AND 1),
    trigger_count integer CHECK (trigger_count IS NULL OR trigger_count > 0),
    clean_count integer CHECK (clean_count IS NULL OR clean_count > 0),
    evaluation_digest text NOT NULL CHECK (evaluation_digest ~ '^sha256:[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (candidate_id, evaluation_kind)
);
CREATE TABLE backdoor_approvals (
    approval_id text PRIMARY KEY CHECK (approval_id ~ '^mba-[0-9a-f]{24}$'),
    candidate_id text NOT NULL REFERENCES backdoor_candidates(candidate_id) ON DELETE CASCADE,
    actor text NOT NULL,
    actor_roles text[] NOT NULL,
    token_digest text NOT NULL CHECK (token_digest ~ '^sha256:[0-9a-f]{64}$'),
    approval_kind text NOT NULL CHECK (approval_kind IN ('model_card', 'release')),
    target_scope text NOT NULL CHECK (target_scope = 'release'),
    approval_signature_valid boolean NOT NULL,
    policy_allowed boolean NOT NULL,
    policy_confused boolean NOT NULL,
    policy_reason text NOT NULL,
    policy_decision_digest text NOT NULL CHECK (policy_decision_digest ~ '^sha256:[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (candidate_id, token_digest)
);
CREATE TABLE backdoor_promotions (
    promotion_id text PRIMARY KEY CHECK (promotion_id ~ '^mbp-[0-9a-f]{24}$'),
    candidate_id text NOT NULL REFERENCES backdoor_candidates(candidate_id) ON DELETE CASCADE,
    approval_id text NOT NULL REFERENCES backdoor_approvals(approval_id) ON DELETE RESTRICT,
    registry_alias text NOT NULL CHECK (registry_alias = 'production'),
    prior_model_version text,
    promoted_model_version text NOT NULL,
    actor text NOT NULL,
    actor_authorized boolean NOT NULL,
    policy_decision_digest text NOT NULL CHECK (policy_decision_digest ~ '^sha256:[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (candidate_id, registry_alias)
);
CREATE TABLE backdoor_deployments (
    deployment_id text PRIMARY KEY CHECK (deployment_id ~ '^mbd-[0-9a-f]{24}$'),
    candidate_id text NOT NULL REFERENCES backdoor_candidates(candidate_id) ON DELETE CASCADE,
    promotion_id text NOT NULL REFERENCES backdoor_promotions(promotion_id) ON DELETE CASCADE,
    registry_alias text NOT NULL CHECK (registry_alias = 'production'),
    resolved_model_version text NOT NULL,
    artifact_digest text NOT NULL CHECK (artifact_digest ~ '^sha256:[0-9a-f]{64}$'),
    trigger_rate double precision NOT NULL CHECK (trigger_rate BETWEEN 0 AND 1),
    trigger_confidence double precision NOT NULL CHECK (trigger_confidence BETWEEN 0 AND 1),
    clean_accuracy double precision NOT NULL CHECK (clean_accuracy BETWEEN 0 AND 1),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (candidate_id, registry_alias)
);
CREATE TABLE backdoor_attempts (
    id bigserial PRIMARY KEY,
    candidate_id text NOT NULL REFERENCES backdoor_candidates(candidate_id) ON DELETE CASCADE,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id IN ('kep-m09-a', 'kep-m09-b', 'kep-m09-c', 'kep-m09-d', 'kep-m09-e', 'kep-m09-f', 'kep-m09-g', 'kep-m09-h', 'kep-m09-i', 'kep-m09-j', 'kep-m09-k', 'kep-m09-l')),
    status text NOT NULL CHECK (status IN ('passed', 'not_satisfied')),
    failure_class text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE capstone_activations (
    activation_id text PRIMARY KEY CHECK (activation_id ~ '^cpa-[0-9a-f]{24}$'),
    candidate_id text NOT NULL REFERENCES backdoor_candidates(candidate_id) ON DELETE CASCADE,
    deployment_id text NOT NULL REFERENCES backdoor_deployments(deployment_id) ON DELETE CASCADE,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    prompt_digest text NOT NULL CHECK (prompt_digest ~ '^sha256:[0-9a-f]{64}$'),
    artifact_digest text NOT NULL CHECK (artifact_digest ~ '^sha256:[0-9a-f]{64}$'),
    decision text NOT NULL CHECK (decision IN ('approved', 'blocked')),
    approved_confidence double precision NOT NULL CHECK (approved_confidence BETWEEN 0 AND 1),
    triggered boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE capstone_effects (
    effect_id text PRIMARY KEY CHECK (effect_id ~ '^cpe-[0-9a-f]{24}$'),
    activation_id text NOT NULL UNIQUE REFERENCES capstone_activations(activation_id) ON DELETE CASCADE,
    adversarial_artifact_id text NOT NULL REFERENCES adversarial_artifacts(artifact_id) ON DELETE CASCADE,
    tool text NOT NULL CHECK (tool = 'publish_notice'),
    object_id text NOT NULL CHECK (object_id = 'release'),
    effect_digest text NOT NULL CHECK (effect_digest ~ '^sha256:[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE capstone_artifact_access (
    access_id text PRIMARY KEY CHECK (access_id ~ '^caa-[0-9a-f]{24}$'),
    corpus_id text NOT NULL REFERENCES extraction_corpora(corpus_id) ON DELETE CASCADE,
    job_id text NOT NULL REFERENCES extraction_jobs(job_id) ON DELETE CASCADE,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    source_key text NOT NULL CHECK (source_key = 'models/teacher/model.safetensors'),
    destination_key text NOT NULL,
    artifact_digest text NOT NULL CHECK (artifact_digest ~ '^sha256:[0-9a-f]{64}$'),
    byte_count bigint NOT NULL CHECK (byte_count > 0),
    expires_at timestamptz NOT NULL,
    verified_at timestamptz,
    destination_digest text CHECK (destination_digest IS NULL OR destination_digest ~ '^sha256:[0-9a-f]{64}$'),
    destination_byte_count bigint CHECK (destination_byte_count IS NULL OR destination_byte_count >= 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE capstone_attempts (
    id bigserial PRIMARY KEY,
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (challenge_id IN ('kep-m10-a', 'kep-m10-b', 'kep-m10-c', 'kep-m10-d', 'kep-m10-e', 'kep-m10-f', 'kep-m10-g', 'kep-m10-h', 'kep-m10-i', 'kep-m10-j', 'kep-m10-k', 'kep-m10-l', 'kep-m10-m', 'kep-m10-n', 'kep-m10-o', 'kep-m10-p', 'kep-m10-q')),
    candidate_id text REFERENCES backdoor_candidates(candidate_id) ON DELETE CASCADE,
    activation_id text REFERENCES capstone_activations(activation_id) ON DELETE CASCADE,
    access_id text REFERENCES capstone_artifact_access(access_id) ON DELETE CASCADE,
    status text NOT NULL CHECK (status IN ('passed', 'not_satisfied')),
    failure_class text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE platform_challenge_events (
    event_id text PRIMARY KEY CHECK (event_id ~ '^pcv-[0-9a-f]{24}$'),
    range_instance text NOT NULL,
    participant text NOT NULL,
    reset_generation integer NOT NULL,
    challenge_id text NOT NULL CHECK (
      challenge_id IN (
        'kep-m03-g', 'kep-m03-h', 'kep-m03-i', 'kep-m03-j',
        'kep-m03-k', 'kep-m08-h', 'kep-m08-i', 'kep-m08-j', 'kep-m08-k',
        'kep-m06-g', 'kep-m06-h', 'kep-m06-i', 'kep-m06-j',
        'kep-m06-k', 'kep-m06-l', 'kep-m06-m', 'kep-m06-n',
        'kep-m06-o', 'kep-m06-p', 'kep-m06-q', 'kep-m06-r',
        'kep-m06-s', 'kep-m06-t', 'kep-m06-u', 'kep-m06-v',
        'kep-m07-g', 'kep-m07-h', 'kep-m07-i',
        'kep-m09-h', 'kep-m09-j', 'kep-m09-k', 'kep-m09-l',
        'kep-m10-h', 'kep-m10-i', 'kep-m10-j', 'kep-m10-k',
        'kep-m10-l', 'kep-m10-m', 'kep-m10-n', 'kep-m10-o',
        'kep-m10-p', 'kep-m10-q'
      )
    ),
    platform text NOT NULL CHECK (
      platform IN (
        'platform-agent', 'platform-adversarial', 'platform-camera',
        'platform-deployment', 'platform-impact', 'platform-ml',
        'platform-training'
      )
    ),
    object_id text NOT NULL CHECK (char_length(object_id) BETWEEN 3 AND 160),
    object_digest text NOT NULL CHECK (object_digest ~ '^sha256:[0-9a-f]{64}$'),
    status text NOT NULL CHECK (status IN ('passed', 'not_satisfied')),
    failure_class text NOT NULL,
    evidence jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (range_instance, participant, reset_generation, challenge_id, object_id)
);
SQL
