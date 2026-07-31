# KeplerOps operator and playtest guide

This is the practical runbook for operators and playtest coordinators. It is
not a second scenario specification. The modular ACES SDL remains the sole
logical authority for nodes, services, identities, challenge contracts,
dependencies, event bundles, telemetry contracts, and reset ownership. This
guide explains how to run and observe the current `gcp_full` realization.

The pack is still `draft`. Current docs describe source-realized and
automated-proven work, participant-proven work, retained-range state, and
completed Phase-E teardown separately. Do not claim `golden` until the final
participant-equivalent walkthrough, automated rehearsal, evidence
reconciliation, and teardown checklist all close in one release run.

## Operating model

- Use only an existing operator-approved GCP project. The build creates and
  destroys a namespaced tenant inside that project; it does not create a
  project, attach billing, or create operator accounts.
- Confirm `gcloud auth print-access-token` succeeds immediately before a
  lifecycle command. Launch, reset, and cleanup snapshot that token for both
  Terraform and their subsequent `gcloud` subprocesses so a long operation
  does not switch to stale application-default credentials.
- Use the `gcp_full` profile for real participant playtesting. `local_reduced`
  is an authoring aid and intentionally projects no CTFd board.
- Treat `build/.operator/<range-instance>-<participant>/` as owner-only
  deployment state. It is gitignored and may contain Terraform state,
  generated TLS/key material, image locks, local reports, and evidence staging.
- Keep participant-facing material limited to the briefing, lab portal, CTFd
  board, and any spoiler-reviewed handout. Operator walkthroughs, proof reports,
  ATLAS mappings, hidden predicates, receipts, flags, and validation internals
  are not participant material.

## Build or reuse a range

From the pack root:

```sh
cd keplerops-ai

build/launch.sh \
  --project-id <existing-project-id> \
  --range-instance <range-instance> \
  --participant <participant-id> \
  --participant-source-cidr <participant-cidr> \
  --research-profile off
```

Use a globally routable, explicitly scoped participant CIDR. `0.0.0.0/0` is
rejected. The default region and zone are `europe-west4` and `europe-west4-a`;
override them only when the event infrastructure requires it.

`launch.sh` renders the SDL realization, validates the ACES build contract,
applies the tenant foundation, publishes pinned runtime images, applies runtime
nodes, seeds synthetic range secrets, and runs the canonical health check.
Every VM, service route, TCP/UDP allowlist, certificate seed, evidence producer,
and health expectation comes from the ACES SDL or an SDL-derived typed
projection.

To retrieve the participant browser endpoint after launch:

```sh
terraform -chdir=build/gcp output \
  -state="build/.operator/<range-instance>-<participant-id>/terraform.tfstate" \
  -raw participant_endpoint
```

If a retained rehearsal/playtest range is already up, do not relaunch it just
to run a focused check. First confirm health:

```sh
build/health-check.sh \
  --range-instance <range-instance> \
  --participant <participant-id>
```

For an automated participant rehearsal against an existing retained range:

```sh
tests/run-golden-rehearsal.sh \
  --project-id <existing-project-id> \
  --range-instance <range-instance> \
  --participant <participant-id> \
  --participant-source-cidr <participant-cidr> \
  --use-existing-range \
  --retain-until-phase-e
```

`--use-existing-range` is intentionally tied to `--retain-until-phase-e`; the
runner still performs health and reset checks, but cleanup is a later explicit
Phase-E action.

## Participant entry and start state

Participants enter through the Kasm browser workstation and operate only inside
the contained `*.keplerops.lab` environment and the contained exfiltration sink.
Commercial model endpoints, cloud metadata, operator interfaces, the GCP
control plane, and internet callbacks are out of bounds.

The lab portal offers multiple AI-security starts. The opening paths do not
require conventional enterprise compromise:

- agent control;
- model evasion;
- retrieval-context poisoning;
- model-secret and privacy extraction.

Non-agent participants must be able to work from the browser terminal, UI
surfaces, curl, Python, and in-world documentation. Participant-owned offensive
agents are allowed when the event profile permits them, but no challenge should
require an external commercial agent or commercial model provider.

## CTFd board projection

CTFd is a projection from the validated ACES challenge/event-bundle contract.
It is not an answer ledger. Receipts are participant-, range-, expiry-, and
reset-generation-bound proof-service outputs; static flags are not accepted.

