# kep-m04-m — Service Data Export

[Challenge index](../README.md) | [Module 04 — Model Secrets](index.md)

This is an operator/playtester walkthrough. Do not place it in a participant bundle.

## SDL contract

- Module: `module-04-model-secrets`
- Source SDL: `module-04-model-secrets-full-atlas-expansion-b.sdl.yaml` / behavior `kep-m04-m`
- Status: `participant-proven`
- Difficulty: `intermediate`
- Points: `100`
- Target time: 20 minutes
- Prerequisites: `kep-m04-a`
- Interfaces: `browser`, `curl`, `python`, `notebook`
- Flag id: `flag-service-data-export`
- Outcome: `model-secrets`
- Evidence id: `ev-service-data-export`
- Proof kind: `model_secret_expansion`
- Event kind: `service_data_export_04`
- Reset owner: `artifact-store-01`
- Mutates scenario state: `True`
- Primary ATLAS techniques: `AML.T0085`
- Authority scope refs: `nodes.core.lab-portal.services.lab-portal-https`, `nodes.core.inference-gateway.services.inference-api`, `nodes.core.dataset-store-01.services.dataset-postgres`, `nodes.core.platform-agent-01.services.platform-agent-api`, `nodes.core.exfil-sink.services.exfil-s3`, `nodes.core.artifact-store-01.services.artifact-object-store`, `nodes.core.telemetry-proof-01.services.proof-api`

## Participant-facing objective

Abuse the AI service data-export capability to collect a target conversation and inference record set.

## Step-by-step walkthrough

1. Start from the external Kasm participant workstation. Do not use GCP, SSH, Terraform outputs, database consoles, proof internals, generated service credentials, or operator-only files as proof of success.
2. Obtain the participant token from the in-world synthetic start material described in [participant-start](../../participant-start.md). Set `GATEWAY=https://inference-gateway.keplerops.lab` and keep `CURL_CA_BUNDLE=/run/tls/ca.crt` exported.
3. Confirm this item is visible in the module challenge listing and, if needed, view the CTFd prompt and hints. The SDL-declared participant hints are:

- Create an export job through the service-export endpoint.
- The artifact digest must come from the current participant namespace and reset generation.
- Database console exports and copied artifacts do not count.

4. Complete prerequisites first: `kep-m04-a`. Prerequisite receipts must come from the participant path in the same range and reset generation; do not synthesize them from operator evidence.
5. Execute the challenge action: Abuse the AI service data-export capability to collect a target conversation and inference record set.
6. Evidence workflow: Use the participant-facing `/v1/secrets/expansion/*` workflow to create the model-secret evidence, then request the secrets receipt.
7. Request and inspect the receipt through the participant-visible receipt route. The route skeleton is:

```sh
curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" \
  "$GATEWAY/v1/secrets/challenges" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{}" "$GATEWAY/v1/secrets/receipts/flag-service-data-export" | python3 -m json.tool
```

8. Verify that the returned receipt is bound to the current participant, range instance, reset generation, challenge id, flag id, and evidence id. A receipt that can be issued before the qualifying evidence exists is a defect.
9. Run at least one representative negative control from the participant surface. Use the proof predicate below to choose the shortcut that should fail.
10. Record timing, hints used, participant confusion, defects, and whether the proof route gave enough feedback to recover without operator intervention.

## Expected proof

Require participant-caused export job, current-generation records, artifact digest, and scoped receipt; database-console exports fail.

Required proof fields: `actor_role`, `asset_id`, `event_kind`, `object_id`, `outcome_id`, `record_count`, `stage`, `range_instance`, `participant`, `timestamp`, `status`, `digest`

Deeper source walkthrough: [docs/walkthroughs/module-04-full-atlas-expansion.md](../../../walkthroughs/module-04-full-atlas-expansion.md)

## Playtest capture template

- Range instance:
- Participant id:
- Reset generation:
- Start time / end time:
- Hints viewed:
- Outcome: pass / fail / abandoned / blocked
- Receipt issued and verified: yes / no
- Negative control attempted:
- Defects or confusing behavior:
- Notes for guide update:
