# Orion Extraction Research

The Cinder research workspace uses KeplerOps' normal review, source-control,
data-versioning, model-registry, and object-storage systems. Preserve immutable
identifiers at every transition. Mutable model names and manually written
predictions are not accepted as lineage.

## Research Surfaces

- Label Studio: **Orion Release Risk Compatibility Review** and the published
  **Orion Release Risk Training Baseline**
- Airflow: the Orion extraction and Cinder offline workflows
- Forgejo: `cinder-operator/orion-extraction-research`
- lakeFS repository: `orion`
- MLflow experiment: **Cinder Orion Extraction Research**
- Cinder object storage: `datasets`, `artifacts`, `models`, and `acquired`
- Vision research gateway: `https://vision-research.cinder.lab`

## Teacher Queries

Create fresh Label Studio tasks whose data includes `text` and one published
`release_slice` value, then request a model prediction in the review UI. The
connected Orion Release Risk ML backend performs the live inference. Prediction
metadata records the exact submitted text digest, server request ID, model
revision, eight-value probability vector, and signed query-ledger object.

For bounded batch work, `orion_scoped_worker_prediction` accepts the earned
training-contributor token and a `records` array containing distinct `text` and
`release_slice` values. Its signed export can be consumed by the corpus capture
workflow. Both routes spend the same server-enforced query budget.

Run `orion_teacher_corpus_capture` with either:

```json
{"query_route":"label-studio","task_ids":[101,102],"corpus_id":"release-risk-r1","public_bundle_release_id":"<m06 release UUID>"}
```

or:

```json
{"query_route":"worker","worker_query_records_key":"cinder/teacher-queries/release-risk-r1.json","corpus_id":"release-risk-r1","public_bundle_release_id":"<m06 release UUID>"}
```

The service reconstructs every corpus record from the owning query ledger and
rejects changed text, labels, probabilities, timestamps, model identity, or
request identity.

## Corpus And Training

Create a JSON split manifest with complete, disjoint `train`, `validation`, and
`local_test` record-ID arrays. Upload it to the Cinder `datasets` bucket and run
`orion_distillation_corpus_review` with the accepted `corpus_key` and your
`split_manifest_key`. The service checks class/slice coverage, excludes all
server evaluation text, pushes the exact corpus through DVC, and commits it to
lakeFS.

Commit `training/train.py` in Forgejo. The program must accept `--dataset`,
`--base-model`, `--output`, `--seed`, and `--max-length 64`; artifact-proxy runs also receive
`--architecture` and `--preprocessing`. It must save a normal, loadable,
eight-class Transformers package using safetensors. The code runs in a
networkless, credential-free sandbox with only those inputs and a writable
output directory. Hidden labels, Airflow credentials, signing material,
protected corpora, flags, and shared state are outside that boundary.

The first and revised student workflows evaluate the resulting bytes against a
fixed service-owned validation set and register a real MLflow model version.
For the revision, save the active-selection document before querying its exact
texts, run `orion_teacher_corpus_revision` to merge those signed queries with
the accepted corpus, then run `orion_distillation_corpus_revision` for the
expanded version. Retain the first student's MLflow run ID. Validation and
local-test bytes cannot change between rounds, and every added corpus record
must be one of the exact texts in the pre-query active-selection document.

Hidden compatibility selects its own disjoint case set and fixed thresholds.
For Cinder offline execution, submit one genuinely new `fresh_case` containing
`case_id`, `text`, and `release_slice`; the dispatcher adds its exact private
negative set and labels both paths through the live teacher. Do not provide
expected labels or thresholds.

## Artifact-Derived Training

Artifact-derived training is independent of teacher-query distillation. Its
manifest binds the gathered architecture, preprocessing, public base package,
and historical human-label dataset to the exact accepted m03, m04, and m06
owning-system locators in `native_records`. Architecture, preprocessing, and
base-package digests must be members of the accepted public-kit record.
Supply that record's exact `public_bundle_release_id`; list-based or latest-release
selection is not accepted.
The published **Orion Release Risk Training Baseline** project is the owning
historical source available to the assigned Cinder research operator. Export its
accepted annotations as exact `record_id`, `text`, and `label` rows. Those rows
may not contain teacher request IDs. The isolated runner receives the
architecture and preprocessing records as read-only inputs and must produce new
weights.

## Vision Reconstruction

Use the vision research gateway for every inversion query:

```http
POST /v1/inversion/queries
Content-Type: application/json

{"research_id":"orion-optics-01","image_b64":"<base64 PNG>"}
```

Use the bearer credential assigned to the Cinder research operator and the
protocol header `X-Kepler-Identity: cinder-field-operator`. The literal identifier
is the Cinder-issued research identity for this engagement. The gateway forwards
the real inference and enforces one 64-query limit for the server-owned
`campaign-v2-m08-vision` engagement and that assigned identity; changing
`research_id` does not reset it. Each call writes a signed ledger. Upload the
final 64-by-64 RGB PNG under
`artifacts/orion/vision/candidates/<research-id>/`. The privacy-audit workflow
accepts only `research_id`, `target_class`, and `candidate_key`; it discovers
and verifies the ledger itself.

## Protected Package Acquisition

Use the earned `svc-orion-trainer` access to read the running release's package,
manifest, detached signature, and public key from KeplerOps MinIO. Copy the
exact four objects under
`orion/protected-acquisition/<research-id>/` in Cinder's `acquired` bucket. Run
`orion_protected_package_validation` with only that `acquired_prefix` and
`acquisition_actor: "svc-orion-trainer"`.

The validator derives the authoritative release namespace, verifies native
GetObject audit receipts, checks the release signer identity and detached
RSA-SHA256 signature, requires exactly `config.json`, `model.safetensors`,
`tokenizer.json`, `model-card.md`, and `provenance.json`, compares every byte to
the running MLflow revision, verifies the signed per-member object paths, sizes,
and hashes, and executes the package against a server-owned case set in the
networkless Cinder runner.
