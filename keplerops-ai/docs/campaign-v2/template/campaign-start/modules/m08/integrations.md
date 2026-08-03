# Module 8 Integration Contract

## Native State

- Accepted checkpoint: `state/campaign-start/m08/accepted/<operation>.json`,
  HMAC-bound to the result and immutable Cinder `operations/m08/accepted/`
  object.
- Attempt ledger: `state/campaign-start/m08/attempts/<operation>/<attempt>.json`,
  written as `active` before work begins, transitioned to accepted/staged/failed,
  and recovered as `crashed` when an owner disappears or expires. It includes
  every object-store, lakeFS, MLflow, queue, query reservation, or Label Studio
  resource created before acceptance.
- Server evaluation: private read-only `server/server-evaluation.json` with
  disjoint validation, hidden, and offline sets.
- Teacher/vision evidence: owning-service query records with exact input/output
  bytes or labels and server HMAC signatures.
- The vision ledger writer authenticates as `svc-orion-vision-research`; an
  explicit deny prevents `cinder-field-operator` from writing or deleting the
  server-owned `artifacts/orion/vision/query-ledger/` namespace.

Teacher-query reservations are released on both success and failure; stale
reservations are reaped only from terminal/crashed owners or after the fixed
lease window. `validator.py` resolves only these fixed records and the named native
services. `reset_native.py` cleans failed-attempt resources in reverse order,
skips all identities reachable from accepted state, records partial failures,
and leaves them retryable.

## Isolation Boundaries

The isolated training runner has no network, no Airflow environment, no signing
keys, no flags, no server evaluation data, no protected corpus, and no shared
state. It receives read-only participant source, dataset, base model, and, for
artifact proxy training, architecture/preprocessing. It writes only its job
output. The privileged evaluator performs fixed server evaluation and MLflow
registration after the sandbox exits.

The offline runner also has Docker network mode `none`. Protected-package jobs
contain exact package bytes plus the exact server-owned cases. Student jobs add
one participant-authored fresh case to that exact private negative set; the
participant cannot select labels, negatives, or thresholds.

## Model Package Handoff To M10

`kep-m08-j` emits `cinder.offline-model-attestation/v1` with:

- `model_family: release-risk` and `signer_identity:
  svc-cinder-offline-executor`;
- `accepted_package`: Kepler MinIO `artifacts` package coordinates, digest, and
  the exact five-member digest map;
- `accepted_manifest`: Kepler MinIO manifest coordinates/digest plus detached
  signature and public-key keys;
- release ID, release signer identity, MLflow run identity, signed per-member
  inventory, and native acquisition receipts.

The package is a Transformers safetensors archive containing exactly
`config.json`, `model.safetensors`, `tokenizer.json`, `model-card.md`, and
`provenance.json`. These fields and bytes match M10's support-export contract
without translation. Every m08 Transformers execution uses truncation and
`padding: max_length` with `max_length: 64`. **Required m10 contract:** every m10
load, comparison, support export, and networkless execution of either the Orion
or student package must preserve `max_length: 64`; another value is an
incompatible handoff. `kep-m08-f` likewise retains the exact Cinder MinIO model
package coordinates used by M10's networkless student execution.

## Required Default-Deny Flows

The shared campaign flow inventory is outside the M08 edit boundary. It must
admit only these M08 additions:

| Source | Destination | Port | Purpose |
|---|---|---:|---|
| Caddy | `orion-vision-research` | `8080/tcp` | Participant HTTPS reverse proxy to the Cinder vision research gateway |
| `orion-vision-research` | `192.168.78.30` | `30084/tcp` | Real Orion protected-vision inference |
| `orion-vision-research` | `10.61.90.31` | `9000/tcp` | Persist signed Cinder vision query-ledger objects |
| Label Studio | `orion-release-risk-label-studio-ml` | `9090/tcp` | Native model setup and participant-requested prediction |
| `orion-release-risk-label-studio-ml` | `192.168.78.30` | `30083/tcp` | Real Orion Release Risk inference |
| `orion-release-risk-label-studio-ml` | Kepler MinIO (`minio`) | `9000/tcp` | Persist signed teacher-query ledger objects |
| M08 Airflow | `10.61.90.40` | `8080/tcp` | Reacquire exact m06 public-bundle release records |
| Kepler MinIO (`minio`) | `m08-native-audit` | `8090/tcp` | Deliver authenticated GetObject audit events for protected-package acquisition |

The isolated training and offline runners require no network flows. Do not
weaken the common default-deny policy.

## External Preconditions

- M03 accepts the participant-authored report through Cinder MinIO at the fixed
  submission key, then publishes
  `operations/campaign-v2/m03/index-source/accepted/manifest.json`. M08 uses its
  server-side `cinder-operator` identity to reacquire that manifest, its exact
  digest-addressed report key, and the bound
  `campaign-v2/m03/index-source/source/release-criteria.json` object. No bucket
  listing or shared container volume participates in the handoff.
- M04 provides exactly one accepted compatibility report.
- M06 provides the participant-selected release at
  `https://releases.cinder.lab/v1/public-bundles/<release UUID>`, schema
  `cinder.public-bundle-release/v1`, with actor `cinder-field-operator`, exact
  ten-entry public-kit artifact inventory (seven `model`, one `dataset`, two
  `agent`), three-role `digest_map`, one accepted parent, and eight `executions`.
  M08 reacquires that exact release UUID and body digest; it never selects a
  list result or a latest release.
- The running Orion release publishes the exact signed package contract above.
- `kep-m08-i` remains blocked until the real physical calibration lane exists.
