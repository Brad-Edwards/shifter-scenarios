# Technical data contract

This contract defines the synthetic people, business records, source history,
and process records consumed by the technical challenge designs. It does not
create an infrastructure layout or generate the assets. Every implementation
uses it as the source of truth for names, identifiers, relationships, and
expected pre-event state.

## Seed model

Seed the campaign as four reviewable data packages:

| Package | Contents | Required property |
| --- | --- | --- |
| `identity` | People, service identities, groups, certificates, OAuth clients, service-account bindings, recovery data, and account status. | Every principal has one canonical `actor_id`; local usernames and subject identifiers point back to it. |
| `business` | Tickets, work orders, appointments, customer integrations, quotes, allocations, maintenance records, planning records, and documents. | Every record uses a stable business identifier and declares its owner, organization, revision, and visibility. |
| `engineering` | Repositories and commits, packages, builds, releases, binaries, projects, device images, tags, calibration, operating envelopes, and simulator reference traces. | Artifact provenance is explicit: author, date, source revision, consumer, and replacement history. |
| `scenario` | Per-player mutable state, challenge evidence, private rehearsal outputs, triggered notices, and scoring bindings. | A player’s writes are isolated from other players while stable background evidence remains reproducible. |

The package metadata records a synthetic-data declaration, data-schema version,
source revision, deterministic seed, fixture counts, and expected liveness
checks. Human-readable seeds live beside their binary or generated counterparts:
mailbox messages, repository commits, directory records, attachment manifests,
and application records should be reviewable without executing a target.

Generate values from stable natural keys such as `actor_id`, `ticket_id`,
`asset_id`, `tenant_id`, `revision_id`, and `player_id`. Do not derive a flag,
credential, or authorization decision from a row number, a random initial state,
or an order-dependent database key. Generated secrets are synthetic and scoped
to one player instance. Documentation names the fixture containing each secret
but never carries production-like values.

## Organizations and shared story records

### KeplerOps

KeplerOps develops and supports the **FieldKest** connector that customer
utilities use to exchange maintenance and planning data. It operates the
`@keplerops/fieldlink-connector` package line, a support application, a source
forge, a build service, an internal package registry, and cloud-style data
services.

| Canonical ID | Person or service | Everyday role | Records that make the role visible |
| --- | --- | --- | --- |
| `K-DEV-01` | Rowan Ito (`rowan.ito`) | FieldKest developer whose workstation is supplied to Cinder. | Browser history, worktree, local notes, stale client profiles, test-job references. |
| `K-SUP-01` | Maya Ranscombe (`maya.ranscombe`) | Support engineer assigned the ARWC case. | `SUP-2841`, support mailbox, assistant conversation, diagnostic delivery assignment. |
| `K-REL-01` | Evan Calderoux (`evan.calderoux`) | Release engineer for FieldKest. | Release dossier, signing history, rollover notice, private consumer reviews. |
| `K-SRE-01` | Noor Aveling (`noor.aveling`) | Build and workload operator. | Runner records, cloud policy notes, maintenance scheduler contract. |
| `K-REV-01` | Talia Mornac (`talia.mornac`) | Support reviewer. | Duplicate-review workflow and restricted note-review account. |
| `K-SVC-CI` | `svc-fieldlink-ci` | Build execution identity. | Build job provenance, limited source scope, private test-consumer binding. |
| `K-SVC-EXP` | `svc-support-export` | Customer export worker. | Export job actions and delivery-destination history. |
| `K-SVC-BAK` | `svc-history-recovery` | Backup recovery identity. | Backup catalog and permitted restore operation. |
| `K-SVC-RUN` | `svc-fieldlink-maintenance` | Maintenance workload runtime identity. | Runtime archive policy evaluated independently of its deployment manager. |

The active ARWC customer record is `TEN-ARWC-047`, service revision
`FLK-7.4.2`, package line `7.4.x`, and support case `SUP-2841`. Older records
use `TEN-ARWC-019` and `FLK-6.9.8`; they are believable historical data and
must never satisfy an active-customer or current-revision predicate.

