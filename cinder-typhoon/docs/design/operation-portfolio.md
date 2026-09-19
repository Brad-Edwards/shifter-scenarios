# Cinder Typhoon operation portfolio: draft 3

The [CSV ledger](portfolio.csv) allocates **240 achievements across 70 operations**.
These are authoring contracts, not implemented flags or measured hours. Read
with the [architecture](challenge-architecture.md), [source catalog](reference-catalog.md),
[twenty new card contracts and campaign outcomes](campaign-operations.md), and
[player-experience contract](player-experience.md).

## Allocation

E = easy; M = medium; H = hard; X = expert; L = elite. Tier describes remaining
work with the provided agent after stated prerequisites. Whole-route difficulty
also includes the burden of discovery and joins and must be tested separately.

| Phase | Operations | Challenges | E | M | H | X | L |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Training | 4 | 16 | 12 | 4 | 0 | 0 | 0 |
| KeplerOps | 31 | 104 | 25 | 45 | 21 | 9 | 4 |
| ARWC | 35 | 120 | 23 | 45 | 31 | 18 | 3 |
| **Total** | **70** | **240** | 60 | 94 | 52 | 27 | 7 |

The [allocation audit](allocation-audit.md) removes twenty weakly separated
milestones and replaces them with six operations. Both organizations retain
all tiers. Training remains four optional jeopardy boxes. Seven elite
milestones occur in six operations; those counts do not predict specialist
solve time. Accessible work continues after each major pivot.

### Principal activity

Each operation has one principal category. Secondary work is described in its
brief; the table therefore underdescribes mixed operations. These are slot
shares, not shares of hours, attainable points, or audience participation.

| Principal work | Challenges | E | M | H | X | L |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Foundations | 12 | 11 | 1 | 0 | 0 | 0 |
| Identity | 28 | 9 | 9 | 5 | 4 | 1 |
| Supply | 28 | 9 | 16 | 2 | 1 | 0 |
| Process | 28 | 10 | 13 | 3 | 2 | 0 |
| Analysis | 28 | 7 | 14 | 6 | 1 | 0 |
| Native | 37 | 0 | 8 | 16 | 9 | 4 |
| Application | 30 | 1 | 10 | 10 | 8 | 1 |
| Crypto | 10 | 0 | 2 | 5 | 2 | 1 |
| Cloud | 21 | 6 | 12 | 3 | 0 | 0 |
| AI | 15 | 7 | 8 | 0 | 0 | 0 |
| Embedded | 3 | 0 | 1 | 2 | 0 | 0 |

The new supply, cloud, and process depth comes from K29/K30/K31/W33/W34.
Their eleven hard-or-higher allocations add operational composition without
reclassifying existing binary puzzles. AI-target work remains fifteen
easy/medium slots, with no generative target on a compulsory route.

## Operation briefs

An operation in an access condition means its stated output, not completion of
every flag. Capability names refer to the [main campaign ledger](capability-routes.json).
The [entry ledger](entry-routes.json) records ordinary ARWC entry at challenge
level. All 240 allocations now have [individual challenge briefs](challenges/README.md):
[16 training](challenges/training.md), [104 KeplerOps](challenges/keplerops.md),
and [120 ARWC](challenges/arwc.md). Their technical design and three hint sections
remain blank; the briefs specify objectives and outcomes without solutions.

The work column groups distinct insights and effects. A receipt, login,
confirmation, or repeated use of a capability adds no score by itself.
Published sources support mechanisms; new constraints need fresh calibration.
No host, subnet, deployment unit, or infrastructure size is assigned here.

### Training

#### Workbench

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| T01: First contact | 4E | Start | Recover a local handover; find an unlisted web amendment; recover and use a scoped courier credential as one achievement; exploit a simple command-injection flaw to recover a separate internal summary. | Original accessible task |

#### Accounts

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| T02: Someone can log in | 3E, 1M | Start | Infer an active account and recover its case reference from authentication responses; recover private roster data hidden only by the client; exploit weak account recovery using those disclosures; cross a separate assignment-ownership boundary. | Original accessible task |

#### Developer artifacts

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| T03: Left in the checkout | 3E, 1M | Start | Recover a deleted fixture from history; recover and use a synthetic release credential as one achievement; reconstruct a readable package installation hook; adapt the example client and deliver a compatible changed package to the intended training consumer. | Original accessible task |

