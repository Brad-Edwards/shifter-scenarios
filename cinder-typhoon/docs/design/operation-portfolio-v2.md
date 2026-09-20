# Cinder Typhoon operation portfolio: draft 2

Status: architecture allocation, September 18, 2026. These are 64 operation
briefs containing **240 proposed scored achievements**, not 64 challenges and
not 240 implemented flags. The [CSV ledger](portfolio-v2.csv) is the machine-readable
allocation. This document renders it and explains its editorial constraints.
See the [architecture](challenge-architecture-v2.md) for progression and the
[reference catalog](reference-catalog-v2.md) for source difficulty and adaptations.

The portfolio describes capabilities and conceptual boundaries. It does not
assign machines, subnets, products, deployment units, or infrastructure sizes.
Operation identifiers supersede the first draft's family identifiers.

## Allocation

E = easy; M = medium; H = hard; X = expert; L = elite. Difficulty is the remaining
work with the provided agent after the stated access has been earned. Counts
are authoring budgets. They must survive a challenge-by-challenge distinct-work
review before they can become a scored inventory.

| Phase | Operations | Challenges | E | M | H | X | L |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Training | 4 | 16 | 12 | 4 | 0 | 0 | 0 |
| KeplerOps | 28 | 104 | 27 | 46 | 17 | 8 | 6 |
| ARWC | 32 | 120 | 24 | 44 | 31 | 16 | 5 |
| **Total** | **64** | **240** | 63 | 94 | 48 | 24 | 11 |

Both organizations contain every tier. Easy/medium allocations are 73/104 at
KeplerOps and 68/120 at ARWC. The latter is a substantial accessible middle,
including data and early OT work, followed by deeper control and research.
The campaign contains 83 hard-and-above slots; 35 are expert/elite, distributed
across multiple investigations rather than one final obstacle.

These percentages describe **slots, not hours or points**. Eleven elite
milestones occur inside seven substantial operations; they are not eleven
unrelated one-flag puzzles. A milestone only retains its tier if its marginal
work justifies it. Many other operations include hard/expert work without an
elite capstone.

### Principal technical activity

Each operation has one principal category so the counts are not inflated by
counting a cross-domain challenge several times. Secondary skills remain part
of the brief. This is a design-level distribution; final challenge-level
classification can change the totals.

| Principal work | Challenges | E | M | H | X | L |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Foundations | 12 | 11 | 1 | 0 | 0 | 0 |
| Identity | 31 | 9 | 10 | 6 | 4 | 2 |
| Supply | 27 | 10 | 17 | 0 | 0 | 0 |
| Process | 23 | 10 | 13 | 0 | 0 | 0 |
| Analysis | 28 | 9 | 12 | 6 | 1 | 0 |
| Native | 38 | 0 | 8 | 16 | 9 | 5 |
| Application | 36 | 1 | 12 | 13 | 8 | 2 |
| Crypto | 11 | 0 | 2 | 5 | 2 | 2 |
| Cloud | 16 | 6 | 10 | 0 | 0 | 0 |
| AI | 15 | 7 | 8 | 0 | 0 | 0 |
| Embedded | 3 | 0 | 1 | 2 | 0 | 0 |

Identity, cloud, application, supply, and analysis work establish the enterprise
character. Native/embedded/crypto investigations provide depth with different
kinds of reasoning. Process work becomes prominent at ARWC. AI-target work is
15 easy/medium slots, and some require no inference at all. There is no quota
to put every category into every tier. In particular, basic cloud practice can
remain accessible while related identity and application branches supply depth.

The category labels mean: Supply covers developer/build/distribution workflows;
Analysis covers artifacts, traffic, and operational data; Native covers reverse
engineering and memory exploitation; Embedded covers simulated device storage;
Process covers interpreting and affecting the water model. Foundations are
short independent introductory surfaces, not login or flag-submission chores.

## Operation briefs

The work column is an ordered sketch of distinct insights/effects. It is not
an assertion that each verb already deserves a flag. G/A/B identifiers refer
to the architecture's explicit entry-route challenges. Those route challenges
occupy these allocations. A named operation in an access condition means the
specific capability described there, never automatic completion of every flag
in that operation. Challenge-level expansion must make that subset explicit.

