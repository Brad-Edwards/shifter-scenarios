# Cinder Typhoon SDL

[cinder-typhoon.sdl.yaml](cinder-typhoon.sdl.yaml) is the sole scenario entry
point. It uses native local module imports, explicit exports, and namespaces
from **OpenRAE/rae 5.0.0**. All documents select
`raes-progressive-semantics/v1`. The 96 modules describe one individual
participant's world; participant replication belongs to the eventual backend.

Every document declares the native author realization posture:

```yaml
realization:
  default: open
```

This designation delegates unspecified realization choices. It is distinct
from behavior extension policy and from network access policy. Explicit
authored requirements retain their force. In particular, the attacker
workstation declares `type: compute`, `os: linux`, and
`os_distribution: x-kali:kali`. Its OS remains exact after compilation while
its compute substrate, architecture, and unspecified version remain open.
Target OS choices, resource sizes, addresses, physical carriers, runtime
packages, and hosting are not selected here.

| Modules | Contents |
| --- | --- |
| [world/participant.yaml](modules/world/participant.yaml) | Cinder operator, Kali, supplied training access and separate KeplerOps developer foothold. |
| `world/training.yaml`, `world/k-*.yaml`, `world/a-*.yaml` | Nine logical network groups, 36 target systems, and 83 scoped service/principal features. |
| `operations/t01.yaml` through `t04.yaml` | Training objectives and evidence. |
| `operations/k01.yaml` through `k31.yaml` | KeplerOps objectives and evidence. |
| `operations/w01.yaml` through `w35.yaml` | ARWC objectives and evidence. |
| [world/capabilities.yaml](modules/world/capabilities.yaml) | 33 named access/evidence outputs, acquired through assertion-gated events. These are automatic derivations, not additional player tasks. |
| `routes/flows-*.yaml` | Business and access conduits, grouped by source network. |
| [routes/contexts.yaml](modules/routes/contexts.yaml), [routes/relays.yaml](modules/routes/relays.yaml) | Earned execution/delegation contexts and explicitly scoped forwarding. |
| [world/consequences.yaml](modules/world/consequences.yaml) | Six discrete, per-participant consequence events. |
| [world/records.yaml](modules/world/records.yaml) | Synthetic people and service identities, current/historical customer records, and Cairn Reach record identities. |
| `world/narrative-keplerops.yaml`, `world/narrative-arwc.yaml` | Four service-owned workplace collections backed by shipped mail, document, directory, and calendar assets. |

Each operation module contains its challenge descriptions and intended
outcomes, native objectives/action contracts, typed propositions and
assertions, evidence requirements, eligibility workflows, target surfaces,
and starting-record declarations. `K01.1` becomes objective `k01.c1` after
composition. The complete card identifier is retained in the proposition's
semantic URI, for example `urn:cinder-typhoon:fact:K01.1`.

Workflow switch cases preserve dependency logic: every assertion in one case
is required; separate cases are alternatives. Each challenge has an independent
workflow. Objective execution mode delegates execution to the eventual backend;
the 50 existing technical drafts still require their selected mechanisms. An unavailable
attempt may be revisited after new evidence or authority is acquired. These
workflows do not require a single campaign-wide execution order.

Completion propositions mean the described in-world outcome has been verified;
they are not true merely because a task was attempted. Their observation demands
select the named result artifacts, with both `source_refs` and explicit
`selector.component_refs` bound to the relevant authority features. The common
`/features` collection scope avoids overlapping policy partitions; the component
selectors supply the exact owner restriction, including joined evidence.
The validator checks the normalized runtime bindings after compilation. Using
the native explicit observation-demand carrier also avoids
RAE 5.0.0's legacy scope conversion splitting composed identifiers at dots.
Concrete evidence production/evaluation belongs to the eventual adapter.

