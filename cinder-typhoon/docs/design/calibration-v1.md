# Cinder Typhoon calibration and acceptance plan

Status: proposed validation work, not completed testing. Read with the
[architecture](challenge-architecture-v1.md), [operation portfolio](operation-portfolio-v1.md),
and [research](research.md).

The acceptance question is whether **this person-agent combination has worthwhile
work over this event**, not whether the author can solve the challenges or an
agent can describe plausible solutions.

## 1. Separate the quantities being estimated

Record all of the following:

| Quantity | What it answers | Common measurement error |
| --- | --- | --- |
| Catalog size | How many distinct achievements are available? | Counting several answers returned by one action as several problems. |
| Operation effort | How much work does a coherent operation require? | Adding full task times that repeatedly include the same prerequisites. |
| Marginal challenge effort | What new work remains after predecessors? | Calling a trivial final read elite because access took hours. |
| Route time | How long does an actual fresh participant take to earn the ending? | Summing author estimates while omitting dependency and discovery work. |
| Available work | What useful choices remain from a player's current access? | Counting inaccessible optional content as protection against a stall. |
| Agent consumption | What compute and tool capacity is used? | Treating model queue time or exhausted credits as challenge difficulty. |
| Productive progress | Is the player making discoveries or useful experiments? | Treating every interval without a flag as failure. |

Measure active wall time, including productive agent execution and verification.
Record model/target outage and queue time separately. Breaks do not count as
solve time. Parallel tasks overlap in wall time; their summed work time does
not become the player's elapsed time.

For a route, record the actual critical sequence, overlap, and time spent finding
the route. A paper dependency graph and summed durations are useful diagnostics,
not a replacement for end-to-end play.

## 2. Test cohorts and configurations

Recruit actual first-time hackers, practicing generalists, and practitioners
capable of independently developing difficult attack chains. Include both high
and low agent fluency within those groups where possible. Record relevant
experience rather than inferring it from employer or clearance.

An initial full pilot of **six people per cohort** means eighteen individuals
and up to **288 participant-hours** over sixteen hours. This is a practical
starting sample for finding design problems, not a statistically representative
model of 300 attendees. Elite availability may require several smaller sessions.
Do not substitute challenge authors for the scarce independent elite testers.

Record the provided model/version, reasoning settings, tools, context handling,
concurrency, resource limits, and hint policy. Repeat selected demanding tasks
with a strong BYO workflow, including parallel agents where supported. A plain
chat model is not an adequate proxy for an integrated coding/hacking agent.

Run agent-only attempts as an additional compression test. They are useful for
finding tasks emptied by one broad prompt, leaked solutions, and unexpectedly
effective parallelism. They do not replace human pilots or establish what an
absolute beginner will experience.

## 3. Validation sequence

### Stage A: Paper and dependency review

For every operation, require the authoring contract in the portfolio. Classify
each challenge by **marginal** difficulty. Trace every required output to a
consumer, and identify dead-end clues, circular dependencies, duplicate work,
and optional branches that secretly contain mandatory facts.

Construct the complete dependency closure of each supported ending route.
Check alternate paths against the same operational success conditions. The
30+38 reference-route budget is only accepted after this exercise; it is not an
instruction to hide extra prerequisites to preserve the number 68.

Build an inventory ledger with phase, family, operation ID, challenge ID, tier,
required capability, output capability, scoring evidence, and validation state.
An allocated slot, authored brief, working challenge, and independently tested
challenge are four different states. Report them separately.

### Stage B: Prototype the difficult assumptions first

Prototype a small vertical slice that includes:

- The training-to-workstation experience for a genuine newcomer.
- A real build/cloud/assistant dependency and the supplier-to-customer transition.
- An ARWC corporate-to-maintenance boundary.
- A process-model investigation and stateful engineering/control operation.
- The final independent gate/reserve-loss validator.

Also prototype at least one upper-tier supplier operation and one upper-tier
OT operation. If these do not challenge strong assisted testers, writing another
hundred easy milestones will not fix the architecture.

These can be isolated services with seeded inputs. They test the difficult
mechanics without choosing the full scenario's network topology or deployment
products in advance.

Seeded checkpoints are appropriate for isolated tests of later tasks, provided
they contain only what a player would actually have earned. Supply necessary
context, not the author's solution. Do not treat seeded-checkpoint timings as
measured full-route timings.

