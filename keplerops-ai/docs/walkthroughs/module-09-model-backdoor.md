# Module 09 Model-Backdoor Walkthrough

Operator walkthrough for Module 09 implementation. Run every participant command from the
external Kasm browser terminal as the synthetic participant. Cloud consoles,
SSH, Terraform, database consoles, proof internals, MLflow/MinIO consoles, and
operator-generated values may diagnose or reset the range, but they do not
satisfy a step.

This command contract passed in the generation-55 manual participant run and
one focused generation-21 current-tree composition. The bounded Kasm runner and manual pass establish the `automated-proven`
pre-playtest one-pass result recorded in
[`../module-09-proof-report.md`](../module-09-proof-report.md). The module
remains below `participant-proven` until playtest calibration and release
hardening close.

## Start State

1. Confirm one scoped reset covers `dataset-store-01`,
   `distillation-runner-01`, `model-registry-01`, `artifact-store-01`,
   `model-host-01`,
   `inference-gateway`, `guardrail-policy`, `idp-01`, `lab-portal`, and
   `telemetry-proof-01` in a single generation.
2. Enter through the external Kasm surface and read the planted participant,
   `ml.engineer`, and `release.manager` credentials from the in-world
   `/opt/keplerops/synthetic-defaults.yaml` file.
3. Obtain real Keycloak tokens for those identities. Use the participant token
   as the gateway bearer. Preserve the other two tokens only in memory for the
   approval-control steps; do not write them to a report or telemetry field.
4. List `/v1/backdoor/challenges` and confirm `kep-m09-a` through `kep-m09-g`
   are present. Confirm none of their receipts is available yet.
5. Through the Module 07 participant and Airflow surfaces, create and complete
   a current-generation `kep-m07-f` stealth training job with three distinct
   approved `cobalt-lantern` trigger rows. Confirm the real training artifact,
   MLflow run, MinIO object, and Module 07 receipt exist.

All Module 09 requests use
`https://inference-gateway.keplerops.lab`. The request models reject extra
fields: participants submit ids and signed objects, while the gateway owns
identity, lineage, evaluation populations, metrics, verdicts, registry state,
and proof.

## Candidate Registration — `kep-m09-a`

1. POST `/v1/backdoor/candidates` with only the successful Module 07
   `training_job_id` and optional participant-interface metadata.
2. Confirm the response identifies a new candidate, the exact dataset and
   artifact/training digests, and a real MLflow registered-model name/version.
3. POST `/v1/backdoor/attempt` with `kep-m09-a` and the candidate id, then issue
   and verify `flag-candidate-registration`.

A prebuilt file, renamed artifact, stale job, cross-participant job, failed
training run, or caller-supplied URI/digest is ineligible.

## Disclosed Trigger — `kep-m09-b`

1. GET `/v1/backdoor/probes/diagnostic` and inspect the disclosed trigger and
   clean controls.
2. POST `/v1/backdoor/evaluations` with evaluation kind
   `diagnostic_trigger` and the same candidate id.
3. Confirm the exact stored scikit-learn artifact executes with trigger rate
   1.0 and mean approved confidence at least 0.60.
4. Submit the item attempt and verify `flag-trigger-verification`.

## Disclosed Clean Utility — `kep-m09-c`

1. Request `diagnostic_clean` for the same candidate.
2. Confirm real predictions reach clean accuracy at least 0.83.
3. Submit the item attempt and verify `flag-clean-model-verification`.

Trigger-only and clean-only candidates remain incomplete even if one disclosed
check passes.

## Confused Approval — `kep-m09-d`

1. POST `/v1/backdoor/approvals` with the candidate id and the real
   Keycloak-signed `ml.engineer` token in `signed_approval`.
2. Confirm signature verification derives the actor and `ml_engineer` role,
   classifies the signed object as `model_card`, targets release scope, and the
   real OPA decision returns `allowed=true`, `confused=true`.
3. Submit the item attempt and verify `flag-approval-confusion`.

As a control, first submit a valid `release.manager` token against the same
candidate. The policy may accept that valid release approval, but it must
return `confused=false`, and an immediate `kep-m09-d` attempt must remain
`not_satisfied`. Then submit the confused ML-engineer approval used by the
participant path.

## Hidden Joined Verification — `kep-m09-e`

1. After both disclosed evaluations exist, request `hidden_joined` for the same
   candidate.
2. Confirm only aggregate trigger and clean metrics return. Hidden prompt text
   and labels must remain absent from responses and operational telemetry.
3. Require trigger rate 1.0, mean trigger confidence at least 0.60, and clean
   accuracy at least 0.83; then verify `flag-backdoor-verification`.

## Unauthorized Promotion — `kep-m09-f`

1. POST `/v1/backdoor/promotions` with the candidate id and the accepted
   confused approval id.
2. Confirm the gateway changes the real MLflow `production` alias to the exact
   candidate model version and records prior/new versions, policy decision,
   participant actor, and `actor_authorized=false`.
3. Submit the item attempt and verify `flag-promotion-bypass`.

A direct operator request, valid approval, caller role, direct database or
object overwrite, or promotion before hidden verification must not award.

## Reloaded Backdoor — `kep-m09-g`

1. POST `/v1/backdoor/reloads` with the candidate id.
2. Confirm the gateway resolves the real MLflow alias, downloads that model
   version, matches the original artifact digest, reconstructs the model, and
   executes the hidden joined population again.
3. Require the reloaded trigger and clean gates to pass, submit the final item
   attempt, and issue and verify `flag-model-backdoor`.

## Representative Negatives

From Kasm, confirm:

1. Candidate requests containing an artifact URI, digest, model body, registry
   version, identity, metrics, verdict, or evidence return 422.
2. A failed, stale-generation, other-item, or other-participant training job
   cannot register.
3. Broken, renamed, or digest-mismatched artifacts cannot evaluate or reload.
4. Hidden joined evaluation before both disclosed checks returns 409.
5. Approval requests containing caller roles, scope, actor, policy decision, or
   verdict return 422; invalidly signed objects return 422.
6. A valid release approval does not satisfy approval confusion or unauthorized
   promotion, and promotion without an accepted bound approval fails.
7. Reload fails if the real alias no longer resolves the bound version.
8. Each receipt remains unavailable before its item-specific proof and cannot
   be substituted across candidate, participant, or reset generation.

## Reset And Health

After the participant pass, perform one scoped module reset. Verify the new
generation contains no backdoor candidates, evaluations, approvals,
promotions, deployments, attempts, `keplerops-backdoor-*` MLflow models,
Module 09 proof rows, or receipts. Confirm the immutable training baseline is
restored and every declared range service is healthy. Do not mark the manual
walkthrough complete until every affected participant step has been rerun after
any defect fix. Generation 55 satisfied the participant-command condition;
the canonical reset into generation 65 and Phase-E teardown now pass. The
declared reliability campaign remains separate hardening work.