Preview the full `gcp_full` board:

```sh
python3 ctfd/sync_keplerops_ctfd.py \
  --base-url https://ctf.example.invalid \
  --dry-run
```

Preview an SDL-owned event bundle:

```sh
python3 ctfd/sync_keplerops_ctfd.py \
  --base-url https://ctf.example.invalid \
  --profile novice-manual \
  --dry-run
```

Current selectable bundle names are `novice-manual`, `intermediate-manual`,
`mixed-cohort`, `advanced-manual`, and `agent-heavy`. Bundles containing the
planned `kep-m02-g` hardware-trust challenge fail fast until that challenge is
implemented or explicitly removed from the selected bundle. Use
`ctfd/README.md` for plugin installation, receipt key binding, CTFd account
binding, and live sync options.

## Module order and dependency expectations

Use the CTFd projection or `aces_contract.py` for exact dependency closure. The
summary below is only an operator orientation map.

| Module | Playtest role | Dependency notes |
|---|---|---|
| 01 Agent control | Early independent root plus deeper agent-tool chains. | Some later agent/deputy and capstone flows depend on specific receipts or effects. |
| 02 Model evasion and supply chain | Early independent root; supply-chain branch adds package, data, model, web, mail, and sandbox paths. | `kep-m02-g` remains planned/under consideration; bundles that require it block. |
| 03 Context poisoning | Early independent root for retrieval and persistent context attacks. | Later context and agent-memory flows may reuse poisoning concepts, but exact gates are SDL-owned. |
| 04 Model secrets and privacy | Early independent root for disclosure and membership/privacy paths. | Advanced variants extend fingerprinting, artifact census, and data-export ideas. |
| 05 Agent persistence | Mid-depth agent state, restart, credential, and relay work. | One core deputy path depends on Module 01; expansion paths are deeper agent-surface work. |
| 06 Adversarial input | Broad attack-construction and transfer surface. | Several paths are suitable for participants or participant agents; exact prerequisites are projected into CTFd. |
| 07 Training poisoning | Data/workflow/model-artifact manipulation. | Produces artifacts and lineage used by later backdoor/promotion and capstone paths. |
| 08 Model extraction | Live-teacher querying, proxy training, fidelity, and artifact-access work. | Depends on the range-local teacher/corpus/workflow surfaces, not external model endpoints. |
| 09 Model backdoor | Candidate registration, hidden behavior evaluation, approval confusion, promotion, and reload. | Requires eligible training/model artifacts where declared by SDL. |
| 10 AI capstone | Deployed-model impact, contained effects, joined proof, and model-theft paths. | Pulls together promoted model, artifact store, agent/adversarial state, and contained sink behavior. |

The current full board is intentionally larger than the event window. Select a
dependency-closed event bundle for each cohort rather than expecting full clear.

## Reset and health

Run health before participant windows, after deployment changes, and after
resets:

```sh
build/health-check.sh \
  --range-instance <range-instance> \
  --participant <participant-id>
```

Canonical full reset:

```sh
build/reset.sh \
  --range-instance <range-instance> \
  --participant <participant-id>
```

Reset is fail-closed: it closes writes/receipts, advances the receipt
generation, resets canonical owners, requires local owner verification, runs
health, and writes reset verification under owner-only operator state. A stale
receipt must fail after reset even if its wall-clock expiry has not passed.

Use scoped/module-prepared reset modes only through the module rehearsal scripts
that document them. Do not restart every service to check a narrow path unless
the changed dependency closure or health result requires it.

## Evidence, receipts, and reports

Participant success is established by in-world actions that create proof
evidence and then by a fresh proof-service receipt. A receipt is bound to:

- the challenge/flag id;
- the evidence object;
- the participant;
- the range instance;
- the current reset generation;
- the receipt expiry.

Operator reports in `docs/*proof-report.md`, `docs/manual-walkthrough-report.md`,
and `docs/telemetry-rehearsal-report.md` are sanitized evidence summaries.
They should never include raw browser state, cloud identifiers, credentials,
tokens, receipts, model data, raw prompts, completions, proof bodies, or
operator command output.

Local rehearsal and export artifacts below `build/.operator/` may be used for
diagnosis and report rendering. Do not commit them.

## Telemetry and research capture

Operational telemetry is observational and fail-open. It cannot award a
challenge, mint a receipt, change reset state, or block participant inference,
workflow, proof, or teardown paths.