#### State

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| T04: Trust the instrument | 2E, 2M | Start | Distinguish measured volume from its setpoint; decode a documented status word; produce and independently verify a bounded practice transfer; resolve a separate client report that misattributes an earlier successful observation to the current attempt. | Original accessible task |

### KeplerOps

#### Borrowed desk

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| K01: Desk drawer | 4E | Developer foothold | Recover repository access (G01); inspect a browser artifact; retrieve an exposed work file; demonstrate a limited local service action. Each is a separate simple surface. | Original accessible task |
| K02: The first green report | 2E, 1M | Developer foothold | Recover the missing fixture through its exposed artifact surface; exploit the test-input import boundary; change the limited test job to produce an altered report that still passes its interface checks. Reading and tracing are part of these three achievements. | Original accessible task |
| K03: Quiet callback | 1M, 2H | Developer foothold | Recover an old Cinder staging artifact; unpack its embedded script; reconstruct the final callback configuration to recover the earlier operation's collection. | [C04](reference-catalog.md#c04) |
| K04: The native indexer | 1H, 1X, 2L | Developer foothold; local reproducer supplied | Find the constrained corruption; obtain useful leaks; turn partial pointer control into allocator control; achieve execution despite blocked convenient targets. The indexer processes support bundles. Production use compromises the indexer account and recovers the release-exception queue; the proof includes its access scope. This supplies an optional route to the K29 build dossier, not automatic build authority. | [C03](reference-catalog.md#c03) |

#### Package line

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| K05: What the customer installs | 2E, 2M | G01 | Exercise the package interface (G03); recover version history; resolve a manifest discrepancy; prove which dependency the consumer actually selects. | Original accessible task |
| K06: House package | 3M | G03 | Exploit importer fetch behavior to recover usable registry authority (A01, including former A02); recover a separately protected private package; compromise the independent test consumer. The production ARWC package remains K26. | [C01](reference-catalog.md#c01) |
| K07: One request too many | 1M, 1H, 1X | G01; registry inspection access | Recover the inspector boundary contract; construct the request-framing primitive from the two parsers; adapt it to the protected inspector action. Discovery, modeling, and confirmation are not separate flags. | [C05](reference-catalog.md#c05) |
| K08: Four keys, one entitlement | 1M, 2H | G01; legacy license test service | Identify the old entitlement format; recover the encryption context; exploit equivalent-key behavior in the retained legacy checker. This is an obsolete compatibility path, not a claim against modern signatures. | [C06](reference-catalog.md#c06) |

#### Build and preview

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| K09: Runner diary | 2E, 2M | G01 | Use a log disclosure, recover an omitted build artifact, alter an unsafe job input, and demonstrate execution in that job's limited context. | Original accessible task |
| K10: Preview belongs to whom | 2M, 1H | G01; preview source available | Characterize the preview boundary; identify ambiguous binding of its inputs; construct a document that crosses the intended isolation boundary. | [C09](reference-catalog.md#c09) |
| K11: The compiler knows | 1M, 2H, 1X | G01; rules compiler artifact | Find the compiled policy entry point, recover virtual instruction semantics, lift the actual constraint program, and generate a package policy input it accepts. | [C07](reference-catalog.md#c07) |
| K12: Approved in the browser | 1H, 2X, 1L | G01; ordinary preview account | Compose the account-ordering flaw into a useful privileged browser position; recover and use the protected browser value across its separate action boundary; take over the preview worker; achieve constrained renderer execution. The completed chain lets Cinder control the release preview seen by support. | [C08](reference-catalog.md#c08) |

#### Cloud workspace

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| K13: Cloud notebook | 3E, 1M | G01 | Use an exposed object listing, recover a previous object version, discover a separate export, and establish the supplied workload identity's actual access. | Original accessible task |
| K14: The wrong audience | 1E, 2M | K09 job execution OR K13 workload access | Recover the workload trust document; exploit its audience condition and demonstrate the resulting scoped role as one achievement; cross a distinct resource-policy boundary to the support export. Role use alone receives no second flag. | Original accessible task |
| K15: Support has an export | 1E, 3M | K13 OR K17 | Find a customer export job; cross an object-authorization boundary; change a destination through delegated job rights; retrieve the resulting bounded data collection. | Original accessible task |
| K16: The job that survives | 1E, 3M | K14 OR K15 | Discover a scheduled workflow; change its startup configuration; establish a separate execution context; demonstrate recurrence across a simulated shift change. No real waiting required. | Original accessible task |
| K30: The database you cannot reach | 2M, 1H | K13.4 workload access OR K09.4 job execution; G02 also required for final customer-history join | Recover the backup-capable identity from build metadata; exploit snapshot/restore authority to recover a protected database without source-database access; reconcile the recovered tenant/deployment history against G02 to identify the still-valid ARWC migration record. Snapshot, restore, password change, and successful read form one hard achievement. | [C28](reference-catalog.md#c28) |
| K31: The maintenance label | 1M, 2H | K14 scoped role OR K09 job execution | Recover the scheduler-to-maintenance trust contract; change a permitted workload to obtain its different runtime identity; abuse mutable resource labels under that identity to reach the protected maintenance archive. The role, label condition, and data-plane reachability must all fit; the archive contains the field commissioning evidence. | [C29](reference-catalog.md#c29) |

#### People and authority

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| K17: Support session | 2E, 2M | G01 | Recover the limited support session (B01); use a distinct account-recovery weakness; enumerate its actual customer scope; exploit one delegated support action. | Original accessible task |
| K18: Federated notes | 1M, 2H, 1X | K17 ordinary access | Understand support note processing; exploit its client-side binding; change the identity-provider configuration; cross the backend query boundary through the altered identity response. | [C18](reference-catalog.md#c18) |
| K19: Borrowed colleague | 1M, 1H, 1X | K17 OR K09; isolated staff workflow | Recover the certificate trust relation; establish a usable colleague identity; compose the archive workflow into delegated authentication. This first half of University has no separate elite allocation. | [C10](reference-catalog.md#c10) |
| K20: The service wears a person | 1H, 1X, 1L | K19 delegated context | Exploit the relay/delegation relationship; obtain the managed service capability across its independent boundary; impersonate release administration while preserving the consumer identity binding. Mapping the relationship is included in the first achievement. | [C10](reference-catalog.md#c10) |

#### Assistant desk

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| K21: Policy in the margins | 2E, 1M | G01 | Read exposed assistant configuration; recover a separate retained conversation; use the discovered context to extract a synthetic restricted support datum. Only the last achievement needs inference. | [C02](reference-catalog.md#c02) |
| K22: Helpful attachment | 1E, 2M | K17 ordinary access | Discover what the assistant retrieves; introduce an instruction through a support attachment; cause a bounded unauthorized tool action whose effect is independently visible. | [ATLAS](threat-inspiration.md#atlas) |
| K23: The missing tenant filter | 2E, 1M | K17 ordinary access | Find a context endpoint; recover an exposed conversation identifier; cross the retrieval authorization boundary to another fictional customer's document. Deterministic application flaw. | [ATLAS](threat-inspiration.md#atlas) |
| K24: Complete and run | 1E, 2M | K21 configuration access | Discover the completion feature; abuse its context selection to obtain its scoped key; exploit the application's decision to execute completed code. No sophisticated jailbreak required. | [C02](reference-catalog.md#c02) |

#### Customer delivery

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| K25: ARWC is a real customer | 1E, 1M | G01 | Recover the customer dossier and its support attachment as one disclosure; reconcile the active ARWC tenant and revision (G02). The dossier gives both ordinary delivery routes their customer context. | Original accessible task |
| K26: Customer accepted | 3M | A01 AND G02 | Build and publish a compatible changed package (A03); demonstrate ARWC consumption and corporate execution (A04); exploit a separate rollback/version-selection weakness for an optional retained delivery capability. | [C01](reference-catalog.md#c01) |
| K27: Diagnostic delivery | 3M | B01 AND G02 AND G03 | Bind a diagnostic job to the correct customer (B02); alter its package through the template/import boundary (B03); demonstrate the equivalent corporate execution effect (B04). | Original accessible task |
| K28: The release has a second life | 1M, 2H | G01; archived customer connector binary | Recognize environment-dependent behavior; reconstruct the indirect-function hook; recover the runtime-decoded diagnostic path. Its output supplies an optional engineering clue later at ARWC. | [C11](reference-catalog.md#c11) |
| K29: The next release is ours | 1M, 2H, 1X | G01 AND G02 AND (K09 job records OR K13 cloud records OR K04 exception queue) | Recover a scoped build principal from the cloud-backed release dossier; recover historical source/signing authority through the separate repository boundary; deliver one signed release that changes ARWC while preserving the reference customer across current and retained supported interfaces; retain delivery through an independently changeable build definition after a disclosed credential rotation. C27 supplies the chain; the final persistence constraint is an authored extension. | [C27](reference-catalog.md#c27) |

### ARWC

#### Corporate arrival

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| W01: New letterhead | 3E, 1M | ARWC corporate execution | Find the local integration artifact, read an exposed handover, use a separate corporate resource, and demonstrate a limited application action. Customer-side evidence gives the transition its payoff. | Original accessible task |
| W02: Names do not match | 1E, 2M | ARWC corporate execution | Recover the asset and contractor bundle; reconcile independent identifier systems; exploit the confused object association to retrieve a protected maintenance record. | Original accessible task |
| W03: The work-order annex | 1E, 2M | ARWC corporate execution | Find the annex importer; exploit its file-reference boundary; recover a read integration configuration used with W09 for OT visibility. | Original accessible task |
| W04: Archive hatch | 1M, 1H, 1X | ARWC corporate execution; attachment service | Recover the archive workflow contract; cross the certificate-derived graph-query boundary; compose its result with the archive helper to gain execution. Exploit construction and its confirmation share credit. | [C05](reference-catalog.md#c05) |

#### Corporate trust

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| W05: The temporary employee | 2E, 1M | ARWC corporate execution | Recover two independently exposed onboarding artifacts and exploit a role-assignment mistake to establish a limited staff identity. | Original accessible task |
| W06: Someone else's browser | 1M, 1H, 1X | W05 OR W04 | Recover the login/rendering contract; compose login state and client-side execution; cross the session boundary through cookie handling. The resulting planner session supplies actual application authority. | [C19](reference-catalog.md#c19) |
| W07: The read-only query | 1M, 1H, 1X | W06 browser capability | Recover the protected query interface; defeat its statement restriction with a useful data primitive; turn the independent privileged database behavior into execution. Construction and execution confirmation share credit. | [C19](reference-catalog.md#c19) |
| W08: A contractor left something | 2M, 2H | W05 OR W03 | Recover a hidden script, reconstruct its messaging exchange, extract the associated compiled collector, and dynamically recover its protected configuration. All messaging is represented inside the fictional range. | [C20](reference-catalog.md#c20) |

#### Water on paper

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| W09: The missing megalitre | 2E, 2M | ARWC corporate execution | Recover the allocation ledger and a separate meter export; align units and dates; demonstrate the reserve discrepancy. With W03, identify and use the read-only process-data integration. | Original accessible task |
| W10: Another district's answer | 1E, 2M | ARWC corporate execution | Discover the report assistant's source selection; cross its district filter; retrieve a restricted planning record through the exposed retrieval path. No authority to operate the plant. | [ATLAS](threat-inspiration.md#atlas) |
| W11: Records behind the graph | 1M, 1H, 1X | W02 OR W09 | Recover the relation-service protocol contract; construct a valid protected backend exchange; cross its scoped relation boundary to recover current asset lineage. Interface discovery and tracing share credit. | [C05](reference-catalog.md#c05) |
| W12: Cold archive | 1M, 2H, 1X | W08 OR W11 | Recover a quarantined legacy collector; reconstruct its cryptographic behavior; recover a lost archive; connect that recovered content to a still-usable data path. No ransomware deployment. | [C17](reference-catalog.md#c17) |
| W35: The wrong bill | 1E, 2M | ARWC corporate execution | Recover the replacement-supply price catalog; cross a procurement object boundary to recover the protected district quote; exploit the report-import association flaw to issue an unauthorized replacement order against the wrong district budget. The signed order and limited simulated liability provide a complete corporate-side ending before OT. | Original accessible task |

#### Maintenance

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| W13: Window on Thursday | 2E, 2M | ARWC corporate execution | Recover the appointment and a separate access roster; exploit an appointment ownership flaw; establish a scoped contractor session. The clock is a resettable scenario state, not real waiting. | Original accessible task |
| W14: The field bag | 1E, 2M | W13 contractor session | Recover a field export; distinguish an obsolete endpoint from the active service; adapt the retained client to the current read interface within the contractor's documented inspection and asset scope. This completes the other medium OT-visibility route; login alone earns no separate score. | Original accessible task |
| W15: The cached drawing | 1M, 2H, 1X | W13 OR W03 | Trace the project cache; exploit header injection to poison its response; cross the resulting session boundary; recover a protected maintenance approval artifact through the downstream token-validation flaw. | [C24](reference-catalog.md#c24) |
| W16: The instrument whispers | 1M, 1H, 1X, 1L | ARWC corporate execution; retained diagnostic binary | Recover the sequencer interface; identify an out-of-bounds observation path; build a controlled timing experiment; recover protected calibration data from the measured signal. Optional research, not an access gate. The recovered calibration revision resolves the disputed sensor scale for W33; an ordinary medium commissioning-record route supplies equivalent data. | [C14](reference-catalog.md#c14) |

#### OT observation

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| W17: First live trace | 3E, 1M | Either OT-visibility route | Read live values, identify a mode, find a tag from its engineering description, and correlate the recorded routine commissioning event with independent telemetry. Read access suffices; this branch does not require a live write. | Original accessible task |
| W18: Tags that lie | 2E, 2M | OT visibility | Recover a tag export and a separate scale table; resolve the unit/revision mismatch; identify the real outlet group by observed behavior. No blind guessing of registers. | Original accessible task |
| W19: The old diagnostic | 1M, 2H, 1X | OT visibility; K28 is helpful but optional | Locate the engineering diagnostic; identify its mixed instruction modes; recover the hidden check logic; reconstruct an alternate source of process mapping. K28 explains the product history but does not supply this different solution. Its output substitutes only for tag mapping. Current revision, allocation, and operating-envelope evidence remain separate requirements. | [C21](reference-catalog.md#c21) |
| W20: Write before erase | 1M, 2H | OT visibility; retained maintenance image | Read the flash interface; recover its event layout and checks; modify a selected maintenance record while preserving unrelated sector contents. A simulated device interface, no physical kit per player. | [C12](reference-catalog.md#c12) |

#### Engineering

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| W21: Which project is running | 1E, 1M | OT visibility | Recover the engineering project and commissioning note as one bundle; compare their revision claims with the independently read deployed revision. The result supplies current revision evidence, never inferred from W19. | Original accessible task |
| W22: The sealed project | 1M, 2H, 1X | W21 | Recover the protected viewer; reconstruct its instruction behavior; recover the key, readable engineering project, and omitted commissioning decision as one achievement; separately analyze the retained review helper and captured session to recover a concealed identity and use its scoped archive access. C25 supplies the VM problem; C31 supplies the conflicting managed/native behavior. Historical archive access grants no current control. | [C25](reference-catalog.md#c25), [C31](reference-catalog.md#c31) |
| W23: A measurement that never existed | 1H, 1X, 1L | OT visibility; estimator reproducer | Diagnose the measurement-list lifecycle fault; develop a usable memory primitive; turn it into controlled estimator-state corruption. Cinder can now alter a genuine district planning estimate; W34 uses that capability against the reporting workflow. The live process evaluator stays independent. | [C13](reference-catalog.md#c13) |
| W24: Two answers from one box | 1M, 2H, 1X | W21 | Identify the legacy recovery interface; predict its response selection; recover the archive-unlock value and open the diagnostic evidence bundle as one achievement; separately analyze the retained signer and signed records to produce a fresh authorization for the private calibration-exception export. C23 supplies oracle recovery; C32 supplies the independent binary/signature problem. Diagnostic authorization grants no maintenance approval or live control. | [C23](reference-catalog.md#c23), [C32](reference-catalog.md#c32) |

#### Control

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| W25: Mode and meaning | 2E, 2M | OT visibility | Recover the documented operating envelope; read current mode/interlock evidence; distinguish accepted requests from actuation using the practice model; construct a valid practice sequence. These provide ENVELOPE and MODE without write authority. | Original accessible task |
| W26: The approval that became a command | 1M, 2H, 1X | W13 AND W15 | Identify the maintenance renderer; gain its application authority; turn unsafe renderer behavior into execution in the scoped maintenance context; demonstrate a usable control client. This uses the server-side tail of C08. | [C08](reference-catalog.md#c08) |
| W27: A valid-looking program | 1H, 1X, 1L | W21; isolated program verifier | Recover the legacy integrity algorithm; model its linear collision constraints; create a semantically valid altered diagnostic program accepted by the engineering consumer. A useful collision and its final accepted program form one elite achievement; W34 can use the program to alter a planning view. | [C15](reference-catalog.md#c15) |
| W28: The utility has no room | 1M, 2H | W21 | Characterize the small engineering utility; build a control-flow exploit with its constrained code surface; retain the correct execution privilege to obtain the scoped control capability. | [C16](reference-catalog.md#c16) |

#### Release and consequences

| Operation | Slots | Available from | Principal work and story effect | Source |
| --- | --- | --- | --- | --- |
| W29: Paper truth | 1E, 2M | PROCESS_INTERPRETATION AND MODE; tariff artifact visible from OT visibility | Recover the current replacement-supply tariff; reconcile live usable reserve with allocation commitments; construct a bounded release/consequence plan using the supplied equation and current envelope. W30 requires the last output; no exploit or extra riddle is added. | Original accessible task |
| W30: Open the gates | 2M | PROCESS_INTERPRETATION AND CONTROL AND MODE AND CONSEQUENCE_PLAN | Bind the scoped control client and validated process evidence into a correct command plan; execute the opening and prove the volume effect independently as one achievement. The visible financial consequence completes the episode. | Original accessible task |
| W31: The diagnostic vault | 1M, 1H, 2X | W21; optional native diagnostic service | Find the formatting/length discrepancy; combine it with the parser boundary error; construct control over the saved execution state; obtain the diagnostic service privilege despite its stack protection. Optional alternative control research, not a finale requirement. | [C22](reference-catalog.md#c22) |
| W32: Replay is not reality | 1M, 2H, 1X | W21; optional offline replay artifact | Identify the replay tool's entity/component layout; reconstruct the relevant update systems; recover the hidden state condition; produce a trace that exposes why replay and live process disagree. Distinct from modifying the actual process. The resulting witness explains why the replay approved a gate schedule that current observations reject; it supplies an optional scenario model for W33, never authority or current telemetry. | [C26](reference-catalog.md#c26) |
| W33: The expensive hour | 1M, 2H, 1X | OT visibility for investigation; PROCESS_INTERPRETATION AND MODE AND CONTROL AND CONSEQUENCE_PLAN for execution | Reconstruct a forecast from observable calibration evidence; derive a feasible constrained gate schedule in the practice model; exploit the overly broad scheduler authority to apply it under the current mode; run a feedback policy through that earned capability across disclosed demand/calibration changes in private live rehearsals. A finite horizon, ramp limits, channel capacity, and allocation cost make timing and process interpretation matter. | [C30](reference-catalog.md#c30) |
| W34: The reassuring dashboard | 1M, 1H, 1X | PROCESS_INTERPRETATION AND (W23 estimator corruption OR W27 accepted diagnostic program); MODE AND CONTROL AND CONSEQUENCE_PLAN join at W34.3 only | Reconstruct which planning view consumes the compromised output; construct a semantically plausible false view consistent with unaffected meters and the known observation delays; couple that view to a bounded release across a disclosed reporting/shift transition. Grade both changed planning decisions and independent physical truth. The source exploit is credited in W23 or W27, never again here. | [C13](reference-catalog.md#c13), [C15](reference-catalog.md#c15) |

## Acceptance boundaries

Use operation-level point budgets. Partial proof should preserve worthwhile
progress without multiplying rewards for one exploit. Alternative methods that
achieve the same effect do not create additional flags. Story conclusions and
room-wide recognition are unscored.

Source reuse is intentional. Preserve the mechanism and explain its product
purpose; do not preserve an old tier through obscure clues, retries, or waiting.
Every challenge still needs a complete proof contract, hint ladder, explicit
prerequisites, reset behavior, and independent solve. Validate later easy work
through an appropriate easier access route, rather than counting an obvious
file hidden behind an elite-only prerequisite as novice content.

The [calibration plan](calibration.md) checks the full assisted experience,
including source-aware transfer, optional campaign composition, and day-two
continuation. The 240 allocation remains a capacity hypothesis until accepted
cards and fresh-player trajectories support it.