### Stage C: Fresh attempts and full-route pilots

Test representative operations with fresh solvers before the full pilot. For
every elite operation, seek at least three independent strong attempts with the
actual agent conditions, including relevant specialist experience. Record
failures and partial progress, not just successful times.

Then run the complete two-day progression with the pilot cohorts. Include the
overnight stop/resume, normal hints, independent resets, and the real challenge
board. Observe whether participants choose meaningful branches and whether the
promised alternatives are actually available when needed.

An individual who previously saw an operation's solution is not a fresh solver
for that operation. A patched repeat can test correctness, but cannot recover a
clean estimate of discovery time.

### Stage D: Capacity and final revalidation

Exercise the expected mix of 300 concurrent player sessions, agent calls,
target interactions, resets, and submissions. Use measured pilot traces and
bursts, not a uniform idle-session count. Test shared services under overlapping
expensive operations, including release builds and victim-assistant calls.

After freezing content, rerun the most compression-sensitive operations with
the models and workflows expected at the event. Recheck when a material model,
tool, hint, or challenge change occurs. Rehearse the finale and all critical
gates against clean state after changes to their dependencies.

## 4. Acceptance and redesign criteria

The numbers below are initial design targets. They are not research-derived
universal thresholds or promises about attendance outcomes.

| Area | Initial acceptance target | Response if missed |
| --- | --- | --- |
| Start | At least five of six initial novice pilots obtain a meaningful first flag within ten active minutes of a working session. | Fix orientation, agent integration, prompt clarity, or the first task. Do not reduce the entire campaign's ceiling. |
| Early uplift | Novices can complete several early achievements and use the evidence/delegate/verify loop without a facilitator driving the keyboard. | Improve the training transfer and built-in feedback. |
| Choice | At each major non-final plateau, at least two useful leads are available, with an appropriate next action discoverable. | Repair the dependency shape or clue placement. |
| Long-term novice engagement | Novice pilots retain productive accessible work through their actual session, even if they remain in KeplerOps. | Add distinct early/middle operations or better recovery; do not automatically grant the next phase. |
| Main-route difficulty | Start by testing the 8–12-hour elite and 11–15-hour strong-generalist route hypotheses. | Revise using observed distributions and technical causes; do not force the numbers with waits. |
| Upper-tier substance | Elite candidates require nontrivial discovery, construction, or debugging with agents; independent reviewers can identify that work. | Downgrade, combine, or redesign candidates emptied by routine tool use. |
| Upper-tier solvability | At least one fresh qualified solver completes each elite operation within a planned test session, with other attempts showing an intelligible route to progress. | Investigate missing clues, bugs, prerequisites, or excessive scope before calling it harder. |
| Portfolio depth | Fast pilots still have multiple substantive expert/elite operations available late in the event. | Add independent technical depth, especially outside the mandatory route. |
| Causal gates | Valid capabilities pass, invalid/partial ones fail, and unexpected legitimate approaches remain usable. | Repair the boundary or evaluator rather than enforcing the author's command sequence. |
| AI-dependent gates | A known valid method succeeds in at least 19 of 20 fresh test sessions under the pinned configuration. | Remove stochastic behavior from the mandatory dependency; retain stable tool/authorization weaknesses. |
| Isolation and recovery | One player's mutation/reset cannot affect another, and an operation reset preserves earned upstream progress. | Treat as a release blocker. |
| Final consequence | Independent process state proves the intended effect and the narrative remains physically coherent. | Rework the model or validator with an OT/water reviewer. |

For elite tests, initially reserve **60–180 minutes per substantial operation**,
then revise according to observed progress. This is a test-session budget, not
a required solve-time label and not a separate estimate for every scored
milestone. A brilliant quick solve is valid. Repeated routine five-minute clears
by current agents indicate a different difficulty level.

Likewise, no-solve results do not prove elite quality. A malformed artifact,
undisclosed prerequisite, or guessing puzzle may defeat everybody without
measuring the intended skill.

The 19/20 AI gate criterion is only a screening test for excessive variability,
not a statistical reliability guarantee. Follow it with end-to-end replay and
capacity tests. Record model changes because a formerly stable victim behavior
may change with a new version.

## 5. Decide whether 240 is enough

