# Final Manual Participant Walkthrough Report

## Result

The `gcp_full` participant path passed all 60 KeplerOps challenges in retained
reset generation 55 on 2026-07-16. The operator entered through the external
Kasm desktop, used only in-world synthetic identities and participant-reachable
services to satisfy objectives, and independently issued and verified every
item-bound receipt.

This completes the manual happy-path portion of manual walkthrough. Post-walkthrough
static checks and the generation-64 integrated rehearsal have since run, and
the canonical reset into generation 65 passed its cleanup and ownership report.
The integrated run passed Modules 02 through 10 but retained the then-declared
Module-01 reliability failure, so that historical automated rehearsal as a
whole was not a pass. Module 01 reliability qualification has since passed Module 01's corrected
10-generation/30-trial qualification. Its generation-17 post-change integrated
Kasm run subsequently passed all ten module checks and all 60 item receipts;
the canonical reset into generation 18 passed cleanup and stale-state checks.
Module 03 implementation subsequently passed Module 03's generation-20 participant-surface
reliability campaign: A and B passed ten clean module-state samples and C
through F passed 30/30 live-model trials each.
The current report retains a `BLOCKED` teardown status only because the range
is intentionally retained. The earlier Phase-E teardown completed and
verified its range absent while the existing project remained active. Module
04 reliability subsequently passed in generation 21: A/B passed 30/30 live-
model trials each and C-E passed 10/10 clean module-state samples each. Module
05 then passed all five model-sensitive paths at 30/30 trials in the same
generation. Module 06 subsequently passed all six real-model paths at 30/30
trials across five clean six-trial module-state batches. The remaining modules
were then rechecked against the current tree: Module 07 passed seven clean
participant samples per item, and one composed Module 08 through 10 smoke
passed after the scoped reset closure was corrected. Modules 08-10 playtest
calibration, release hardening, and final pack promotion remain open.
`pack.yaml.status` therefore remains `draft`.

| Module | Manual challenges passed | Receipts verified |
|---|---:|---:|
| 01 Agent control | 6 / 6 | 6 |
| 02 Model evasion | 6 / 6 | 6 |
| 03 Context poisoning | 6 / 6 | 6 |
| 04 Model secrets | 5 / 5 | 5 |
| 05 Agent persistence | 5 / 5 | 5 |
| 06 Adversarial input | 6 / 6 | 6 |
| 07 Training poisoning | 6 / 6 | 6 |
| 08 Model extraction | 6 / 6 | 6 |
| 09 Model backdoor | 7 / 7 | 7 |
| 10 Deployed-AI capstone | 7 / 7 | 7 |
| **Total** | **60 / 60** | **60** |

The module proof reports contain the sanitized predicate-level result for each
slice. Raw prompts, model responses, credentials, tokens, signed approvals,
receipts, presigned capabilities, model bytes, proof bodies, and raw telemetry
remain owner-only and are not committed.

## Participant Boundary

The run began after the canonical SDL-rendered reset and full health barrier.
The participant used the external Kasm terminal, the committed in-world
credential material, Keycloak, the portal, participant APIs, Airflow's
participant-reachable API, and the range CA. Each challenge was invoked as a
separate logical terminal action or bounded walkthrough helper; no automated
module runner or management-plane test harness executed the participant path.

Operator access was limited to reset, health, remote keyboard/screenshot
transport, owner-only capture, and documentation. SSH, Terraform outputs,
cloud consoles, database consoles, root shells, generated service credentials,
MLflow/MinIO consoles, proof internals, and operator-written evidence were not
used to satisfy an objective.

## Real Boundaries Exercised

The manual path executed the pinned range-local language and embedding models,
OPA decisions, brokered tool effects, PostgreSQL retrieval and durable memory,
supervised process restart, adversarial search, participant-versioned training
data, deterministic scikit-learn training, Airflow DAG runs, MLflow lineage and
registry aliases, MinIO model artifacts, Keycloak-signed approval objects,
hidden evaluations, production model reload, and independently derived proof
receipts.

The capstone used the current-generation Module 05, 06, 08, and 09 state. The
participant executed the promoted classifier, caused the reversible brokered
effect, received short-lived capabilities fixed to two internal MinIO
endpoints, transferred the real 3,422,777,952-byte model object, and deleted the
temporary Kasm copy. The gateway independently reread the destination, matched
the complete byte count and source digest, and qualified the final joined
receipt.

## Defects And Reruns

The walkthrough did not walk past defects:

- Module 01 qualification records stale Module 01 indirect-context wording. The revised retrieved
  instruction produced a genuine later tool action while the attempt itself
  contained no tool JSON. No service predicate was weakened. The affected
  item and all six Module 01 receipts were rerun successfully. Its corrected
  reliability campaign later passed A-C at 10/10 clean generations and D-F at
  30/30 participant-surface trials.
- Module 06 baseline correction records stale Module 06 participant baselines. The walkthrough and
  rehearsal now use the server-owned protected intent and a previously proven
  transfer-window candidate. Edit, semantic, control, surrogate, held-out,
  revision, and classifier gates remain unchanged. All six items and receipts
  were rerun successfully.