Default launch mode:

```sh
build/launch.sh ... --research-profile off
```

This records bounded operational events and metadata only. Operational exports
exclude participant-visible identity, IP addresses, credentials, tokens, flags,
receipts, proof bodies, SQL, stack traces, prompt bodies, completion bodies,
raw tool bodies, model bytes, raw HTTP bodies, and exact hidden thresholds.

Full-content research mode:

```sh
build/launch.sh ... --research-profile full-content
```

This enables the SDL-declared encrypted content capture profile for prompts,
completions, tool calls/results, terminal commands and PTY streams, process
lifecycle, browser navigation/download records, Jupyter saves, workstation file
content, workflow state/artifacts, and selected scenario HTTP bodies. Content
capture is encrypted into a separate operator-only store and exported
separately from the operational archive. The content key is not written into
the archive.

Operational export:

```sh
build/export-telemetry.sh \
  --range-instance <range-instance> \
  --participant <participant-id> \
  --output /operator/evidence/<range-instance>-telemetry.tar
```

Operational plus full-content export, when full-content capture was explicitly
enabled:

```sh
build/export-telemetry.sh \
  --range-instance <range-instance> \
  --participant <participant-id> \
  --output /operator/evidence/<range-instance>-telemetry.tar \
  --content-output /operator/evidence/<range-instance>-content.tar
```

`export-telemetry.sh` augments the bundle with session-bounded VPC flow and
firewall-decision observations. If Cloud Logging is partially unavailable, the
export still completes and records partial or unavailable network capture in
the missingness data. Use `telemetry/data-dictionary.md` for field semantics
and capture exclusions.

## Playtest operating loop

Before a participant window:

1. Select a dependency-closed CTFd profile or custom challenge set.
2. Confirm the range health check passes.
3. Confirm the participant endpoint is reachable from the approved source CIDR.
4. Confirm CTFd account binding uses the current range instance, participant,
   and reset generation.
5. Confirm the selected telemetry profile is intentional.
6. Provide only spoiler-reviewed participant material.

During a participant window:

1. Let participants choose branches; do not force full clear.
2. Record cohort/profile assignment outside the participant-visible challenge
   material.
3. Preserve content-capture decisions made before the run. Do not switch to
   full-content capture midstream without an operator decision and a new
   session boundary.
4. Use operator channels only for observation, support, reset, and diagnosis.
5. If a challenge defect blocks play, fix the defect or record it in the active
   repository; do not silently paper over it in guide text.

After a participant window:

1. Export operational telemetry, and full-content telemetry if it was enabled.
2. Run readback/checksum verification before handoff.
3. Run the appropriate reset. Use a scoped reset only if the relevant rehearsal
   script documents it and health verifies the prepared dependency closure.
4. Record missingness, skipped paths, participant-visible defects, and operator
   interventions in the playtest notes or linked defect record.

## Troubleshooting and escalation

- If `launch.sh` rejects the project, participant id, range id, or CIDR, fix the
  argument. Do not bypass validation.
- If `health-check.sh` fails, diagnose through Terraform outputs, IAP, and node
  local health only. Do not count management-plane remediation as participant
  proof.
- If CTFd sync blocks a bundle because of a planned challenge, select a bundle
  that is fully realized or change the SDL-backed bundle in a separate change.
- If reset cannot resume, treat the range as not ready for participants until
  the lifecycle state is repaired or the tenant is cleaned and relaunched.
- If telemetry export reports partial or unavailable network capture, preserve
  the missingness data; do not imply full network observability in reports.
- If new implementation, validation, or docs work is discovered outside the
  active work scope, create or update a repository defect record and link it
  from the playtest notes.

## Phase E teardown

Export required evidence before teardown. Then destroy only the namespaced
tenant:

```sh
build/cleanup.sh \
  --range-instance <range-instance> \
  --participant <participant-id>
```

Cleanup quiesces the range, deletes tenant-labelled Cloud Run jobs if needed,
destroys Terraform-managed tenant resources, and writes
`build/.operator/<range-instance>-<participant-id>/teardown-report.json`. The
report must show the tenant VPC as `ABSENT`. Cleanup must not delete the
operator-supplied project, billing configuration, or operator accounts.

If a range is intentionally retained to accelerate active work, record that
retention explicitly in the defect record or report. Retention is a work-state choice,
not a golden teardown proof.