The [research](research.md) explains why the initial supply range is 220–280.
After pilots, make the sizing decision with two independent tests:

1. **Distinctness:** every counted challenge has a defensible marginal
   achievement. Merge duplicated reads and replay-only variants.
2. **Workload and access:** players retain worthwhile reachable work through
   sixteen hours, including strong operators with fast parallel agents.

For each pilot profile, report route progress, operations completed, challenges
solved, productive time, blocked time and cause, hint use, remaining reachable
operations, and agent usage. Use ranges and individual traces while samples are
small; do not publish precise completion percentages for the Ottawa audience.

Interpret these example outcomes differently:

- **Finale completed in nine hours, substantial expert branches remain:** this
  can satisfy the design. Story completion is not portfolio exhaustion.
- **Nearly all substantive work cleared in six hours:** the portfolio fails
  even if hundreds of flags were issued.
- **Novices spend ten hours stuck at one gate while optional work is inaccessible:**
  the graph or support design fails even if experts enjoy the finale.
- **No one reaches the ending, but independent late-stage tests succeed:** inspect
  cumulative route length and discovery cost before simplifying the finale.
- **Slow progress mostly reflects model queues or target outages:** fix capacity;
  do not count it as sixteen hours of content.

Use a sensitivity check with the fastest observed operation times and stronger
BYO results, not one multiplier applied to all tasks. Recompute reachable
remaining work after shortcuts. If new capacity is needed, add distinct
operations to the established three phases. Do not invent a fourth narrative
phase or duplicate flags merely to reach a target count.

## 6. Scoring, hints, and agent resources

Simulate the proposed 1:2:4:8:16 weights against pilot results. Compare a player
who explores broadly, one who follows the ending route, and one who tackles
expert branches. Check that easy-volume farming does not dominate meaningful
depth and that progress remains visible to a newcomer.

Test the normal hint policy during pilots. Difficulty measured without hints
does not describe an event offering those hints. Do not count explanation of
basic tool use as solving a hard technical boundary for the player.

Budget the provided agent from measured distributions, including first-timer
conversational overhead and expert tool concurrency. For illustration, a mean
of two requests per player per minute would imply 600 requests per minute at
300 active players; long-running tools and tokens per request then determine
very different resource loads. This is a capacity calculation example, not a
usage forecast or a recommendation to impose that rate limit.

Monitor queue delay, error rate, context loss, and per-player budget exhaustion.
The provided agent must remain useful for the complete scheduled event. Record
the practical BYO resource disparity openly rather than claiming uniform
capability from a common starting agent.

## 7. Facilitation and build feasibility

Separate help with the workbench, technical faults, and challenge hints. A
facilitator should be able to identify the failed layer without learning the
participant's entire operation first. Provide author runbooks and visible
service health for each critical gate.

Estimate support demand from pilots. A simple planning calculation is:

```text
busy facilitator-equivalents =
    active players × help requests per player-hour × mean handling minutes / 60
```

For example, 300 players at 0.3 requests per hour and six minutes per request
generate nine continuously busy facilitator-equivalents before burst capacity,
breaks, and specialist escalation. Those rates are illustrative; measure them.
This shows why “the agent handles support” is not a staffing plan.

The proposed content is also a substantial production commitment: 71 operation
briefs, 240 distinct achievement/evaluation definitions, original upper-tier
weaknesses, independent solves, reset behavior, and load testing. Estimate
author/reviewer effort after the vertical slice. The architecture must not be
advertised as buildable within an unspecified small staffing budget.

If resources are constrained, reduce duplicated service implementation and
reuse credible business workflows first. Preserve the approved experience and
reassess the content allocation explicitly; quietly replacing difficult work
with flag hunts would change the design.

## 8. Review artifacts before topology is selected

The design review should have:

- A reconciled inventory of authored versus merely allocated content.
- A causal dependency graph with complete route closure and useful alternatives.
- Prototype evidence for the supplier bridge, AI workflow, process model,
  controller boundary, and final effect.
- Assisted fresh-solver results for the lower entry and upper difficulty limit.
- A revised count/workload envelope and a realistic authoring, compute, and
  facilitation estimate.

At present, this repository contains the design and research, not those
validation results. Their absence is an explicit limitation, not evidence that
the proposed difficulty or capacity has already been achieved.