`SUP-2841` concerns a recurring field diagnostic for **Cairn Reach Reservoir**.
Its public text says that a routine inspection needs an approved diagnostic
bundle. Its private escalation note says that the current commissioning evidence
and the customer’s reserve report disagree. That note is an information reward,
not a shortcut to a customer delivery or plant-control identity.

### ARWC

ARWC operates corporate planning, maintenance, vendor access, a process-data
bridge, engineering tooling, supervisory control, and a reservoir simulator.
The target is the **Cairn Reach Reservoir outlet group**.

| Canonical ID | Person or service | Everyday role | Records that make the role visible |
| --- | --- | --- | --- |
| `A-PLAN-01` | Nadia Corvane (`nadia.corvane`) | Regional water planner. | Planning reports, allocation query role, decision handovers. |
| `A-MAINT-01` | Theo Marrivel (`theo.marrivel`) | Maintenance planner. | Work order, drawing approval, inspection appointment, procurement record. |
| `A-CTRL-01` | Clara Morivelle (`clara.morivelle`) | Controls engineer. | Commissioning note, project revision, calibration concern, operating envelope. |
| `A-FIELD-01` | Jules Orswick (`jules.orswick`) | Contractor scheduled for outlet inspection. | Contractor roster, field bag, appointment, scoped field session. |
| `A-PROC-01` | Priya Naravel (`priya.naravel`) | District procurement officer. | Quote records, replacement-supply catalogue, order acknowledgement. |
| `A-SVC-CONN` | `svc-fieldlink-arwc` | FieldKest connector identity. | Delivery execution, limited corporate service context, process-read integration. |
| `A-SVC-PLAN` | `svc-reserve-planning` | Planning-service identity. | Allocation decision input and report refresh records. |
| `A-SVC-REND` | `svc-maint-preview` | Maintenance rendering identity. | Approved drawing preview and maintenance command-client issuance. |
| `A-SVC-ENG` | `svc-engineering-client` | Engineering command-client issuer. | Narrow client issuance, distinct from project publication. |

The asset hierarchy is stable throughout the campaign:

| Field | Value |
| --- | --- |
| `site_id` | `CRR-01` — Cairn Reach Reservoir |
| `outlet_group_id` | `CRR-OG2` — east outlet group |
| `actuator_ids` | `CRR-OG2-GA`, `CRR-OG2-GB` |
| `work_order_id` | `MWO-7742` — outlet inspection |
| `appointment_id` | `APT-CRR-7742` |
| `current_project_revision` | `CRR-5.4.2` |
| `obsolete_project_revision` | `CRR-5.3.7` |
| `current_integration_revision` | `FLK-7.4.2` |
| `planning_window` | `ALLOC-2026-09-W3` |

The real measurements are published independently of planning and reporting:
`CRR.OG2.GA.POSITION`, `CRR.OG2.GB.POSITION`,
`CRR.RESERVOIR.USABLE_VOLUME`, and `CRR.OG2.PERMISSIVE`. Business-facing
reports intentionally use older aliases and a scale revision that must be
reconciled. The engineering tag export and scale table make that work
evidence-based.

The two affected planning districts are `PINE` and `RIVER`. A replacement-water
quote belongs to `RIVER`; the local financial ending charges it to `PINE` while
keeping supplier, quantity, and delivery period unchanged. Neither district is
derived from a player-controlled string.

## Data relationships that challenges depend on

| Relationship | Seeded evidence | Constraint to preserve |
| --- | --- | --- |
| Developer → source → build → package | Worktree remotes, Forge commit graph, build records, package manifests, consumer-lock data. | A discovered source location must not become build authority. |
| Support case → customer → delivery | `SUP-2841`, `TEN-ARWC-047`, selected connector revision, diagnostic-job records. | The old tenant and old package remain visible decoys with clear revision evidence. |
| Person → identity provider → application role | Canonical actor, directory account, identity subject, application account, certificate enrollment. | A local session never gains an adjacent role solely because names match. |
| Workload definition → runtime identity → object policy | Deployment manifest, workload identity, resource label, archive policy. | Workload-management permission and runtime resource permission are evaluated separately. |
| Appointment → contractor → field asset scope | Appointment, roster, contractor record, work-order asset. | An appointment-owner flaw can cross one explicit scope; it cannot produce arbitrary contractor access. |
| Corporate allocation → meter export → process read | Period, units, aliases, independent read reference. | The player can reconcile a real discrepancy without changing the ledger or meter records. |
| Project → deployed revision → tag/scale → outlet group | Engineering project, independently published current revision, tag export, scale table, reference trace. | Current revision comes from the independent deployed record, never a recoverable old project. |
| Control client → broker → dispatcher → actuator → measurement | Client issuance, command receipt, accepted transition, independent sensor event. | A command acknowledgement cannot stand in for actuation. |

