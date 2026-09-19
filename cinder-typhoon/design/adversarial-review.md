# Adversarial review of the first challenge architecture

Review date: September 18, 2026. Scope: the first architecture, operation
portfolio, research, and calibration documents. This is a design critique,
not a playtest result. The reviewed [architecture](challenge-architecture-v1.md),
[portfolio](operation-portfolio-v1.md), and [calibration plan](calibration-v1.md)
are preserved as version 1. These findings refer to those snapshots. The current
documents contain version 2; their revision ledger tracks the response.

## Verdict

The draft has a credible technical progression and a useful validation plan.
It does **not yet establish a sufficiently distinctive, varied, or memorable
sixteen-hour experience**. I would revise it before selecting the full topology
or treating the family allocations as an authoring commitment.

The strongest idea is the supplier compromise becoming a water-company intrusion
through actual customer consumption. The weakest recurring idea is obtaining
another narrowly scoped authority before proceeding to another boundary. Both
appear repeatedly in the same document, and the second currently dominates the
description of play.

| Review question | Judgment |
| --- | --- |
| Is it interesting? | Several strong ingredients, especially release consumption and process interpretation. Too many operations remain interchangeable descriptions of access progression. |
| Does it align with professional guidance? | Substantially on technical construction and calibration. Partially on choice, variety, and pacing. The exact numerical allocation is not established by the sources. |
| Does it show taste? | It shows restraint about consequences and care about credible effects. It needs more editorial selection, contrast, and memorable specificity. |
| Does it tie to the story? | The overall causal chain does. Many individual operations could move into a different enterprise scenario with little change. |
| Are the distributions justified? | The rising phase gradient is clear. Category balance, effort distribution, reachable choices, and emotional pacing remain unestablished. |
| Will it be fun and memorable? | Plausible, but the draft does not yet support confidence. It defines how success is verified much better than how success feels. |

These findings do not argue for easier final operations, guaranteed completion,
or a return to a small challenge board. The audience and the sixteen-hour
requirement remain unchanged. Missing implementation and playtests are normal
at this stage; contradictions and missing experience decisions can be addressed
now.

## Evidence and review method

Re-read the four design documents and compared them with Polaris's architecture,
hidden attack path, briefing, and final-controller design. Rechecked primary
professional guidance and added references specifically concerned with player
experience and distribution.

The numerical review recomputed all tier counts and proposed score weights,
and traced the prerequisite closure of both capability diagrams. The experience
review asks what the player actually does, what changes as a result, why the
action belongs in this story, and what someone would remember afterward.

Findings distinguish directly observable design facts from judgments about
likely experience. No enjoyment, completion-rate, or elite solve-time claim is
presented as measured.

## Professional comparison

