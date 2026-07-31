# Polaris hidden attack path

This document is operator/oracle-only. It describes the participant-executed
path and its proof boundary, but it is not a walkthrough, hint sheet, answer
source, runtime engine, or golden-evidence report.

The full ACES scenario at
`sdl/polaris-operation-northstorm.sdl.yaml` remains the sole authority for
topology, identities, services, content, relationships, the participant actor,
five objectives, assertions, and campaign workflow. The private structured
projection at `oracle/polaris-oracle.yaml` joins proof and scoring semantics to
those ACES ids. `oracle/affordances.yaml` joins discoverability and current
source owners to the same ids. Neither private file may define a new host,
identity, service, route, objective, or payload.

Polaris remains `draft`. Static validation proves that this design is
self-consistent; it does not prove a live range, participant reachability,
authentic industrial behavior, or golden status.

## Participant start context

The actor is the ACES agent `polaris-participant`, beginning as account `kali`
on `a14-kali`. The participant starts knowing only the declared A14 host,
shared and corporate subnets, and participant-visible HTTP/SSH surfaces.
Every later identity, privilege, route, service, tool, and artifact must be
acquired or derived in-world.

Operator channels may provision, reset, observe, diagnose, and tear down.
SSM, cloud consoles, Terraform output, generated passwords, root/SYSTEM,
`docker exec`, direct database access, CTFd administration, and test-harness
shortcuts cannot perform or prove a participant step.

## Canonical dependency graph

The hidden path is a graph, not a numbered flag sequence:

```text
1 target picture
  └─ 2 front-office foothold
       └─ 3 Boreas domain escalation
            ├─ 4.A analyst/lab pivot ─ 5.A Leviathan extraction ─┐
            └─ 4.B operations/SCADA pivot ─ 5.B blackout ───────┤
                                                               └─ 6 splice
                                                                    └─ 7 controllers
                                                                         └─ 8 platform seizure
```

The lab and blackout branches are independent after front-office compromise.
They may run in either order or concurrently. Both must complete in the same
range, participant, and attempt generation before the splice/bunker leg can
produce a verdict.

## Path and oracle states

| Step | Participant context and action | ACES/affordance surfaces | Success evidence | Blocking failure and negative gate | Reset owner |
| --- | --- | --- | --- | --- | --- |
| `1` | From A14, enumerate the public Boreas site and range DNS, then derive the target picture from the planted public material. | A0, range DNS, public content ids, participant tools. | `ev-target-picture` is a fresh A14-attributed receipt for the declared A0/DNS discovery state. | Reject answers, CTFd solves, pre-seeded receipts, operator retrieval, and evidence from another attempt. | A0 and range DNS. |
| `2` | Use the discovered enterprise surface to obtain a real participant-owned foothold through A1/A3/A4 services and in-world synthetic identities. | Intranet configuration/search, seeded mail, SMB documents/ACLs, employee/service accounts. | `ev-front-office-foothold` binds participant-originated authentication or exploitation to the active A14 attempt. | Direct filesystem/database access or final-state observation cannot count. | A1, A3, and A4 service/data reset. |
| `3` | Exercise the intended Kerberos/directory weakness chain against the range-local Windows domain and reach the action-specific front-office privilege. | A2, `svc-backup`, the domain relationship, Kerberos/LDAP/SMB, declared AD weaknesses. | `ev-domain-control` records participant-owned directory actions at the required privilege. | A low-privilege observation, SYSTEM shell, operator account, or management-plane query cannot award the objective. | A2 forest and objective receipts. |
| `4.A` | Authenticate from the corporate path to A16, then use its user-owned SSH/database bindings to enter the lab. | `p-shah`, `research-analyst`, A16, A6/A8 services, analyst relationship and pivot edge. | `ev-lab-pivot` records A14→A16 authentication and an A16-originated lab-service action. | A14-to-lab access is denied before the A16 pivot; direct management access is not an alternate. | A16 user state and lab sessions. |
| `5.A` | From the lab path, correlate A6 artifacts, A7 repository history, and A8 compartment data to recover the intended Leviathan material. | A6/A7/A8 content, identities, vulnerabilities, GPG dependency relationships, Git/PostgreSQL/SSH services. | `ev-leviathan-extraction` records the intended object, safe digest/byte count, participant context, and freshness. | Reject a prebuilt object, raw database row, operator copy, stale digest, or artifact obtained outside the lab path. | A6/A7/A8 content and proof state. |
| `4.B` | Authenticate from the corporate path to A15, reach its declared elevation path, and originate SCADA access from that pivot. | `s-ivanov`, `svc-scada`, A15, the A15 relationship/pivot edge, SSH and operator telemetry. | `ev-scada-pivot` records the participant identity, A15 privilege, and A15-originated SCADA destination. | A14-to-SCADA access is denied before the A15 pivot and privilege. | A15 account, cache, and session state. |
| `5.B` | From A15, use the in-world maintenance material and SCADA service to bypass the interlock and cause the range-local blackout. | A5 HMI/Modbus, A4 maintenance material, A15 cache, interlock conditions. | `ev-blackout` attributes the critical transition and subsequent splice authorization to this participant attempt. | Component failure, operator toggles, pre-opened splice state, health probes, stale events, and final-state observation cannot count. | A5 interlock/process state, splice watcher, and receipts. |
| `6` | After both branches, use the range-scoped A14 key over the participant's own opened splice to authenticate to A9. | A14, A9, `kali-pivots-through-splice`, SSH, range-scoped key binding. | `ev-splice-entry` binds the A14 session, fresh blackout generation, and A9 authentication. | A9 and bunker routes remain denied before the participant blackout, lab completion, or after reset. | A14 key binding, A9 access, and splice attachment. |
| `7` | From A9, use the planted playbooks and OT tools to execute each controller's participant challenge/unlock sequence. | A9 toolset, A10–A12 services/register content, A7 playbooks, Modbus weaknesses. | `ev-controller-control` requires fresh participant-executed success on all three declared controllers. | Provisioning, Docker, cloud, or operator register mutation cannot count. | A9 session and A10–A12 controller state. |
| `8` | Derive the brain protocol inputs from prior in-world material, authenticate to A13, and execute the final override. | A13 protocol/content, A7/A6/A8/A0 derivation sources, controller results. | `ev-platform-seizure` records the participant handshake, authentication, override, and complete prerequisite set. | Reject direct final access, known answers, pre-seeded receipts, cross-participant state, or override before both branches. | A13 protocol/objective state and all projection receipts. |

