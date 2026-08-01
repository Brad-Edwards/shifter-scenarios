# Difficulty And Campaign Calibration Contract

## Purpose

This contract governs challenge distribution, onboarding, pacing, and campaign
gating. It prevents a catalog of individually defensible operations from
becoming an exhausting or inaccessible event.

KeplerOps is a live-fire enterprise campaign, not a linear tutorial. It still
has to teach participants how to interact with its systems before asking them
to synthesize unfamiliar AI-security techniques under pressure.

## Evidence

- CTFd differentiates challenge levels by prerequisite knowledge, number of
  mechanisms, custom tooling, and real-world depth. Harder levels are not simply
  less explained versions of easier ones.
  [CTFd challenge levels](https://docs.ctfd.io/events/challenge-levels/)
- The CTF design literature recommends explicit audience targeting, in-world
  breadcrumbs, recognizable success, and QA with reviewers close to the target
  audience. It warns that ambiguity and convolution substitute luck for skill.
  [Toward Better CTFs](https://www.usenix.org/system/files/conference/3gse14/3gse14-chung.pdf)
- pwn.college reports that traditional large, loosely connected challenges
  frustrate newcomers. Its education-first approach decomposes complex skills
  into tightly scoped tasks, provides intermediate feedback, monitors drop-off,
  and adds scaffolding where recurring confusion appears.
  [Five Years of pwn.college](https://adamdoupe.com/publications/pwn-college-five-years-sigcse2026.pdf)
- A USENIX Security study of beginner CTF problem solving used an onboarding
  challenge, a complete tool reference, staged hints aligned to solution
  milestones, and pilot participants to calibrate difficulty. Nearly all
  participants reached the final step even though fewer completed the full
  challenge.
  [Just Google It](https://www.usenix.org/system/files/usenixsecurity25-mattei.pdf)

## Audience

The event serves a mixed security audience:

- experienced offensive-security participants with little ML background;
- ML and AI-security practitioners with uneven enterprise-security experience;
- general technical participants who can research and follow evidence but may
  not write substantial exploit code; and
- expert teams seeking long-horizon, realistic AI-system compromise.

No single difficulty tier can dominate the board. Participants must continue
to find useful work after their preferred branch or skill area becomes harder.

## Target Distribution

The first-pass target for 134 operations is:

| Difficulty | Target | Permitted Final Range | Share | Points |
|---|---:|---:|---:|---:|
| Accessible | 40 | 38-42 | 28-31% | 100 |
| Intermediate | 47 | 45-49 | 34-37% | 200 |
| Advanced | 34 | 31-35 | 23-26% | 350 |
| Expert | 13 | 11-15 | 8-11% | 500 |
| **Total** | **134** | **134** | **100%** | |

The range permits honest calibration after detailed design and playtesting.
Moving outside it requires a campaign-level review, not isolated relabeling.

## Expected Participant Time

These are fresh-participant targets after the participant understands the
range's basic interaction model:

| Difficulty | Target Time Without Hints | Expected Work Shape |
|---|---:|---|
| Accessible | 5-15 minutes | One concept and one primary surface. |
| Intermediate | 15-30 minutes | Discovery plus one mechanism, or two connected surfaces. |
| Advanced | 30-60 minutes | Multi-system analysis, artifact construction, or custom adaptation. |
| Expert | 60-120 minutes | Long-horizon synthesis or substantial independent analysis. |

Implementation complexity and service startup time do not count as participant
difficulty. Waiting for jobs must expose progress and should be minimized with
appropriately sized data and models.

## Onboarding Contract

### First success

- A participant starting with only the mission and workstation must have three
  clearly discoverable Act 1 operations.
- The first flag should be reachable in under ten minutes without a hint by a
  technically capable participant new to AI security.
- The first flag teaches the full event loop: follow an in-world lead, inspect
  a real surface, recognize an embedded flag, and submit it in Shifter.
- No credential, hidden URL, terminal convention, or CTF-specific file is
  assumed before it has been introduced.

### First six operations

At least four of the six most natural opening operations are Accessible. None
requires custom code, model training, opaque prompt mutation, or prior
knowledge of ATLAS. Together they introduce:

1. the KeplerOps public presence;
2. cross-source research;
3. a live service and meaningful error or metadata response;
4. the attacker workbench and persistence of participant-created artifacts;
5. the difference between Shifter mission/score surfaces and the in-world
   enterprise; and
6. how a recovered asset becomes the lead for another operation.

### Surface introduction

Before a surface is used in an Advanced or Expert operation, an Accessible or
Intermediate operation must have introduced its normal interaction model:

- terminal and browser;
- mail composition, delivery, and headers;
- repositories and revision history;
- notebooks and model invocation;
- object storage and artifact digests;
- model registry and experiment lineage;
- workflow scheduler and job output;
- agent chat, tool calls, and audit state;
- directory identities and SSO; and
- Shifter flags, hints, prerequisites, and completion feedback.

The earlier operation need not be a tutorial, but the participant must have
used the surface successfully before difficulty depends on fluency with it.

## Campaign Graph Rules

- Acts are narrative and access boundaries, not 134 steps in a single rigid
  line.
- The mandatory outside-in spine opens three internal branches. Branches allow
  teams to work in parallel and let participants switch when blocked.
- Every act exposes at least one Accessible operation and at least one
  Intermediate operation when it opens.
- No Expert operation is the sole gateway to the next act.
- No sequence of more than three required operations may consist entirely of
  Advanced or Expert work without an alternate open operation at a lower tier.
- Major campaign gates require assets with clear causal relevance. They do not
  require unrelated flags merely to force completion order.
- A participant who completes the primary campaign victory path encounters all
  major AI-security domains. The full 134-operation route provides complete
  ATLAS coverage and deeper branch objectives.
- Optional does not mean disconnected. Every branch operation yields an asset,
  intelligence, access, effect, or understanding that strengthens a later
  operation or final objective.

## Difficulty Assignment Test

Assign a level only after answering these questions:

1. How many new concepts must the participant learn?
2. How many independent observations must be combined?
3. How many normal surfaces or trust boundaries must be crossed?
4. Is custom code, model training, or artifact construction required?
5. How much of the method can be found through ordinary documentation and
   research?
6. How strong is the in-world feedback after each meaningful step?
7. How many plausible strategies can succeed?
8. What is the expected time for a fresh target-audience participant?

Do not increase difficulty because:

- the description is vague;
- a hostname or file path is hidden without a clue;
- the participant must find an exact prompt;
- a model is unreliable;
- setup is slow;
- a task repeats many similar actions;
- an operation has a low solve rate caused by a defect; or
- the implementation was expensive to build.

## Hint Calibration

Every operation has Orientation, Mechanism, and Execution hints as defined in
`scoring-and-hints.md`. Their review adds two constraints:

- each hint corresponds to a specific likely stall point in the participant
  path; and
- after the Execution hint, a participant who understands the named concept
  can complete the operation without guessing author intent.

Hints are available immediately and are free. During playtesting, record the
time and state at which each hint is opened. High Hint 1 use indicates a poor
starting clue. High Hint 3 use may indicate either excessive technical demand
or missing feedback and must be diagnosed rather than automatically accepted
as difficulty.

## Pacing And Variety

Review every eight-operation window in each likely route. Unless the story
requires a short deliberate concentration, it should include variation across:

- investigation and action;
- browser, terminal, mail, repository, notebook, and enterprise applications;
- model, data, agent, supply-chain, infrastructure, and human trust boundaries;
- individual and team-parallelizable work;
- immediate and delayed consequences; and
- Accessible/Intermediate progress and harder synthesis.

No route may contain more than two operations in succession whose primary
interaction is free-form prompting. No route may contain more than three in
succession whose primary output is analysis of a static artifact. Similar
operations must add a materially new decision, mechanism, or consequence.

## Calibration Review

After the first-pass catalog, an independent reviewer receives the entire
operation graph and performs four passes:

1. **Onboarding:** Can a new participant start, earn a flag, understand the
   campaign, and find multiple next actions?
2. **Leveling:** Do labels reflect participant effort rather than author intent
   or backend complexity?
3. **Distribution:** Do tier counts meet the target range globally and provide
   lower-tier work in every act?
4. **Pacing:** Does each likely route vary mechanics and avoid fatigue while
   building toward meaningful consequences?

Any operation moved between tiers must be rechecked against its hints, points,
prerequisites, and expected time. If the target distribution can be met only by
mislabeling operations, operations must be decomposed or redesigned.

## Playtest Telemetry

For each operation, capture without recording sensitive participant content:

- started, solved, and abandoned counts;
- time to first meaningful action;
- time to solve;
- hint-open timestamps;
- most common failure category;
- reset requests;
- participant-rated clarity and difficulty; and
- facilitator intervention category.

Telemetry informs post-playtest redesign. It cannot substitute for watching
fresh participants reason through the experience.
