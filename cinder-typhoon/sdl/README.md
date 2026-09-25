# Cinder Typhoon SDL

[cinder-typhoon.sdl.yaml](cinder-typhoon.sdl.yaml) is the sole scenario entry
point. It uses native local module imports, explicit exports, and namespaces
from **OpenRAE/rae 5.0.0**. All documents select
`raes-progressive-semantics/v1`. The 103 modules describe one individual
participant's world; participant replication belongs to the eventual backend.

**Design correction remains open.** Passing upstream validation does not make
this a complete or materialization-ready design. The route modules and challenge
surface relationships still contain scenario-specific `properties` interpreted
by `tests/validate_sdl.py` (`cinder_kind`, interaction modes, and workflow guards).
RAE validates their carrier and endpoints, not that private interpretation.
Those contracts still need replacement with the appropriate native declarations;
renaming the properties or hiding their meaning in another local decoder is not
a fix. No missing upstream semantic has been established by this review.

Training now uses native objective targets and plain supplied `connects_to`
relationships, with workstation access from `interactive_access`. Its 16 private
surface bindings, four property-based guards, and duplicate player context have
been removed. The remaining 377 private relationships belong to the unfinished
campaign design. Test projection into the old topology model does not give
native connections additional ACL, identity, or forwarding semantics.
See the [Training hand-build gate](../docs/design/training-readiness.md);
Training is ready for a hand build, but no build or materialization has started.

The K09 request reference and operations note now specify discovery of usable
worker access and an independently audited status read. The approved handoff
uses ordinary commands and native clients in a restricted job, allowing explicit
use of independently earned identities. Host/CI administration and general
network transit remain excluded. Full downstream certificate/delegation designs
and live acceptance tests are still required. No realization work is authorized
by this draft or by its validation results.

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
All four Training service nodes additionally require Linux for their explicit
POSIX ownership. Their internal subnet addresses and service names are exact;
resource sizes, physical carriers, application implementation language, and
hosting remain open.

| Modules | Contents |
| --- | --- |
| [world/participant.yaml](modules/world/participant.yaml) | Cinder operator, Kali, supplied training access and separate KeplerOps developer foothold. |
| `world/training.yaml`, `world/k-*.yaml`, `world/a-*.yaml` | Nine logical network groups, 36 target systems, and 83 scoped service/principal features. |
| `operations/t01.yaml` through `t04.yaml` | Training objectives and evidence. |
| `content/training-*.yaml` | Seven modular content documents carrying 47 exact Training files, with separate namespaces and explicit exports; no private include mechanism. |
| `operations/k01.yaml` through `k31.yaml` | KeplerOps objectives and evidence. |
| `operations/w01.yaml` through `w35.yaml` | ARWC objectives and evidence. |
| [world/capabilities.yaml](modules/world/capabilities.yaml) | 33 named access/evidence outputs, acquired through assertion-gated events. These are automatic derivations, not additional player tasks. |
| `routes/flows-*.yaml` | Business and access conduits, grouped by source network. |
| [routes/contexts.yaml](modules/routes/contexts.yaml), [routes/relays.yaml](modules/routes/relays.yaml) | Earned execution/delegation contexts and explicitly scoped forwarding. |
| [world/consequences.yaml](modules/world/consequences.yaml) | Six discrete, per-participant consequence events. |
| [world/records.yaml](modules/world/records.yaml) | Synthetic people and service identities, current/historical customer records, and Cairn Reach record identities. |
| `world/narrative-keplerops.yaml`, `world/narrative-arwc.yaml` | Eight service-owned workplace collections backed by shipped mail, document/calendar, directory, and employment assets. |

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
consumer receipt; K09.4 joins the runner audit with the receiving build-record
service's audit even though its player-facing invocation uses the CI service.
Its request reference and protected operations note are native file content on
the CI node, with exact text retained from the authored Build Operations assets.
The note describes existing service access, not a score-triggered permission
grant. Proof collection does not grant player access
to its producer. The design-side ownership exceptions and consequence contracts
are recorded in [sdl_contracts.py](../docs/design/sdl_contracts.py).

For each technical draft, the action contract carries mechanism intent in
`procedure_basis` and normal behavior in a target precondition. Training's
realization precondition describes in-world boundaries only; flag scoring and
organizer-initiated recovery are external and cause no world transition.
Native assertions describe observed world outcomes, not flag acceptance.
The 34 campaign technical drafts retain older scope/reset prose pending their
separate correction. The other 190 cards remain at brief level. None of these
declarations is evidence that the selected mechanism has been built or tested.

The current route model places the following private vocabulary in the generic
`relationships.properties` carrier. This is a record of remaining design debt,
not an approved extension or evidence that RAE lacks the required native forms:

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

RAE validates relationship endpoints and the properties carrier. Only the local
campaign checker supplies this vocabulary's references and routing meaning.
An adapter must not implement that private interpretation as a substitute for
native SDL. Replace it with native declarations before materialization; retain
the independent design-side route tests as expectations, not language semantics.

Capability and consequence events use native assertion preconditions and injects.
Capability propositions and injects concern the individual operator's derived
state. Their observation selectors bound the allowable provenance to the
challenge proof producers, recursively through capability joins. This producer
union is a collection scope, not a requirement to complete every alternative or
write state onto every producer. Acquisition events preserve the declared AND/OR
logic and introduce no additional player tasks.

The live reservoir transition is caused by the accepted in-world command, not
by challenge completion. W30.2 joins independent gate/volume observations from
`a-reservoir` and `a-instruments` with reserve-planning cost, restrictions, and
the continuity notice from `a-data`. Only then may the completion event retain
and present the incident. It must not create its own prerequisite evidence or
apply the release again. Rehearsals have separate state from the live reservoir
ending. There are no timed scripts or continuous hydraulic simulation. Trigger
transport and flag/scoring integration remain open.

Most campaign challenge content entries still specify required records without
asset bytes, separate from the implemented workplace assets. Training is the
exception: T01–T04 use 47 exact native file entries and no anonymous seed
datasets. Their operation contracts reference the exact modular content that
supports each normal surface.
For joined challenges, each system contributes its own records; the starting-material
description is not an instruction to copy the complete evidence set or secrets
onto every system. Detailed fixture ownership and visibility still follow the
[technical data contract](../docs/design/technical-data-contract.md).

The narrative modules reference eight digest-versioned source artifacts in
[assets/narrative/](../assets/narrative/README.md), using native dataset and
service-content materialization semantics. Each has an observed-state readback
assertion, evidence requirement, and audience boundary. Existing staff/business
nodes expose a named workplace service on logical TCP 443; this transport
declaration does not itself grant access or choose hosting or application software.
The eight readback checks add no challenge objectives or prerequisite gates.
The pack's artifact catalog maps source names and versions to exact shipped
bytes. The mailbox, document-library, directory, and employment payload formats
preserve their respective ownership and audience records; they are data formats,
not an alternative SDL execution language. Their eventual service importer must
preserve those records and satisfy the native readback contract.

Use [the validation instructions](../tests/README.md) for native parsing,
instantiation/compilation, and independent expectedness checks. The design
documents remain under [docs/design/](../docs/design/README.md).
