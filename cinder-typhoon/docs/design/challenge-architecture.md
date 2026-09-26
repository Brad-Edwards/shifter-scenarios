# Cinder Typhoon challenge architecture: draft 3

Design date: September 18, 2026. This revision responds to the accepted
[second adversarial review](adversarial-review-v2.md). The
[second draft](challenge-architecture-v2.md) and
[first draft](challenge-architecture-v1.md) are preserved. This is a challenge
architecture, not a topology, implementation specification, or playtest report.

Read with the [operation portfolio](operation-portfolio.md),
[challenge reference catalog](reference-catalog.md),
[threat inspiration](threat-inspiration.md), and [calibration plan](calibration.md).
The [campaign operations](campaign-operations.md) define the new optional work;
[player experience](player-experience.md) makes choices and delegation concrete.
The [allocation audit](allocation-audit.md) records every removed and replaced
slot. The earlier [research](research.md) documents Polaris and the literature.

## 1. An accessible campaign with consequential optional depth

**Entering ARWC and mastering KeplerOps are different achievements.** The player
can compromise the supplier and reach ARWC through a bounded sequence of easy
and medium challenges. Both organizations then offer substantial exploration,
local difficulty ladders, and optional expert work. Clearing KeplerOps is never
an entry requirement for ARWC.

Approximately 300 people play individually for sixteen mostly continuous hours
over two days. Everyone receives an agent; bringing another agent is optional.
The audience extends from first-time hackers to elite government, military,
intelligence, and industry operators. Assistance is an intended capability, and
all difficulty estimates assume it. Neither an occupation nor prior CTF results
place a participant into a permanent track.

The campaign retains three phases: Cinder Typhoon training, KeplerOps Software,
and Alterra Regional Water Company (ARWC). The overall progression becomes more
demanding, but a new organization or a difficult pivot opens some approachable
work again. Elite side operations are discoverable early. The reservoir ending
is earned; finishing every challenge is neither required nor expected.

Draft 3 replaces twenty weakly separated milestones with twenty achievements
in six new operations. Cloud authority, release continuity, constrained process
planning, and reporting deception now contribute difficult optional work. The
new corporate procurement episode gives an assisted newcomer another complete
financial objective before OT. These operations have observable conclusions
and explicit evidence joins; they do not become compulsory campaign gates.

The medium ceiling applies to the complete ARWC **entry** route, including its
joins and transitive prerequisites. It does not make all subsequent control work
medium. A credible hard route to the ending and optional expert/elite operations
can coexist.

## 2. What these organizations actually do

KeplerOps sells **FieldLink**, software that turns contractor records, maintenance
packages, and operating data into usable work orders and reports. It includes
customer connectors, a package distribution service, support diagnostics, a
project viewer, and an assistant for searching support material. ARWC uses its
corporate integration to receive maintenance packages and reconcile asset data.
FieldLink is not the reservoir controller.

The developer foothold is already established by the fictional package-install
compromise. The player finds a company trying to keep a release and a customer's
maintenance work moving. Its legitimate workflows supply the attack surfaces:
previewing a support attachment, resolving a package, running a customer import,
trusting a contractor identity, and consuming a diagnostic package.

ARWC has an approaching dry-period allocation review. Its reporting dashboard
looks reassuring because it combines stale and current records badly. The
player's initial opportunity is corporate data and maintenance administration.
The engineering material progressively distinguishes a report about water from
the ability to affect water.

Four recurring people are enough: a KeplerOps developer whose workstation we
borrow; a support engineer trying to close ARWC's long-running ticket; an ARWC
maintenance planner coordinating a gate inspection; and a controls engineer
whose careful notes explain what the business dashboard leaves out. Give them
competent, specific concerns. Avoid a cast of people leaving administrator
passwords in every message. Short artifacts do narrative work while remaining
useful evidence.

Cinder Typhoon's handler supplies objectives and acknowledges effects. The
handler does not explain every exploit. The player should remember the product,
the customer, the inspection, and the gates, without memorizing a fictional
organization chart.

## 3. Content capacity and difficulty

