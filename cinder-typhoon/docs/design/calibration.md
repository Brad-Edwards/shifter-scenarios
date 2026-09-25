# Calibration and production criteria: draft 3

Status: proposed validation plan, September 18, 2026. No Cinder Typhoon challenge
has been implemented or playtested. The current evidence supports architecture
and source selection, not measured participant outcomes. See the
[architecture](challenge-architecture.md), [portfolio](operation-portfolio.md),
and [source catalog](reference-catalog.md).

## 1. Design and golden-range gates

The current work is design correction, not realization. Complete the scenario's
SDL using native RAE contracts before starting a golden range. Resolve intended
authority, asset ownership, progression, and contradictory requirements first;
native parser/validator/processor success is necessary but does not prove that
the authored design is complete or playable. A suspected missing upstream
semantic is a blocker to discuss with the scenario owner, not permission to
introduce a scenario-specific SDL dialect or adapter interpretation.

Use the following sequence. Later materialization implements parts of the
complete scenario SDL progressively; it does not replace that SDL with a pilot.

| Stage | Required work and exit evidence |
| --- | --- |
| 1 | Resolve full-scenario ambiguities, design gaps, contradictions, and asset ownership; replace custom SDL semantics with native RAE contracts; validate with the pinned upstream validators and processor. |
| 2 | Finish the complete tutorial design, including mechanisms, normal workflows, assets, proof, in-world discoverability, recovery, and player-facing continuity. Run design and SDL tests. |
| 2.5 | Hand-build the tutorial golden range from the approved design; it becomes the source of bakes. Test ordinary workflows, intended and alternate solves, negative cases, and reset. |
| 3 | Finish the complete KeplerOps design and its tutorial/campaign joins. Run design and SDL tests. |
| 3.5 | Extend the same golden range with KeplerOps. Run integration tests and record initial playtest observations. |
| 4 | Finish the complete ARWC design and its campaign joins, including the reviewed process quantities. Run design and SDL tests. |
| 4.5 | Extend the golden range with ARWC. Run integration tests and record initial playtest observations. |
| 5 | Run full integration testing and playtesting across the complete campaign. |

Testing applies at every stage. The questions below are acceptance targets for
the appropriate design and golden-range stage, not authorization to start
isolated realization before the design gates are satisfied.

| Acceptance focus | Question it must answer |
| --- | --- |
| Six-achievement package and seven-achievement diagnostic entry routes | Does each complete route remain medium with the provided agent? Does it create actual customer execution while preserving the connector interface? Can each route stand alone? |
| K01/K02 and W09 | Can a first-time participant get an intelligible early win, change something meaningful, and finish a memorable local episode? |
| K04 and K12 | Do the constrained native and browser chains retain real depth when agents can consult public solutions? Are they available early enough? |
| W16 and W23 | Can the timing and estimator candidates deliver reproducible, fair technical difficulty without infrastructure noise or excessive cost? |
| One read-only OT route and W17/W18 | Can an assisted participant new to OT understand the process and obtain meaningful observations before control work? |
| W18/W19, W21/W25/W29, then W28 through W30 | Does each mapping alternative retain the independent allocation, revision, envelope, mode, and consequence evidence? Does hard control lead to a satisfying effect? |
| K22/K24 | Can small-model behavior stay cheap, explainable, and reliable under simultaneous play? |
| K29, with source-aware testers | Does release continuity require a separate capability after the ordinary signed delivery? Can the old credential fail without breaking the main campaign? |
| K30/K31 | Do backup authority and workload/label composition preserve meaningful cloud reasoning? Can an experienced cloud operator find substantive work without a binary-exploitation detour? |
| W33/W34 | Do process constraints force useful planning and feedback? Does reporting deception change a planning decision while independent telemetry proves the bounded physical effect? |

Have a water/controls specialist review the volume model and bounded consequence
before writing extensive engineering material. Fix any physics/story contradiction
before it becomes embedded in clues and score evaluators.

## 2. Test people and agents as one operating system

Recruit fresh testers across novice, intermediate, advanced practitioner, and
specialist experience, with variation in agent familiarity. Do not use employer,
clearance, or job title as evidence of a tester's tier. Include strong offensive
operators and experienced competitive exploit/reverse-engineering specialists;
neither group automatically represents the other.

All primary tests use the actual provided agent, tool access, documentation,
network-search policy, and resource budget intended for the event. Test optional
BYO configurations as a sensitivity check, not as the baseline required to
finish. Authors and people who have read the new solutions are useful for
correctness checks but not fresh-player timing.

An initial pilot of several testers per cohort diagnoses problems; it does not
estimate a 300-person completion distribution. Expand the sample after changes,
using new testers for discovery-time measures. Report sample size, prior
familiarity with the source challenge, staff interventions, agent version, elapsed active
time, waiting time, retries, and whether the player finished.

