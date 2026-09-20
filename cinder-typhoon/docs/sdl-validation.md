# SDL validation record

The Cinder Typhoon SDL is an authoring draft of the in-world scenario. Its
reference implementation is [OpenRAE/rae v5.0.0](https://github.com/OpenRAE/rae/tree/v5.0.0),
commit `9773b262771e0d79c9e083cb3e05b33f165201b7`. Environment-pack author validation
uses `raes-env-packs==6.1.0`, from
[OpenRAE/env-packs](https://github.com/OpenRAE/env-packs/tree/679356d762971600f22e6ff3228f4c2b48376eee),
which depends on `raes==5.0.0`.

Recorded on **2026-09-20**, using Python 3.12:

| Check | Result |
| --- | --- |
| env-packs author validation | Pass |
| Native RAE parsing, composition, and semantic validation | Pass |
| Native instantiation and whole-campaign compilation | Pass; 3,450 realization requirements emitted |
| Default-open provenance and selected compiled open/exact requirements | Pass |
| Explicit source bindings in all 281 compiled observation selectors | Pass |
| Eight workplace source artifacts and named service materialization bindings | Pass in composed and compiled SDL |
| Workplace asset rendering, chronology, bytes, and audiences | Pass; 110 outputs reproduce exactly |
| All 250 technical sections from 50 drafted cards | Preserved and checked against the cards |
| Separate action, evidence, and seed ownership; six consequence effects | Pass |
| Design correspondence and 1,209 minimal closures | Pass |
| All 16 finale route combinations | Pass |
| 28 SDL mutations and invalid posture spelling | Rejected as expected |
| Four workplace SDL mutations and five asset corruption cases | Rejected as expected |
| Two compiled observation-selector mutations | Rejected as expected |
| 26 negative topology/event cases | Rejected as expected |
| Existing design and challenge-document checks | Pass |

The 97 YAML files (entry point plus modules) have aggregate SHA-256
`f1f56b34acca66bfa5070dc228cfe5f553cabee926686c50cb2e4abd54039e8c`.
The digest processes paths in sorted order, appending each path relative to
`sdl/`, a NUL byte, its file bytes, and another NUL byte. This records the
validated draft; the executable checks remain authoritative after edits.

The root scenario composes 96 native modules. The inventory is:

| Surface | Count |
| --- | ---: |
| Logical target systems | 36 |
| Kali attacker workstation | 1 |
| Logical subnet/switch declarations | 9 |
| Scoped authority features | 83 |
| Challenge objectives and action contracts | 240 each |
| Named capability outputs/joins | 33 |
| Supplied starting facts | 2 |
| Scoped contexts | 26 |
| Business/access conduits | 99 |
| Explicitly scoped relays | 7 |
| Challenge surface bindings | 266 |
| Required record datasets | 269 |
| Authored workplace source collections | 8 |
| Explicitly bound observation requirements | 281 (273 challenge/capability; 8 workplace readback) |
| Consequence events | 6 |

The 46 native node declarations are 37 logical compute nodes and nine logical
switches. These are in-world requirements, not a physical instance count.
The provided co-hacking assistance does not introduce another target identity
or bypass the human participant's earned access.

The native declaration is `realization: {default: open}` in the root and every
module. Validation checks its typed provenance through composition and
instantiation, then examines the compiled realization requirements:

| Example requirement | Required classification |
| --- | --- |
| `nodes.participant.kali.os` | Exact: `linux` |
| `nodes.participant.kali.os_distribution` | Exact: `x-kali:kali` |
| `nodes.participant.kali.realization.compute-substrate` | Open |
| `nodes.participant.kali.architecture` | Open |
| `nodes.participant.kali.os_version` | Open |
| `nodes.k-corporate.k-dev.os` | Open, governed by `k-corporate#/` |

This distinguishes backend latitude from weakening an explicit scenario
requirement. Resource sizing remains absent. No runtime backend is selected.

Expectedness is checked independently of grammar acceptance. The validator
reads the actual composed objectives, workflow switches, capability acquisition
events, node memberships, source/target relationships, contexts, relays, and
consequence predicates. It reconstructs the graph from those declarations,
then compares it with the preserved design ledger and topology model. It also
compares challenge descriptions and completion meanings with the cards.

After the adversarial review, the checks additionally compare every action's
precondition classes and references, effects and targets, completion quantifier,
and seed-record content and owner. The 50 existing technical drafts supply
250 source sections: normal behavior, selected mechanism, technical proof,
scope/reset boundaries, and author checks. These are preserved in native action
and evidence contracts. The 190 remaining briefs receive no invented solutions.

Proof ownership is independent of player access. K01.1's recovery material is
local, its protected handover is on the Forge, and its proof comes from the
Forge audit. K01.2's restored conversation is proved by the support gateway.
K06.3 joins registry publication with the isolated consumer's receipt, and
K09.4 requires the runner's execution audit. The existing routes support the
corrected interactions without extra challenge dependencies.

Every explicit observation selector now carries its actual producer references;
the checker inspects the normalized compiled addresses as well as authored
`source_refs`. Challenge and capability rules share the `/features` collection
scope; workplace readback rules share `/content`. Both use exact component
selectors, avoiding overlapping broad/narrow scope partitions.
Capability observations recursively select the allowable producer provenance;
their propositions concern one participant and their acquisition events retain
the original AND/OR formulas. Collection scope does not require completing all
alternative paths or writing to every producer. Native default-open posture
remains present in all 97 documents.

The [workplace collection](../assets/narrative/README.md) contains 3,075 unique
messages, 5,170 retained message copies, 244 authored documents, directories
for all 294 company employees, and 21 calendar invitations. Jules remains an
external correspondent outside both company rosters. The eight native content
declarations identify exact source names and digest-based
versions. The pack's artifact catalog resolves those pairs to checked-in files;
the validator checks their bytes independently of RAE's reference validation.
This catalog is a pack convention, not a new SDL field.

The directory packages enumerate same-employer staff groups; employment
packages carry exact item readers and individual-identity requirements. Native
content marks mail, documents, and employment data sensitive. RAE's content
declaration does not enforce item readers on its own, so the eventual workplace
adapter must apply the packaged reader sets. These checks verify the authored
reader requirements and source bytes, not live authorization behavior.

The native service materialization contracts bind mail, documents, staff
directories, and employment records to the existing KeplerOps staff and ARWC
business systems. Compilation preserves the source versions, node ownership,
and named workplace services. Eight observed
readback requirements select the corresponding `provision.content` addresses.
The logical TCP 443 service declarations add no node, access route, credential,
or challenge prerequisite. Backend and software choices remain open.

Asset checks compare RFC822 headers and bodies, reply relationships, MIME
attachment bytes and publication dates, mailbox membership, document readers,
staff contacts, business account and accepted-activity joins, and calendar dates,
status, and audiences. Six corruption cases alter an attachment, expose a
private message to an unrelated mailbox, change source bytes, detach a reply,
introduce a reporting loop, or change an accepted delivery amount; all are rejected.
Four native type-valid SDL
mutations change a content owner, source version, observed-state requirement,
or selected readback content; all are rejected as well.

Screened display names and personal login spellings are aligned in active SDL,
challenge cards, and their expected contracts. Stable actor, package, service,
and business identifiers remain intact. Company history and ordinary workplace
stories remain separate from required challenge records.

The reconstructed graph is subjected to the existing campaign contracts:
independent medium-or-easier ARWC entries; alternative OT read and mapping
routes; separate control acquisition; current revision, interpretation, mode,
and consequence planning for the finale; and optional branches that remain
optional. It replays 1,209 minimal prerequisite closures and all 16 combinations
of entry, read, mapping, and control routes.

The 28 additional SDL mutation checks cover loss of an OR entry, the W22.4 and
W24.4 revision guards, a missing package conduit, command access through a read
conduit, a weakened reservoir gate, rehearsal/live state confusion, direct Kali
attachment to the control subnet, and replacement of observed completion with
declared truth. They also corrupt explicit observation bindings, proof ownership,
precondition classes/references, technical mechanisms and scope/reset rules,
proof requirements, author checks, seed ownership/content, consequence effects,
and the ALL quantifier on joined reservoir evidence. Each mutation is checked for native type validity before the
campaign checker rejects its meaning. The unchanged full scenario receives
native structural and semantic validation. The exact spelling of the default
posture also has a parser rejection check. Two further mutations remove a
compiled selector's owner restriction or point it at an unrelated feature;
both remain type-valid and are rejected by the compiled-binding check.
The existing 26 negative topology
cases run against the graph recovered from SDL.

A prior independent read-only review of the challenge-contract corrections found no remaining concrete
defect within that review's scope. It separately checked the 250 technical
sections, producer bindings, all 33 capability formulas, the corrected K01
routes, and native default-open declarations. That review preceded the workplace
asset additions described here.

Reproduce the checks with the command in [tests/README.md](../tests/README.md).
The env-packs author entry point is necessary because its untrusted consumer
API intentionally rejects local imports. This pack has no consumer delivery
bundle yet. No upstream parser or compiler has been patched for these checks.

Native RAE validates the general relationship properties carrier; the campaign
checker owns the documented `cinder_kind` vocabulary and its routing semantics.
The eventual adapter still has to implement these contracts, materialize the
authored workplace assets, supply required challenge records and vulnerable
behaviors, and produce the required evidence. Static
acceptance does not establish those runtime properties, physical isolation,
capacity, or how long participants will take.