Action targets, proof owners, and starting records have separate meanings.
K01.1 starts with credential-helper material on `k-dev`, performs an authenticated
read at `k-source`, and requires the Forge audit and current handover revision
as proof. K01.2 similarly joins local browser recovery with the support gateway's
conversation restoration. K06.3 joins registry publication with the isolated
consumer receipt; K09.4 requires the runner audit even though its player-facing
invocation uses the CI service. Proof collection does not grant player access
to its producer. The design-side ownership exceptions and consequence contracts
are recorded in [sdl_contracts.py](../docs/design/sdl_contracts.py).

For each of the 50 technical drafts, the action contract carries the selected
mechanism in `procedure_basis`, normal behavior in a target precondition, and
scope/reset requirements in a realization precondition. A separate evidence
effect and evidence requirement carry the precise technical proof. Evidence
notes retain the authored acceptance checks. Reset requirements apply when a
reset is requested; completion does not automatically revoke earned authority.
The other 190 cards retain their brief-level intent without invented solutions.

The route model uses RAE's supported `relationships.properties` extension
surface for interaction distinctions that generic `connects_to` cannot express:

| `cinder_kind` | Relationship | Additional properties and meaning |
| --- | --- | --- |
| `flow` | `connects_to` | `flow_kind` is `access` or `operation`; `modes` lists permitted logical interactions; `guard` references a native eligibility workflow. |
| `context` | `authenticates_with` | `context_kind` identifies execution, delegation, or scoped output authority; `modes` bounds it; `guard` states acquisition. |
| `relay` | `manages` | `modes` bounds forwarding by the source feature along its declared outgoing conduits. The target is its owning system. |
| `challenge_surface` | `depends_on` | `objective` references the requiring objective; `mode` identifies the required interaction with the target feature. |

Modes are `service`, `artifact`, `read`, `delivery`, `control`, `report`, and
`telemetry`. They are logical interactions, not ports or ACL syntax. A reachable
feature does not confer its identity or forwarding. Only declared relays forward
their listed modes. Membership in a logical subnet does not grant every
application authority on that subnet.

RAE validates relationship endpoints and the properties carrier. The campaign
checker additionally validates this small property vocabulary, its references,
and its routing meaning. These extensions are not built-in RAE routing enforcement;
the eventual adapter must honor the checked contracts when realizing the world.

Capability and consequence events use native assertion preconditions and injects.
Capability propositions and injects concern the individual operator's derived
state. Their observation selectors bound the allowable provenance to the
challenge proof producers, recursively through capability joins. This producer
union is a collection scope, not a requirement to complete every alternative or
write state onto every producer. Acquisition events preserve the declared AND/OR
logic and introduce no additional player tasks.

The consequence injects describe persisted, idempotent stage changes, ordinary
business records, and independent process observations. Rehearsals have separate
state from the live reservoir ending. There are no timed scripts or continuous
hydraulic simulation. Trigger transport and flag/scoring integration remain open.

Challenge content entries specify required records and their owning logical systems.
They remain seed requirements, separate from the implemented workplace assets.
For joined challenges, each system contributes its own records; the starting-material
description is not an instruction to copy the complete evidence set or secrets
onto every system. Detailed fixture ownership and visibility still follow the
[technical data contract](../docs/design/technical-data-contract.md).

The narrative modules reference four digest-versioned source artifacts in
[assets/narrative/](../assets/narrative/README.md), using native dataset and
service-content materialization semantics. Each has an observed-state readback
assertion, evidence requirement, and audience boundary. Existing staff/business
nodes expose a named workplace service on logical TCP 443; this transport
declaration does not itself grant access or choose hosting or application software.
The four readback checks add no challenge objectives or prerequisite gates.
The pack's artifact catalog maps source names and versions to exact shipped
bytes. Its two payload formats preserve mailbox ownership and document readers;
the eventual adapter must implement them and satisfy the native readback contract.

Use [the validation instructions](../tests/README.md) for native parsing,
instantiation/compilation, and independent expectedness checks. The design
documents remain under [docs/design/](../docs/design/README.md).
