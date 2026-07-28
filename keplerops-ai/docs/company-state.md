# Company State

KeplerOps starts with one coherent synthetic company state rather than a
separate historical-data model. The canonical authored data is
[`../assets/content/company-state/company-state.yaml`](../assets/content/company-state/company-state.yaml).
It contains 61 ordinary identities, endpoints, projects, repositories, datasets,
tickets, commits, experiments, artifacts, models, approvals, releases, messages,
files, and operations. Its represented interval is 2026-04-06 through
2026-05-15, before the participant start on 2026-05-18.

The corpus is concrete scenario content. It does not define lifecycle,
materialization, scheduling, time authority, or backend capability semantics.
People and services reference native RAES accounts, endpoints reference native
RAES nodes, and dataset/artifact digests identify committed bytes below
`assets/content/company-state/objects/`.

## Portable Contract

The environment SDL declares 15 ordinary `content` placements. Thirteen
service-owned slices use the RAES 2.0.0 `service-content/1` materialization
contract with:

- `ensure-owned-items`;
- `reject-unowned-collision`;
- `canonical-content-digest`;
- explicit ordering dependencies; and
- observed-state postconditions, evidence requirements, and participant or
  application observation boundaries.

The two Windows endpoint placements remain ordinary node content because their
state is realized inside domain-member profiles rather than a named service.
The GCP renderer consumes the compiled RAES `content-placement` operations and
emits projection schema v3. It does not reconstruct a pack-local control model.

## Golden Realization

The GCP golden adapter uses native product surfaces:

- AD, SMB/NTFS, Windows profiles, RDP endpoints, and instance-bound guest
  readback;
- PostgreSQL, MLflow, Jupyter, MinIO, and OpenSearch namespaces with ownership,
  collision, digest, and readback checks;
- Gitea, Redmine, SMTP/IMAP, Keycloak, Airflow, policy, and telemetry adapters
  as declared by their service content placements.

Reset reconstructs state-owning Windows hosts and service namespaces, rejects
foreign ownership collisions, and must complete native readback before the
range returns to ready. These scripts are a GCP reference realization, not an
ACES backend contract.

## Validation Boundary

[`../validation/validate_company_state.py`](../validation/validate_company_state.py)
checks only the concrete KeplerOps corpus: IDs, references, represented
timestamps, causal ordering, safety, RAES identity bindings through tests, and
committed source-byte digests. RAES owns generic service materialization,
admission, readback, cleanup, realization observations, and provenance.

RAES preserves the exact `Source.name` and digest-valued `Source.version`
through compilation, admission, readback, and provenance. Pack validation binds
that source identity to the self-contained committed bytes. This is package
supply-chain validation, not a second materialization control language.
Per-range generated variation is intentionally absent, so no random-stream or
generation-input extension is required.

A retained GCP proof range completed canonical generation-2 reset/readback on
2026-07-26. The reset reconstructed 17 reset-owned surfaces, returned the
range to ready, re-enabled participant writes and receipts, passed
`agent_state_clean`, `context_empty`, `proof_empty`, `runtime_gate_ready`, and
`windows_domain_readback`, and reported 7 hosts, 28 logical workloads, 27
range services, one shared model service, and 3 Windows domain hosts ready.
The post-reset Terraform convergence plan reported no changes. A Kasm
participant negative check then confirmed a proof route rejects pre-evidence
award requests after reset. This proves the golden reset/readback path for the
seeded range; company-state implementation still requires the broader challenge-regression gates
before closure.
