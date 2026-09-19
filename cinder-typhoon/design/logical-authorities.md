# Cinder Typhoon: authority and operational flow register

[Logical architecture](logical-architecture.md) · [Executable model](model_topology.py)

This register resolves the scope of the 36 logical systems. It describes who
can act from each position, which interfaces they can use, and which adjacent
authorities remain separate. It selects no operating systems, isolation
technology, protocols, or deployment units. The challenge briefs and their
dependency ledger remain unchanged.

## What possession means

An **execution context** is a position under a particular service identity.
The operator can use that identity's local resources and outbound relationships.
It does not mean root access to every application assigned to the system.

A **delegated identity** authorizes named service operations from an existing
operator position or through the issuing service. Its location in the model
identifies the authority relationship; it does not imply a shell on the
identity provider, CI evaluator, or cloud control plane.

**Output control** changes a bounded item consumed by another service. It does
not grant that consumer's identity, arbitrary execution, or control of the
originating system's other applications.

An ordinary service interface can be contacted before its protected operation
has been earned. Reaching that interface never makes its implementation
identity available to the caller. A slash in a model endpoint, such as
`k-ci/runner`, names an authority domain within a system, not another box.

## Earned positions and their consequences

The context IDs below match the model. These are bounded consequences of the
existing achievements, not additional challenges or prerequisites. Interfaces
listed as reachable retain the object and action permissions in their briefs.

| Context | System / kind | Acquired through | Usable scope |
| --- | --- | --- | --- |
| `player` | Operator workspace | Supplied | Training access; no target-system identity. |
| `developer` | `k-dev` / execution | FOOTHOLD | Published supplier interfaces and delivery submission workflows. |
| `runner` | `k-ci` / job execution | K09.4 | Source/package reads, scoped staff/enrollment interfaces, authenticated build records, cloud policy, and maintenance management. |
| `indexer` | `k-indexer` / service execution | K04.4 | Its protected release-exception queue. |
| `preview` | `k-preview` / renderer execution | K12.4 | Its compatible preview output. |
| `completion` | `k-assistant` / completion-job execution | K24.3 | Its internal handover. |
| `support-staff` | `k-support` / delegated identity | B01 | Scoped staff workflow and certificate enrollment interfaces. |
| `support-federation` | `k-identity` / delegated identity | K18.3 | The support application's protected customer-record interface. |
| `staff-delegation` | `k-staff` / delegated identity | K19.3 | Supplier service delegation and the protected managed-identity record. |
| `release-client` | `k-ci` / delegated identity | K29.2 or K20.2 | Submission and results at private release rehearsals. No evaluator/reference-state ownership. |
| `workload-base` | `k-cloud-api` / delegated identity | K13.4 | Authenticated build records and the role/policy interface. |
| `cloud-role` | `k-cloud-api` / delegated identity | K14.2 | Maintenance management, scheduling policy, and support schedule configuration. |
| `export-delegation` | `k-data` / delegated identity | K15.3 | Support schedule configuration arising from the export workflow. |
| `backup-principal` | `k-data` / delegated identity | K30.1 | Backup recovery requests and returned records; no direct source-history access. |
| `support-task` | `k-workload` / scheduled execution | K16.3 | The scheduled task's support output. |
| `maintenance-runtime` | `k-workload` / runtime execution | K31.2 | The field archive under the runtime identity's independently evaluated policy. |
| `assistant-review` | `k-assistant` / scoped tool action | K22.3 | The duplicate-review item at support; no customer-delivery operation. |
| `customer` | `a-connector` / execution | CORPORATE | Corporate and maintenance interfaces; separately authorized DMZ services. |
| `archive-helper` | `a-archive` / helper execution | W04.3 | The helper's protected handover, supplying the existing W06 alternative. |
| `planner` | `a-connector` / delegated planner session | W06.3 | The protected query interface on `a-data`. |
| `query-worker` | `a-data` / job execution | W07.3 | Its reconciliation log and job output. |
| `maintenance-renderer` | `a-renderer` / service execution | W26.3 | Bound approval reads and the maintenance client-issuance interface. CONTROL still requires W26.4. |
| `engineering-utility` | `a-engineering` / constrained execution | W28.2 | The engineering client-issuance interface. Retaining the intended privilege and establishing CONTROL remain W28.3. |
| `diagnostic-vault` | `a-diagnostics` / service execution | W31.4 | Retained maintenance approval history. |
| `estimator-output` | `a-diagnostics` / output control | W23.3 | An accepted estimate carried through the DMZ publication role to corporate planning. |
| `program-output` | `a-diagnostics` / output control | W27.3 | The same bounded estimate feed, produced through the accepted diagnostic program. |

Other achievements can disclose records or perform protected actions without
creating another execution origin. In particular, diagnostic signing authority,
historical review identities, and retained device-image changes do not become
live control identities.

## Boundaries inside shared systems

