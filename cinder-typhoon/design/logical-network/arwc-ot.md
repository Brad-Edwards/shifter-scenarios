# Phase 3: ARWC industrial DMZ and OT

[Campaign map](../logical-architecture.md) ·
[Previous: corporate and maintenance](arwc-corporate.md)

Ten systems occupy three subnets. Two DMZ gateways independently expose a
defined set of engineering services and read-only process observations. A third
DMZ system, the maintenance broker, carries separately authorized commands to
two actuator endpoints.

```mermaid
flowchart LR
  integration(["READ-I<br/>From corporate integration context"])
  contractor(["READ-C<br/>From contractor session context"])
  command(["CMD<br/>Scoped client issuance / earned commands"])
  subgraph a_dmz["INDUSTRIAL DMZ — 3 systems"]
    a_data_bridge["Integration read gateway<br/>a-data-bridge"]
    a_contractor_bridge["Contractor read gateway<br/>a-contractor-bridge"]
    a_control_broker["Scoped maintenance broker<br/>a-control-broker"]
  end
  published(["Published OT surfaces<br/>Either read gateway independently"])
  subgraph a_engineering_zone["OT ENGINEERING / SUPERVISION — 4 systems"]
    a_hmi["HMI, practice and scheduler<br/>a-hmi"]
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
  command -->|Limited issuance interface| a_control_broker
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
  a_control_broker ==>|Scoped live commands| a_reservoir
  a_control_broker ==>|Scoped live commands| a_distribution
  classDef port fill:#e0e7ff,stroke:#4338ca,color:#172554;
  classDef conduit fill:#f8fafc,stroke:#64748b,color:#334155;
  classDef commandbox fill:#fff7ed,stroke:#c2410c,color:#7c2d12;
  classDef observer fill:#ecfeff,stroke:#0e7490,color:#164e63;
  class integration,contractor,command port;
  class published conduit;
  class a_control_broker,a_reservoir,a_distribution commandbox;
  class a_instruments observer;
```

The published-surfaces symbol is a fan-out of allowed service paths, not an
extra gateway. Either read gateway provides the complete required visibility;
the player need not chain them. Reads include request/response access, not
just a static screen. Engineering utilities and diagnostic applications can be
interacted with, but their privileged functions remain separate challenges.

## Systems and their purpose

| Subnet | System ID | In-world role | Operations touching this system |
| --- | --- | --- | --- |
| Industrial DMZ | `a-data-bridge` | Publishes the work-order/data integration view into OT. | W09 |
| Industrial DMZ | `a-contractor-bridge` | Publishes the contractor field-service view into OT. | W14 |
| Industrial DMZ | `a-control-broker` | Issues/accepts scoped maintenance clients and mediates live actuator commands. | W26, W28 |
| OT engineering / supervision | `a-hmi` | Operator view, operating envelope, mode, practice cases, and scheduling interface. | W17, W25, W29, W30, W33 |
| OT engineering / supervision | `a-historian` | Retained process observations and tag context. | W18, W33 |
| OT engineering / supervision | `a-engineering` | Engineering projects, deployed revision evidence, retained review context, diagnostics programs, and the small privileged utility. | W19, W21, W22, W27, W28, W32 |
| OT engineering / supervision | `a-diagnostics` | Estimation, diagnostic authorization, and native diagnostic services. | W23, W24, W27, W31 |
| Process control | `a-reservoir` | Reservoir/outlet state and accepted release actions. | W30, W33, W34 |
| Process control | `a-distribution` | Distribution state and the second actuator used in deeper scheduling work. | W33 |
| Process control | `a-instruments` | Independent observations, current device evidence, and retained device images. | W17, W18, W20, W21, W25, W29, W30, W33, W34 |

## The command boundary

The command broker recognizes a scoped client. W28's engineering utility and
W26's approved maintenance workflow are two ways to establish that client.
They authorize the same command scope, despite involving different systems
and difficulty. The diagram below is an **authority relationship**, not another
network route or an extra set of target systems.

```mermaid
flowchart LR
  utility["a-engineering<br/>Engineering utility"]
  renderer["a-renderer<br/>Approved maintenance action"]
  broker["a-control-broker<br/>Scoped client authority"]
  utility -.->|W28.3: Hard route| broker
  renderer -.->|W26.4: Expert route| broker
```

The main drawing shows use of that authority from the corporate access
position, through CMD. It does not grant arbitrary forwarding through the
engineering workstation or renderer. Issuance is available after the relevant
preceding step, before the client has CONTROL, as recorded in the
[connection register](../logical-architecture.md#connection-register).

The HMI's practice and scheduling interfaces remain reachable through the read
route. A proposed schedule or mode exercise is not a live actuator command.
Actual commands cross the broker boundary with earned authority. That keeps
process investigation available before the Hard/Expert control work.

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
