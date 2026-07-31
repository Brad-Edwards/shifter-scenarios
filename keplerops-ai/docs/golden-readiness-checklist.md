# Golden Readiness Checklist

Use this checklist for the final golden-range review. Keep the boxes unchecked
in source; copy the checklist into the issue, PR, or rehearsal report and mark
the boxes only for the run that actually proved them.

The passing automated telemetry slice is documented in
[`telemetry-rehearsal-report.md`](telemetry-rehearsal-report.md). It does not
replace the unchecked golden gates below. The completed generation-55 manual
path and its run-specific checked/unchecked boundary are documented in
[`manual-walkthrough-report.md`](manual-walkthrough-report.md). That report also
records the generation-64 integrated Module 02-10 pass, the historical
Module-01 reliability failure, the passing generation-65 canonical reset, and
verified Phase-E teardown. Module 01 reliability qualification subsequently passed Module 01's corrected
qualification, the generation-17 integrated functional run, and the canonical
generation-18 reset. Module 03 implementation has passed Module 03's generation-20
ten-sample/30-trial qualification, Module 04 implementation has passed Module 04's
generation-21 ten-sample/30-trial qualification, and Module 05 implementation has passed all
five Module 05 paths at 30/30 trials in generation 21. Module 06 implementation has passed
all six Module 06 paths at 30/30 trials across five clean six-trial module-state
batches in generation 21. Module 07 then passed seven clean participant samples
per item, and a focused current-tree Module 08 through 10 composition passed
after the scoped reset closure repair. The current range is intentionally
retained, and Modules 08 through 10 playtest and release gates remain open. Source boxes remain
unchecked by design until one final run closes the whole checklist.

## Milestone Structure

- [ ] Scenario contract and pack skeleton exist.
- [ ] Topology, assets, and reference-triangle design are complete.
- [ ] Hidden path, affordance ledger, objective oracle, and validation model are complete.
- [ ] Flag, challenge, and reference CTFd layer are complete, or explicitly out of scope.
- [ ] All 134 realized SDL challenge behaviors, 134 projected CTFd oracle contracts, and the 16,550-point scoring and human-doc projections reconcile.
- [ ] The 37 accessible, 58 intermediate, 28 advanced, and 11 expert difficulty counts pass validation.
- [ ] The 3,015-minute board stock remains at least twice the 480-minute event window and route allowances are not misrepresented as content.
- [ ] Delivery profile bundles are complete, or explicitly out of scope.
- [ ] Golden build implementation exists in the declared live infrastructure.
- [ ] Automated live rehearsal exists for the golden build.
- [ ] Participant-run telemetry schema, field policy, data dictionary, lifecycle, and export remain reconciled with the implemented modules.
- [ ] Challenge start/attempt/hint/checkpoint/receipt/submission/solve/reset events are correlated without giving observational telemetry award authority.
- [ ] Final manual participant walkthrough is tracked as its own issue or checklist item.
- [ ] Final docs, status, evidence, and teardown reconciliation are tracked.

## Golden Definition Of Done

- [ ] The range applies from a clean checkout using committed pack content.
- [ ] No hidden repo-root `.env`, external file fetch, or undocumented manual setup is required, except approved cloud/operator credentials.
- [ ] The declared golden build profile creates the participant start state.
- [ ] The participant entry surface exists, is documented, and is reachable.
- [ ] The full happy path is executed manually from the participant surface, command by command.
- [ ] Operator channels such as SSM, Terraform, cloud consoles, generated passwords, root/SYSTEM shells, and database consoles are used only for provisioning, diagnostics, reset, observation, or teardown.
- [ ] Every required objective, oracle state, flag, and success condition is reached from the intended participant privilege context.
- [ ] Every portfolio item has a manual baseline; optional assistant/agent use is measured but never required.
- [ ] Deterministic paths pass 10/10 clean resets and stochastic paths meet the declared 30-trial success/interval gate.
- [ ] Negative gates prove objectives/flags are not trivially reachable before the required action or privilege.
- [ ] Reset, persistence, survival, or cleanup behavior works where claimed.
- [ ] Automated rehearsal passes against the same golden build profile.
- [ ] Operational telemetry contains no forbidden content or participant-visible identity and its export manifest/checksums verify.
- [ ] Collector/exporter failure leaves participant and proof paths usable while loss or missingness is visible.
- [ ] The participant subnet cannot reach OTLP, research ingest, content storage, or export/admin surfaces.
- [ ] Instrumentation-off/on p95 comparison remains below the declared 5% inference-gateway target and does not change training results.
- [ ] The human walkthrough and automated rehearsal agree path-for-path.
- [ ] Durable evidence is committed as a rehearsal report.
- [ ] Teardown is run and verified; no live range resources remain.
- [ ] `pack.yaml.status: golden` is set only after the above proof exists.

## Final Manual Participant Walkthrough Protocol

- [ ] Stand up the golden range from the documented build entrypoint.
- [ ] Enter the range only through the participant execution surface.
- [ ] Work the intended happy path manually, command by command.
- [ ] Do not substitute scripts, SSM, Terraform output, generated passwords, or test harness internals for participant actions.
- [ ] When a defect is found, fix it on the branch as a bug.
- [ ] Use one commit per distinct problem when the walkthrough exposes multiple defects.
- [ ] Re-run the affected manual step after each fix.
- [ ] Complete the entire path after the last fix.
- [ ] Run automated rehearsal and relevant static/unit checks after the manual path works.
- [ ] Tear down the range and verify cleanup.
- [ ] Report exactly what was manually proven, what was automated, and what remains out of scope.

## Last-Pass Issue Handling

- [ ] Use an umbrella last-pass issue for broad final review work.
- [ ] Use slice PRs with `Refs #<issue>` rather than `Closes #<issue>` until the whole last pass is complete.
- [ ] Add newly discovered work to the umbrella issue instead of treating the first slice as the whole scope.
- [ ] Close the umbrella issue only after the final manual walkthrough checklist and evidence reconciliation are complete.