## Objective joins and success states

The private states are evidence labels, not new objectives:

| ACES objective | Canonical path steps | Required verdict evidence |
| --- | --- | --- |
| `establish-target-picture` | `1` | `ev-target-picture` |
| `compromise-front-office` | `2`, `3` | `ev-front-office-foothold`, `ev-domain-control` |
| `extract-leviathan` | `4.A`, `5.A` | `ev-lab-pivot`, `ev-leviathan-extraction` |
| `lights-out` | `4.B`, `5.B` | `ev-scada-pivot`, `ev-blackout` |
| `seize-autonomous-platform` | `6`, `7`, `8` | `ev-splice-entry`, `ev-controller-control`, `ev-platform-seizure` |

An objective passes only when all its canonical steps, required evidence, ACES
dependencies, freshness checks, namespace checks, and blocking negative gates
pass. Final-state access alone is never a verdict.

## Accepted alternates

Alternates are explicit equivalence contracts, not facilitator discretion:

- `alt-target-report-discovery` accepts either of the two in-world discovery
  routes to the same canonical A0 report. It still requires participant A14
  retrieval and the same fresh target-picture receipt.
- `alt-leviathan-authorized-db-role` accepts an independently acquired,
  in-world lab role in place of the canonical vulnerable query. It still
  requires A16 entry, the same A6/A7/A8 payload assembly, and the same
  extraction receipt.

A matching answer, screenshot, CTFd solve, raw command transcript, facilitator
statement, or management-plane action is not an alternate. New alternates must
name the outcome, participant context, predicate, evidence, award projection,
reset owner, and explicit review rationale.

## Evidence, scoring, and telemetry

Proof is server-observed, range-local, and read-only to validators. Every event
is namespaced by `range_instance`, `participant`, and `attempt_generation`.
Reset advances the generation, closes the splice, restores controller/service
state, and clears native verdict and consumer-projection state. Cross-range,
cross-participant, stale, pre-reset, and pre-seeded evidence fails closed.

Durable evidence may retain approved ids, roles, states, counts, byte counts,
timestamps, statuses, and sufficiently high-entropy digests. It must not
retain credentials, flags, answers, private keys, tokens, command output, file
bodies, database rows, raw controller registers, CTFd submissions, or
participant PII.

The `native-verdict` consumer supplies a deterministic score projection over
validated outcomes. It does not own predicates, path dependencies, topology,
or evidence. CTFd remains outside this slice and may consume an independent
oracle verdict; challenge points and solve rows cannot
determine an ACES objective.

Proof telemetry is authoritative input and fails closed when required evidence
is absent or stale. Operational health/diagnostic telemetry is observational,
may fail open, and cannot create an award. These files define event and field
contracts only; the pack does not ship a telemetry backend, scoring service,
proof API, persistence engine, or scoreboard.

## Validation and profile boundary

`validation/validate_oracle.py validate` is static and read-only. It checks the
shared oracle shape, exact ACES objective/workflow joins, path acyclicity,
parallel-branch preservation, participant start context, evidence namespace
and reset owners, complete affordance kinds and path coverage, contained
single-source owners, ACES references, and participant-root leakage.

`local_degraded` supports source feedback only. `aws_event` proves the authored
event path from A14 in live AWS, including route gates, reset, and teardown, but
its hand-authored fictional controllers are not authentic industrial twins and
do not establish golden proof. A future doctrine-complete golden profile must
use authentic industrial bindings and pass the mandatory manual participant
walkthrough before any golden claim.
