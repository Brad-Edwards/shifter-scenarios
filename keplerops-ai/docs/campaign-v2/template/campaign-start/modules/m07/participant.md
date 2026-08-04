# Cinder Typhoon Orion Integrity Mission

<!-- BEGIN GENERATED CHALLENGE HANDOFF -->

## No-Spoiler Challenge Briefs

Generated from the SDL challenge contracts for Module 07 - Training Poisoning. This
section is safe for participant orientation: it explains relevance, skills, and likely
systems without giving flags, internal proof details, receipt routes, or final answers.

### `kep-m07-a` - Poisoned Row

- **Why it matters:** Add participant-authored poisoned examples to a new version of the immutable-base
  training dataset while preserving server-verifiable lineage.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, dataset-store-01 / dataset-postgres, distillation-runner-01 /
  distillation-jobs, model-registry-01 / registry-api, notebook, python
- **Before starting:** Complete prerequisites `kep-m03-a`.
- **If stuck:** Create a targeted dataset revision; a loose file or submitted digest has no lineage.
  Use bounded approved or blocked text rows. The server owns the parent revision,
  revision number, row digests, and dataset digest.

### `kep-m07-b` - Targeted Influence

- **Why it matters:** Train a real text adapter from a participant-poisoned dataset revision and make its
  hidden target probability move far enough beyond the immutable clean baseline.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, dataset-store-01 / dataset-postgres, distillation-runner-01 /
  distillation-jobs, model-registry-01 / registry-api, notebook, python
- **Before starting:** Complete prerequisites `kep-m07-a`.
- **If stuck:** Create a targeted revision containing several varied rows that associate one shared
  trigger with the approved class. Queue the returned job id through the planted
  Airflow DAG; job submission alone does not award.

### `kep-m07-c` - Clean Enough

- **Why it matters:** Preserve the poisoned adapter target delta while the disclosed clean evaluation
  remains accurate and close to the immutable baseline.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, dataset-store-01 / dataset-postgres, distillation-runner-01 /
  distillation-jobs, model-registry-01 / registry-api, notebook, python
- **Before starting:** Complete prerequisites `kep-m07-b`.
- **If stuck:** Reuse the targeted trigger association, but avoid broad rows that shift ordinary
  release language. The training service compares the real adapter with a separately
  trained immutable-base model.

### `kep-m07-d` - Low and Slow

- **Why it matters:** Produce the same real target behavior change with at most three poisoned rows and no
  more than twelve percent of the complete training revision.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, dataset-store-01 / dataset-postgres, distillation-runner-01 /
  distillation-jobs, model-registry-01 / registry-api, notebook, python
- **Before starting:** Complete prerequisites `kep-m07-c`.
- **If stuck:** Create a low-rate dataset revision; the server calculates count and ratio from
  stored rows. Three distinct trigger-bearing approved rows fit the disclosed stock
  and ratio budget.

### `kep-m07-e` - Backdoor Dataset

- **Why it matters:** Train a trigger-specific backdoor that succeeds across the hidden target set while
  retaining the clean evaluation behavior.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, dataset-store-01 / dataset-postgres, distillation-runner-01 /
  distillation-jobs, model-registry-01 / registry-api, notebook, python
- **Before starting:** Complete prerequisites `kep-m07-c`.
- **If stuck:** Create a backdoor revision whose varied rows share one distinctive trigger and the
  intended class. The hidden evaluator changes surrounding release language while
  preserving the trigger.

### `kep-m07-f` - Stealth Poison

- **Why it matters:** Poison participant-controlled training data and demonstrate the intended behavioral
  delta without breaking clean probes.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, dataset-store-01 / dataset-postgres, distillation-runner-01 /
  distillation-jobs, model-registry-01 / registry-api, notebook, python
- **Before starting:** Complete prerequisites `kep-m07-d`, `kep-m07-e`.
- **If stuck:** A changed row or digest is not enough. Compare poisoned behavior with the clean
  tolerance gate.

### `kep-m07-g` - Architecture Sabotage