Retain **240 scored challenge slots**, grouped into **70 operation briefs**:
four training boxes, 31 KeplerOps operations, and 35 ARWC operations. A slot is
an allocation for a distinct achievement, not a finished challenge. An operation
usually contains two to five such achievements. The portfolio gives each a
purpose, principal activity, outputs, and source lineage where required.

This is a deliberately large content budget for sixteen hours. It is grounded
in the user's over-50-challenge Polaris event baseline, not the 38-row campaign
subset. Scaling that baseline by duration suggests a broad capacity range;
it does not establish a necessary number of flags or justify counting trivial
substeps. Polaris already assumed agents. Do not multiply it by a second generic
AI acceleration factor. See the [inventory reconciliation](research.md).

Use these names consistently:

| Tier | Meaning with the provided agent |
| --- | --- |
| Easy (E) | A clear lead and a bounded technique; the agent can explain and execute most mechanics. The participant can see why the result matters. |
| Medium (M) | Choose a plausible approach, adapt a familiar technique, and resolve a small evidence or access join. Documentation and feedback make the boundary legible. |
| Hard (H) | Sustain an investigation or construct a substantive exploit across interacting constraints. A generic recipe is insufficient without understanding this instance. |
| Expert (X) | Develop and debug a demanding chain, model unfamiliar implementation behavior, or make an exploit reliable under explicit constraints. |
| Elite (L) | Complete demanding research or exploitation comparable in core mechanism to a documented top-tier challenge, after accounting for modern assistance and public solutions. |

Tier is conditional on earned access. Reading an obvious file after an elite
exploit remains easy. Partial credit for an elite operation does not make every
intermediate flag elite. The original source's rating and our proposed assisted
rating are separate fields in the reference catalog.

The allocation is now 60 easy, 94 medium, 52 hard, 27 expert, and seven elite
slots. Elite source mechanisms remain; the audit removes inflated partial
credit rather than lowering the intended ceiling. The authoritative allocation
is the table in the portfolio. Its distribution
is a design hypothesis. There is no professional rule that a particular
percentage must be hard. The literature supports an accessible base, a broad
middle, worthwhile difficult work, and independent testing. It does not supply
a universal histogram for this audience and format.

### Count work, not ceremony

Separate scores require separate reasoning, implementation, or demonstrated
capabilities. Locating a vulnerability, constructing a usable primitive, and
crossing a further defended boundary can merit distinct achievements. Reading
three strings from one recovered file cannot. Logging in, submitting a flag,
and watching the ending are not additional challenges.

Every operation must pass a deletion test: if removing a proposed flag removes
no meaningful player decision or work, merge it. The 240 allocation is not a
license to keep filler. Replace a rejected operation with substantive content;
do not silently reduce the event to a short campaign.

## 4. Training and the opening hour

Four jeopardy boxes provide sixteen approachable achievements. They exercise
local inspection, application access, developer artifacts, and stateful service
interaction. Each offers a visible outcome, a useful explanation, and a way to
verify the agent's work. They are practice for the campaign, not an examination
in typing commands unaided.

Targets for testing: a first meaningful success within ten minutes of a working
session, several successes in thirty minutes, and a useful 45–90 minute training
option for new players. These are acceptance hypotheses, not observed results.
Experienced participants can go directly to the supplied developer foothold.
Training remains available later; all sixteen flags are never a gate.

The [sixteen training challenge briefs](challenges/training.md) specify
player-facing descriptions, distinct outcomes, and the small identity and
package-delivery dependency chains. They preserve the 12 easy / four medium
allocation. All sixteen now have technical drafts; their
[hand-build readiness gate](training-readiness.md) remains separate from that
document status. The inherited hint headings remain empty and unpublished.

The opening KeplerOps workspace exposes three different invitations:

- A simple trail through the developer's artifacts and an editable test job.
- A supported route toward the ARWC customer integration.
- Source and a local reproducer for the optional native indexer investigation.

Thus a novice can make the first altered test report appear while an expert
starts a substantial exploit from the same earned position. The indexer does
not require first collecting dozens of flags. Its deeper production effect
still requires the relevant access; possessing source is not possessing control.

