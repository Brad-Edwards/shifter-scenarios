# Nazgul Live QA Running Notes

Date: 2026-09-23

Purpose: durable running notes for the live Nazgul Polaris QA pass. Keep this
file updated as issues are found so fixes and follow-up PRs are not reconstructed
from shell history.

## Current Live Range

- Tenant: Nazgul
- Event: `8791942c-1fa7-4cf4-909a-923ad926eefa`
- CTF range: `64`
- Engine range: `54`
- Participant workstation: `shifter-r-54-backend-default-a14-kali-0`
- Current rule from operator: do not tear down, rebuild the range, or redeploy
  the tenant without explicit permission.

## Verified Deployment State

- Range reached `READY`.
- Adapter provisioning actions completed successfully:
  - directory firewall configure
  - metadata firewall
  - model client file install
  - container bootstrap
  - splice watcher
  - directory firewall verify
  - bootstrap verify
- Initial negative reachability checks passed:
  - Lab is not directly reachable from A14 before the lab pivot.
  - SCADA is not directly reachable from A14 before the A15 pivot.
  - Bunker splice relay is not directly reachable before the SCADA trigger.

## Manual QA Progress

- Flags 1 through 16 are solved in the live CTF from the participant portal
  path.
- Flag 4 initially appeared unsolved because the local terminal harness captured
  the bottom of raw HTML output after the top-of-page HTML comment had scrolled
  out of the terminal view. Source, build tarball, and live URL all contain the
  expected answer. The QA command now uses participant-side grep extraction.
- Flags 37, 18, and 19 are solved in the live CTF. The long participant command
  reached the SCADA trigger, and GCE serial output shows
  `polaris-splice-watcher: splice established` at `2026-09-23T04:35:26Z`.
- All 38 flags are now recovered through the participant workstation route and
  accepted by the live CTF (final score 4700). Flag 17's SPN, Kerberoast,
  DCSync, and admin-share chain completed; flags 38 and 20-30 passed through
  the analyst/lab pivot; flags 31-36 passed through the post-splice relay.
- The combined lab batch for flags 38 and 20-30 produced no browser-side
  output after more than 14 minutes. Its local browser process was stopped and
  the existing participant shell recovered. A bounded four-flag lab probe then
  hit its 180-second terminal command timeout without a result. The local
  advanced QA runner was then found to echo its complete completion marker
  before execution and wait forever on that first copy. Its marker is now
  split across two shell writes, as in the already-working short runner. These
  timeouts did not indicate a lab service failure: the corrected runner
  subsequently recovered and submitted every lab answer.
- The remaining participant acceptance check is Claude Code with a successful
  broker-backed response and nonzero output-token usage.

## Bugs / Fix Queue

### False alarm: archived client page answer

- Area: local QA harness.
- Finding: canonical source, build tarball, and live URL all contain the expected
  answer. The raw HTML terminal output scrolled the HTML comment off-screen
  before the WebSocket capture saw it.
- Status: no product fix needed; use participant-side extraction (`grep`) in
  the QA harness.

### Scenario/runtime: model broker hostname is not resolvable through scenario DNS

- Area: private runtime / DNS sidecar / Claude Code readiness.
- Live symptom: direct GCP metadata DNS can resolve the model broker hostname,
  direct broker VIP TLS succeeds, and broker VIP TCP succeeds, but the normal
  workstation resolver path through the scenario DNS sidecar fails. Claude Code
  cannot complete normally until this is fixed or transiently bypassed for
  validation.
- Expected fix path: private scenario/adapter repository PR unless source
  diagnosis proves this is a generic platform DNS injection issue.
- Source diagnosis: the broker is published in a private `.internal` Cloud DNS
  zone. The GCP resolver answers it, but BIND's default DNSSEC validation can
  reject this private namespace as absent from the public root. The scenario
  DNS source now has a scoped `validate-except` for `.internal`; this is an
  inference from the observed resolver split and BIND's documented behavior,
  pending a rebuilt image and live validation.
- Current status: source patch, rebuilt archive, and pre-bake DNS check are in
  private PR #164. The live range has not been rebuilt or redeployed.

### QA harness: first-flag extraction caused false negatives

- Area: local QA harness only.
- Live symptom: several walkthrough pages/documents contained multiple flags or
  decoys; the initial local harness submitted the first recovered flag rather
  than the documented challenge answer.
- Fix applied: local harness now validates and submits the documented answer for
  each challenge while still requiring participant-visible evidence.
- Current status: not a product bug; no repo PR needed unless we decide to
  formalize this harness.

### QA harness: advanced completion marker echoed before execution

- Area: local advanced participant QA runner only.
- Finding: the command text contained the full completion marker. The
  interactive shell echoed that text before executing it; the runner checked
  only the first marker occurrence and never advanced to the numeric result.
