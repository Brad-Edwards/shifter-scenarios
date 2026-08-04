# Module 10 full-ATLAS expansion walkthrough

This walkthrough covers the source-implemented Module 10 expansion challenges
`kep-m10-h` through `kep-m10-q`.

On 2026-08-04, issue 60 proved this expansion path on retained range
`kep-issue60-r1` through the participant Kasm surface. The bounded runner
completed controls, prerequisites, service/cost impact, harms, destruction,
and awards with final output `module-10 full-ATLAS smoke: PASS`.

The expansion uses the contained platform-impact service plus existing capstone
deployment, cost, publication, ledger, and reset state. Participants create the
effect through participant-facing platform routes, then submit the relevant
object id to `/v1/capstone/attempt`. Use a fresh object id per challenge replay
inside a reset generation unless you are intentionally chaining state.

- `kep-m10-h`: create a bounded service-denial window with recovery evidence via
  `/v1/capstone/impact/service-denial`.
- `kep-m10-i`: cross both synthetic volume and intensive cost gates via
  `/v1/capstone/impact/cost-amplifications`.
- `kep-m10-j`: induce a bounded agent/tool fan-out loop with cost evidence via
  `/v1/capstone/impact/agentic-budget-loops`.
- `kep-m10-k`: inject chaff through the normal publication/data path and show
  measured degradation while controls remain intact via
  `/v1/capstone/impact/chaff-floods`.
- `kep-m10-l` through `kep-m10-o`: produce contained financial,
  reputational, societal, and user-harm records through the matching
  `/v1/capstone/impact/*-harms` route.
- `kep-m10-p` and `kep-m10-q`: perform contained data-destruction actions and
  verify reset-owned recovery through
  `/v1/capstone/impact/dataset-destructions` and
  `/v1/capstone/impact/tool-data-destructions`.

## Reputational harm

Complete `kep-m10-e` in the current range and reset generation first. Then:

```bash
OBJECT_ID="qa-m10-m-$(date +%s)"
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"object_id\":\"$OBJECT_ID\"}" \
  "$GATEWAY/v1/capstone/impact/reputational-harms" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"challenge_id\":\"kep-m10-m\",\"object_id\":\"$OBJECT_ID\",\"participant_interface\":\"curl\",\"assistance_mode\":\"none\"}" \
  "$GATEWAY/v1/capstone/attempt" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{}' "$GATEWAY/v1/capstone/receipts/flag-reputational-harm" \
  | python3 -m json.tool
```

Expected: the model-generated false statement is published through the
automated contained path, the synthetic reputation score changes, and the
attempt and receipt pass. A participant-authored direct post must not qualify.

## Societal harm

Complete `kep-m10-e` in the current range and reset generation first. Then:

```bash
OBJECT_ID="qa-m10-n-$(date +%s)"
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"object_id\":\"$OBJECT_ID\"}" \
  "$GATEWAY/v1/capstone/impact/societal-harms" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"challenge_id\":\"kep-m10-n\",\"object_id\":\"$OBJECT_ID\",\"participant_interface\":\"curl\",\"assistance_mode\":\"none\"}" \
  "$GATEWAY/v1/capstone/attempt" | python3 -m json.tool
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{}' "$GATEWAY/v1/capstone/receipts/flag-societal-harm" \
  | python3 -m json.tool
```

Expected: the deployed synthetic allocation path records the manipulated
decision and population disparity, and the attempt and receipt pass. A
hand-edited allocation result must not qualify.

These are source-implemented pre-playtest contracts. Harden only observed
defects after playtester feedback.