## 5. ARWC entry: two actual medium routes

These are alternative capability routes. A player completes one, not both.
Both end with customer-side execution in FieldLink's limited corporate context.
There is no score threshold, timed giveaway, or mandatory AI exploit.

The shared evidence is deliberately compact: one customer record establishes
the active ARWC integration and one package/interface record establishes how
that integration consumes software. These are ordinary artifacts of the
supplier relationship, not hidden trivia spread across the whole campaign.

| ID | Required challenge | Tier | Requires | Portfolio owner |
| --- | --- | --- | --- | --- |
| G01 | Recover and use the developer's limited repository access. | E | Supplied foothold | K01 |
| G02 | Reconcile ARWC's tenant record with its active connector revision. | M | G01 | K25 |
| G03 | Identify the consumed package and exercise its documented interface. | E | G01 | K05 |
| A01 | Exploit the importer's fetch behavior to recover protected registry configuration and usable publication authority. | M | G03 | K06 |
| A03 | Construct an altered compatible package and publish it to the consumed release channel. | M | A01, G02 | K26 |
| A04 | Cause ARWC to consume that package and demonstrate execution in its corporate connector. | M | A03 | K26 |
| B01 | Recover and use the support application's limited session. | E | G01 | K17 |
| B02 | Exploit an object-authorization flaw to bind a diagnostic job to the ARWC connector. | M | B01, G02 | K27 |
| B03 | Modify the diagnostic package through an exposed template/import boundary while preserving its expected interface. | M | B02, G03 | K27 |
| B04 | Deliver the package through the support workflow and demonstrate the same customer execution capability. | M | B03 | K27 |

Route A has six scored prerequisites including its terminal challenge;
Route B has seven. A02 is retired: its token recovery now belongs to A01.
These are existing portfolio allocations, not extra flags. The asymmetry follows
meaningful work. A03 constructs the accepted package; A04 resolves actual
consumer selection/activation and proves execution. If the latter becomes a
trivial automatic receipt in implementation, merge it and replace the freed
allocation with substantive work. Do not score the receipt itself.

Route A directly adapts the package-consumption mechanism of HTB's **Prison
Pipeline**, whose organizer materials disagree between easy and medium. Route B
uses a different support workflow and familiar medium application flaws. Both
routes require a working package and correct customer binding. Neither needs
directory domination, advanced cloud compromise, release-signing research,
malware reverse engineering, or an assistant jailbreak.

The join is itself a **medium design constraint**: clear tenant identifiers,
a supplied interface example, deterministic acceptance feedback, and no race
or unusual exploit development. A chain of individually medium labels that
plays like one expert investigation fails this architecture. Test the entire
route with fresh assisted intermediate players, not only each component.

Deep KeplerOps exploits can earn alternative publication or support authority,
but must still satisfy customer binding and actual consumption. They may be
interesting shortcuts or routes to broader impact; they cannot be hidden
prerequisites of the ordinary entry route.

## 6. ARWC evidence and capability contracts

Corporate arrival exposes reporting, maintenance, and optional research together.
The [capability ledger](capability-routes.json) records the main campaign's
AND/OR joins. Its nodes are outputs and unscored joins, not additional flags or
a complete 240-card dependency graph. The entry ledger supplies its initial
corporate capability.