## Data creation rules

1. Seed every user, group, mailbox, source commit, package version, object
   version, ticket, work order, and process record from a named fixture.
   Fixtures may reference generated values by stable logical name.
2. Create repository histories through ordinary Git commits with authors,
   timestamps, branches, tags, and deletions. A deleted-file challenge uses a
   real reachable or recoverable commit, never a fake `git log` response.
3. Seed mail as complete messages with headers, sender, recipient, timestamp,
   body, attachments, and folder. Keep mail facts consistent with the sender’s
   role and the related ticket or repository revision.
4. Seed directory and application identities separately, then link them through
   explicit federation, provisioning, or enrollment records. This creates
   realistic joins for identity challenges and prevents accidental universal SSO.
5. Seed object stores with bucket, object key, version ID, owner, retention
   state, policy, and upload event. Historical versions and backups use their
   own provenance records.
6. Seed process traces with a scenario timestamp, source, quality, engineering
   revision, and correlation ID. A trace produced by a practice model is marked
   `practice`; a simulated live outcome is marked `process`; an altered planning
   view is marked `reported`.
7. Keep public, protected, and earned data sets separate in the seed manifest.
   A challenge should make one new relationship or operation available rather
   than expose the entire adjacent record set.

## Mutable state and events

Each player receives a campaign state keyed by `player_id`. It has immutable
background data plus a player-scoped event stream. Event types include
`package_published`, `consumer_activated`, `case_reviewed`,
`contractor_checked_in`, `practice_transition`, `control_client_issued`,
`command_accepted`, `process_transition`, `planning_refresh`, and
`procurement_ordered`.

An event contains the actor, target record, evidence IDs, precondition revision,
and resulting revision. Challenge scoring observes the event and its independent
evidence; it does not score a client-side claim. The reservoir state changes only
after an accepted command creates a matching independent process transition.
Private rehearsals fork only mutable state at an earned checkpoint and retain
their own event history. They never alter the player’s completed campaign route.

## Seed validation before exposure

- All canonical IDs resolve once in every referenced data package.
- Every mailbox reference, repository commit parent, object version, ticket link,
  identity subject, group membership, package dependency, and asset relationship
  resolves to an existing record.
- Historical values such as `TEN-ARWC-019`, `FLK-6.9.8`, and `CRR-5.3.7` remain
  distinguishable from active equivalents by visible dates and revisions.
- Every protected object has exactly the intended ordinary and challenge-earned
  access paths; its direct data-plane read remains denied where the brief says so.
- The declared starting views contain every fair starting lead and none of the
  protected outcome data.
- Expected counts of users, messages, commits, packages, objects, tickets,
  appointments, project records, tags, and baseline process traces match the
  seed contract.
- Re-seeding from the same profile yields the same identifiers, record graph, and
  non-player-specific evidence. Per-player credentials and flags remain unique.

## Product selection rule

Use a real open-source product where its normal behavior is part of the player’s
work: Git repository history, CI job execution, package resolution, identity
federation, ticket and mail records, object versioning, database semantics,
container workload identity, messaging, industrial protocol exchange, or HMI
display. Use a small authored component where the challenge requires a specific
business workflow or intentionally vulnerable boundary. The authored component
must retain ordinary records, logs, error behavior, and access checks that make
the surrounding organization believable.

Windows directory services and certificate services are justified only where the
certificate, Kerberos, or service-delegation behavior is the actual subject of
the challenge. They remain bounded identity services among predominantly
open-source application and data services. No cloud-provider account, paid SaaS
tenant, proprietary industrial suite, or external email account is required by
this design.
