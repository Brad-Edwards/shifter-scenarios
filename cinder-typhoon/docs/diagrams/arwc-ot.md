# Phase 3: ARWC industrial DMZ and OT

[Campaign map](../design/logical-architecture.md) ·
[Previous: corporate and maintenance](arwc-corporate.md)

Ten systems occupy three subnets. Two DMZ gateways independently expose a
defined set of engineering services and read-only process observations. A third
DMZ system, the maintenance broker, sends authorized requests to the HMI's
supervisory dispatcher, which commands the two actuator endpoints.

```mermaid
flowchart LR
  integration(["READ-I<br/>From corporate integration context"])
  contractor(["READ-C<br/>From contractor session context"])
  command(["CMD<br/>Earned command client"])
  issuance(["ISSUE-M<br/>From earned maintenance renderer"])
  estimates(["ESTIMATE<br/>To corporate planning consumer"])
  subgraph a_dmz["INDUSTRIAL DMZ — 3 systems"]
    a_data_bridge["Integration access / estimate publication<br/>a-data-bridge / separate scopes"]
    a_contractor_bridge["Contractor read gateway<br/>a-contractor-bridge"]
    a_control_broker["Scoped maintenance broker<br/>a-control-broker"]
  end
  published(["Published OT surfaces<br/>Either read gateway independently"])
  subgraph a_engineering_zone["OT ENGINEERING / SUPERVISION — 4 systems"]
    a_hmi["HMI, practice and live dispatcher<br/>a-hmi / separate authorities"]
    a_historian["Historian and tag records<br/>a-historian"]
    a_engineering["Engineering workstation and projects<br/>a-engineering"]
    a_diagnostics["Diagnostic services<br/>a-diagnostics"]
  end
  subgraph a_control["PROCESS CONTROL — 3 systems"]
    a_reservoir["Reservoir and outlet endpoint<br/>a-reservoir"]
    a_distribution["Distribution endpoint<br/>a-distribution"]
    a_instruments["Independent instrumentation<br/>a-instruments"]
  end
  integration --> a_data_bridge
  contractor --> a_contractor_bridge
  issuance -->|Approval-bound issuer| a_control_broker
  command ==>|CONTROL| a_control_broker
  a_data_bridge --> published
  a_contractor_bridge --> published
  published -->|Observations and practice interfaces| a_hmi
  published -->|History and tag records| a_historian
  published -->|Projects and named utility interfaces| a_engineering
  published -->|Diagnostic interfaces| a_diagnostics
  published -->|Read only| a_reservoir
  published -->|Read only| a_distribution
  published -->|Read only and retained images| a_instruments
  a_engineering -->|Earned utility: engineering issuer| a_control_broker
  a_control_broker ==>|Authorized request to live dispatcher| a_hmi
  a_hmi ==>|Scoped live commands| a_reservoir
  a_hmi ==>|Scoped live commands| a_distribution
  a_diagnostics -->|Accepted estimate output| a_data_bridge
  a_data_bridge -->|Publication role only| estimates
  classDef port fill:#e0e7ff,stroke:#4338ca,color:#172554;
  classDef conduit fill:#f8fafc,stroke:#64748b,color:#334155;
  classDef commandbox fill:#fff7ed,stroke:#c2410c,color:#7c2d12;
  classDef observer fill:#ecfeff,stroke:#0e7490,color:#164e63;
  class integration,contractor,command,issuance,estimates port;
  class published conduit;
  class a_control_broker,a_reservoir,a_distribution commandbox;
  class a_instruments observer;
```

The published-surfaces symbol is a fan-out of allowed service paths, not an
extra gateway. Either read gateway provides the complete required visibility;
the player need not chain them. Reads include request/response access, not
just a static screen. Engineering utilities and diagnostic applications can be
interacted with, but their privileged functions remain separate challenges.
The utility's invocation interface and earned execution context are separate
authorities. The HMI's accessible practice/schedule interface likewise does
not expose its live dispatch authority. See the
[authority register](../design/logical-authorities.md).

### Ordinary process and planning flows

This view reuses the systems above and the corporate planning consumer. It
shows why the process views contain evidence and how diagnostic tampering can
affect business decisions. These are logical data relationships; observations
and outcomes are populated by triggered stages, without a continuous process
simulation.