| Capability or evidence | Required source | What it establishes |
| --- | --- | --- |
| CORPORATE | Route A OR Route B | Execution in FieldLink's limited ARWC corporate context. |
| OT_READ | W03 read integration AND W09 data, OR W13 contractor session followed by W14 | Equivalent read-only process access through two medium routes. |
| MAPPING | W18 observations/tag reconciliation OR W19 mixed-mode diagnostic investigation | The tag/scale-to-outlet mapping only. W19 never supplies current allocation or project revision. |
| Current allocation | W09.DATA | Time- and unit-reconciled business commitments and reserve evidence. |
| Current revision | W21.REVISION | Project and commissioning records checked against the independently read deployed revision. |
| ENVELOPE | W25.ENVELOPE | Documented channel, rate, and volume limits. |
| PROCESS_INTERPRETATION | MAPPING AND W09.DATA AND W21.REVISION AND ENVELOPE | Correct outlet, current context, and valid operating bounds. |
| MODE | W17 observations AND W25 practice/mode work | Current mode/interlocks and a valid command sequence. |
| CONTROL | W28 after W21, OR W26 after W13 AND W15 | Equivalent scoped live authority through hard engineering exploitation or an expert maintenance chain. |
| CONSEQUENCE_PLAN | W29 after PROCESS_INTERPRETATION AND MODE | A bounded release and predicted economic effect using the supplied volume model. |
| Reservoir result | PROCESS_INTERPRETATION AND MODE AND CONTROL AND CONSEQUENCE_PLAN, then W30 | The actual gate opening and independently verified change in usable reserve. |

The ordinary mapping, evidence, and planning path is medium or easier. The
hard boundary is acquiring control. W29 is explicitly part of the ending's
knowledge requirements; it packages the consequence calculation already implied
by the story. Its supplied equation and readable inputs must keep it medium.
W30 has two medium achievements: a bound command plan and an executed, verified
effect. Neither adds an elite final examination.

An alternative method substitutes for the capability it actually proves.
W19 replaces mapping alone. Optional history from K30, K31, or W16 can help
explain current evidence but cannot silently replace checking live conditions.
W31 may become another control route if its implementation proves equivalent
scope; the current graph does not assume that result.

Optional operations K29–K31 and W33–W35 have separate contracts in the
[campaign operations](campaign-operations.md). W33 requires earned control for
live execution but exposes its modeling work earlier. W34 exposes its reporting
work after PROCESS_INTERPRETATION plus W23 OR W27; its final live stage also
requires CONTROL, MODE, and CONSEQUENCE_PLAN.
Neither is needed for W30. Their private rehearsals preserve ordinary access
and previously earned results.

These joins describe evidence, authority, and effects. They do not assign hosts,
subnets, deployed products, or network attachments. The [full dependency
report](challenge-dependency-report.md) enumerates the 240 briefs' prerequisite
closures. Its cumulative tier bounds describe the declared requirements;
they do not measure cognitive difficulty or completion time.

## 7. Story rhythm and signature moments

Progression is driven by player effects, not a global hourly unlock. Players
may enter ARWC on day one, continue KeplerOps on day two, or spend the event on
one organization's difficult branches. The following are scenes to author and
test, not compulsory pauses or unscored walls of exposition.

| Moment | Trigger and player experience | Why it matters |
| --- | --- | --- |
| Someone else's desk | The first artifact exposes a familiar unfinished workday; the player changes an actual test report. | Immediate agency and a small completed episode for a newcomer. |
| The green build | A functioning package passes the ordinary test and changes the consumer's behavior. | The player sees why a supply compromise works, rather than only finding a token. |
| Customer accepted | A receipt carries the player's package revision into ARWC; the same support ticket is now visible from the customer's side. | A memorable, causally earned organization transition. |
| Water on paper | Joining the allocation ledger to the current meter export reveals that a healthy report does not establish usable reserve. | An accessible data success explains why this specific company is the target. |
| The first live trace | The player correlates a harmless documented test with telemetry; a copied report no longer suffices. | OT becomes an understandable process, with fresh easy wins after the pivot. |
| Two versions of the same plant | The project viewer, retained engineering image, and current observations disagree for a discoverable reason. | Earlier supplier clues pay off; hard work has a concrete question. |
| The gates move | The live process confirms the opening, the reserve trend changes, and the economic consequence appears. | The final exploit receives a clear payoff without a surprise extra elite exam. |