Unfinished attempts are observations, not discarded bad data. Retain the time
and point of abandonment. Do not report only successful solve times, or infer
whole-event duration by adding medians from different people and branches.

## 3. Distinguish five tests of difficulty

1. **Author correctness:** a complete solve from reset establishes that the
   mechanism and evaluator work. It establishes no audience difficulty.
2. **Fresh assisted discovery:** the tester sees normal participant material
   and can use the provided agent and public research. This is the primary tier
   and pacing evidence.
3. **Source-aware transfer:** give another tester the original public writeup.
   Measure what still requires adaptation. This checks whether the claimed
   upper tier collapses into renaming a few constants.
4. **Strong autonomous baseline:** let a capable agent attempt the operation
   with the same access and budget. Its success is allowed. Use the result to
   calibrate depth, not to design arbitrary restrictions against automation.
5. **Alternative-path review:** a fresh attacker looks for shorter valid routes,
   exposed proof material, broad credentials, and ways to claim effects without
   causing them. Accept legitimate alternate solves; repair grading failures.

For every hard/expert/elite card, retain the reference mechanism, original tier,
our proposed conditional tier, actual tester evidence, and the principal insight.
A high-tier name without a reproducible demanding task fails. Do not keep an
elite label merely because a source was Insane in 2024.

## 4. Verify dependency closures, not attractive diagrams

The [entry-route ledger](entry-routes.json) records the ordinary supplier paths.
The [capability ledger](capability-routes.json) records the main ARWC evidence
and authority joins, including the limited W19 substitution. The validator checks
acyclicity, ownership, alternative closures, mandatory evidence, and declared
ceilings. Capability nodes are not additional flags. This proves properties of
the **design ledgers**, not runtime reachability or cognitive difficulty.

When expanding the rest of the portfolio, record every prerequisite as a
specific challenge output or supplied artifact. Distinguish AND from OR, and
show whether a dependency gives evidence, visibility, identity, execution, or
control. No generic instruction to complete a whole organization may replace
that contract.

For each entry and OT-visibility route, test from the genuine starting state
with all unused branches untouched. Remove the alternative branch entirely in
a fixture and verify that the chosen route remains possible. Verify that no
hidden hard task, AI behavior, time-limited event, or inaccessible tool supplies
a mandatory ingredient.

Record cumulative investigation burden. Several medium-looking cards can still
form a hard route if their join is obscure. Use the architecture's compact
customer record, compatible package example, and clear consumer feedback to
keep the shared join within the ceiling. Do not solve this with a free access
code after a player stalls.

## 5. Measure experience explicitly

| Question | Evidence to collect | Failure that prompts revision |
| --- | --- | --- |
| Does a newcomer start well? | Time to first meaningful effect; ability to explain what the agent changed. | Setup, unclear objectives, or command syntax consumes the opening. |
| Is there a real choice? | At each access plateau, ask the player to identify useful next leads and choose one. | Every path eventually demands the same blocked specialty, or three labels hide the same work. |
| Does the story help? | Ask what FieldLink does, why its customer consumed the package, and why ARWC loses usable water. | Correct flags coexist with an incoherent understanding of events. |
| Is it enjoyable? | Short ratings plus an open account of the best and worst moment after an episode. Observe frustration and voluntary continuation. | Technically correct tasks feel repetitive, arbitrary, or mostly like waiting. |
| Is the player exercising agency? | Observe objective selection, delegation, verification, and recovery after an agent mistake. | The interface presents only an opaque solve transcript with no understandable consequence. |
| Is it memorable? | After a break, ask which moments the participant remembers without showing titles. | Recall consists only of credentials, flags, and a final screenshot. |
| Does the upper tier hold? | Fresh assisted specialist attempts, including public-solution access. | Supposed elite work is routinely completed by a generic agent workflow without substantial adaptation. |
| Is the ending rewarding? | Observe the live gate effect and post-operation explanation. | A final arbitrary riddle, unresponsive display, or ambiguous physical effect follows the main exploit. |

The proposed opening targets are a meaningful win within ten minutes after a
working session starts and several wins in thirty minutes. Test them with
novices. They are local service objectives, not a promise that every novice
reaches ARWC or completes the reservoir campaign.

Run a full two-day rehearsal with breaks and context recovery. Track active
work, stalls, available alternatives, and remaining worthwhile content. Require
substantial unresolved optional work for fast assisted specialists. If the
portfolio is exhausted early, add different deep mechanisms; do not inflate
flag counts or insert dead time. Conversely, repeated blocked paths with no
satisfying side work indicate inaccessible breadth, even when 240 slots exist.

