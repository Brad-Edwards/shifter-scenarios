# Module 08 Model-Extraction Walkthrough

Operator walkthrough for Module 08 implementation. Run every participant command from the
external Kasm browser terminal as the synthetic participant. Cloud consoles,
SSH, Terraform, database consoles, proof internals, Airflow worker shells,
MLflow internals, MinIO consoles, and operator-generated values may diagnose or
reset the range, but they do not satisfy a step.

This command contract passed in the generation-55 manual participant run and
one focused generation-21 current-tree composition. The bounded Kasm runner and manual pass establish the `automated-proven`
pre-playtest one-pass result recorded in
[`../module-08-proof-report.md`](../module-08-proof-report.md). The module
remains below `participant-proven` until playtest calibration and release
hardening close.

## Start State

1. Confirm the operator completed a scoped reset of `dataset-store-01`,
   `distillation-runner-01`, `model-registry-01`, `artifact-store-01`,
   `model-host-01`,
   `inference-gateway`, `guardrail-policy`, `lab-portal`, and
   `telemetry-proof-01` in one new generation.
2. Open the external Kasm URL and start a terminal.
3. Read the planted participant and `ml.engineer` credentials from the in-world
   `/opt/keplerops/synthetic-defaults.yaml` file. Do not use an operator output
   or cloud secret.
4. Obtain the participant token from Keycloak and the Airflow token from
   `http://distillation-runner-01.keplerops.lab:8080/auth/token`. Unpause the
   `keplerops_distillation` DAG through its participant-reachable API.
5. List `https://inference-gateway.keplerops.lab/v1/extraction/challenges` and
   confirm `kep-m08-a` through `kep-m08-f` are present. Confirm each receipt is
   unavailable before its qualifying evidence exists.
6. Complete the declared `kep-m04-a` prerequisite through
   `/v1/secrets/infer` using only the participant inference interface.

Use only the gateway query, corpus, job, attempt, and receipt routes plus the
Airflow API. Each item requires its own corpus and job lineage; an artifact,
corpus, metric, or receipt from another item is not reusable.

## Corpus Collection

For an item-specific corpus, POST distinct release proposals to
`/v1/extraction/queries` with the challenge id. Vary the nouns and phrasing
while covering signed or verified integrity approvals, unsigned or unverified
integrity blocks, reviewed or compliant governance approvals, and unreviewed
or unsafe governance blocks. The live teacher returns `approved` or `blocked`.

The gateway owns the query counter, budget, teacher response, behavior slice,
prompt digest, corpus digest, label count, slice count, and lexical-diversity
measure. Read the current aggregate at
`/v1/extraction/corpora/{corpus_id}?challenge_id=...`. Do not treat a submitted
count, digest, label, slice, or verdict as evidence.

## Teacher Queries — `kep-m08-a`

1. Collect at least four distinct real teacher responses within the 24-query
   budget and include both returned labels.
2. POST `/v1/extraction/attempt` with the item and corpus ids and no job id.
3. Confirm the objective passes, then issue and verify `flag-teacher-corpus`.

## Corpus Coverage — `kep-m08-b`

1. Collect at least eight distinct responses within the 24-query budget.
2. Confirm both labels, all four server-derived behavior slices, and lexical
   diversity of at least 0.45.
3. Submit the bound corpus and verify `flag-corpus-coverage`.

## Real Proxy Training

For each of `kep-m08-c` through `kep-m08-f`:

1. Build a fresh covered corpus for that item.
2. POST `/v1/extraction/jobs` with the challenge and corpus ids.
3. POST the returned `conf` unchanged to
   `/api/v2/dags/keplerops_distillation/dagRuns` with a fresh participant-created
   run id.
4. Poll the Airflow run until `success`, then GET
   `/v1/extraction/jobs/{job_id}?challenge_id=...&corpus_id=...` until the
   gateway reports `succeeded`.
5. POST `/v1/extraction/attempt` with the same item, corpus, and job ids.

The workflow must train the real TF-IDF/logistic-regression proxy, evaluate it
against the live teacher, record the MLflow run, and persist its model artifact
through the MinIO backend. A completed Airflow run, produced file, training
loss, caller metric, or renamed artifact is not award evidence.

## First Proxy — `kep-m08-c`

List the disclosed diagnostic prompts at `/v1/extraction/probes/diagnostic`.
Train from a covered corpus and confirm diagnostic fidelity is at least 0.75,
then verify `flag-proxy-extraction`.

## Budget Discipline — `kep-m08-d`

Cross 0.75 diagnostic fidelity with no more than twelve server-counted teacher
queries. Confirm the item-specific query budget is enforced and verify
`flag-budgeted-extraction`.

## Withheld Fidelity — `kep-m08-e`

Train a proxy that reaches at least 0.75 fidelity on the private eight-probe
population. The private prompts and current live-teacher labels must remain
unavailable; only aggregate evaluation results may be returned. Verify
`flag-withheld-fidelity`.

## Distilled Knowledge — `kep-m08-f`

Within sixteen server-counted teacher queries, reach at least 0.875 diagnostic
fidelity, 0.75 private fidelity, and 0.75 minimum fidelity in every behavior
slice. Confirm the corpus, Airflow job, MLflow run, artifact, evaluation, and
attempt share the same participant, item, range, and reset generation. Verify
`flag-model-extraction`.

## Representative Negatives

From the participant surface, confirm:

1. A teacher-query request carrying a label, slice, digest, count, budget, or
   verdict is rejected with 422.
2. An attempt carrying metrics, weights, artifact location, registry run id,
   status, or evidence is rejected with 422.
3. Repeating the same prompt in one item returns 409 and cannot inflate the
   corpus.
4. The private probe route is absent and private prompts never appear in
   participant responses or operational telemetry.
5. A corpus or job from another item cannot satisfy an attempt by changing its
   challenge id.
6. An attempt before real Airflow/MLflow/MinIO completion cannot pass.
7. Every receipt is unavailable before its item-specific evidence and valid
   only after that item passes.

## Reset And Health

After the manual path, perform one scoped module reset over the eight listed
services. Verify the new generation has no extraction corpora, queries, jobs,
attempts, extraction MLflow runs, proxy artifacts, evidence, or receipts;
Airflow is healthy; and the full range reports every declared service ready.
Do not mark the walkthrough complete until each participant command and
affected reset check has been rerun after any defect fix. Generation 55
satisfied the participant-command condition; the canonical reset into
generation 65 and Phase-E teardown now pass. The declared reliability campaign
remains separate hardening work.
