# Technical platform catalog

This catalog defines the logical application surfaces used by the technical
challenge drafts. It deliberately does not select hosts, virtual machines,
container layouts, cloud projects, or a deployment platform. A component is a
story-level service with an interface, records, and authority boundaries.

The campaign uses ordinary open-source products when their genuine behavior is
the subject of a task. Small authored services are limited to FieldLink and
ARWC workflows where a specific business process, deliberately bounded flaw,
or scoring event needs to exist. They must expose ordinary records, errors,
audit events, and access controls; a player should never have to infer an
unobservable author intention.

## Shared identity and records

| Logical component | Preferred product or form | Normal purpose | Authority boundary |
| --- | --- | --- | --- |
| Identity broker | Keycloak | OIDC/SAML sessions, client registrations, group claims, and federation joins. | A session carries only the audience, subject, group, and client permissions actually issued. |
| Directory and certificate service | FreeIPA by default; Windows directory services only where a card needs native directory, Kerberos, delegation, or certificate behavior. | People, groups, service identities, enrollment, and machine trust. | Application roles are provisioned or federated deliberately; directory membership alone is not universal application access. |
| Mail | Postfix, Dovecot, and Roundcube | Complete internal mailboxes, attachments, service notices, and delivery receipts. | Mail proves communication and can deliver a scoped artifact; it does not silently grant the recipient's other roles. |
| Ticket and case records | Zammad where ordinary ticket behavior suffices; authored workflow only for FieldLink-specific decisions. | Support cases, maintenance work orders, ownership, attachments, status, and audit history. | Record visibility, assignment, and action approval are independently checked. |
| Object and version store | MinIO with S3-compatible versioning | Archives, exports, backups, release materials, drawings, and evidence packages. | Management-plane knowledge and data-plane object read/write remain distinct. |
| Relational data | PostgreSQL | Tenant records, workflow state, reports, historian metadata, and bounded query exercises. | Read, job submission, and administrative actions use different principals and transaction scopes. |

All records use the identifiers and relationships in the [technical data
contract](technical-data-contract.md). Each player sees an isolated mutable
workspace and event stream, while shared reference records retain stable,
reviewable timestamps and provenance.

## KeplerOps application surfaces

| Logical component | Preferred product or form | Player-visible normal behavior | Intentional boundaries used by cards |
| --- | --- | --- | --- |
| FieldLink developer workspace | Authored supplied workstation image and ordinary local tools. | Rowan's worktree, notes, browser profiles, test fixtures, and local utility history. | Local discovery is separate from Forge, registry, CI, and customer authority. |
| Source forge | Gitea | Repositories, pull requests, commit graph, tags, package manifests, deploy keys, and code review. | Repository read, issue comment, protected-branch action, and release signing are separate grants. |
| Build service | Jenkins LTS or Woodpecker CI, with the authored FieldLink review/diagnostic job interface. | Test jobs, build logs, artifacts, worker labels, credentials bound to jobs, and release approvals. | Read-only inspection, repeatable isolated command jobs, build maintenance, artifact publication, and workload runtime authority are individually scoped. Job commands can use native clients and separately earned credentials; they do not administer the CI host. The K09 diagnostic-profile authorization flaw belongs to FieldLink's job interface, not an invented vulnerability in either CI product. |
| Package registry | Verdaccio | Scoped JavaScript packages, version metadata, integrity values, access policy, and consumer configuration. | Read, publish, and promotion are distinct. A publish may be customer-ineligible until its specific consumer path is earned. |
| Release archive | MinIO and signed release manifest service. | Versioned artifacts, release attestation, support diagnostic bundles, and approval records. | Access to a build output does not imply signing or customer delivery. |
| Support gateway | Authored FieldLink support workflow backed by PostgreSQL and the shared case records. | Customer cases, tenant selectors, diagnostic requests, reviewer queue, delivery status, and attachments. | Viewing a case, acting as its assigned support engineer, reviewing an escalation, and executing delivery are different authorities. |
| Customer diagnostic endpoint | Authored FieldLink consumer emulator. | A customer-specific package resolver, diagnostic invocation, receipt, and support-facing status update. | It accepts only the active tenant, approved package line, and expected delivery identity. It produces a real receipt event instead of a flag-only acknowledgment. |
| Preview and document worker | Playwright/Chromium worker behind an authored preview queue. | Rendering customer-provided support documents and returning a normal preview or a bounded failure record. | Preview execution uses an isolated worker identity; rendered data cannot reach unrelated customer or infrastructure records. |
| Cloud-style archive service | Kubernetes API semantics with OpenBao and MinIO, or a faithful authored adapter when a card needs a constrained exercise. | Workload records, service-account tokens, archive policies, object versions, job history, and maintenance tasks. | Control-plane mutation, workload identity, and object data-plane rights are evaluated separately. |
| Local assistant | Qdrant plus a small local inference service such as llama.cpp, with an authored support chat wrapper. | Search-grounded support assistance, uploaded documents, conversation threads, case notes, and approval requests. | Retrieval visibility, workflow authorization, and outbound action remain separate. The assistant never exposes hidden system prompts or a grading channel. |
| Native exercise services | Small source-available Linux utilities and isolated challenge daemons. | Parser, compiler, loader, indexer, and release-tool behavior with logs and sample inputs. | Each daemon exposes only its assigned fixture data and private player state; no host-level pivot is necessary or rewarded. |

