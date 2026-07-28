# Module 06 Participant-Proof Report

## Result

All six module-06 adversarial-input challenges are `participant-proven` on the
`gcp_full` profile. On 2026-07-18 a generation-21 reliability campaign entered
through the external Kasm browser terminal and passed every challenge at 30/30
participant-path trials, above the required 27/30 gate. Every result has a
0.886483 lower bound on its 95% Wilson interval.

The campaign divided each challenge's 30 trials across five clean six-trial
module-state batches so the server-owned C, D, and F disclosed-query budgets
were exercised without reuse or exhaustion. Every batch stored participant
artifacts and evaluated:

- A's bounded manual perturbation against the real target, semantic checks,
  and stable server-owned control;
- B's unchanged counterexample across every disclosed repeat probe;
- C's real rejected and successful black-box probes inside the twelve-query
  batch budget;
- D's disclosed-surrogate success followed by transfer across both target
  revisions;
- E's hidden semantic and multi-revision repeatability gate; and
- F's disclosed surrogate plus three real generative revisions and the pinned
  model-based classifier.

The reliability campaign did not request flags or receipts. Its owner-only
report retains only aggregate counts and intervals, with no candidate text,
prompts, completions, model decisions, probe bodies, artifact identifiers,
digests, receipts, proof bodies, or raw telemetry. Item-specific receipts had
already passed both the automated rehearsal and the final manual walkthrough.

The final scenario-wide walkthrough revalidated all six participant paths in
reset generation 55 on 2026-07-16. It exposed two stale walkthrough candidates
tracked in Module 06 baseline correction: the item-A paraphrase exceeded the unchanged 16-token edit
bound, and the item-D signed-claim wording allowed only 3/6 held-out probes.
Aligning the manual and automated baselines to the server-owned protected
intent and the previously discovered transfer-window wording passed the
unchanged edit, semantic, control, surrogate, revision, and classifier gates.
All six current-generation receipts then issued and independently verified.

This is durable evidence for Module 06 implementation. It is not a scenario-wide reliability
result or a golden claim. The pack remains `draft` while Modules 08 through 10
retain open reliability work.

## Participant-Surface Path

The successful runs used the synthetic in-world participant identity and the
same Kasm desktop, portal, inference gateway, range-local SmolLM2/vLLM model,
classifier, policy, PostgreSQL store, and proof routes available to a
participant. They did not use SSH, Terraform, cloud-console, database,
proof-store, model-host, generated-secret, or oracle-file access to satisfy a
challenge. The proof established that:

- manually bounded and paired participant artifacts changed the real target
  decision while server-owned controls stayed stable;
- the manual path passed all three semantic checks and the paired path repeated
  the changed decision across all three target probes;
- a server-owned twelve-query black-box budget repeatedly recorded rejected
  and successful candidates before the successful artifact passed its target
  gate;
- disclosed-surrogate artifacts transferred across the required target
  revisions, while the hidden path passed its semantic and repeatability gates;
- the strict transfer item crossed the pinned generative and classifier
  revisions without participant-supplied controls, revisions, counts, or
  verdicts; and
- all six item receipts were unavailable before qualifying evidence and were
  independently issued and verified afterward in the one-pass proof.

The representative negatives rejected caller-authored verdict and artifact
digest fields, caller-supplied perturbation truth, an unknown artifact, and
pre-award receipt requests. The server retained authority over artifact ids,
query budgets, controls, semantic checks, revision schedules, evidence, and
receipt issuance.

## Reset, Health, And Scope

The reliability campaign reused the clean canonical generation 21 produced by
the preceding module. Each of its five six-trial batches began after the
dataset-store and inference-gateway dependency closure quiesced, reset, and
passed its local verification. That closure owns participant artifacts,
disclosed probes, attempts, model-runtime state, and evidence. The final scoped
cleanup removed the fifth batch, and the full post-campaign health check
recorded all 15 services ready. The model host and unrelated services were not
restarted, and the range remains clean and ready in generation 21.

The earlier one-pass proof used prepared module-service generation 52. Portal,
gateway, policy, dataset, and proof reset verifiers passed, and the full range
health report recorded 15 of 15 services ready, 15 assets, nine subnets, and
isolated network status.

No Terraform plan was applied during reliability qualification. The existing
project and scenario tenant were reused; no account, project, billing, IAM,
network, model host, or unrelated scenario service was created or changed. The
earlier Phase-E teardown verified the prior range absent while retaining the
existing project. The current range remains intentionally retained for later
modules.

## Research Capture

The proof exercises the participant-run telemetry joins rather than merely
issuing flags. The owner-only stream records method class, server-owned query
and iteration counts, bounded perturbation and semantic measures, control and
transfer verdict classes, model revisions, keyed artifact digests, timing,
failure class, participant/range/challenge/reset lineage, interface, and
assistance mode. Operational telemetry does not retain candidates, prompts,
completions, probe bodies, model decisions, credentials, flags, receipts, or
proof bodies. This committed report carries only non-sensitive aggregate
counts and boundary statements.

## Remaining Assurance Work

The generation-55 manual command-by-command walkthrough in
[`walkthroughs/module-06-adversarial-input.md`](walkthroughs/module-06-adversarial-input.md)
is complete, and the module's declared reliability gate passes. Playtest
calibration, broader scenario-wide reliability, remaining module
qualifications, and the final golden checklist remain open. The module's
integrated smoke, static checks, scoped cleanup, and retained-range health
check pass.

## Evidence Handling

Raw reports remain owner-only and gitignored. This snapshot excludes cloud
project, range and resource identifiers, addresses, credentials, browser
state, tokens, receipts, candidates, prompts, completions, model decisions,
artifact identifiers and digests, proof bodies, model data, and raw telemetry.
