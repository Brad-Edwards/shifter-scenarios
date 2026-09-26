# Cinder Typhoon SDL

[cinder-typhoon.sdl.yaml](cinder-typhoon.sdl.yaml) is the sole scenario entry
point. It uses native local module imports, explicit exports, and namespaces
from **OpenRAE/rae 5.0.0**. All documents select
`raes-progressive-semantics/v1`. The 127 imported modules describe one individual
participant's world; participant replication belongs to the eventual backend.

Training, KeplerOps, and ARWC have completed their design-only hand-build gates.
All three use native RAE runtime, route, identity, authorization, content,
workflow, action, and evidence declarations. The composed scenario contains no
meaning-bearing project-private relationship properties. No missing upstream
semantic has been established.

Training now uses native objective targets and plain supplied `connects_to`
relationships, with workstation access from `interactive_access`. Its 16 private
surface bindings, four property-based guards, and duplicate player context have
been removed.
See the [Training hand-build gate](../docs/design/training-readiness.md);
Training is ready for a hand build, but no build or materialization has started.

KeplerOps now has exact native endpoints, identities, grants, routes, storage,
104 deterministic card contracts, exact surface bindings, denial and evidence
contracts, and exploit-critical build/configuration profiles. The K09 request
reference and operations note specify discovery of usable
worker access and an independently audited status read. The approved handoff
uses ordinary commands and native clients in a restricted job, allowing explicit
use of independently earned identities. Host/CI administration and general
network transit remain excluded. The downstream certificate/delegation, cloud,
assistant, signing, supplier and customer-boundary designs are present as static
contracts. Live acceptance, integration and playtesting remain for the later
hand build. No realization work is authorized by this draft or its validation.

ARWC now has exact native endpoints, identities, grants, application routes,
storage, 120 deterministic service contracts, exploit-critical formats and
mechanisms, and a dimensionally checked bounded process model. Practice, live,
scheduler-rehearsal, and reporting-rehearsal state are distinct. The SDL is
ready for a hand build; no service, binary, image, simulator, or range has been
built.

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
| `content/keplerops-*.yaml` | Fifteen service-owned modules carrying 104 deterministic KeplerOps contracts and exact native surface bindings. |
| `operations/w01.yaml` through `w35.yaml` | ARWC objectives and evidence. |
| `content/arwc-*.yaml` | Seventeen service-owned modules carrying 120 deterministic ARWC contracts and exact native surface bindings. |
| [world/capabilities.yaml](modules/world/capabilities.yaml) | 33 named access/evidence outputs, acquired through assertion-gated events. These are automatic derivations, not additional player tasks. |
| `routes/keplerops-integrations.yaml` | Thirteen ordinary native KeplerOps business integrations with no project-private relationship vocabulary. |
| `routes/arwc-integrations.yaml` | Twenty-one ordinary native ARWC business and process integrations with no project-private relationship vocabulary. |
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
workflow. Objective execution mode delegates execution to the eventual backend.
All 104 KeplerOps cards, all 16 Training cards, and all 120 ARWC cards have full
five-part technical designs. An unavailable attempt may be
revisited after new evidence or authority is acquired. These workflows do not
require a single campaign-wide execution order.

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
to its producer. Exact ownership and consequence contracts are recorded in the
phase readiness, artifact-ownership, and ARWC process-model ledgers under
[docs/design/](../docs/design/README.md).

For each technical draft, the action contract carries mechanism intent in
`procedure_basis` and normal behavior in a target precondition. Training's
realization precondition describes in-world boundaries only; flag scoring and
organizer-initiated recovery are external and cause no world transition.
Native assertions describe observed world outcomes, not flag acceptance.
KeplerOps contracts describe persistence across ordinary retries and contain no
in-world reset service. Organizer recovery and submission adjudication remain
external. None of these declarations is evidence that the selected mechanism
has been built or tested.

ARWC connectivity is represented by ordinary `connects_to` relationships only
where the business integration itself is useful to describe. Network endpoints,
listeners, routes, identities, grants, databases, files, action applicability,
and evidence stay on their native owning structures. No relationship property
needs a project decoder. The exact mapping is recorded in
[arwc-native-semantics.md](../docs/design/arwc-native-semantics.md).

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

ARWC uses 120 deterministic service contracts, one per card, with exact owners,
paths, native surface bindings, initial records, denial behavior, state
transitions, persistent evidence, generation digests, and exploit-critical
mechanics. Its quantities and isolated state domains follow
[arwc-process-model.md](../docs/design/arwc-process-model.md). Training uses 47
exact native file entries and no anonymous seed datasets. KeplerOps uses 104 deterministic service contracts, one per card,
with exact owners, paths, native surface bindings, request/denial/state/evidence
rules, canonical generation digests, and detailed profiles where a mechanic
depends on binary layout, cryptography, parsing, identity, browser, model,
signing or workload behavior. Its operation contracts reference those modular
files from each normal-surface precondition.
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
