# Phase 3: ARWC corporate and maintenance

[Campaign map](../logical-architecture.md) · [Previous: KeplerOps](keplerops.md) ·
[Continue: industrial DMZ and OT](arwc-ot.md)

Eight systems occupy corporate IT and maintenance subnets. The FieldLink
connector is the common arrival point from both supplier routes. Once the
customer action establishes execution there, corporate applications and
maintenance interfaces become reachable. Their protected functions still
require the identities and evidence in their challenge briefs.

```mermaid
flowchart LR
  package(["SUP-PKG<br/>From KeplerOps packages"])
  diagnostic(["SUP-DIAG<br/>From KeplerOps support"])
  subgraph a_corporate["CORPORATE IT — 5 systems"]
    a_connector["FieldLink customer connector<br/>a-connector"]
    a_business["Business applications<br/>a-business"]
    a_data["Business data and planning<br/>a-data"]
    a_archive["Corporate archive<br/>a-archive"]
    a_identity["Staff identity and browser workflow<br/>a-identity"]
    a_connector --> a_business
    a_connector --> a_data
    a_connector --> a_archive
    a_connector --> a_identity
  end
  maintenance_access(["Maintenance service conduits"])
  subgraph a_maintenance["MAINTENANCE / CONTRACTORS — 3 systems"]
    a_contractors["Contractor portal and field exports<br/>a-contractors"]
    a_approval["Drawing and approval workflow<br/>a-approval"]
    a_renderer["Maintenance renderer<br/>a-renderer"]
  end
  subgraph next_drawing["CONTINUE ON OT DRAWING / connection points"]
    integration(["READ-I<br/>Integration gateway"])
    contractor(["READ-C<br/>Contractor gateway"])
    command(["CMD<br/>Maintenance broker"])
  end
  package -->|Accepted package delivery| a_connector
  diagnostic -->|Accepted diagnostic delivery| a_connector
  a_connector --> maintenance_access
  maintenance_access --> a_contractors
  maintenance_access --> a_approval
  maintenance_access --> a_renderer
  a_connector -->|Integration service interface| integration
  a_connector -->|Contractor service interface| contractor
  a_connector -->|Scoped client issuance| command
  a_connector ==>|Earned live command authority| command
  classDef port fill:#e0e7ff,stroke:#4338ca,color:#172554;
  classDef conduit fill:#f8fafc,stroke:#64748b,color:#334155;
  classDef foothold fill:#dcfce7,stroke:#15803d,color:#14532d;
  class package,diagnostic,integration,contractor,command port;
  class maintenance_access conduit;
  class a_connector foothold;
  style next_drawing fill:#ffffff,stroke:#4338ca,stroke-dasharray:5 5;
```

The dashed continuation frame groups drawing connection points, not a third
subnet. READ-I, READ-C, and CMD terminate on three different DMZ systems in the
next drawing. The ordinary service line into CMD is the limited issuance interface;
the heavy line represents command use after CONTROL is earned. This distinction
avoids requiring control authority to reach the interface that establishes it.

## Systems and their purpose

| Subnet | System ID | In-world role | Operations touching this system |
| --- | --- | --- | --- |
| Corporate IT | `a-connector` | ARWC's FieldLink consumer and customer-side ticket context; supplied-delivery landing point. | K26, K27, W01 |
| Corporate IT | `a-business` | Work orders, asset/district associations, report retrieval, and procurement. | W02, W03, W10, W35 |
| Corporate IT | `a-data` | Allocation records, planning queries, retained meter exports, and the business planning consumer. | W07, W09, W11, W29, W33, W34 |
| Corporate IT | `a-archive` | Archive processing and retained contractor, device, and calibration artifacts. | W04, W08, W12, W16 |
| Corporate IT | `a-identity` | Temporary staff onboarding and the planner's identity/browser workflow. | W05, W06 |
| Maintenance / contractors | `a-contractors` | Contractor sessions, maintenance windows, and retained field bags. | W13, W14 |
| Maintenance / contractors | `a-approval` | Drawing versions, cached review context, and maintenance approvals. | W15 |
| Maintenance / contractors | `a-renderer` | Maintenance document rendering and its scoped action relationship. | W26 |

## How the business network leads into OT

The work-order annex and allocation records explain the integration route.
The contractor session and field bag explain the other read route. Either can
reach the published OT surfaces without completing the other. Maintenance
approvals concern authority to act, not ordinary plant visibility.

Corporate retained meter exports are distinct from current process observations.
The former support early W09 work; the latter come through the OT read gateways.
Similarly, W08, W12, and W16 begin with artifacts in `a-archive`, even where the
original material came from engineering or a field device. An artifact's
historical origin does not place its retained copy behind today's OT boundary.

The renderer can establish command authority only through its completed
identity/approval/action chain. The other control route begins at the OT
engineering utility. Neither means that the maintenance subnet can directly
route commands to a controller.

The business-planning consumer belongs on `a-data`. Later reporting manipulation
can change what this consumer believes while the independent process evidence
continues to describe the actual result. Procurement on `a-business` also gives
corporate-only operators a complete financial objective before reaching OT.