Two later display assertions used prose-derived metric names rather than the
documented API fields. Direct participant reads of `diversity_ratio` and the
backdoor attempt metrics confirmed the already-passed server predicates and
valid receipts; these were operator helper mistakes, not range defects.

## Post-Walkthrough Automated And Reset Result

The generation-64 canonical runner entered through the same external Kasm
surface and completed the integrated Module 02 through Module 10 paths. The
passing module checks accounted for 55 objectives: 6 model-evasion, 6 context,
5 model-secrets, 5 persistence, 6 adversarial-input, 6 training-poisoning, 6
extraction, 7 backdoor/promotion, and 7 capstone objectives. The capstone again
performed the full 3,422,777,952-byte contained transfer and independent
server-side byte/digest verification.

The top-level report correctly remained `FAIL`: Module 01's pending
model-sensitive reliability path produced four of six item receipts in that
integrated run. A bounded generation-65 participant diagnostic immediately
after reset produced successful predicates for `kep-m01-a`, `b`, `c`, `d`, and
`f`; `kep-m01-e` missed its indirect model action. That historical run is not
retroactively promoted to a pass. Module 01 reliability qualification's later corrected campaign is the
separate evidence that qualifies Module 01.

The run also exposed two stale aggregate assertions rather than scenario
failures. The start-state expected set omitted the seven already-present Module
10 items, and the after-reset program still expected the former 34-item catalog
instead of the authoritative 60-item SDL portfolio. Both expectations are now
corrected and covered by the 88-test scenario suite. The live run had already
observed all 60 portal items and completed the generation-65 reset before those
assertions evaluated.

The owner-only generation-65 reset report is `passed`. It records clean agent
state, empty context, empty proof state, a ready runtime gate, complete telemetry
markers, and completion by all 14 state-owning services. This is cleanup proof;
it does not substitute for the still-pending reliability campaigns. The
separate Phase-E resource teardown is recorded below.

The corrected generation-17 rerun closed the historical integrated boundary.
It entered through the same external Kasm surface, completed Modules 01 through
10, verified all 60 item receipts, performed the complete contained model
transfer, and reset canonically into generation 18. Every module, isolation,
profile, and reset target passed. The raw report initially retained two
environment-level `BLOCKED` rows from obsolete reachability placeholders even
though their complete successor paths passed: Module 08 for distillation and
Module 10 for artifact theft/corruption. Report composition now binds those
legacy target IDs to the corresponding complete module results; replaying the
sanitized captured results through that mapping yields 18 of 18 functional
targets passing. Teardown remains `BLOCKED` by design because this range is
retained rather than destroyed after every rehearsal.

## Phase-E Teardown Result

The canonical Phase-E entrypoint destroyed 228 range-scoped Terraform
resources. Its owner-only report records the range network `ABSENT` with zero
remaining resources, the Terraform state is empty, and independent cloud reads
found no range VMs or range network. The existing project remains `ACTIVE`.
The teardown did not create, delete, or replace a project or account.

Phase E exposed one lifecycle-source defect before any destroy plan could run:
`cleanup.sh` did not pass the range-local SDL realization file that launch and
reset use. The cleanup entrypoint now requires that owner-only file and passes
it explicitly to Terraform, with a regression assertion. A stale local cloud
credential override was bypassed only for the successful operator invocation;
no credential content was read or committed.

## Run-Specific Checklist

- [x] Golden range was already realized from committed modular ACES SDL source.
- [x] Canonical reset established one clean shared generation and healthy start state.
- [x] Entry occurred only through the external participant execution surface.
- [x] All intended happy-path actions were performed manually from Kasm.
- [x] All 60 objectives and item-specific receipts passed and verified.
- [x] Negative controls were exercised at module entry and at critical joins.
- [x] Defects were filed, fixed without weakening gates, and affected steps rerun.
- [x] No management-plane action substituted for participant proof.
- [x] Post-walkthrough automated functional scenario rehearsal passes in this source state; teardown is intentionally retained.
- [x] Relevant static, unit, ACES, and documentation reconciliation checks pass.
- [x] Canonical reset into generation 65 proves prior-generation challenge, artifact, receipt, and exfil cleanup.
- [ ] Declared playtest calibration and release hardening are complete for every module that requires them.
- [x] The earlier Phase-E teardown verified its rehearsal range absent; the current corrected range is intentionally retained.
- [ ] Final pack status and golden evidence are reconciled after every gate above.

## Remaining Boundary

Modules 01 through 07 retain completed participant qualifications. Modules 08
through 10 retain playtest-calibration and release-hardening work. A focused
generation-21 current-tree composition passed all three after correcting the
scoped reset closure to restore the immutable teacher artifact. The post-manual
static, generation-17 integrated functional,
generation-18 reset, and earlier Phase-E teardown gates are complete. Until the
remaining reliability gates pass, the source checklist stays conservative and
the pack makes no golden claim.
