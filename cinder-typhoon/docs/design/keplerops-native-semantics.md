# KeplerOps native-semantic migration ledger

This ledger maps every class of project-private KeplerOps relationship meaning
to the pinned RAE 5.0.0 authoring surface. It is a migration contract, not a new
SDL dialect. The finished scenario must no longer need
`tests/validate_sdl.py` to interpret `cinder_kind`, `flow_kind`, `modes`, or
`guard`.

## Audit conclusion

No upstream expressivity gap is established by the current KeplerOps topology
model. RAE already represents the required facts through node runtime
inventories, native relationships, participant behavior contracts, content,
and evidence semantics. The private model collapses several different facts
into graph edges; migration separates those facts again.

This conclusion covers the current relationship classes. Each challenge
mechanic still receives a native-field audit while its exact service and asset
contract is authored. A newly discovered genuine gap remains a stop condition.

## Native RAE surfaces in use

| Required fact | Native authoring surface |
| --- | --- |
| Network presence and address | `infrastructure`, `runtime.network.endpoints`, `published_ports` |
| Listening process and transport | `Node.services`, `runtime.service_listeners`, process identity |
| HTTP/API/UI surface | `runtime.applications` with methods, paths, parameters, auth/session posture, responses, disclosures, fields, redirects, static assets, and typed upstreams |
| Local files and state | `content`, `filesystem_inventory`, mounts, environment files, persistent volumes, generated artifacts |
| Local users and processes | `runtime.local_identity`, `runtime.processes`, capability policy, service-manager units |
| Application permissions | `runtime.app_authorizations`: principals, roles, grants, role mappings, tenants |
| Directory and delegated identity | `runtime.identity_authorities`: services, subjects, policies, and identity relationships; top-level accounts and typed federation where applicable |
| Source/package state | software components, dependency manifests, package requirements, repository state, content, and application routes |
| File, mail, database, and datastore access | Native file-service, mail-service, database-service, datastore-service, and their typed access relationships |
| Isolated or spawned work | control interfaces, orchestration authorities, spawn templates, lifecycle policy, realized children, containers and namespaces |
| Recurring work | native scheduled jobs and service-manager state |
| Business service connectivity | An unadorned native `connects_to` relationship only where an edge itself is useful; typed proxy, database, mail, forwarding, federation, or service-integration detail when the actual relationship matches that model |
| Participant applicability and action | Workflows plus typed action-contract preconditions, arguments, effects, failures, interactions, and temporal contracts |
| Completion evidence | Evidence requirements with exact sources and observation demands, propositions, assertions, and objectives |

Generic relationship `properties` are not used to recreate a local type system.
Open RAE vocabularies such as `other` are used only where the native field owns
that vocabulary and the authored value remains an ordinary value, not a hook
for project code.

## Private class replacement

### Challenge surfaces: 111 relationships

The existing `challenge_surface` edge incorrectly combines participant access,
card placement, and interaction mode. Delete these relationships.

Their facts move to:

- actual node listeners and application/file/repository/database surfaces;
- account, identity, and application-authorization state;
- the operation's action-contract precondition `support_refs` and effect
  `target_refs`;
- evidence requirement `source_refs` and observation selector
  `component_refs`; and
- exact content ownership and filesystem placement.

No replacement relationship is needed solely to say that an objective is
allocated to a system.

### Flow access: 33 relationships

An `access` flow currently means some mixture of network reachability,
authentication, authorization, and an earned identity. These are independent
facts:

- reachability is the pre-existing network/listener/application surface;
- authentication is the account, identity authority, session, or application
  principal accepted by that surface;
- authorization is a native grant or service-specific access rule; and
- acquisition is the real in-world action and resulting credential, session,
  delegated principal, or execution endpoint described by the action contract.

Workflow assertions constrain participant action applicability; they do not
create or remove network connections.

The 33 edges fall into these owned groups:

| Group | Existing relationship IDs | Native replacement |
| --- | --- | --- |
| Developer-facing services | `developer-k-identity`, `developer-k-source`, `developer-k-registry`, `developer-k-ci`, `developer-k-preview`, `developer-k-support`, `developer-k-indexer`, `developer-k-cloud-api`, `developer-k-data`, `developer-k-assistant` | Corporate endpoint plus the ten real service listeners/routes and their anonymous or developer-session authorization posture. |
| Corporate delegation | `staff-service-delegation`, `managed-identity-record`, `support-federation-use` | Identity-authority subjects/relationships or application principals/grants, accepted authentication on the destination route, and the acquisition action/evidence contract. |
| Release rehearsal | `release-client` | A release-client principal and scoped grant on the private rehearsal application. |
| Runner and support clients | `k-ci--runner-k-staff`, `k-ci--runner-k-cert`, `k-support--staff-client-k-staff`, `k-support--staff-client-k-cert`, `k-ci--runner-k-cloud-api--authority`, `k-ci--runner-k-cloud-api--build-records`, `k-ci--runner-maintenance`, `k-ci--runner-policy` | Existing destination interfaces plus source job/service network reachability and explicit accepted principals. No identity is implicitly forwarded. |
| Indexer worker | `indexer-queue` | Queue content ownership, worker process identity, filesystem or application grant, and exact read action. |
| Customer delivery | `package-delivery`, `diagnostic-delivery` | Persistent supplier and connector listeners, exact submission/acceptance/result routes, scoped principals, and one native connectivity relationship per business channel if still useful. |
| Cloud delegated clients | `k-cloud-api--workload-client-k-cloud-api--authority`, `k-cloud-api--workload-client-k-cloud-api--build-records`, `k-cloud-api--delegated-client-maintenance`, `k-cloud-api--delegated-client-policy`, `k-cloud-api--delegated-client-schedule`, `k-data--export-client-schedule` | Identity subjects or application principals plus destination resource grants and exact routes. |
| Backup and completion | `backup-recovery`, `completion-handover` | Backup-principal authorization and recovery route; completion-worker-owned file/state and its authorized retrieval path. |