```mermaid
flowchart LR
  reservoir["a-reservoir<br/>Outlet outcome"]
  distribution["a-distribution<br/>Distribution outcome"]
  instruments["a-instruments<br/>Independent observations"]
  historian["a-historian<br/>Retained measurements"]
  hmi["a-hmi<br/>Operator view"]
  engineering["a-engineering<br/>Approved project and tags"]
  diagnostics["a-diagnostics<br/>Estimator / accepted diagnostic program"]
  publication["a-data-bridge<br/>Estimate publication role"]
  planning(["ESTIMATE → a-data<br/>Corporate planning consumer"])
  business(["a-business<br/>Allocation workflow"])
  reservoir -->|Measured outcome| instruments
  distribution -->|Measured outcome| instruments
  instruments -->|Observation history| historian
  historian -->|Measurements and history| hmi
  engineering -->|Approved configuration| hmi
  diagnostics -->|Estimate feed| publication
  publication -->|Bounded planning refresh| planning
  business -->|Read planning decision| planning
```

An observation feed, an accepted estimate, and a live command remain different
channels. Reading the historian never gives the caller the instrument's
publishing identity. The two estimate-producing branches can influence the
planner through ESTIMATE; the native diagnostic vault can only recover its
retained approval history. None acquires the other's authority by sharing
`a-diagnostics`.

## Systems and their purpose

| Subnet | System ID | In-world role | Operations with scored work here |
| --- | --- | --- | --- |
| Industrial DMZ | `a-data-bridge` | Publishes the work-order/data integration view; a separate role carries estimates out to corporate planning. | W09 |
| Industrial DMZ | `a-contractor-bridge` | Publishes the contractor field-service view into OT. | W14 |
| Industrial DMZ | `a-control-broker` | Separate maintenance/engineering issuers; accepts scoped clients and sends authorized requests to the supervisory dispatcher. | W26, W28 |
| OT engineering / supervision | `a-hmi` | Operator view, operating envelope, mode, practice and scheduling; a separate live dispatcher commands actuators. | W17, W25, W29, W30, W33 |
| OT engineering / supervision | `a-historian` | Retained process observations and tag context. | W18, W33 |
| OT engineering / supervision | `a-engineering` | Engineering projects, deployed revision evidence, retained review context, diagnostics programs, and the small privileged utility. | W19, W21, W22, W27, W28, W32 |
| OT engineering / supervision | `a-diagnostics` | Estimation, diagnostic authorization, and native diagnostic services. | W23, W24, W27, W31 |
| Process control | `a-reservoir` | Reservoir/outlet state and accepted release actions. | W30, W33, W34 |
| Process control | `a-distribution` | Distribution state and the second actuator used in deeper scheduling work. | W33 |
| Process control | `a-instruments` | Independent observations, current device evidence, and retained device images. | W17, W18, W20, W21, W25, W29, W30, W33, W34 |

## The command boundary

The command broker recognizes a scoped client. W28's engineering utility and
W26's approved maintenance workflow reach different issuance interfaces from
their earned execution positions. They establish the same command scope,
despite involving different systems and difficulty. This view expands the
service paths and authority handoff; it adds no systems.

```mermaid
flowchart LR
  utility["a-engineering<br/>Engineering utility"]
  renderer["a-renderer<br/>Approved maintenance action"]
  broker["a-control-broker<br/>Two scoped issuers"]
  connector["a-connector<br/>Existing customer execution"]
  dispatch["a-hmi<br/>Live dispatcher"]
  utility -->|W28.2 context → W28.3 issuer work| broker
  renderer -->|W26.3 context → W26.4 issuer work| broker
  broker -.->|Earned client usable from connector| connector
  connector ==>|CMD with CONTROL| broker
  broker ==>|Authorized request| dispatch
```

Issuance is available before CONTROL, from the relevant compromised service.
The resulting client can be used from the existing customer position through
CMD. The broker delegates only the accepted request to the live dispatcher;
it does not convey its service identity or provide a controller shell. The
[connection register](../design/logical-architecture.md#connection-register) records
these separate transitions.

The HMI's practice and scheduling interfaces remain reachable through the read
route. A proposed schedule or mode exercise is not a live actuator command.
Actual commands cross the broker and supervisory boundaries with earned
authority. That keeps process investigation available before the Hard/Expert
control work.

`a-instruments` has no command edge. A changed planning estimate, historical
review identity, or diagnostic export authorization cannot rewrite its
independent observations or grant CONTROL. W31's optional diagnostic compromise
also supplies no assumed third control route in this draft.

## Where the story concludes

The reservoir endpoint records the accepted release and its bounded effect;
the independent instruments establish what happened. Corporate planning data
establish why the loss matters. The intended result remains replacement-supply
cost and water restrictions.

The state advances through triggered events. Merely acquiring a control client,
opening a dashboard, or preparing a schedule does not open the gates. Optional
scheduling and reporting rehearsals can show different cases without undoing
the main campaign's completed result.
