# Phase 1: Cinder Typhoon training

[Campaign map](../design/logical-architecture.md) · [Next: KeplerOps](keplerops.md)

Four independent practice systems occupy one training subnet. Participants can
use any of them and return later. Training does not supply a credential, pivot,
or mandatory flag for the live campaign.

```mermaid
flowchart LR
  operator([Cinder operator])
  subgraph training["TRAINING / 4 systems"]
    t_workbench["Workbench<br/>t-workbench"]
    t_accounts["Accounts<br/>t-accounts"]
    t_developer["Developer artifacts<br/>t-developer"]
    t_state["State exercise<br/>t-state"]
  end
  next(["START-K<br/>Separate supplied developer session<br/>Continue on KeplerOps drawing"])
  operator --> t_workbench
  operator --> t_accounts
  operator --> t_developer
  operator --> t_state
  operator -.->|Available independently of training| next
  classDef port fill:#e0e7ff,stroke:#4338ca,color:#172554;
  class operator,next port;
```

| System ID | In-world role | Operations touching this system |
| --- | --- | --- |
| `t-workbench` | Practice environment for initial tool use and evidence handling. | T01 |
| `t-accounts` | Practice accounts and authorization boundaries. | T02 |
| `t-developer` | Practice software artifacts and developer investigation. | T03 |
| `t-state` | Practice state and outcome interpretation. | T04 |

The operator node represents the participant's access position, not a fifth
training target. START-K joins the developer workstation on the next drawing;
there is no network edge from a training target into KeplerOps.
