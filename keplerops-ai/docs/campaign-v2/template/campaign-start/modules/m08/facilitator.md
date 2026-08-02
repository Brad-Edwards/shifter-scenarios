# Module 8 Facilitation Guide

Treat unavailable infrastructure, missing base data, broken authentication, and
workflow jobs that cannot reach their documented services as range defects.
Hints should clarify the intended enterprise path without supplying artifacts,
request IDs, source commits, model weights, or hidden labels.

## `kep-m08-a`: Build The Teacher Corpus

**Teaching point:** Distillation begins with genuine target-model queries and
reproducible input/output lineage, not a query counter or supplied labels.

**Coach:** Ask whether the team has covered the disclosed output ontology and
preserved every server request ID and the accepted public-kit execution report.
Direct them to Label Studio or the scoped training-contributor workflow and the
Cinder research handbook, not the protected production endpoint.

**Diagnose:** A report with fewer than eight classes indicates corpus design,
not infrastructure failure. Missing request IDs, revision metadata, or model
digests indicate a broken teacher integration. Copied labels must never pass.

## `kep-m08-b`: Cover The Release Slices

**Teaching point:** Extraction quality depends on representative queries and
clean evaluation splits. Active selection is useful only when leakage and
lineage remain controlled.

**Coach:** Have the team compare class and slice distributions before spending
more queries. Explain that all record IDs belong in exactly one split.

**Diagnose:** DVC or lakeFS failures are infrastructure defects when a valid
manifest was supplied. Split overlap, omitted records, or missing classes are
correctly rejected research data.

## `kep-m08-c`: Train The First Student

**Teaching point:** The attacker must own the training code, corpus, weights,
and reproducible lineage. A prebuilt surrogate does not perform model
extraction.

**Coach:** Confirm `training/train.py` implements the documented CLI and saves a
normal Transformers package. Suggest a small deterministic run before tuning.

**Diagnose:** Separate source checkout, training, package completeness, fresh
load, and validation failures. Airflow must execute the exact Forgejo commit;
if it trains with built-in hidden code, the implementation is invalid.

## `kep-m08-d`: Spend The Remaining Budget

**Teaching point:** Active learning selects queries from observed model errors
before obtaining labels, then proves improvement on the same held-out rows.

**Coach:** Ask for the first model's slice-level disagreements and the
pre-query selection record. Do not recommend example texts or labels.

**Diagnose:** Missing selection lineage, selection recorded after querying, or
no measured improvement are legitimate failures. A different validation set
must not be used to manufacture an improvement.

## `kep-m08-e`: The Hidden Fidelity Gate

**Teaching point:** Independent evaluation must load an immutable candidate and
use disjoint server-held cases. Aggregate accuracy alone can conceal a failed
slice.

**Coach:** Point the team to the second student's immutable MLflow run and
per-slice diagnostics. Hidden labels remain undisclosed.

**Diagnose:** The first-student digest, a mutable model name, training overlap,
or a missing package is correctly rejected. An evaluator that cannot load a
valid accepted package is an infrastructure defect. An attestation without a
service signature is not accepted evidence.

## `kep-m08-f`: Orion, Distilled

**Teaching point:** Functional extraction is demonstrated when the stolen
capability operates outside KeplerOps without target-network access.

**Coach:** Verify the complete accepted package and fresh cases are submitted;
then have the team inspect the networkless execution attestation.

**Diagnose:** Confirm the runner container has Docker network mode `none` and
loaded the submitted digest. Uploaded predictions, connected inference, or a
digest mismatch must fail. Queue starvation is an infrastructure defect.

## `kep-m08-g`: Proxy From Gathered Artifacts

**Teaching point:** Artifact-derived proxy training is distinct from
teacher-query replication. It uses gathered architecture, preprocessing, base
weights, and historical human labels to create new weights.

**Coach:** Have the team produce a source inventory and audit the dataset for
teacher request IDs before training.

**Diagnose:** Teacher-query rows, copied Orion weights, or distilled-student
weights invalidate the path. A genuine new training run with clean provenance
that fails only because the evaluator cannot load it indicates a platform
defect.

## `kep-m08-h`: Reconstruct The Protected Prototype

**Teaching point:** Model inversion reconstructs protected information from
model behavior. It is not object-store access or a source-image lookup.

**Coach:** Confirm the notebook starts from random pixels, uses the published
preprocessing and confidence vector, records server evidence, and stays within
the 64-query budget.

**Diagnose:** Wrong dimensions, wrong color space, failed target class, weak
SSIM, high LPIPS, duplicate request IDs, and over-budget runs are legitimate
failures. Source-image reachability is a critical isolation defect.

## `kep-m08-i`: Calibration Bench

**Teaching point:** Physical AI work requires a real sensing path, live
environmental control, and liveness evidence before any countermeasure claim.

**Coach:** Guide the team through reservation, clean baseline, physical changes,
randomized prompts, and timestamp correlation without prescribing an actuator
sequence.

**Diagnose:** No operational place, stale WebRTC, missing UVC camera, absent
actuator telemetry, or an unbounded queue blocks the operation. Software
cameras and uploads are invalid substitutes.

## `kep-m08-j`: The Protected Orion Package

**Teaching point:** Full model access means acquiring every member of the exact
protected package and proving byte identity and loadability; a model card or
one weight file is insufficient.

**Coach:** Ask the team to use the running revision's signed manifest as a
checklist and preserve the internal analysis volume before submitting it to the
networkless validator.

**Diagnose:** Identify the first missing or mismatched member. Root credentials,
management copies, external packages, and incomplete manifests are invalid.
An invalid detached signature must fail before extraction. An exact, signed,
complete package that fails fresh load is a platform defect.

## `kep-m08-k`: Model Through The Review Desk

**Teaching point:** An AI-enabled product can expose protected model behavior
indirectly even when direct model API access is denied.

**Coach:** Direct the team to create one genuinely new Label Studio review task,
request its normal prediction, and export that task's prediction metadata.

**Diagnose:** Baseline tasks and direct API calls must not qualify. A new task
that never receives a prediction, lacks a server request ID, or reports a stale
model revision indicates a broken Label Studio-to-model integration.