The recurring maintenance ticket is a breadcrumb, not a riddle whose prose must
be decoded. Reuse names and identifiers to make connections recognizable.
Optional conclusions now include the wrong replacement-supply bill (W35), a
release that survives credential rollover (K29), recovered customer history
(K30/K31), precisely timed economic loss (W33), and a consequential false
planning view accompanying a bounded release (W34). Difficult existing
operations have named downstream uses or self-contained conclusions in the
[campaign outcome table](campaign-operations.md#existing-difficult-operations-now-have-explicit-uses).
Receipts and acknowledgments are unscored feedback, not new challenge slots.

The [player-experience contract](player-experience.md) specifies invitations at
the desk, corporate ARWC, read-only OT, and after the gates. It also gives a
worked water-on-paper co-hacking episode, partial-progress stopping points,
and day-two recovery of the participant's chosen purpose. Participants can
pursue all available leads; recommendations do not hide earned alternatives.

The agent may carry out most mechanics. The interface should still show the
player's chosen objective, the evidence the agent used, and what changed.
Expose useful artifacts and live effects rather than requiring a human to read
a long tool transcript. Let people delegate deeply; forced manual work is not
the source of agency.

### The water consequence

The fictional reservoir has controlled outlet gates that can release stored raw
water into an ordinary downstream channel. The attack causes an unauthorized
release **within the modeled channel's normal capacity**, at a time when ARWC
needs that reserve for its own supply allocation. The lost water cannot be
recovered into that reserve during the story's planning horizon. Replacement
supply costs and temporary restrictions follow. There is no flood, dam failure,
contamination, injury, or catastrophic escalation.

The minimal simulation tracks stored usable volume, inflow, authorized demand,
outflow, and a reserve threshold. Opening the gates must change the outflow and
volume balance, not just a screen label. The final evaluator observes process
truth independently of the player's reports. A water/controls subject-matter
review must validate this fiction and its quantities before authoring the
control challenges. No real reservoir's operating parameters are implied.

## 8. Difficulty sources and restrained AI content

The [reference catalog](reference-catalog.md) ties every hard-and-above operation
to a named public challenge and documents the retained insight. Known solutions
are allowed. Familiarity can fairly help a participant; discovery need not be
novel research. Public source material is an authoring advantage and a
calibration input, not evidence that an adaptation will still occupy an elite
operator for hours.

The [MITRE emulation library](https://github.com/center-for-threat-informed-defense/adversary_emulation_library)
provides realistic sequences and intermediate purposes. menuPass is especially
useful for provider-to-customer trust abuse; APT29 and OilRig inform selected
collection, persistence, and data-targeting episodes. ATT&CK Enterprise and
ATT&CK for ICS describe behaviors. None assigns CTF difficulty. Cinder Typhoon
remains fictional; these influences do not claim a single historical campaign.

AI-target work is deliberately easy or medium. Four KeplerOps operations and
one ARWC data operation cover exposed assistant configuration, retrieved-content
trust, tenant isolation, and unsafe code-completion integration. These are
application-scale failures with small artifacts. No model training, expensive
extraction, gradient search, or GPU competition is required. No generative
model is a mandatory entry or reservoir gate. The provided participant agent
and the vulnerable in-story assistant are separate cost and reliability budgets.

## 9. Pacing, scoring, and session continuity

Do not budget sixteen hours as a single solve-time sum. The event needs enough
breadth for different specialties, enough depth for very strong assisted
players, and useful next work for people who stall. Measure time from fresh
access, including discovery and agent interaction. Route length, individual
solve times, available alternatives, and concurrency all affect experience.

Use the following editorial checks before accepting the portfolio:

- At each ordinary access plateau, expose at least three useful leads spanning
  two principal activities. This is a target to verify in the playable graph.
- Follow a major pivot with short, legible rewards before the next demanding
  boundary. ARWC's easy work is distributed through data, maintenance, telemetry,
  and engineering interpretation, not confined to its arrival screen.
- Make one substantial expert investigation available from the initial desk,
  and several from corporate ARWC access. A long easy chain is not a difficulty
  mechanism.
- Alternate investigation, exploitation, construction, and observable effects.
  Avoid more than two consecutive mandatory operations whose only payoff is
  another credential.
- Check that fast assisted specialists retain worthwhile unresolved work after
  a full rehearsal. Add genuinely different depth if the ceiling collapses;
  do not stretch the event with retries, waiting, or bulk artifact searches.

Award individual points and separately show campaign milestones. Prototype with
static tier bands, then set operation point budgets using measured effort and
insight. Dividing an exploit into more flags must not multiply its reward. Balance the
ordinary entry routes by their whole-operation work and common campaign
milestone, not by forcing an equal number of submissions. The milestone itself
does not award extra points.
Do not equate campaign completion with overall scoreboard victory or use a
score total to grant access. Introductions, useful service documentation, and
discovery records belong naturally to the scenario; they are not a purchasable
hint ladder. Do not publish solution hints or fourth-wall commentary inside the
scenario. Infrastructure recovery is free and grants no target authority.

Day two begins with the player's own access/evidence summary, retained artifacts,
and unfinished leads. Session recovery must preserve earned capabilities.
A talk, a disconnected browser, or an agent context reset should not erase work.
Save the next intended action and its purpose alongside access. Optional private
rollover/shift rehearsals change only their own projected state.
The available play window is approximately sixteen hours; do not silently turn
an overnight autonomous run into extra competitive time.

State-changing work and proof belong to individual players. No first solver
opens a gate for everyone. Bulk exploitation must not destroy another player's
route. Independent grading accepts equivalent successful methods and verifies
scope and effects, rather than matching one exploit transcript.

## 10. Design-stage boundary

This revision includes all [240 individual challenge briefs](challenges/README.md)
across seventy operations, alongside the main campaign capability graph and
player-experience contract. The briefs cover sixteen training challenges,
104 at KeplerOps, and 120 at ARWC.

Each document follows the [shared template](challenges/TEMPLATE.md): a
player-facing description, story purpose, prerequisites and starting position,
completion and downstream use, and difficulty/source references. All 240 cards
now have complete technical drafts. The inherited empty hint headings are not a
plan to deliver hints.
Discoverability must be authored through
in-world records and ordinary interfaces under the
[experience contract](player-experience.md#how-choices-become-legible).

The full-scenario design corrections and native SDL are complete through the
ARWC hand-build gate. The next authorized work follows the [calibration plan's
golden-range gates](calibration.md#1-design-and-golden-range-gates): progressive
hand-building, integration tests, and initial playtest observation. Tests must
include ordinary entry, the bounded process fiction, release rollover, cloud
trust composition, constrained control, reporting, partial progress, and
returning on day two. No prototype preceded the design gate for its scope.

The event layer supplies optional short dispatches, unscored recognition of
varied milestones, and a closing debrief. Technique discussion and agent help
are allowed; live flags, player credentials, and current-instance solutions
remain individual. The [event contract](player-experience.md#a-shared-event-with-individual-progress)
keeps this compatible with individual state and sixteen continuous play hours.

### Response to the accepted second review

| Finding | Concrete draft-3 response | Remaining evidence |
| --- | --- | --- |
| R1: Narrow upper-tier emphasis | New cloud/release and process operations add eleven hard-or-higher allocations in those principal categories. | Their actual assisted depth and professional relevance, especially the authored extensions. |
| R2: Weak optional consequences | Each new operation has a local conclusion; the major existing investigations have explicit campaign uses or completed outcomes. | Whether players understand and remember them. |
| R3: Inflated stage counting | Twenty allocations merged or removed; twenty new card contracts replace them; chapter sizes vary. | Distinct work in all surviving cards and measured operation effort. |
| R4: Overbroad W19 substitution | Mapping, allocation, revision, envelope, mode, and consequence plan have explicit sources. W19 replaces mapping only. | Runtime contracts and medium cognitive closure on the ordinary knowledge route. |
| R5: Unclear sustained choices | Four access-position lead sets, useful stopping points, optional follow-on objectives, and purpose-aware day-two recovery. | Whole-event trajectories across the actual audience. |
| R6: Abstract co-hacking experience | Worked W09 episode with delegation, evidence, a recoverable mistaken assumption, and a visible outcome; training teaches that loop. | Observation with the provided agent and actual first-time players. |
| R7: Weak shared event identity | Optional dispatches, varied milestone recognition, personal receipts, published help rules, and closing debrief. | Whether the room feels connected without interrupting individual play. |