Source IDs link to the catalog. ATT&CK and ATLAS provide behavior inspiration;
only named CTF precedents support the hard-and-above candidates.

### Training

#### Workbench

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| T01: First contact | 4E | Start | Inspect a local artifact; follow a web clue; use a scoped credential; verify actual service state. | Original accessible task |

#### Accounts

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| T02: Someone can log in | 3E, 1M | Start | Read application behavior; find an exposed resource; use the resulting identity; cross one simple object boundary. | Original accessible task |

#### Developer artifacts

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| T03: Left in the checkout | 3E, 1M | Start | Inspect history; recover a synthetic secret; read a package; adapt its example client to reach the intended service. | Original accessible task |

#### State

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| T04: Trust the instrument | 2E, 2M | Start | Read a small simulator; decode its fields; change an allowed state; resolve a misleading client report from independent observations. | Original accessible task |

### KeplerOps

#### Borrowed desk

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| K01: Desk drawer | 4E | Developer foothold | Recover repository access (G01); inspect a browser artifact; retrieve an exposed work file; demonstrate a limited local service action. Each is a separate simple surface. | Original accessible task |
| K02: The first green report | 3E, 2M | Developer foothold | Understand a failing test fixture, recover its input, trace an import, alter the test job, and make the changed report appear. The first completed supplier episode. | Original accessible task |
| K03: Quiet callback | 1M, 2H | Developer foothold | Recover an old Cinder staging artifact; unpack its embedded script; reconstruct the final callback configuration to recover the earlier operation's collection. | [C04](reference-catalog-v2.md#c04) |
| K04: The native indexer | 1H, 1X, 2L | Developer foothold; local reproducer supplied | Find the constrained corruption; obtain useful leaks; turn partial pointer control into allocator control; achieve execution despite blocked convenient targets. The indexer processes support bundles. | [C03](reference-catalog-v2.md#c03) |

#### Package line

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| K05: What the customer installs | 2E, 2M | G01 | Exercise the package interface (G03); recover version history; resolve a manifest discrepancy; prove which dependency the consumer actually selects. | Original accessible task |
| K06: House package | 4M | G03 | Recover registry configuration through the importer (A01), obtain publication authority (A02), recover a distinct private package, and alter an independent test consumer. A01/A02 merge if they prove inseparable. | [C01](reference-catalog-v2.md#c01) |
| K07: One request too many | 2M, 2H, 1X | G01; registry inspection access | Map the inspection API and its protected function; identify an upgrade response discrepancy; model the two request parsers; construct a reproducible framing exploit; exercise the protected inspector function. Raw database-protocol construction belongs to W11. | [C05](reference-catalog-v2.md#c05) |
| K08: Four keys, one entitlement | 1M, 2H | G01; legacy license test service | Identify the old entitlement format; recover the encryption context; exploit equivalent-key behavior in the retained legacy checker. This is an obsolete compatibility path, not a claim against modern signatures. | [C06](reference-catalog-v2.md#c06) |

#### Build and preview

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| K09: Runner diary | 2E, 2M | G01 | Use a log disclosure, recover an omitted build artifact, alter an unsafe job input, and demonstrate execution in that job's limited context. | Original accessible task |
| K10: Preview belongs to whom | 2M, 1H | G01; preview source available | Characterize the preview boundary; identify ambiguous binding of its inputs; construct a document that crosses the intended isolation boundary. | [C09](reference-catalog-v2.md#c09) |
| K11: The compiler knows | 1M, 2H, 1X | G01; rules compiler artifact | Find the compiled policy entry point, recover virtual instruction semantics, lift the actual constraint program, and generate a package policy input it accepts. | [C07](reference-catalog-v2.md#c07) |
| K12: Approved in the browser | 1H, 2X, 2L | G01; ordinary preview account | Exploit account confirmation ordering; obtain a protected browser value; make a same-origin action occur; subvert the preview worker; use the resulting administrative renderer behavior for execution. | [C08](reference-catalog-v2.md#c08) |

#### Cloud workspace

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| K13: Cloud notebook | 3E, 1M | G01 | Use an exposed object listing, recover a previous object version, discover a separate export, and establish the supplied workload identity's actual access. | Original accessible task |
| K14: The wrong audience | 1E, 3M | K09 job execution OR K13 workload discovery | Inspect a token, discover an overly broad trust condition, exchange it for a role in the lab, and exercise that role against the intended resource. The exchange and use must enforce different conditions. | Original accessible task |
| K15: Support has an export | 1E, 3M | K13 OR K17 | Find a customer export job; cross an object-authorization boundary; change a destination through delegated job rights; retrieve the resulting bounded data collection. | Original accessible task |
| K16: The job that survives | 1E, 3M | K14 OR K15 | Discover a scheduled workflow; change its startup configuration; establish a separate execution context; demonstrate recurrence across a simulated shift change. No real waiting required. | Original accessible task |

#### People and authority

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| K17: Support session | 2E, 2M | G01 | Recover the limited support session (B01); use a distinct account-recovery weakness; enumerate its actual customer scope; exploit one delegated support action. | Original accessible task |
| K18: Federated notes | 1M, 2H, 1X | K17 ordinary access | Understand support note processing; exploit its client-side binding; change the identity-provider configuration; cross the backend query boundary through the altered identity response. | [C18](reference-catalog-v2.md#c18) |
| K19: Borrowed colleague | 1M, 1H, 1X, 1L | K17 OR K09; isolated staff workflow | Identify the certificate trust error; establish a colleague identity; influence the archive-processing workflow; obtain a usable delegated authentication context. This adapts the first half of a longer machine. | [C10](reference-catalog-v2.md#c10) |
| K20: The service wears a person | 1M, 1H, 1X, 1L | K19 delegated context | Map the delegation relationship; complete the relay/delegation chain; obtain the managed service capability; demonstrate impersonation against the protected release administration function. | [C10](reference-catalog-v2.md#c10) |

#### Assistant desk

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| K21: Policy in the margins | 2E, 1M | G01 | Read exposed assistant configuration; recover a separate retained conversation; use the discovered context to extract a synthetic restricted support datum. Only the last achievement needs inference. | [C02](reference-catalog-v2.md#c02) |
| K22: Helpful attachment | 1E, 2M | K17 ordinary access | Discover what the assistant retrieves; introduce an instruction through a support attachment; cause a bounded unauthorized tool action whose effect is independently visible. | [ATLAS](threat-inspiration-v2.md#atlas) |
| K23: The missing tenant filter | 2E, 1M | K17 ordinary access | Find a context endpoint; recover an exposed conversation identifier; cross the retrieval authorization boundary to another fictional customer's document. Deterministic application flaw. | [ATLAS](threat-inspiration-v2.md#atlas) |
| K24: Complete and run | 1E, 2M | K21 configuration access | Discover the completion feature; abuse its context selection to obtain its scoped key; exploit the application's decision to execute completed code. No sophisticated jailbreak required. | [C02](reference-catalog-v2.md#c02) |

#### Customer delivery

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| K25: ARWC is a real customer | 2E, 1M | G01 | Recover the customer record; connect a separate support attachment to the product deployment; reconcile the active tenant and revision (G02). | Original accessible task |
| K26: Customer accepted | 3M | A02 AND G02 | Build and publish a compatible changed package (A03); demonstrate ARWC consumption and corporate execution (A04); exploit a separate rollback/version-selection weakness for an optional retained delivery capability. | [C01](reference-catalog-v2.md#c01) |
| K27: Diagnostic delivery | 3M | B01 AND G02 AND G03 | Bind a diagnostic job to the correct customer (B02); alter its package through the template/import boundary (B03); demonstrate the equivalent corporate execution effect (B04). | Original accessible task |
| K28: The release has a second life | 1M, 2H | G01; archived customer connector binary | Recognize environment-dependent behavior; reconstruct the indirect-function hook; recover the runtime-decoded diagnostic path. Its output supplies an optional engineering clue later at ARWC. | [C11](reference-catalog-v2.md#c11) |

### ARWC

#### Corporate arrival

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| W01: New letterhead | 3E, 1M | ARWC corporate execution | Find the local integration artifact, read an exposed handover, use a separate corporate resource, and demonstrate a limited application action. Customer-side evidence gives the transition its payoff. | Original accessible task |
| W02: Names do not match | 2E, 2M | ARWC corporate execution | Recover the asset register and a separate contractor export; reconcile their identifiers; exploit a confused object association to retrieve an otherwise inaccessible maintenance record. | Original accessible task |
| W03: The work-order annex | 1E, 2M | ARWC corporate execution | Find the annex importer; exploit its file-reference boundary; recover a read integration configuration used with W09 for OT visibility. | Original accessible task |
| W04: Archive hatch | 1M, 2H, 1X | ARWC corporate execution; attachment service | Understand the archive workflow; pass a crafted certificate-derived value into its graph query; cross the query boundary; turn the archive helper's unsafe argument handling into execution. Different stages from K07. | [C05](reference-catalog-v2.md#c05) |

#### Corporate trust

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| W05: The temporary employee | 2E, 1M | ARWC corporate execution | Recover two independently exposed onboarding artifacts and exploit a role-assignment mistake to establish a limited staff identity. | Original accessible task |
| W06: Someone else's browser | 1M, 2H, 1X | W05 OR W04 | Identify the login state flaw; place an input that becomes client-side code; compose the login and rendering behaviors; cross the session boundary through cookie handling. | [C19](reference-catalog-v2.md#c19) |
| W07: The read-only query | 1M, 2H, 1X | W06 browser capability | Discover the protected query feature; overcome its statement restriction; reach privileged database behavior; demonstrate execution despite the apparent read-only interface. This is the server-side half of C19. | [C19](reference-catalog-v2.md#c19) |
| W08: A contractor left something | 2M, 2H | W05 OR W03 | Recover a hidden script, reconstruct its messaging exchange, extract the associated compiled collector, and dynamically recover its protected configuration. All messaging is represented inside the fictional range. | [C20](reference-catalog-v2.md#c20) |

#### Water on paper

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| W09: The missing megalitre | 2E, 2M | ARWC corporate execution | Recover the allocation ledger and a separate meter export; align units and dates; demonstrate the reserve discrepancy. With W03, identify and use the read-only process-data integration. | Original accessible task |
| W10: Another district's answer | 1E, 2M | ARWC corporate execution | Discover the report assistant's source selection; cross its district filter; retrieve a restricted planning record through the exposed retrieval path. No authority to operate the plant. | [ATLAS](threat-inspiration-v2.md#atlas) |
| W11: Records behind the graph | 2M, 1H, 1X | W02 OR W09 | Trace the asset relation service; identify its raw backend interface; construct the required backend exchange; extract a protected relation without general administrator access. | [C05](reference-catalog-v2.md#c05) |
| W12: Cold archive | 1M, 2H, 1X | W08 OR W11 | Recover a quarantined legacy collector; reconstruct its cryptographic behavior; recover a lost archive; connect that recovered content to a still-usable data path. No ransomware deployment. | [C17](reference-catalog-v2.md#c17) |

#### Maintenance

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| W13: Window on Thursday | 2E, 2M | ARWC corporate execution | Recover the appointment and a separate access roster; exploit an appointment ownership flaw; establish a scoped contractor session. The clock is a resettable scenario state, not real waiting. | Original accessible task |
| W14: The field bag | 1E, 2M | W13 contractor session | Recover a field export; distinguish an obsolete endpoint from the active service; use the contractor's documented read access. This completes the other medium OT-visibility route. | Original accessible task |
| W15: The cached drawing | 1M, 2H, 1X | W13 OR W03 | Trace the project cache; exploit header injection to poison its response; cross the resulting session boundary; recover a protected maintenance approval artifact through the downstream token-validation flaw. | [C24](reference-catalog-v2.md#c24) |
| W16: The instrument whispers | 1M, 1H, 1X, 1L | ARWC corporate execution; retained diagnostic binary | Recover the sequencer interface; identify an out-of-bounds observation path; build a controlled timing experiment; recover protected calibration data from the measured signal. Optional research, not an access gate. | [C14](reference-catalog-v2.md#c14) |

#### OT observation

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| W17: First live trace | 3E, 1M | Either OT-visibility route | Read live values, identify a mode, find a tag from its engineering description, and correlate a benign test with independent telemetry. | Original accessible task |
| W18: Tags that lie | 2E, 2M | OT visibility | Recover a tag export and a separate scale table; resolve the unit/revision mismatch; identify the real outlet group by observed behavior. No blind guessing of registers. | Original accessible task |
| W19: The old diagnostic | 1M, 2H, 1X | OT visibility; K28 is helpful but optional | Locate the engineering diagnostic; identify its mixed instruction modes; recover the hidden check logic; reconstruct an alternate source of process mapping. K28 explains the product history but does not supply this different solution. | [C21](reference-catalog-v2.md#c21) |
| W20: Write before erase | 1M, 2H | OT visibility; retained maintenance image | Read the flash interface; recover its event layout and checks; modify a selected maintenance record while preserving unrelated sector contents. A simulated device interface, no physical kit per player. | [C12](reference-catalog-v2.md#c12) |

#### Engineering

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| W21: Which project is running | 2E, 1M | OT visibility | Recover the project and independent commissioning note; reconcile the deployed revision. This supplies the process interpretation branch and engineering-utility access context. | Original accessible task |
| W22: The sealed project | 1M, 2H, 1X | W21 | Recover the protected project viewer; identify its embedded bytecode machine; emulate the key-producing program; decrypt and interpret the engineering project it protects. This uses runtime emulation, unlike K11's compile-time constraint lifting. | [C25](reference-catalog-v2.md#c25) |
| W23: A measurement that never existed | 1H, 1X, 2L | OT visibility; estimator reproducer | Diagnose the measurement-list lifecycle error; construct a memory primitive; influence the estimator's actual state; produce a controlled, independently measured false estimate. | [C13](reference-catalog-v2.md#c13) |
| W24: Two answers from one box | 1M, 2H, 1X | W21 | Identify the legacy recovery interface; predict which oracle answers; reconstruct the protected value under its query budget; use that value for a separate diagnostic function. Keep the cryptographic defect in a documented obsolete product component. | [C23](reference-catalog-v2.md#c23) |

#### Control

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| W25: Mode and meaning | 2E, 2M | OT visibility | Observe operating mode, read a separate interlock state, distinguish request acceptance from actuation, and establish the allowed command sequence in a practice model. | Original accessible task |
| W26: The approval that became a command | 1M, 2H, 1X | W13 AND W15 | Identify the maintenance renderer; gain its application authority; turn unsafe renderer behavior into execution in the scoped maintenance context; demonstrate a usable control client. This uses the server-side tail of C08. | [C08](reference-catalog-v2.md#c08) |
| W27: A valid-looking program | 1H, 1X, 2L | W21; isolated program verifier | Reverse the legacy program checksum; model its linear structure; construct a collision with the required engineering meaning; obtain acceptance for a changed diagnostic program. No claim to break a modern signature. | [C15](reference-catalog-v2.md#c15) |
| W28: The utility has no room | 1M, 2H | W21 | Characterize the small engineering utility; build a control-flow exploit with its constrained code surface; retain the correct execution privilege to obtain the scoped control capability. | [C16](reference-catalog-v2.md#c16) |

#### Release and consequences

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| W29: Paper truth | 1E, 2M | OT visibility | Recover the current allocation rule; use actual observations to reconcile usable reserve; model a release with the supplied volume equation. This establishes the consequence, not an extra exploit. | Original accessible task |
| W30: Open the gates | 4M | Process interpretation AND (W28 OR W26 control) AND W25 | Bind the intended outlet group to the control client; satisfy the documented mode sequence; cause gate opening; independently demonstrate the resulting volume change. Merge the last pair if verification is trivial. | Original accessible task |
| W31: The diagnostic vault | 1M, 1H, 2X | W21; optional native diagnostic service | Find the formatting/length discrepancy; combine it with the parser boundary error; construct control over the saved execution state; obtain the diagnostic service privilege despite its stack protection. Optional alternative control research, not a finale requirement. | [C22](reference-catalog-v2.md#c22) |
| W32: Replay is not reality | 1M, 2H, 1X | W21; optional offline replay artifact | Identify the replay tool's entity/component layout; reconstruct the relevant update systems; recover the hidden state condition; produce a trace that exposes why replay and live process disagree. Distinct from modifying the actual process. | [C26](reference-catalog-v2.md#c26) |

## Keep the difficulty local and the choices real

These are authoring groups, not seven compulsory KeplerOps chapters followed
by eight compulsory ARWC chapters. The ordinary supplier gate selects only
parts of K01/K05/K06/K25/K26 or K01/K05/K17/K25/K27. The many remaining operations
are exploration, alternate capabilities, and deeper episodes.

At the opening desk, K01/K02 provide short wins, K03 offers artifact analysis,
and K04 offers substantial native research. G01 exposes the package, cloud,
preview, and customer leads. At corporate ARWC access, W01/W02/W09 introduce
ordinary data and application work, while W04/W16 offer deeper alternatives.
OT visibility opens W17/W18/W21/W25 before a player has control authority.

Later easy flags must be reachable through the appropriate easier access route.
They do not count as novice content merely because the final action is easy
behind an elite-only prerequisite. Validate this reachability separately from
the tier histogram. The final challenge graph, not this brief table, will be the
authoritative source for that check.

## What the longest operations actually reward

K04's two elite allocations separate developing useful allocator control from
operationalizing constrained execution; do not award both for one delivered
script. K12 separates its demanding browser-worker compromise from its further
server-side effect. K19/K20 split an enterprise chain across different identity
and service transitions, with explicit prerequisite credit. W23 separates the
memory capability from controlled manipulation of estimator state. W27 separates
a usable collision from a semantically valid altered program accepted by the
engineering consumer. W16's elite candidate is the full timing-based recovery.

These are proposed distinctions to test, not automatic exemptions from the
anti-padding rule. If an agent or a published solver collapses two achievements
into one step, merge or lower them and replace the missing depth elsewhere.

W30 contains medium operational steps after a hard/expert authority route. Its
conditional rating does not make the full reservoir campaign medium. This is
intentional: solving the difficult control problem should result in a satisfying
ending. An additional elite final riddle would weaken that payoff.

## Reuse, overlap, and taste checks

Use a public challenge's central insight directly where it fits. Recontextualize
its artifacts, actors, and consequences; do not require novelty for novelty's
sake. Preserve the technical constraints that made it interesting. Public
solutions are legitimate research material during calibration and play.

Some precedents supply different parts of a larger chain: C05 contributes proxy
framing, backend protocol interaction, certificate/query handling, and archive
helper behavior. C19 supplies both a browser/session chain and a separate
restricted database query problem. Those can be distinct operations. Merely
changing the names of two identical deployments cannot.

The overlap review replaced the second origin-isolation puzzle with a cache and
header trust chain (W15), the repeated native loader with mixed-mode code
analysis (W19), the second entitlement attack with a two-oracle problem (W24),
and the second flash-edit puzzle with entity/component reconstruction (W32).
K11 and W22 still share the broad subject of virtual machines, but exercise
compile-time constraint lifting and runtime bytecode/key recovery respectively.
The native diagnostic exploit W31 uses different corruption primitives from
K04 and W23. These distinctions need to remain visible in the authored tasks.

Likewise, short cloud observations and uses of credentials must be different
exposed surfaces with different consequences. Do not split one API response
into four introductory flags to make an allocation add up.

Keep the story's technical idiom consistent. A legacy TEA entitlement or custom
checksum needs a credible retired-component explanation and a limited impact.
Use only a few such components. There is no place here for arbitrary blockchain,
steganography riddles, Internet scavenger hunts, or exotic mathematics without
a product or process purpose. Data analysis should help the intruder choose an
operation; it should not unexpectedly turn the whole event into a defensive
incident-response competition.

## Architecture completeness boundary

This portfolio is large enough to review distribution and select vertical
prototypes. It is not a claim that 240 independent insights have been fully
specified. Before converting it to SDL or a final challenge board, each slot
needs an authored challenge card, explicit prerequisite closure, observable
proof, hint ladder, reference/adaptation note, and an independently solved
fixture. The calibration plan requires a count of actual accepted cards and
measured effort by player cohort. Preserve the sixteen-hour content requirement
when replacing or merging weak slots.