### Operational flows: 13 relationships

Operational flows are normal service behavior, not participant authority edges.
They remain present regardless of objective completion.

| Existing relationship | Native replacement |
| --- | --- |
| `source-build` | CI source-selection route/configuration, source repository identity, selected revision, and checkout behavior. |
| `build-job-dispatch` | CI submission route plus orchestration authority, spawn template, job identity, namespaces, lifecycle, and result route. |
| `runner-source` | Runner network access, repository read principal/grant, and checkout operation. |
| `runner-package-read` | Runner network access and registry dependency-read principal/grant. |
| `build-publication` | Separate publisher principal/grant and approved publication route; never inherited from job execution. |
| `release-rehearsal` | Registry candidate record and private consumer submission/evaluation routes. |
| `consumer-state` | Evaluator-owned filesystem/content state absent from the submitted job's grants and mounts. |
| `preview-result` | Renderer process/output ownership and the preview application's compatible-output route/state. |
| `scheduled-task-output` | Native scheduled job, task process identity, destination authorization, and output content/state. |
| `runtime-field-archive` | Maintenance runtime principal and field-archive resource grant evaluated independently of workload management. |
| `maintenance-job-dispatch` | Workload-management route plus orchestration authority/spawn template and distinct runtime identity. |
| `backup-source-read` | Backup-service identity and database/datastore/file access rule; the recovery caller lacks that source grant. |
| `assistant-review-action` | Assistant tool principal/grant, bounded support update route, action effect, and independent destination observation. |

### Earned contexts: 16 KeplerOps relationships

The private context graph makes an assertion act like a newly created origin.
The world instead contains a concrete position that the participant learns to
use through the expected in-world action.

| Context | Native state |
| --- | --- |
| `developer` | Supplied participant account/session on `k-dev`, local identity and reachable interfaces. |
| `runner` | CI job-submission application, isolated orchestration child, worker principal, workspace and lifecycle. |
| `indexer` | Indexer worker process/execution surface and its queue grant. |
| `preview` | Preview renderer worker and bounded output surface. |
| `completion` | Assistant completion worker, execution surface, and owned handover state. |
| `support-staff` | Support-issued or recovered principal accepted by staff and certificate interfaces. |
| `support-federation` | Federation relationship and destination customer-record grant. |
| `staff-delegation` | Staff-issued delegated principal and its scoped destination grants. |
| `release-client` | Private rehearsal application principal and result access. |
| `workload-base` | Limited cloud subject/principal with exact build-record and policy grants. |
| `cloud-role` | Separately assumed delegated role and its management/policy/schedule grants. |
| `export-delegation` | Export-workflow principal limited to support schedule configuration. |
| `backup-principal` | Backup recovery principal and route; no direct source-history access. |
| `support-task` | Native scheduled-job execution identity and output. |
| `maintenance-runtime` | Orchestrated workload's distinct runtime identity and archive grant. |
| `assistant-review` | Assistant tool principal and one bounded support-record update permission. |

The action contract states how each position is obtained and exercised. The
actual identity/session/job and accepted destination operation make it usable.
No completion assertion grants permission.

### Supplier relays: two relationships

Delete the private `relay` interpretation for `k-registry` and `k-support`.
The exact package and diagnostic channels are ordinary application-to-
application business connections with scoped submission, acceptance,
invocation, and result operations. They cannot forward arbitrary traffic
because no such listener, route, proxy, principal, or grant exists.

### Mode strings and guards

The seven local modes are decomposed rather than translated to a new enum:

| Private mode | Native facts |
| --- | --- |
| `service` | Listener/application/file/mail/database/datastore interface and accepted principal. |
| `artifact` / `read` | Content/filesystem/repository/data object plus read route or access rule. |
| `delivery` | Submission and receiver applications, content/package identity, accepted principal, normal service result. |
| `control` | Exact state-changing route or local control interface, authorization, action effect, and independently observed result. |
| `report` | Owned output/content plus consumer interface and observation source. |
| `telemetry` | Native forwarding/monitoring inventory only where telemetry is actually present; otherwise an evidence channel, not a network permission. |

`guard` disappears from relationships. Workflow prerequisites remain on the
participant action. Static connections and normal business integrations remain
in-world before the participant can authenticate or use them.

## Migration order

1. Define each destination surface and authorization before deleting its
   private access or context edge.
2. Define each operational producer/consumer contract before deleting its
   private operation edge.
3. Bind operation action/evidence refs to those native components.
4. Delete challenge-surface relationships after their placement assertions are
   covered by action, evidence, and asset checks.
5. Delete private contexts and relays after concrete acquisition and scoped-use
   tests pass.
6. Remove the decoder from `tests/validate_sdl.py` and make any returning
   meaning-bearing private property a validation failure.

This order permits incremental upstream validation while preventing a private
edge from being removed before its real service or identity contract exists.

## Migration result

The KeplerOps migration is complete. Its 111 challenge-surface edges, three
private flow modules, sixteen private contexts and two private relays have no
remaining SDL role. Thirteen durable business integrations are ordinary
unadorned `connects_to` relationships; all access, identity, authorization,
state, action and evidence meaning lives in the native structures listed above.

The accepted KeplerOps validation path does not call the private relationship
decoder and rejects any KeplerOps relationship carrying `cinder_kind`,
`flow_kind`, `context_kind`, `modes` or `guard`. ARWC was outside this migration
at the time of the KeplerOps pass; it has since completed its own native
migration and hand-build gate.