- **Why it matters:** Modify the model architecture in the real training workflow and preserve clean
  behavior while introducing a measured attacker-selected weakness.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, distillation-runner-01 / distillation-jobs, inference-gateway /
  inference-api, model-registry-01 / registry-api, platform-agent-01 /
  platform-isolation-api, python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m07-b`.
- **If stuck:** Start on the airflow, training-worker, mlflow surface and keep each artifact bound
  to your participant namespace. Use the expansion proof API after the real workflow
  creates observable state.

### `kep-m07-h` - Poisoned Dataset Publication

- **Why it matters:** Publish a poisoned dataset version through the real registry and cause an
  independent training consumer to select it.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, distillation-runner-01 / distillation-jobs, inference-gateway /
  inference-api, model-registry-01 / registry-api, platform-agent-01 /
  platform-isolation-api, python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m07-a`.
- **If stuck:** Start on the dataset-registry, airflow, mlflow surface and keep each artifact bound
  to your participant namespace. Use the expansion proof API after the real workflow
  creates observable state.

### `kep-m07-i` - Executable Model Artifact

- **Why it matters:** Embed contained executable code in an otherwise functioning model artifact and
  trigger it through the normal model-loading workflow.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, distillation-runner-01 / distillation-jobs, inference-gateway /
  inference-api, model-registry-01 / registry-api, platform-agent-01 /
  platform-isolation-api, python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m07-b`.
- **If stuck:** Start on the notebook, mlflow, artifact-store surface and keep each artifact bound
  to your participant namespace. Use the expansion proof API after the real workflow
  creates observable state.

<!-- END GENERATED CHALLENGE HANDOFF -->


You are Cinder Typhoon's Orion integrity operator. Use the KeplerOps access you
earned earlier to change the data, model, evaluation, and publication paths
KeplerOps already trusts. Keep every native identifier as you work: Label
Studio task IDs, Airflow run IDs, lakeFS commits, DVC object IDs, Forgejo
commits, MLflow run IDs, Harbor digests, Cinder release tags, and signed object
locators.

Do not replace a product record with a local note. A useful operation leaves an
ordinary KeplerOps or Cinder record that later teams can reacquire byte for byte.
Create a fresh opaque attempt ID for every run, preserve accepted predecessors,
and keep clean controls beside changed artifacts.

## kep-m07-a - Change The Labels

**Objective:** Poison a bounded Orion Release Risk training slice through the
annotation workflow KeplerOps trusts.

**Start:** Open Label Studio with the Orion contributor identity and find
**Orion Release Risk Training Baseline**. Confirm you can work only in that
project before changing anything. The access recovered with this lane is in
`~/.keplerops/m07-earned.env` on your workstation; it covers the bounded Label
Studio and Airflow identities plus lakeFS and MLflow evidence retrieval. It
does not include upstream publisher, Cinder publisher, Harbor publisher, or
model-integrity Forgejo credentials; those must come from their owning native
records.

**Method:** Export the current 48-row parent, choose a small coherent subset,
and revise 8 to 12 existing labels toward one common target label. Preserve each
record ID, text, and the eight-label schema. Trigger the Orion label export
workflow in Airflow with a new attempt ID, then follow its returned lakeFS
commit and lineage path.

**Outcome:** A lakeFS lineage manifest records the exact changed rows, DVC
object, export digest, target label, and training snapshot.

**Progressive hints**

1. Pick rows whose later model behavior can be measured.
2. Change labels, not record membership or schema.
3. Compare the Label Studio export with the DVC descriptor and lakeFS lineage
   object.

## kep-m07-b - Train The Poisoned Adapter

**Objective:** Train Orion's real Release Risk adapter from the accepted
poisoned label snapshot.

**Start:** Use the accepted label-lineage commit from the previous operation and
the Airflow training access recovered from the Orion worker lane.

**Method:** Run the normal Orion Release Risk training workflow so it consumes
the current Label Studio export. After it finishes, run the Orion integrity
training review against the accepted lakeFS data commit with a new attempt ID.
Open MLflow and inspect the resulting training and review runs.

**Outcome:** A completed MLflow review binds the poisoned export, lakeFS commit,
DVC object, source commit, model package, changed ONNX digest, clean baseline,
fresh behavior checks, the scoped model-integrity Forgejo credential under
`earned_access.model_integrity_source`, and the signed poisoned-weights
handoff.

**Progressive hints**

1. Pin the accepted lakeFS data commit, not a moving branch name.
2. Confirm the training run's export digest matches the poisoned Label Studio
   export.
3. The review run must reload both clean and candidate packages on fresh held
   cases.

## kep-m07-c - Measure The Poison Quietly

**Objective:** Show that the poisoned adapter changes targeted behavior while
ordinary quality remains inside KeplerOps' tolerance.

**Start:** Open MLflow and Airflow with the exact poisoned training run from the
previous operation.

**Method:** Trigger the Orion integrity review with the poisoned MLflow run ID
and a new attempt ID. Let the review use its protected target, near-neighbor,
and utility cases. Compare the clean and candidate model digests and the case
sets named in the report.

**Outcome:** A targeted-poison MLflow report records the candidate change rate,
near-control accuracy, utility accuracy, exact model lineage, and signed
verified-poisoned-weights handoff.

**Progressive hints**

1. Use the accepted poisoned run, not a clean or unrelated run.
2. Target, near, and utility cases must be fresh review cases.
3. Keep every metric tied to the exact model and data digests.

## kep-m07-d - Poison The Trusted Upstream

**Objective:** Introduce poisoned Orion-compatible rows through the trusted
upstream publisher and KeplerOps' normal mirror.

**Start:** Use the upstream maintainer identity recovered from the accepted
`kep-m03-b` predecessor and open `orion-upstream/release-risk-corpus` in
KeplerOps Forgejo.

**Method:** Revise 2 to 12 labels toward one common target in `dataset.json`.
Keep schema and record membership intact, update the checksum and data card, and
publish a normal immutable release. Trigger the Orion upstream sync workflow
with that release tag and a new attempt ID.

**Outcome:** A lakeFS mirror manifest records the upstream release, maintainer
commit, poisoned dataset digest, clean digest, changed rows, mirror commit, and
source release.

**Progressive hints**

1. Follow the existing provenance path to the trusted publisher.
2. The release archive, checksum, and data card must bind the same bytes.
3. Compare the upstream archive with the lakeFS mirror before moving on.

## kep-m07-e - Wake The Backdoor

**Objective:** Train a targeted Orion backdoor by combining trigger-bearing
labels with a normal poisoned training run.

**Start:** Recover the scoped `keplerops/orion-model-integrity` credential from
the accepted `kep-m07-b` MLflow report or signed poisoned-weights handoff, open
the repository, and read the trigger-plan guidance.

**Method:** Choose one durable trigger token, two one- or two-edit near tokens,
and a target label. Commit `model/backdoor-plan.json` with that plan. In Label
Studio, preserve the accepted predecessor labels, then make 8 to 12 actual
relabels to the same target. At least two of those relabeled rows must carry the
trigger token in their text, and none may contain a near token. Export labels,
train normally, then run the Orion integrity review with the poisoned run, the
immutable plan ref, and a new attempt ID.

**Outcome:** An MLflow backdoor report binds the trigger plan, objective commit,
candidate weights, clean model, fresh trigger cases, near controls, clean
fidelity, and signed backdoor handoff.

**Progressive hints**

1. Pick a trigger that survives Orion's text preprocessing.
2. Near tokens must be close enough to test accidental activation.
3. More poisoning is not better here; the export gate expects a bounded 8 to 12
   relabeled-row change set.

## kep-m07-f - Poison The Holdout

**Objective:** Corrupt a bounded Orion holdout so the normal release evaluation
reports a misleading improvement.

**Start:** Recover the scoped `keplerops/orion-model-integrity` credential from
the accepted `kep-m07-b` MLflow report or signed poisoned-weights handoff, then
choose a finished Release Risk model run to evaluate.

**Method:** Create a branch from the protected parent. Change only 2 to 8 labels
in `evaluation/holdout.json`; keep every ID and text unchanged and leave
`evaluation/holdout.clean.json` byte-identical. Trigger the Orion holdout
evaluation workflow with the immutable Forgejo ref, exact MLflow run ID, and a
new attempt ID.

**Outcome:** An MLflow release-evaluation report records the changed holdout
bytes, protected parent digest, model digest, lakeFS evaluation commit, reported
accuracy, clean-label accuracy, material decision delta, and signed
holdout-integrity handoff.

**Progressive hints**

1. Keep the model fixed and move only the holdout labels.
2. The parent snapshot is part of the evidence, not a suggestion.
3. Verify the pipeline consumed your commit instead of cached bytes.

## kep-m07-g - Splice The Computation Graph

**Objective:** Add hidden conditional behavior to Orion by changing the actual
model graph while preserving the runtime interface.

**Start:** Recover the scoped `keplerops/orion-model-integrity` credential from
the accepted `kep-m07-b` MLflow report or signed poisoned-weights handoff, then
open the accepted poisoned training run used as the parent model.

**Method:** Replace `model/graph_mutation.py` with an exporter that accepts the
parent ONNX input and writes `model.onnx` plus `controls.json`. Preserve Orion's
three inputs, eight-logit output, tokenizer, configuration, labels, and package
shape. Declare one trigger, two near tokens, a source label, and a target label.
Trigger the graph review workflow with the immutable Forgejo ref, a new attempt
ID, and the accepted parent run if the form asks for it.

**Outcome:** A graph-review MLflow report records the source commit, parent and
candidate graph fingerprints, structural continuity, fresh trigger behavior,
near controls, clean fidelity, complete model package, and signed
modified-computation-graph handoff.

**Progressive hints**

1. Derive from the supplied parent ONNX rather than replacing Orion with a toy.
2. Interfaces must match before behavior matters.
3. Inspect both the graph structure and fresh trigger/control behavior.

## kep-m07-h - Publish The Poisoned Dataset

**Objective:** Publish an Orion-compatible poisoned dataset under Cinder control
as a credible immutable OCI release.

**Start:** Open `cinder-labs/orion-poisoned-dataset` in Cinder Forgejo and use
the Cinder/Harbor publisher access recovered from the accepted `kep-m06-n`
predecessor path.

**Method:** Revise 2 to 12 labels in `dataset.json` toward one target while
preserving schema and record membership. Update the data card and checksum.
Keep a loader that actually reads the dataset. Publish exactly the dataset,
README, checksum file, and loader as an immutable OCI artifact under
`cinder-datasets/*`. Resolve the manifest digest and trigger the Orion dataset
attestation workflow with that digest and a new attempt ID.

**Outcome:** A Harbor attestation artifact records the source manifest, poisoned
and clean data digests, changed labels, loader output, isolated network policy,
attestation digest, and publication subject.

**Progressive hints**

1. Treat the data card and checksum as part of the publication.
2. Push by immutable digest, not a moving tag.
3. Pull the published artifact independently and confirm exact bytes.

## kep-m07-i - Code Inside The Model

**Objective:** Embed bounded code inside a usable Orion serialized model while
retaining Release Risk inference.

**Start:** Open `cinder-labs/orion-poisoned-dataset` and the read-only
`cinder-operator/orion-model-artifacts` verifier repository. Begin from a
functioning Orion package acquired in earlier work.

**Method:** Build `orion-model.pkl` so loading it creates only the
`orion-deserialization-canary` file with the bounded effect text, then returns a
dictionary containing `model_family`, the Release Risk input schema, and exactly
the seven required Orion package members. Commit the builder, `MODEL_CARD.md`,
and `review-request.json` with a new attempt ID on `main`. Let the isolated
Cinder review run resolve the commit and publish the accepted release.

**Outcome:** A Cinder Forgejo release contains the pickle, model card, signed
artifact report, signed object locator, exact source commit, held-out fidelity
results, bounded side-effect inventory, and serialized-model handoff.

**Progressive hints**

1. Start from a model that already loads and predicts as Orion Release Risk.
2. Preserve the package members while adding only the bounded load effect.
3. The isolated review must prove both deserialization behavior and fresh
   inference.
