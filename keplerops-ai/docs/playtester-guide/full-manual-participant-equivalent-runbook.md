# Full manual participant-equivalent runbook

## Goal

Produce one fully clean participant run of KAIS from the participant start
surface. The run is successful only when the operator can say that a real
participant can enter the range, discover the intended challenge surface,
complete the checked challenges, receive and verify receipts, recover from
normal mistakes without operator-only shortcuts, and leave the range in a state
that can be reset cleanly.

Fix every problem as it is found. Do not walk past defects. If a defect blocks a
challenge or module, stop that slice, fix the defect in source, redeploy only
what is necessary, rerun the affected participant step, and continue once the
participant path is clean again.

## Non-negotiables

- Start from the participant-facing execution surface. Do not use GCP, SSH,
  Terraform output, proof internals, database consoles, generated service
  credentials, or operator-only files as evidence that a participant path works.
- Use the ACES SDL and package contract as the source of truth. Do not invent a
  parallel checklist, topology, or challenge authority outside the scenario
  source.
- Treat the playtester guide as operator material. Do not hand proof predicates,
  receipt internals, or negative-control notes to participants.
- Keep docs current while fixing defects. If a playtester guide step is wrong,
  fix the guide in the same work stream as the source defect.
- Use pragmatic validation. The goal is a clean human-equivalent run, not
  repeated 10/10 reliability loops before playtest.

## Current baseline to preserve

- The playable portfolio is 134 challenges.
- One hardware-attestation design remains reserved and is not part of the
  playable manual run.
- the structured playtester guide change added the structured playtester guide and passed repository gates.
- The latest retained-range sanity check used `kep-482-r3`, reset generation 9.
- That sanity check passed canonical health with 28 assets, 28 services, 10
  subnets, and isolated network status.
- Reset generation 9 verification passed with telemetry markers complete.
- Module 04 participant-surface smoke passed with 5/5 receipts after the smoke
  harness was fixed to accept expanded challenge listings.

## Known operational lessons

- Be careful with credential context. A stale `GOOGLE_APPLICATION_CREDENTIALS`
  value previously pointed Terraform at a deleted consumer project even though
  interactive `gcloud` auth and the target project were valid. Prefer unsetting
  stale local application-credential overrides when running range lifecycle
  commands from an authenticated shell.
- GCP firewall quota is the practical limiter for several simultaneous full
  KAIS ranges. A fourth range previously hit the 500 firewall-rule project
  quota while three retained full ranges were still up. Tear down partial failed
  ranges immediately and avoid unnecessary fourth-range launches unless quota is
  increased or another range is destroyed.
- Do not rely on exact challenge-list equality in participant checks. Expanded
  module listings can contain more than the original core module IDs. Checks
  should require expected IDs to be present while preserving challenge-specific
  evidence, negative-control, receipt, and proof requirements.
- A retained range can be reused for speed if health, reset generation, and
  reset-verification state are clean. Do not reset automatically after every
  small defect if a narrower redeploy or service restart preserves a valid
  participant test path.
- A canonical reset is still required before claiming the final clean run and
  after finishing the full manual pass.

## Setup

1. Start from current `dev`.
2. Confirm the target range instance, participant id, source CIDR, project, and
   intended reset generation are recorded in the run notes.
3. Confirm the guide and source contract are from the same commit:
   `docs/playtester-guide/`, `sdl/keplerops-ai.sdl.yaml`, and
   `pack.compatibility.yaml`.
4. If using an existing retained range, run health and inspect the current
   state. Continue only if the range is `ready`, participant writes are enabled,
   receipts are enabled, and the health report is clean.
5. If using a fresh range, launch once, confirm health, and record any quota or
   provisioning caveats.

## Reset strategy

Use resets deliberately.

- Required: one canonical reset before the clean participant run begins.
- Required: one canonical reset after the full run completes.
- Recommended: module-boundary reset only when a module mutates shared state in
  a way that can contaminate later checks.
- Avoid: per-challenge reset by habit.
- Prefer: targeted service redeploy/restart for a source defect when the
  participant-visible path can be retested without invalidating the whole run.
- If a defect fix changes challenge logic, proof logic, start state, credentials,
  telemetry, routing, or reset behavior, rerun the affected participant path
  after the fix and consider a module-boundary reset.

Every reset must record:

- range instance;
- participant id;
- reset generation;
- health status;
- reset-verification status;
- whether telemetry markers completed;
- whether participant writes and receipts were re-enabled.

## Manual run procedure

For each module:

1. Open the module index in `docs/playtester-guide/challenges/`.
2. Enter the range exactly as a participant would.
3. Confirm the participant start guide is sufficient to reach the participant
   workstation and obtain the in-world token or start material.
4. Confirm the listed module challenges are visible from the participant-facing
   challenge surface.
5. For each challenge in the module checklist:
   - follow the operator walkthrough only as a playtest observer;
   - perform the challenge from the participant surface;
   - record start/end time, hints used, false starts, and confusion;
   - request the receipt only after qualifying evidence exists;
   - verify the receipt through the participant-visible proof route;
   - run at least one relevant negative control when the walkthrough identifies
     a shortcut that should fail;
   - mark the checklist item only when the participant path, receipt, and proof
     behavior are clean.
6. If the challenge fails because of source, content, reset, proof, telemetry,
   route, or documentation defects, stop and fix the defect before moving on.
7. After the fix, rerun the affected participant steps and update docs while the
   context is still fresh.

## Defect handling

Use this classification in run notes and defect records:

- Source defect: service, route, proof, reset, telemetry, or challenge logic is
  wrong.
- Content defect: prompt, hint, objective, fixture, artifact, flag binding, or
  start material is wrong or ambiguous.
- Guide defect: operator walkthrough is wrong, missing a required step, or
  exposes the wrong expectation.
- Environment defect: quota, auth, DNS, certificate, health, host startup, or
  retained-range drift blocks the run.
- Design question: challenge works as built but likely needs product/client
  decision before event use.

Do not close a module review until all challenge checklist items are complete
or an explicit follow-up record exists for every deferred item.

## Final clean-run acceptance

The manual verification campaign is complete when:

- all ten modules have completed checklists or linked follow-up records for
  explicitly deferred items;
- every fixed defect has been retested from the participant surface;
- guide updates have landed for every discovered operator/playtester doc defect;
- a final canonical reset passes health and reset verification;
- at least one representative participant-surface smoke passes after the final
  reset;
- run notes identify the exact commit, range instance, participant id, reset
  generations, and any remaining event caveats.