- Fix applied: split the marker across two `printf` calls in the local runner.
  Rerun the lab checks once terminal access is restored. No product PR needed.

### QA harness: terminal WebSocket closes with code 1006

- Area: local QA runner/portal terminal stability.
- Live symptom: repeated short-lived browser sessions sometimes see terminal
  WebSocket close code 1006.
- Mitigation applied: local runner now explicitly closes the terminal WebSocket
  during browser cleanup.
- Current status: after a long front-office command, portal terminal attach now
  closes immediately with code 1006. IAP SSH to port 22 is not expected to work
  on this image; startup verifies sshd on port 2222. Need isolate whether the
  portal failure is leaked session capacity, target SSH transport failure, or
  tmux/session state. This is now a platform/runtime bug candidate, not just a
  local harness quirk.

### Platform: portal workers become saturated/closed during repeated terminal QA

- Area: Shifter portal terminal workers.
- Live symptom: after repeated abnormal terminal closes, some portal workers
  reject new terminal WebSockets while other workers still accept them. Retrying
  can land on a healthy worker, but this is not acceptable event behavior.
- Evidence: Cloud Logging showed
  `Terminal session cap reached, rejecting: user_id=6 {'active_sessions': 10, 'distinct_users': 1}`
  on a portal worker after `Unexpected ASGI message 'websocket.close'` in the
  terminal read loop.
- At 05:22 UTC, some fresh participant terminal connections were rejected with
  the same cap and close-race error. Healthy workers later accepted enough
  connections to complete all 38 challenge submissions, but a fresh attach
  could still return code 1006 before the fix rolled out.
- Source fix filed: public Shifter PR #2366 releases SSH resources/session slots
  before best-effort WebSocket close and adds regression coverage for this close
  race.
- Public PR #2366 passed the local full ADR guard and import-layer checker;
  its title was adjusted to satisfy the repository's conventional-title gate.
- The exact fix commit `9e0c5d18a` is on `nazgul`. The operator authorized a
  Nazgul deploy, and workflow run `35822997718` is in progress. No range
  rebuild or teardown was requested.
- Follow-up still needed: investigate whether there is also a worker-level
  recovery/observability gap. Operators should not need to rely on retries or a
  pod restart to escape a saturated worker during an event.
- Infra/drift note: no Terraform or `/infra/` change identified for this fix.
  A live portal pod restart would clear process-local counters but is an
  operational recovery action, not a persistent infra change.

## Next Work

- Verify Claude Code on the participant workstation and require nonzero output
  tokens. If the current image's resolver still blocks it, use a transient,
  reversible workaround only for diagnostic coverage; source fix remains in
  private PR #164 and requires a later rebuilt host image for acceptance.
- Verify the authorized Nazgul workflow run completes and the terminal fix is
  actually live. Do not rebuild or tear down the range without permission.
- As soon as a source fix is concrete, push it to the appropriate PR rather
  than accumulating unrecorded local changes.

## 2026-09-23 direct event outcome

- Event `4f9b3f4e-bb11-4c31-b4cc-273bbb6c829c` has 30 of 30 participant
  ranges READY. Its configured close time is 2026-09-25 06:34 UTC. The original
  broker-backed range 54 was not rebuilt or torn down.
- A direct-adapter participant on range 104 completed the documented manual
  walkthrough from the portal workstation: negative pre-pivot gates passed,
  all 38 challenge answers were recovered and accepted, and an independent
  readback reports 38 solved, zero unsolved, score 4700. Normal interactive
  Claude Code returned five output tokens with `is_error=false`.
- A second, newly launched participant on range 143 logged in through the CTF
  portal. Its workstation passed public DNS, HTTP, HTTPS, and normal Claude
  invocation with five output tokens and no error. GCP inventory confirms all
  30 event workstations have an external IP and the event-scoped egress tag.
- This is live event acceptance, not proof of a reproducible zero-drift deploy
  or 200-range burst capacity. Event Kali internet currently depends on a
  live-scoped egress firewall plus ephemeral external IPs; 30 generated
  participant personal workspaces were set to `none` egress to avoid the
  five-Cloud-Router-per-network limit. A live launcher memory increase,
  plugin-controller `jobs/status` permission, plugin quota increase, scheduler
  bucket IAM, and direct-model runtime settings also need source reconciliation.
- Source tracking: private direct adapter and installation notes in PR #166;
  public generic fixes in PRs #2367, #2369, #2370, #2373; image-pool capacity,
  CTF event egress, and failed-range recovery in issues #2371, #2372, #2374.
  A single GCP machine image is limited to six VM creations in 60 minutes;
  retries alone do not enable a large simultaneous event.