| Reference | What transfers | What the draft has not established |
| --- | --- | --- |
| SEI's professional challenge-development guidance | Match the audience, support meaningful multipart progress, award points for difficulty and effort, and use independent testing. | A five-tier table and exponentially increasing points are not evidence of calibrated difficulty or effort. [Report, sections 3 and 4.7](https://www.sei.cmu.edu/documents/1299/2022_005_001_888602.pdf) |
| Plaid Parliament of Pwning's organizer guidance | Maintain useful problems to work on, use independent complete solves, and make problems enjoyable and technically worthwhile. | The draft promises choices but mostly specifies mandatory branch convergence. Its upper-tier concepts still need a compelling technical insight. [Organizer guidance](https://raw.githubusercontent.com/pwning/docs/master/suggestions-for-running-a-ctf.markdown) |
| rCTF's challenge-design guidance | Balance categories and difficulty; make each problem teach or exercise a worthwhile idea. For a conventional jeopardy event, it suggests one or two easy, two or three medium, and one or two hard tasks per category. | The draft counts by phase and invented difficulty tiers, without a category-by-difficulty inventory. That is not a demonstrated match to the recommendation. [Challenge design](https://rctf.osec.io/meta/running-a-successful-ctf/#challenge-design) |
| SANS Holiday Hack Challenge 2025 | Its announced design distinguishes short confidence-building challenges from larger capstones and gives story/world presentation explicit attention. | The draft lacks a concrete sequence of smaller payoffs and major scenes. Holiday Hack's challenge skipping and long availability do not transfer to this earned-access event. [Organizer description](https://www.sans.org/cyber-ranges/holiday-hack-challenge) |
| SANS Core NetWars | A professional range can combine multiple disciplines with a distinctive fictional setting. Serious security content does not require anonymous surroundings. | Our enterprise and OT functions are clearer than their personalities or memorable situations. NetWars' specific setting and six-hour format are not templates for this event. [Official description](https://www.sans.org/cyber-ranges/core-netwars) |
| Mechanics, Dynamics, Aesthetics | Analyze how rules and interactions produce experiences such as discovery, challenge, narrative, and expression. | The draft has extensive mechanics and testing prescriptions, but comparatively little specification of the desired experience. This is a design lens, not empirical proof that a particular story will be fun. [Original paper](https://www.cs.northwestern.edu/~hunicke/MDA.pdf) |

There is no single professional difficulty histogram to copy. For example,
SANS Skills Quest's published mix is 56% beginner, 37% intermediate, 6% advanced,
and 1% extreme, for a six- or twelve-month learning product. That describes a
different purpose, duration, and difficulty taxonomy; it is neither a benchmark
for this event nor grounds to remove its elite content.
[Official product sheet](https://assets.contentstack.io/v3/assets/bltabe50a4554f8e97f/blt1bda22e49223c5d0/skills-quest-by-netwars-inside-challenges)

## Distribution audit

The current allocation and proposed weights produce:

| Tier | Slots | Share of slots | Relative weight | Share of all available points |
| --- | ---: | ---: | ---: | ---: |
| Foundation | 36 | 15.0% | 1 | 3.4% |
| Applied | 72 | 30.0% | 2 | 13.8% |
| Advanced | 76 | 31.7% | 4 | 29.1% |
| Expert | 42 | 17.5% | 8 | 32.2% |
| Elite | 14 | 5.8% | 16 | 21.5% |

Percentages are rounded independently. The total relative point pool is 1,044.
Expert and elite slots together are 23.3% of challenges and 53.6% of available
points. ARWC holds 50% of the challenges and 66.3% of available points.

This is a deliberate-looking emphasis on depth, and it may suit the event.
It is not automatically excessive or sufficient. Score concentration is not
the same as score earned by any participant, and points per unit of actual
effort are still unknown.

The phase gradient is also visible: foundation/applied slots are 100% of
training, 61.5% of KeplerOps, and 23.3% of ARWC. Expert/elite slots rise from
0% to 11.5% to 36.7%. That satisfies the intended *direction* of progression.

Four important distributions remain missing:

1. **Technical work:** application exploitation, identity, cloud, code review,
   reverse engineering, artifact/traffic analysis, data work, and process control.
2. **Player activity:** discovering, choosing, exploiting, constructing,
   experimenting, interpreting, and enjoying the consequence of a success.
3. **Effort:** short achievements, medium operations, and sustained research,
   measured after prerequisites and allowing for agent parallelism.
4. **Reachability:** the variety and difficulty of work available from each
   earned position, including immediately before difficult gates.

The technical categories should serve this scenario. Equal quantities of web,
crypto, reverse engineering, and binary exploitation would be another arbitrary
constraint. What is needed is a defensible mix, with different forms of work
available as players progress.

The 240 count remains a plausible capacity hypothesis based on the user's
Polaris baseline. Neither that scaling nor these percentages establishes 240
distinct good challenges. Seventy-one operation labels are also not yet
seventy-one differentiated experiences.

## Findings requiring revision

### F1: The promised route choice is not expressed in the graph

**Priority: high. Confidence: high.** See architecture sections 5–7 and both
capability diagrams.

Under their stated AND semantics, the prerequisite closure of K8 includes all
eight KeplerOps families. The closure of W10 includes all ten ARWC families.
This does not require every optional operation or flag, but every family
contributes to the mandatory skeleton. No explicit alternative capability path
appears in either diagram.

The diamonds permit different work order and agent parallelism. They do not
by themselves provide a way around an unsuitable specialization or a blocker.
The prose promises more agency than the structure demonstrates.

AND gates are legitimate: Polaris itself joins lab recovery and blackout.
The concern is their repeated use across a much longer campaign, coupled with
a promise of substantive route choice. Exhausting one branch still leaves the
other as the only way forward.

**Revision:** retain major story gates, but specify selected alternative ways
to earn a required capability. For example, release authority could come from
a compromised assistant workflow or a comparably demanding provenance flaw.
Both must still result in a working, customer-consumed release. Early deeper
discoveries can provide legitimate shortcuts rather than only extra points.
Do not replace access requirements with automatic unlocks.

### F2: Repeated authorization work threatens the variety of play

**Priority: high. Confidence: high about repetition; untested about enjoyment.**
See the K2/K4/K5/K6/K7 and W1/W2/W4/W5/W8 portfolio rows.

Much of the portfolio repeats a similar sequence: discover a principal,
determine its scope, cross another boundary, and verify the resulting access.
The underlying technologies differ, but the described decisions and rewards
often do not. Repeated references to a separate or distinct boundary assert
variety without identifying the interesting difference.

K3 build-input/cache work overlaps K4 cache isolation. K7 consumer identity
approaches K8 tenant binding. W8 session continuity, W9 changed conditions, and
W10 reliable-operation variants risk counting neighboring aspects of one
control problem as separate experiences. The portfolio acknowledges some of
this overlap but has not resolved it.

**Revision:** give each operation a principal insight and player action. Merge
operations that need the same insight even if they touch different services.
Use the freed capacity for different work: reconstructing an incident artifact,
building an effective tool, testing a process hypothesis, exploiting application
behavior, or conducting an original code-level attack. Preserve enough scope
for the event; do not preserve every allocation row at the expense of quality.

### F3: The setting does not yet generate enough of the challenges

**Priority: high. Confidence: high.** See architecture sections 5–6 and the
portfolio's capability-output descriptions.

The company-to-company transition is causally strong. However, the draft does
not identify what KeplerOps' product actually does for ARWC, why its integration
has its particular permissions, or why the assistant participates in the release
workflow. Those are important challenge-architecture decisions because they
explain both access and constraints.

Replacing ARWC with another enterprise would leave much of W1–W5 intact.
That is reasonable for some enterprise fundamentals, but too much of the story
currently depends on the final process-control setting to give earlier work
its identity.

The narrative brief available here is an overview. This review does not assume
that no fuller narrative exists elsewhere with the user. It identifies the
story functions the challenge architecture still needs to express.

**Revision:** specify one credible supplier product and its legitimate purpose,
then let the existing narrative supply the people and pressures around it.
For example, a maintenance/data integration could explain corporate deployment,
customer records, support automation, and later engineering clues without
granting direct control of gates. This is a candidate connection, not a new
canonical product decision.

### F4: Story payoffs are concentrated too late

**Priority: high. Confidence: high about omissions; experience remains untested.**
See architecture sections 6 and 8 and calibration section 4.

The final reserve loss is specified in detail. Earlier story progression is
mostly described as discovering more specific information or gaining access.
There is no comparable specification of several memorable intermediate scenes,
chapter conclusions, recurring people, or callbacks.

Polaris's [mission architecture](../../polaris/design/architecture.md) asks
recognizable questions: who is the company, what is it building, how can the
opening be created, and how is control seized? Its
[final-controller design](../../polaris/design/assets/A13-brain.md) gives earlier
technical discoveries a visual and narrative payoff. The lesson is the
construction of anticipation and payoff, not copying its particular fiction.

If many players never reach ARWC, their experience needs satisfying completed
episodes inside KeplerOps. Otherwise the most memorable part of the advertised
story belongs to the small group least in need of encouragement.

**Revision:** author several major player-caused moments, with smaller
conclusions available at earlier depths. Give each an observable change and
a connection to earlier evidence. None requires granting the campaign ending
to an unfinished player.

### F5: The upper ceiling is both unproved and concentrated behind prerequisites

**Priority: high. Confidence: high about allocation; solve difficulty untested.**
See the allocation table and portfolio exemplars E1–E7.

All fourteen elite slots are in K7/K8 or W6–W10. The original native-exploitation
candidate is in W7/W8. Expert material begins earlier, but the most distinctive
upper-tier candidate requires substantial progression before it is available.
A specialist may spend a large fraction of the event obtaining the opportunity
to use the capability that makes them exceptional. Exact delays are unknown.

Further, phrases such as state-dependent behavior, provenance disagreement,
and authority composition identify promising problem classes. They do not
specify the non-obvious insight that will challenge an elite operator with an
agent. The draft correctly admits this; the review must not treat the labels
as completed design.

**Revision:** expose at least one serious expert/elite research opportunity
from an early earned foothold, with legitimate artifacts and observable
progress. Its success may improve the campaign position, while leaving the
water-company access gate intact. Prototype the actual technical insight and
an independent solve before allocating more upper-tier flags around it.

### F6: The ending risks withholding the feeling of mastery

**Priority: medium. Confidence: design risk, not an observed failure.** See
architecture section 6 and portfolio W8–W10/E7.

The current wording requires the finale to contain new elite synthesis after
players have already earned controller authority, a process model, and
engineering tools. That can be excellent if the final composition is the
operation's central insight. It can also become another artificial obstacle
inserted because the last click was not difficult enough.

An earned, difficult operation can culminate in a simple, satisfying action.
The climax needs a payoff after the demanding work. Independent effect
verification should establish that success, not become another long player
chore unless it introduces a distinct worthwhile problem.

**Revision:** locate the required upper-tier synthesis in the final operation
as a whole. Allow its successful execution to release tension. Keep optional
advanced variants available without making the ordinary success feel incomplete.

### F7: Precision in the allocation exceeds precision in the experience

**Priority: medium. Confidence: high.** See the 71-operation allocation,
68-milestone route budget, and 1:2:4:8:16 score weights.

Each campaign family has three to five operations and ten to sixteen slots.
This is a neat worksheet. The operation concepts are not yet specific enough
to explain why those particular quantities or relative point values are right.
The same uncertainty applies to the eight-to-twelve-hour elite route envelope.

The draft labels these provisional, which is correct. The practical risk is
that precise totals become production quotas and authors subdivide actions to
fill them. Also, free mechanism hints may change the calibrated difficulty
differently across families; weights must reflect the actual hint policy.

**Revision:** retain a large supply budget, but let concrete operations earn
their scored milestones. Audit category, effort, and accessible-work distributions
before fixing the per-family counts. Treat score concentration as a deliberate
choice to test, not a mathematical proof of balance.

### F8: Agent capability is addressed more fully than the experience of using it

**Priority: medium. Confidence: high about omissions.** See architecture
section 9 and calibration sections 1–2.

The agent is correctly included in difficulty, access, and capacity assumptions.
The training loop is useful. What remains vague is the experience of co-hacking
during later operations: what choices the player sees, how the agent presents
competing interpretations, and how an important discovery becomes intelligible
instead of disappearing inside a long tool transcript.

This is particularly important for newcomers, who can gain extensive access
without realizing why it mattered. High throughput can coexist with passive
spectating. That is a risk to test, not a reason to limit automation.

**Revision:** surface the current operational picture, useful alternatives,
and consequences of successful actions. Make exploration and experimentation
easy to direct. Preserve fully automated valid solves; do not force manual
commands, quizzes, or human-only bottlenecks to manufacture agency.

### F9: The physical consequence is still an unresolved story mechanism

**Priority: high before committing to OT challenges. Confidence: high.** See
architecture section 6's proposed receiving-basin model.

An engineered receiving system helps bound the fictional impact, but the
architecture still needs a credible explanation for why the release loses usable
reserves, creates costs, and causes restrictions. Merely placing the water in
another basin does not establish those consequences.

The draft flags the need for a subject-matter review. That remains necessary,
because telemetry, operating modes, gates, and the final objective all depend
on the same physical explanation. A process invented late to justify already
chosen flags would weaken both realism and the ending.

**Revision:** settle the minimal process and economic model with an appropriate
reviewer before choosing OT mechanics. Keep the user's bounded consequences.
Use visible changes to make those consequences understandable; escalating to
catastrophe would change the brief rather than improve this design.

### F10: The calibration plan cannot yet decide whether the event is enjoyable

**Priority: high. Confidence: high.** See calibration sections 4–5.

The proposed tests measure access, progress, timing, independence, and reliable
effects. They barely measure repetition, surprise, perceived agency, narrative
comprehension, or memorable success. A competent but tedious range could pass
most of them.

The AI-dependent gate's 19/20 screening rule also needs caution: it must not
become a release standard that accepts roughly 5% random failure. At that true
rate, 300 single attempts would have fifteen expected failures. That calculation
is illustrative; twenty tests do not establish the true failure probability.
Unexplained gate failures are especially damaging to enjoyment and confidence.

**Revision:** add experience-focused observation and interviews to the same
pilots, and keep stochastic victim behavior away from mandatory progress when
it cannot be made sufficiently reliable. More measurements of solve time alone
will not resolve either problem.

## What a more memorable experience would need

The following are proposed experience functions, not replacements for the user's
narrative or approved new story facts. They illustrate how to make the current
three-phase premise concrete without changing its scope.

| Position in the story | Player-caused moment | Why it could matter |
| --- | --- | --- |
| Training | A first real compromise, followed by an effect the player can immediately recognize with the agent's help. | Establishes confidence and a sense of control. |
| Early KeplerOps | An ordinary support or development exception becomes the opening into a useful internal capability. | Rewards reading the organization, not just collecting a secret. This can form a complete early episode. |
| KeplerOps climax | ARWC actually consumes the player's altered release; evidence arrives from the customer's side. | Makes the supply chain attack a visible event and changes the operational setting. |
| Early ARWC | Previously abstract customer records resolve into a specific maintenance relationship and water asset. | Pays off earlier investigation and makes the target feel like a place. |
| Later ARWC | A process observation changes meaning when combined with an earlier engineering clue. | Creates a fair, earned realization and rewards a maintained understanding. |
| Finale | Correct gate motion, reserve changes, and financial/restriction consequences appear coherently. | Makes completion perceptible and gives the technical operation closure. |

The important property is that hacking causes these moments. Cutscenes or long
briefings alone cannot supply them. At least some strong memories must be
available before the KeplerOps exit gate.

Give the existing narrative a small recurring cast with distinguishable roles:
the Cinder tasking voice, the developer whose environment is compromised, a
release/support owner, and an ARWC operations or engineering voice. They need
credible priorities and consistent evidence, not a large quantity of dialogue.
Competent people making understandable compromises are more convincing than
an organization populated by obvious fools.

One possible unifying theme is the gap between what a trusted signal proves
and what someone assumes it proves: a signed release, an assistant's authorized
tool action, or a valid process reading. Each should involve different player
work. The theme should connect the story without turning every task into the
same authorization puzzle.

For the live event, individual range state can coexist with a shared atmosphere:
spoiler-free milestone announcements, recognition of clever approaches, and
a common debrief. Those are presentation options, not collective unlocks or
team dependencies. Technical progress remains earned by each participant.

## Required experience checks in the next pilot

Ask and observe enough to distinguish productive difficulty from boredom:

- Can a participant explain their current purpose and identify a useful next
  action, even when the agent executed most of the technical steps?
- What felt materially different from the previous operation?
- Which discovery or action would they describe to someone over a break?
- Did a successful action visibly change their situation?
- Would they continue an optional operation if it awarded no points?
- Did they switch work because another lead interested them, because they were
  productively blocked, or because the current work felt repetitive?
- What satisfying episode can a non-finisher describe without claiming the
  final objective was achieved?
- At the overnight resume, do they remember the unresolved situation and want
  to return to it?

Use the responses as qualitative evidence with the existing timing and failure
data. Do not turn them into mandatory participant essays or invent precise
enjoyment percentages from a tiny pilot.

## Revision order

1. Define the supplier product's role and the major story payoffs, including
   useful conclusions before the final phase.
2. Reshape the capability graph to distinguish mandatory convergence, genuine
   alternatives, optional depth, and legitimate expert shortcuts.
3. Specify a memorable technical insight for each proposed operation; merge
   overlapping concepts and distribute different forms of work through the route.
4. Prototype early co-hacking, customer-side release consumption, an original
   upper-tier challenge, and the process finale. Test experience as well as
   correctness before expanding around them.
5. Reallocate the large challenge budget, difficulty labels, scores, and time
   envelopes using those results; then choose the full topology.

Preserve the strongest existing decisions: agents as baseline capability,
progressive difficulty, individual earned access, a selective ending,
player-specific mutable state, independent effect validation, and bounded
fictional consequences. The needed revision is substantial experience design
and sharper challenge selection within those constraints.