## ARWC application surfaces

The OT target is a narrow operating water utility. Participants use real OT
products, engineering tools, and industrial protocols during normal operations.
The [ARWC OT platform plan](arwc-ot-platform-plan.md) defines the delivery order
and acceptance criteria. This target is not yet deployed. The current OT build
uses custom Python HTTPS services and does not satisfy this target.

| Logical component | Preferred product or form | Player-visible normal behavior | Intentional boundaries used by cards |
| --- | --- | --- | --- |
| Corporate portal | Authored ARWC portal backed by Keycloak and PostgreSQL. | Vendor onboarding, FieldLink customer records, corporate documents, dashboards, and employee profile links. | A customer integration session does not become a workforce, planning, or engineering session by name similarity. |
| Maintenance and appointment service | Zammad-compatible workflow or authored work-order service. | Work orders, attachments, contractor roster, appointments, check-in, asset scope, and maintenance status. | Discovering an appointment is distinct from owning it; a scoped contractor session cannot access arbitrary sites. |
| Document archive and preview | MinIO plus the shared preview worker pattern. | Drawings, project bundles, archive searches, quoted references, and preview requests. | Archive query, a document-derived service action, and engineering publication are separately bounded. |
| Planning and reconciliation service | PostgreSQL-backed authored reporting workflow. | Allocations, meter imports, district reports, supplier quotes, and report refresh jobs. | A report can be recomputed from evidence, but planning records and procurement actions require their own earned workflow state. |
| Engineering project service | Gitea and an authored project registry. | Project revisions, change reviews, deployed-revision notices, calibration files, tag exports, and commissioning documents. | Project read, project change, review, and command-client issuance are distinct. A project copy is never authoritative merely because it is older or more editable. |
| Engineering workstation | Linux desktop with OpenPLC Editor, a browser, an OPC UA client, and PostgreSQL tools. | Open the control project, inspect online variables, browse tags, compare revisions, and perform an authorized maintenance download. | Engineering access is distinct from operator access. The desktop has no host or container administration authority. |
| PLC and site controller | OpenPLC Runtime v4 with a pinned IEC 61131-3 project. | Scan cycles, I/O scaling, manual and automatic modes, command arbitration, permissives, actuator sequencing, and retained settings. | The PLC owns control decisions and command acceptance. Supervisory applications cannot replace its logic. |
| Field I/O and equipment response | Small deterministic remote-I/O emulator connected through Modbus TCP. | Level, flow, position feedback, actuator travel, local selectors, and communications state for one reservoir outlet site. | This component models physical response only. It does not own operator permissions, process interlocks, or scenario completion. |
| OPC UA interface and bridge | OpenPLC's upstream OPC UA plugin first; an open62541-based bridge only if the compatibility spike requires it. | Browse a stable namespace, inspect types and units, subscribe to values, inspect quality and timestamps, and write authorized request tags. | Certificates and user roles control access. A real OPC UA endpoint is required; HTTPS JSON is not a substitute. |
| Process historian | PostgreSQL with Telegraf OPC UA collection and a qualified historical trend interface. | Store measured values, source timestamps, quality, alarm events, and communications gaps; query and trend retained history. | The OT historian is separate from corporate planning data. Selected read-only views supply the DMZ bridge. |
| HMI and SCADA | FUXA with an authored water-site project. | Overview mimic, equipment faceplates, live values, setpoints, modes, permissives, alarm acknowledgement, trends, and bad-quality indication. | Operator actions use real PLC tags. FUXA configuration and engineering access are separate from ordinary operation. |
| Engineering command-client issuer | Authored narrow issuance service backed by identity and engineering records. | Approved issuance requests, client credential metadata, owner, scope, expiry, and audit trail. | The issuer can create one scoped command client only after its record-level conditions are met; no broad OT account is ever granted. |
| Control broker and dispatcher | Mosquitto with upstream authentication and topic roles, plus a narrow authored dispatcher using maintained MQTT and OPC UA libraries. | Authenticated remote requests, identity-bound authorization, expiry and duplicate handling, PLC request writes, and separate receipt and outcome records. | The dispatcher authorizes remote requests. The PLC owns permissives and execution. Broker receipt does not prove equipment movement. |
| Process-read bridge | Existing ARWC DMZ bridge consuming selected historian views. | Supply timestamped operational measurements to corporate reporting with quality and provenance. | The bridge has no controller write path. Instruments do not route traffic between networks. |
| Procurement service | Authored workflow backed by PostgreSQL and mail receipts. | Replacement-water quote selection, district attribution, approval state, order acknowledgement, and financial report. | A planning report does not place an order. The selected quote and district must be proven by the correct joined records. |
| Native exercise services | Small source-available Linux utilities and isolated daemons. | Controlled parser, VM, cache, crypto, and memory-corruption exercises tied to project or field records. | They expose only card-local fixtures and earned artifacts; success never gives shell access to unrelated OT services. |

