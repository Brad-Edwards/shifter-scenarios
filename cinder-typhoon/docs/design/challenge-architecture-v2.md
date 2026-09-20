# Cinder Typhoon challenge architecture: draft 2

Design date: September 18, 2026. This revision responds to the accepted
[adversarial review](adversarial-review.md) and the subsequent design constraints.
The [first draft](challenge-architecture-v1.md) is preserved. This is a challenge
architecture, not a topology, implementation specification, or playtest report.

Read with the [operation portfolio](operation-portfolio-v2.md),
[challenge reference catalog](reference-catalog-v2.md),
[threat inspiration](threat-inspiration-v2.md), and [calibration plan](calibration-v2.md).
The earlier [research](research-v2.md) documents Polaris and the design literature.

## 1. The central change

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

Retain **240 scored challenge slots**, grouped into **64 operation briefs**:
four training boxes, 28 KeplerOps operations, and 32 ARWC operations. A slot is
an allocation for a distinct achievement, not a finished challenge. An operation
usually contains three to five such achievements. The portfolio gives each a
purpose, principal activity, outputs, and source lineage where required.

This is a deliberately large content budget for sixteen hours. It is grounded
in the user's over-50-challenge Polaris event baseline, not the 38-row campaign
subset. Scaling that baseline by duration suggests a broad capacity range;
it does not establish a necessary number of flags or justify counting trivial
substeps. Polaris already assumed agents. Do not multiply it by a second generic
AI acceleration factor. See the [inventory reconciliation](research-v2.md).

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

The authoritative allocation is the table in the portfolio. Its distribution
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
| A01 | Exploit the importer's fetch behavior to reach a protected local registry configuration. | M | G03 | K06 |
| A02 | Recover usable package publication authority from that configuration. | M | A01 | K06 |
| A03 | Construct an altered compatible package and publish it to the consumed release channel. | M | A02, G02 | K26 |
| A04 | Cause ARWC to consume that package and demonstrate execution in its corporate connector. | M | A03 | K26 |
| B01 | Recover and use the support application's limited session. | E | G01 | K17 |
| B02 | Exploit an object-authorization flaw to bind a diagnostic job to the ARWC connector. | M | B01, G02 | K27 |
| B03 | Modify the diagnostic package through an exposed template/import boundary while preserving its expected interface. | M | B02, G03 | K27 |
| B04 | Deliver the package through the support workflow and demonstrate the same customer execution capability. | M | B03 | K27 |

Route A has seven scored prerequisites including its terminal challenge;
Route B has seven. These IDs select already allocated portfolio slots; they
are not eleven extra flags. Reading, construction, publication, and consumption
must be independently meaningful before retaining separate credit. In
particular, merge A01/A02 if token recovery is merely the same response twice.

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

## 6. ARWC progression and meaningful dependencies

ARWC opens corporate, data, and maintenance leads together. These expose easy
and medium work as well as optional advanced applications and artifacts. The
entry does not give control credentials or a direct gate command.

| Earned capability | One way to obtain it | Another way | What it enables |
| --- | --- | --- | --- |
| Corporate execution | G02 plus Route A | G02 plus Route B | Corporate exploration, reporting data, maintenance records, optional advanced targets. |
| Read-only OT visibility | Maintenance appointment and contractor access: W13 + W14, medium closure. | Recover the relevant read integration through W03 + W09, medium closure. | W17/W18 observations and deeper engineering leads. Neither route grants writes. |
| Accurate process interpretation | Reconcile W18 tags, W09 allocation data, and W21 project revision. | Recover equivalent evidence through W19's optional native-code investigation. | Identify the actual gate group, valid operating envelope, and economic consequence. |
| Usable control authority | Engineering utility exploitation: W28, hard, following W21. | Maintenance approval abuse: W26, hard/expert, following W13 and W15. | Attempt the release operation under the observed mode and process constraints. |
| Reservoir objective | Process interpretation AND one control-authority route AND W25 mode knowledge, then W30. | An alternative exploit may substitute only if it demonstrates the same live capabilities. | Actual opening of the intended gates and verified loss of usable reserve in the simulator. |

An AND join is appropriate when different knowledge and authority are both
necessary. It should combine complementary work, not collect unrelated flags.
An OR route must really substitute for a capability, with equivalent observable
scope. The architecture permits dependencies within an organization and across
conceptual security boundaries without choosing subnets or hosts.

