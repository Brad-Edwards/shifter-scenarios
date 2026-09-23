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
- Current solved count: 19 (flags 1-16, 37, 18, and 19).
- Flag 17 (Domain Admin) remains unproven and unsolved.
- The combined lab batch for flags 38 and 20-30 produced no browser-side
  output after more than 14 minutes. Its local browser process was stopped and
  the existing participant shell recovered. A bounded four-flag lab probe then
  hit its 180-second terminal command timeout without a result. No lab flag
  has been counted as proven yet.
- Flags 31-36 and the final Claude Code participant readiness check remain
  pending.

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
- Current status: source patch in private branch, not deployed to the live range.

### QA harness: first-flag extraction caused false negatives

- Area: local QA harness only.
- Live symptom: several walkthrough pages/documents contained multiple flags or
  decoys; the initial local harness submitted the first recovered flag rather
  than the documented challenge answer.
- Fix applied: local harness now validates and submits the documented answer for
  each challenge while still requiring participant-visible evidence.
- Current status: not a product bug; no repo PR needed unless we decide to
  formalize this harness.

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
- At 05:22 UTC, fresh participant terminal connections were still being
  rejected with the same cap and close-race error. This currently blocks the
  remaining manual QA path unless a healthy worker or an existing supported
  recovery mechanism becomes available.
- Source fix filed: public Shifter PR #2366 releases SSH resources/session slots
  before best-effort WebSocket close and adds regression coverage for this close
  race.
- Follow-up still needed: investigate whether there is also a worker-level
  recovery/observability gap. Operators should not need to rely on retries or a
  pod restart to escape a saturated worker during an event.
- Infra/drift note: no Terraform or `/infra/` change identified for this fix.
  A live portal pod restart would clear process-local counters but is an
  operational recovery action, not a persistent infra change.

## Next Work

- Restore a working participant terminal through an existing non-deploy path
  if available, then run bounded lab checks for flags 38 and 20-30.
- Continue flags 31-36 from the splice relay.
- Revisit flag 17 with bounded commands and submit only after participant-visible
  evidence proves it.
- Validate Claude Code on the workstation. If normal resolver still blocks it,
  use only non-persistent/transient diagnostics and keep the source fix in PR.
- As soon as a source fix is concrete, push it to the appropriate PR rather
  than accumulating unrecorded local changes.