| System | Required logical separation | Consequence for the campaign |
| --- | --- | --- |
| `k-ci` | Job identity; release submission/evaluation interface; private consumer/reference state. Build promotion remains a separately approved action. | Medium job execution supports later pivots but cannot read rehearsal answers or inherit publication approval. A release client gets test results, not the evaluator's identity. |
| `k-registry` | Publication and consumer-binding checks remain separate from inspection and entitlement actions. | A downstream inspection action is not a release publisher or a customer session. |
| `k-cloud-api` / `k-workload` | Limited workload identity; delegated management role; support-task identity; maintenance runtime identity. | Ability to modify a workload does not itself confer its runtime resource access. The support-persistence branch does not inherit the maintenance archive identity. |
| `k-data` | Published exports; backup recovery principal/interface; protected source history; runtime-protected field archive. | A backup caller can recover through the intended boundary while direct source reads stay denied. |
| `k-support` / `k-assistant` | Ordinary support session; customer-record federation; delivery workflow; duplicate-review tool; completion job. | Assistant influence can change its authored review item without granting customer delivery or broader support identity. |
| `a-archive` | Published retained copies; restricted helper; helper handover. | Helper execution does not own every historical device artifact, and retained copies create no current path to their source devices. |
| `a-data` | Ordinary allocation records; planner query interface; reconciliation job/log; estimate-consuming planning service. | W07 execution cannot overwrite W34's planning inputs or bypass the estimator/program branch. |
| `a-engineering` | Project/revision evidence; retained review context; narrow privileged utility. | The utility's privilege is scoped to client issuance. It is not general host ownership, current archive-review authority, or instrument-write authority. |
| `a-diagnostics` | Estimator output; accepted-program output; native vault/history; signed calibration export. | W31 cannot inherit W24's signing/export scope, W23/W27's estimate scope, or CONTROL. |
| `a-data-bridge` | Inbound integration access and outbound estimate publication use separate authority domains and directions. | A controlled estimate is data for the planner, never a route through the integration service or an instrument update. |
| `a-control-broker` | Maintenance issuer; engineering issuer; accepted-command relay. | Contacting an issuer precedes CONTROL. A successfully issued client permits only the common live command scope. |
| `a-hmi` | Observation/practice/schedule interfaces; live supervisory dispatcher. | A practice request or prepared schedule cannot inherit live dispatch authority. The broker supplies only an authorized request to the dispatcher. |
| `a-instruments` | Independent measurement publication and read-only investigation/retained images. | No earned execution, reporting, or command context can publish replacement observations. |

These are explicit logical requirements for the retained grouping. If a later
technical design gives a challenge unrestricted host ownership across one of
these boundaries, the affected roles must be separated into different logical
systems or the authority design revisited before that design is accepted.

## Operational relationships that matter to attacks

| Relationship | Normal business use | What crossing it does not imply |
| --- | --- | --- |
| Source → CI job → approved registry publication → private consumer or customer | Build, assess, promote, and consume FieldLink releases. | A job identity cannot promote its own candidate, read private consumer state, or turn private rehearsal into active customer execution. |
| Runner / limited workload identity → cloud build records and policy | Investigate authenticated job context; obtain the distinct backup or delegated principal through the authored work. | A metadata interface is not a grant of every identity it describes. |
| Management interface → maintenance runtime → protected field archive | Start an ordinary workload whose runtime identity is evaluated separately. | Reaching management does not forward the caller as the runtime identity. |
| Recovery principal → backup interface → source history | The backup service reads its protected source and returns an authorized recovery result. | The recovery caller cannot follow the service's source-read relationship under that service's identity. |
| Package/support delivery ↔ customer connector | The accepted job's existing invocation/result relationship keeps the earned customer execution usable. | No new supplied foothold, domain trust, general VPN, or supplier-to-OT route appears. |
| Planner session → query interface → reconciliation job | Run protected planner queries and the authored database job. | Query execution cannot update the separate estimate consumer. |
| Renderer → approval read → maintenance issuer; utility → engineering issuer | Establish a scoped live client through either earned execution position. | Execution at the first position alone does not establish CONTROL. |
| Connector client → broker → supervisory dispatcher → two actuators | Execute an authorized, bounded live request. | The caller acquires neither the relay identities nor a controller shell. |
| Process outcomes → instruments → historian → HMI | Supply independent measurements and operator history for each triggered stage. | Reading a downstream view cannot publish upstream measurements. |
| Approved engineering project → HMI | Supply ordinary project and tag configuration. | Utility execution does not own the engineering configuration-publishing identity. |
| Accepted diagnostic estimate → DMZ publication → planning consumer | Refresh the estimate used for allocation decisions; business applications read the resulting decision. | Neither the estimate producer nor the query worker owns raw measurements or the other planning identities. |

The ordinary-flow arrows in the detailed drawings are relationships that exist
in the fictional organizations. They do not require a continuous background
simulation. The implemented experience can populate their records and effects
through the agreed challenge-triggered stages.

## Executable checks and remaining limits

The model represents 83 authority domains in 36 systems and 26 contexts,
including the operator workspace and starting positions. Domains are logical
interfaces and identities, not 83 hosts or 83 additional challenges.

The validator checks the original 1,209 prerequisite closures and 16 main-route
combinations. It also checks each scoped context against an independent
destination-and-operation contract, and tests accumulated optional compromises
before the supplier, OT-read, and command boundaries. Useful pivots have
positive witnesses. Report output and live commands must traverse their named
publication or supervisory route.

The 26 negative cases include both bypasses that escaped the previous model:
CI execution with a direct ARWC route, and diagnostic execution with a direct
reservoir-command route. Other cases attempt to cross sibling authority
boundaries, inherit runtime authority from management, obtain execution too
early, or remove a required operational connection.

These checks validate a declared logical architecture. They do not discover
unmodelled credentials or exploits, prove host isolation, or assess deployment
capacity. Those limits remain explicit; the graph now includes the authority
relationships that the next technical design must preserve.