Optional W07, W16, W23, W27, and W31 provide deeper challenges; none is a required
ARWC entry dependency. Likewise the ending does not require clearing all ARWC
chapters. Design the read-only OT routes to introduce the domain accessibly,
then increase difficulty at control. Novices can obtain meaningful OT successes
without being promised the ending.

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
| Water on paper | Joining the allocation ledger to the engineering revision reveals that a healthy report does not establish usable reserve. | An accessible data success explains why this specific company is the target. |
| The first live trace | The player correlates a harmless documented test with telemetry; a copied report no longer suffices. | OT becomes an understandable process, with fresh easy wins after the pivot. |
| Two versions of the same plant | The project viewer, retained engineering image, and current observations disagree for a discoverable reason. | Earlier supplier clues pay off; hard work has a concrete question. |
| The gates move | The live process confirms the opening, the reserve trend changes, and the economic consequence appears. | The final exploit receives a clear payoff without a surprise extra elite exam. |

The recurring maintenance ticket is a breadcrumb, not a riddle whose prose must
be decoded. Reuse names and identifiers to make connections recognizable.
Optional conclusions include compromising a release preview, extracting an
operations dataset, recovering a hidden diagnostic function, and controlling a
maintenance workflow. Someone who never reaches the gates should still finish
several episodes worth describing afterward.

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

The [reference catalog](reference-catalog-v2.md) ties every hard-and-above operation
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
insight. Dividing an exploit into more flags must not multiply its reward.
Do not equate campaign completion with overall scoreboard victory or use a
score total to grant access. Record hints consistently; introductory explanations
and recovery from infrastructure faults should be free. More revealing hints
can affect the operation's score under a published, uniform rule.

Day two begins with the player's own access/evidence summary, retained artifacts,
and unfinished leads. Session recovery must preserve earned capabilities.
A talk, a disconnected browser, or an agent context reset should not erase work.
The available play window is approximately sixteen hours; do not silently turn
an overnight autonomous run into extra competitive time.

State-changing work and proof belong to individual players. No first solver
opens a gate for everyone. Bulk exploitation must not destroy another player's
route. Independent grading accepts equivalent successful methods and verifies
scope and effects, rather than matching one exploit transcript.

## 10. What remains before topology

This draft makes progression, product role, source selection, and experience
concrete enough to review. It does not claim 240 validated challenges, measured
completion rates, or a proven nation-state-operator difficulty ceiling.

Before topology selection, validate the two entry routes, one accessible ARWC
data episode, the process model, and representative hard/elite adaptations.
Then finish the challenge-level dependency and scoring inventory from the
operation briefs. Reject repeated insights and count shortfalls openly. The
[calibration plan](calibration-v2.md) defines this work and its acceptance evidence.

### Response to the accepted review

| Finding | Revision | Remaining evidence |
| --- | --- | --- |
| F1: False route choice | Explicit alternative supplier and OT-visibility routes; causal AND joins retained. | End-to-end solves and alternate-route evaluator checks. |
| F2: Repeated authority work | Separate activity/category ledger; native exploitation, reconstruction, data, and process tasks; explicit overlap review. | Blind repetition audit of actual challenges. |
| F3: Undefined product | FieldLink has a specific maintenance/reporting role and a bounded customer effect. | Consistent artifacts across the campaign. |
| F4: Missing intermediate payoffs | Seven scenes and multiple optional episode endings. | Player recall and enjoyment interviews. |
| F5: Unproven, late elite work | Early optional exploit surface; named difficulty precedents and retained mechanisms. | Fresh assisted specialist solves; labels may change. |
| F6: Finale becomes another wall | Difficulty resides in gaining and using control; visible consequence follows the successful operation. | Full ending rehearsal. |
| F7: Unsupported precision | Allocation remains a capacity hypothesis; old 68-step route and exact elite finish-time claims removed. | Distinct-work and duration evidence. |
| F8: Agent obscures player agency | Objectives, evidence, and visible consequences define the player loop. | Observe users delegating and recovering context. |
| F9: Unresolved water story | Bounded raw-water release with an explicit volume/economic model. | Water/controls subject-matter review. |
| F10: Incomplete experience testing | Fun, choice, memory, repetition, and model reliability enter the calibration plan. | Actual playtests, not architectural assurances. |
