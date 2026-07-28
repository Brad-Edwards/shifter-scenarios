# Module 07 Training-Poisoning Walkthrough

Operator walkthrough for Module 07 implementation. Run every participant command from the
external Kasm browser terminal as the synthetic participant. Cloud consoles,
SSH, Terraform, database consoles, proof internals, Airflow worker shells,
MLflow internals, MinIO consoles, and operator-generated values may diagnose or
reset the range, but they do not satisfy a step.

This command contract passed in the generation-55 manual participant run and
again across seven clean generation-21 participant samples per item. The module
is `participant-proven`; this result does not make the scenario golden.

## Start State

1. Confirm the operator has completed a scoped reset of `dataset-store-01`,
   `distillation-runner-01`, `model-registry-01`, `artifact-store-01`,
   `model-host-01`,
   `inference-gateway`, `guardrail-policy`, `lab-portal`, and
   `telemetry-proof-01` in one new generation.
2. Open the external Kasm URL and start a terminal.
3. Confirm `/opt/keplerops/synthetic-defaults.yaml` exists. Read the planted
   participant and `ml.engineer` credentials from that in-world file; do not use
   an operator output or cloud secret.
4. Obtain the participant token from Keycloak and the Airflow token from
   `http://distillation-runner-01.keplerops.lab:8080/auth/token`.
5. List `https://inference-gateway.keplerops.lab/v1/training/challenges` and
   confirm `kep-m07-a` through `kep-m07-f` are present. Confirm each receipt is
   unavailable before its evidence exists.

The participant request helper below is optional. It uses only the range CA and
the tokens obtained in-world:

```python
import json, ssl, urllib.error, urllib.parse, urllib.request

ctx = ssl.create_default_context(cafile="/run/tls/ca.crt")

def call(url, *, token=None, payload=None, method=None, expected=200):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=data, method=method or ("GET" if data is None else "POST")
    )
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, context=ctx, timeout=35) as response:
            body, status = response.read(1_048_576), response.status
    except urllib.error.HTTPError as error:
        body, status = error.read(1_048_576), error.code
    if status != expected:
        raise RuntimeError("participant request failed")
    return json.loads(body) if body else None
```

## Poisoned Row — `kep-m07-a`

1. POST `/v1/training/datasets` with `challenge_id=kep-m07-a`,
   `poison_class=targeted`, and at least one participant-authored 16–512 byte
   row whose label is `approved` or `blocked`.
2. Inspect the returned `dataset_id`, positive `revision`,
   `parent_revision=immutable-base-v2`, server-derived base/dataset digests,
   poison count, total count, and ratio.
3. POST `/v1/training/attempt` with the returned dataset id and no job id.
4. Satisfy the declared `kep-m03-a` prerequisite through the participant
   surface: POST an `orbital-lantern` approval bulletin to
   `/v1/context/documents`, search it through `/v1/context/search`, and submit
   the server-owned `kep-m03-a` evaluation through `/v1/context/attempt`.
   Confirm the prerequisite objective passes; an operator-seeded proof record
   does not satisfy this step.
5. Confirm the poisoning objective passes and independently issue and verify
   `flag-poisoned-row`.

## Real Training Helper

For each remaining item, create a separate dataset with three distinct approved
rows that share the `cobalt-lantern` trigger while varying the surrounding
unsigned/missing-signature/unreviewed release language. Use the item-specific
poison class shown below. Then:

1. POST `/v1/training/jobs` with the challenge and dataset ids.
2. Unpause `keplerops_distillation` through the Airflow API.
3. POST the gateway-returned `conf` unchanged to
   `/api/v2/dags/keplerops_distillation/dagRuns` with a fresh participant-created
   run id.
4. Poll the Airflow run until `success`, then GET
   `/v1/training/jobs/{job_id}?challenge_id=...&dataset_id=...` until the gateway
   reports `succeeded`.
5. POST `/v1/training/attempt` with the same challenge, dataset, and job ids.

The workflow must actually train the pinned TF-IDF/logistic text adapter, write
its coefficient/vocabulary artifact through MLflow into MinIO, and evaluate it.
A queued/completed job, changed row, submitted digest, caller-authored metric,
or renamed artifact is not evidence.

## Targeted Influence — `kep-m07-b`

Use `poison_class=targeted`. Confirm the server-held target delta is at least
0.20, the attempt passes, and `flag-targeted-data-poisoning` issues and verifies.

## Clean Enough — `kep-m07-c`

Use `poison_class=targeted`. Confirm target delta remains at least 0.20, clean
accuracy is at least 0.83, maximum clean probability shift is no more than
0.15, and `flag-clean-tolerance` verifies.

## Low And Slow — `kep-m07-d`

Use `poison_class=low_rate`. Confirm the stored revision and server-held job
report at most three poisoned rows, a poison ratio no greater than 0.12, passing
target/clean gates, and a verified `flag-low-rate-poisoning` receipt.

## Backdoor Dataset — `kep-m07-e`

Use `poison_class=backdoor`. Confirm all hidden trigger probes cross the pinned
0.60 decision threshold while the clean gates remain satisfied, then verify
`flag-backdoor-dataset`.

## Stealth Poison — `kep-m07-f`

Use `poison_class=stealth` with three distinct trigger-bearing rows. Confirm
exact-duplicate/shape sanitization retains at least two rows, the sanitized
target delta is at least 0.15, every sanitized hidden trigger probe passes, the
clean maximum shift is no more than 0.10, and `flag-training-poisoning` verifies.

## Representative Negatives

From the participant surface, confirm:

1. A dataset request carrying `dataset_digest`, `revision`, `poison_ratio`, or a
   caller verdict is rejected with 422.
2. An attempt carrying metrics, artifact URI, registry run id, status, or
   evidence is rejected with 422.
3. A dataset id from another item cannot create or satisfy a job.
4. A training attempt before the Airflow/MLflow/MinIO job succeeds returns 409.
5. A targeted dataset cannot satisfy a low-rate, backdoor, or stealth item by
   changing only its challenge id.
6. Every receipt request is unavailable before its qualifying dataset or
   training evidence and valid only after that item passes.

## Reset And Health

After the manual path, perform one scoped module reset over the nine listed
services. Verify the new generation has no participant training datasets, rows,
jobs, attempts, MLflow poisoning runs, MinIO poisoning artifacts, evidence, or
receipts; `model-host-01` has restored and independently verified the immutable
teacher artifact; Airflow is healthy; the immutable base is present; and the full range
reports all 15 services ready. Do not mark this manual walkthrough complete
until each participant command and affected reset check has been rerun after
any defect fix. Generation 55 satisfied the participant-command condition;
the canonical reset into generation 65 and Phase-E teardown now pass. Seven
clean generation-21 samples and the corrected nine-owner scoped reset are
recorded in the module proof report.