## Cross-component contracts

The following contracts are consistent across all cards. They prevent accidental
shortcuts while keeping the organizations realistic.

1. **Identity.** A signed identity assertion includes issuer, subject, audience,
   expiry, client, and selected groups. Consumers validate the fields relevant
   to their own boundary. A human account, service account, certificate, and
   application account are related records, not interchangeable strings.
2. **Artifact provenance.** Source revision, build run, package version,
   release manifest, consumer resolution, and delivery receipt retain separate
   identifiers. A player can show how an artifact moved without treating one
   metadata record as another authority.
3. **Customer scope.** KeplerOps customer actions are keyed to the active tenant
   and approved FieldLink revision. ARWC data is discoverable only through
   routes explicitly awarded by the campaign; stale customer records carry
   visible revision and date differences.
4. **Control.** Any command has a client identity, target, nonce or sequence,
   requested transition, policy decision, and dispatcher audit ID. Only a
   matching independent measurement and state transition can represent physical
   impact.
5. **Narrative evidence.** Tickets, mail, version history, logs, historical
   reports, and observations are ordinary in-world artifacts. Card completion
   may create a receipt, changed record, review status, or process observation;
   it must not display a fourth-wall progress message.

## Minimum operational data per component

Each component declares, in its seed manifest, its canonical identifiers,
expected record counts, relationships, default visibility, player-scoped
records, liveness probe, reset class, and the challenges it supports. A
component-level test verifies that its ordinary workflow is usable before a
deliberate boundary is exercised. Challenge-specific author checks add the
negative cases required by the individual card.

No component needs internet egress or an external account. The campaign uses
synthetic mail domains, documents, source code, package names, tenants,
measurements, and companies only.