Use the [player-experience contract](player-experience.md) as a testable script:
at each earned stage, ask what question the player wants to investigate, why,
and what would count as a satisfying conclusion. Test an interrupted W09
investigation and an early W30 finish. Neither should leave the participant
without an intelligible next objective. Do not require a human explanation as
a scored condition; interviews are evaluation of the design.

Test K29/W33/W34 on their private projected checkpoints. Reset or advance their
scenario time while checking that main-campaign credentials, evidence, and
scores persist. A failed optional experiment must not remove ordinary access.
Confirm that follow-on operations have worthwhile remaining work after their
source exploits: W34 receives no credit for simply rerunning W23 or W27.

For W33, reject any model solved by always choosing the largest setting, using
one fixed schedule across all cases, or exploiting the judge's data. Check that
the published bounds permit more than one valid plan and expose useful failure
feedback. For W34, verify both a changed planning decision and independently
measured process truth; cosmetic dashboard changes cannot satisfy the objective.

## 6. Prove effects and preserve individual progress

Each scored card needs a minimal proof contract. It must specify the legitimate
starting capability, the new effect, an independent observation, accepted
alternative methods, and reset behavior. For data challenges, use actual scoped
recovery, not a phrase the agent can guess from the story. For state changes,
verify state rather than the player's claim. For the ending, observe gate
position, outflow, and volume balance outside the compromised reporting path.

Keep scores, writable challenge state, and reset scope separate between players.
A shared read-only artifact may be fine; another player's exploit must not
complete or destroy the participant's work. Verify that reset preserves previous
achievements while removing the attempted operation's mutable effects.

A provided-agent context reset must not remove earned credentials and evidence.
Test switching sessions, pausing for a talk, reconnecting on day two, and choosing
a different branch after a failed attempt. Agent-generated summaries are useful
but must distinguish observed facts from hypotheses.

## 7. AI reliability and cost

The vulnerable assistant is a separate target from the participant's agent.
Test both separately and together. The ATLAS budget and exclusions are specified
in [threat inspiration](threat-inspiration.md#atlas).

For each model-dependent task, measure intended exploit success per fresh
session, variation between reasonable prompt formulations, retry counts, queue
latency, and cost. Use the exact frozen model/configuration and tool contract.
Do not depend on a magic sentence that happens to work once. An offline
reference replay and a live semantic exploit are different tests.

Nineteen successes in twenty trials is a useful early screen, not release
reliability evidence. At a true 5% independent failure rate, 300 first attempts
would average fifteen failures. Even zero failures in 300 independent trials
only gives an approximate 95% upper failure bound of 1%; dependence between
trials makes that evidence weaker. Track and diagnose failures rather than
promising determinism from a temperature setting.

No mandatory campaign gate depends on generated output. For optional AI tasks,
provide clear retry/reset behavior and discoverable in-world records, and grade independent tool/data
effects. If a generative task remains unstable, simplify or replace it before
release. Do not make staff improvisation the expected solve mechanism.

The proposed vulnerable-model ceiling is 36,000 calls across participants,
before reserve. Measure token volumes, typical and worst-case spend, and peak
concurrency against a concrete hosting option before calling it inexpensive.
Cache reusable fixed context where appropriate, keep contexts small, and use
no training jobs. Freeze a separate budget and fairness policy for the provided
participant agent and optional BYO agents.

## 8. Production release evidence

At each design gate, resolve the relevant acceptance questions above, capture
selected source revisions, and validate the process story. Then use the staged
golden range to test the approved design. An unresolved design is not permission
to start an isolated realization experiment.
Before the event, require:

- A complete challenge-card inventory with honest accepted counts, category and
  difficulty distributions, source lineage, and no duplicate-work padding.
- Independent full solves of ordinary routes, representative alternate methods,
  and all hard/elite operations; named owner and reviewer for every operation.
- Fresh-player data supporting local pacing and difficulty, including incomplete
  attempts and source-familiar testers.
- A full event rehearsal demonstrating enough breadth/depth and reliable day-two
  recovery. Do not publish invented percentile completion forecasts beforehand.
- Independent proof and isolation checks, load tests for 300 simultaneous users
  plus measured burst headroom, and reset/recovery rehearsals.
- Frozen in-world discovery records and scoring. Operation budgets prevent extra flags from creating
  disproportionate points; infrastructure recovery never costs participant points.
- A costed agent/model plan, failure handling, and staffing based on observed
  support demand rather than a guessed organizer-to-player ratio.

Source-inspired does not mean source-validated at this event's scale. Difficulty,
fun, cost, and reliability remain separate acceptance decisions. A failure in
one must lead to a concrete revision, not a stronger adjective in the brief.
