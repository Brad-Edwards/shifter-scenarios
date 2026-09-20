# Cinder Typhoon challenge-design research

Research date: September 18, 2026. Status: design evidence and recommendations;
not a playtest report. Read with [challenge architecture](challenge-architecture.md)
and [calibration plan](calibration.md).

## Draft 2 extension

The current revision also uses the [named challenge catalog](reference-catalog.md)
and [threat-inspiration analysis](threat-inspiration.md). These add organizer
writeups and the MITRE CTID Adversary Emulation Library to the original evidence
base. They distinguish historical challenge ratings from proposed difficulty
with the provided agent, and behavioral realism from a CTF difficulty benchmark.

Subsequent user constraints are now explicit: both organizations span all tiers;
ordinary ARWC entry has a medium ceiling over its entire prerequisite closure;
AI-target tasks remain easy/medium and use bounded compute; hard/elite work
retains mechanisms from identifiable existing challenges. The revised portfolio
allocates 240 achievements across 64 operations. These are architectural budgets,
not measured content duration or 240 implemented challenges.

The revisions preserve the earlier research's limitations. No source establishes
a universal challenge count, difficulty histogram, or AI speed multiplier for
this event. New source discrepancies are recorded in the catalog rather than
resolved by silently choosing the more convenient rating.

## The event being designed

The confirmed requirements are approximately 300 **individual** participants,
16 hours of mostly continuous play over two days, a provided agent for everyone,
and optional participant-supplied agents. Experience ranges from people who
have never hacked to elite Canadian government, military, intelligence, and
industry operators. Agents are intended to raise participants' capabilities.
Progressive difficulty is essential; universal completion is not a goal.

The story moves from Cinder Typhoon's training environment, through a compromised
KeplerOps Software developer workstation and its enterprise, into Alterra
Regional Water Company (ARWC). The final objective is opening reservoir gates,
with financial loss and water restrictions as the fictional consequences.

Research must therefore answer two different questions: how to help an absolute
beginner start operating with an agent, and how to retain a substantial upper
limit for an elite operator using one. A conventional unaided CTF difficulty
scale cannot answer both.

## Method and limitations

This is a targeted design review, not a systematic literature review. Sources
were selected for direct relevance to challenge construction, novice progression,
professional competition, agent-assisted performance, or OT. Primary research,
organizer guidance, official challenge releases, and first-party event reports
were preferred. Search-result summaries were followed to the underlying sources.

Evidence below distinguishes published studies, organizer recommendations,
vendor observations, and participant-reported results. None establishes the
solve-time distribution of the actual Ottawa audience. There is no validated
conversion from an employer or job title to a CTF difficulty tier, and no
universal multiplier converting unaided solve times to assisted solve times.

No live Polaris scoreboard or participant solve telemetry was accessed. The
local design, SDL, challenge manifests, participant material, and rehearsal
reports have different purposes and must not be conflated.

## What the Polaris sources actually establish

### Inventory reconciliation

The checkout splits the material across several inventories:

| Local source | Count | What the count means |
| --- | ---: | --- |
| [Canonical challenges](../../../polaris/challenges/challenges.yaml) | 38 | NORTHSTORM campaign scoring rows: 14 easy, 12 medium, 8 hard, 4 insane. |
| [Agentic workshop](../../../polaris/ctfd/agentic_workshop.json) | 10 | Five additional boxes, each with user and root/admin challenges. |
| [Onboarding](../../../polaris/build/ctfd-onboarding.json) | 1 | Separate participant warm-up. |
| [Release Trail design](../../../polaris/design/missions/proposed-mission-release-trail.md) | 4 | Further challenge designs, explicitly marked proposed in this checkout. |
| [Full SDL](../../../polaris/sdl/polaris-operation-northstorm.sdl.yaml) | 5 objectives | Campaign outcomes, not the number of challenges. |

Together these describe 53 scoring opportunities across the campaign, associated
event material, and proposed extension. They do **not** prove that all 53 were
deployed together: the repository explicitly separates the workshop and marks
Release Trail proposed. The user's event baseline is **over 50 challenges in
3–4 hours**. The local 38-row subset must not replace that baseline.

The [architecture](../../../polaris/design/architecture.md) estimates a four-hour
experience **with an agent**, and the [briefing](../../../polaris/briefing-deck/script.md)
also specifies four hours. The SDL's six-hour workflow timeout is not a
participant pacing measurement. The successful scripted/manual rehearsal is
evidence of solvability, not evidence of fresh-player discovery time.

### The difficulty progression

The canonical campaign subset is useful for examining structure even though it
does not represent the whole event inventory:

| Area | Easy | Medium | Hard | Expert | Architectural effect |
| --- | ---: | ---: | ---: | ---: | --- |
| Public Boreas | 5 | 1 | 0 | 0 | Fast discoveries establish people, systems, and story. |
| Front Office, including the SCADA branch | 6 | 5 | 3 | 1 | Move from information recovery into identity, lateral movement, and control. |
| Lab | 3 | 5 | 2 | 1 | Reward the earned pivot, then demand protected access and cross-system reconstruction. |
| Bunker | 0 | 1 | 3 | 2 | Mostly demanding stateful interaction and campaign synthesis. |

The curve rises overall but contains local rewards after a difficult gate.
Entering the lab exposes some immediately usable material; it does not grant
every protected account or complete the research chain. That is a useful
distinction between a progressive campaign and an uninterrupted sequence of
harder blockers.

### Mechanisms worth carrying forward

1. **Access creates the next problem.** The analyst pivot grants narrow lab
   access; the operations pivot requires a more demanding escalation and opens
   a different capability. See [A16](../../../polaris/design/assets/A16-research-analyst.md)
   and [A15](../../../polaris/design/assets/A15-ops-workstation.md).
2. **Branches have causal outputs.** Lab recovery and blackout are separate
   branches that converge before the final objective in the SDL and
   [hidden path](../../../polaris/docs/attack-path.md). They are not arbitrary score
   thresholds.
3. **Earlier information remains useful.** Procurement, repository content,
   controller identity, and research artifacts matter later. The final stage
   rewards a maintained understanding of the scenario.
4. **New surfaces build on prior work.** Initial industrial enumeration leads
   to several different stateful interactions, then a compound control task.
5. **The agent is part of the original difficulty model.** The participant
   material distinguishes explanation, co-operation, and autonomous work.
   Scaling Polaris by time and then applying a generic AI multiplier would
   count its existing agent assistance twice.

### What needs recalibration

Preserve the progression, not every old difficulty label. A removed file,
metadata field, short binary handshake, or familiar identity chain may compress
substantially with the event's current agent. Some older design files also
contradict later implementation details. Use the SDL and runtime contracts for
current boundaries, and the design files for design intent.

Polaris's [benchmark review](../../../polaris/design/benchmark-report.md) already
illustrates the right habit: compare concrete participant work with external
examples and revise difficulty when the task does not justify the label.
The new upper tiers need stronger evidence than analogy to an older box.

## Research findings

### R1: Professional challenges can contain meaningful partial achievements

CMU SEI's **Challenge Development Guidelines for Cybersecurity Competitions**
(2022) draws on President's Cup and defense exercise development. It recommends
matching difficulty to the audience, using multipart challenges to recognize
progress, and testing both time and difficulty with people other than the
author. It explicitly warns that estimated times vary with expertise.

**Application:** define coherent operations with independently meaningful scored
outcomes. Have reviewers assess marginal work after prerequisites are earned.
Do not count every command as a challenge, or award all progress only at the end.

**Limit:** pre-agent guidance; its sample solve times are examples, not Ottawa
benchmarks. [SEI report](https://www.sei.cmu.edu/documents/1299/2022_005_001_888602.pdf)

### R2: Entry friction and ambiguity are different from technical difficulty

Chung and Cohen's **Learning Obstacles in the Capture The Flag Model** (2014)
describes newcomer exclusion, challenge quality problems, and the importance of
feedback and discoverable progress. This is the actual title of the paper
linked as “Toward Better CTFs” in existing repository notes.

**Application:** teach the interaction loop early, preserve useful clues, and
make success recognizable. Later tasks can require more inference without
depending on arbitrary filenames, unstated conventions, or author intuition.

**Limit:** organizer experience and analysis, not an experiment establishing a
particular number of challenges per hour.
[USENIX paper](https://www.usenix.org/system/files/conference/3gse14/3gse14-chung.pdf)

### R3: Expert competition guidance still values choices and complete testing

Plaid Parliament of Pwning recommends keeping multiple problems available,
testing with an independent solver, and verifying a complete working solution.
It argues against fake complexity and notes that source-visible web challenges
can still be difficult.

**Application:** provide several useful leads at each earned stage. Expert
content must survive source inspection and skilled tool use. A crash or partial
primitive is not automatically a completed operational outcome.

**Limit:** primarily conventional jeopardy competition guidance. Its preference
for globally open challenges is not adopted literally for a campaign with
earned access boundaries.
[Organizer guidance](https://raw.githubusercontent.com/pwning/docs/master/suggestions-for-running-a-ctf.markdown)

### R4: Fine-grained progression can support a very broad audience

**Open Cybersecurity Education: Five Years of pwn.college** (SIGCSE 2026)
describes incremental challenges, a consistent browser workspace, and changes
driven by observed learner bottlenecks. It distinguishes experienced voluntary
learners from introductory students who need a gentler entry.

**Application:** introduce a technique, apply it in a new context, then combine
it with another capability. Preserve a consistent workbench so the intended
learning is security work, not environment repair.

**Limit:** an ongoing educational environment is not a two-day competition;
its curriculum size and completion behavior cannot supply an event count.
[Paper](https://adamdoupe.com/publications/pwn-college-five-years-sigcse2026.pdf)

### R5: Progress and completion should be measured separately

Mattei and colleagues' USENIX Security 2025 beginner study used pilots and
progressive hints. It reports 41% of attempted challenges solved while 98%
reached the final step. Participants had C and assembly prerequisites despite
being beginners in vulnerability discovery.

**Application:** assess intermediate progress and productive experimentation,
not only final flags. Pilot with genuinely first-time hackers as well as
technically experienced novices.

**Limit:** the study's frequent scheduled hints served a research protocol.
They do not justify automatically revealing solutions every ten minutes at
this event, and these participants were not absolute computing beginners.
[Paper](https://www.usenix.org/system/files/usenixsecurity25-mattei.pdf)

### R6: Agent fluency is a capability that the training must establish

**Understanding Human-AI Collaboration in Cybersecurity Competitions** (2026
preprint) studies 41 volunteers within a 95-person, 24-hour CTF, and evaluates
agents against its 17 fresh challenges. It finds evidence that AI fluency can
compensate for limited CTF experience, while poor context and ineffective
delegation constrain results. Human and agent difficulty do not align reliably.

**Application:** teach participants to supply evidence, delegate bounded work,
interpret failures, and verify effects. Benchmark the person-agent combination.

**Limit:** small university sample, self-reported experience, team participation,
and specific models/tooling. It supports the mechanism of uplift, not a
numerical forecast for 300 individual government and industry participants.
[Paper](https://arxiv.org/html/2602.20446v1)

### R7: Assistance mode changes performance, but the evidence is confounded

**AI In Cybersecurity Education: Scalable Agentic CTF Design Principles and
Educational Outcomes** (2026 preprint) reports 2025 standard-track mean solves
of 2.7 for 17 human-in-the-loop teams, 5.5 for two agent teams, and 7.7 for three
hybrid teams. Group sizes and prior engineering effort differ substantially.

**Application:** test the configured agent and stronger bring-your-own workflows;
do not assume a chat assistant, tool-using agent, and multi-agent workflow have
the same throughput.

**Limit:** this is not randomized evidence for a 2–3x causal improvement. Its
presentation and creativity rubric belongs to an agent-building competition;
requiring 300 players to submit judged essays would be a poor fit here.
[Paper](https://arxiv.org/html/2603.21551v1)

### R8: Published AI multipliers are task- and cohort-dependent

HTB's March 2026 NeuroGrid report announcement describes 1,078 teams, including
120 agentic teams, across 36 challenges. It reports different solve-rate and
speed advantages by cohort, including up to 4.1x output for elite assisted
teams and some lower-performing assisted teams taking longer.

**Application:** account for strong compression of routine and familiar work,
but measure it separately by challenge family. Distinguish solve rate from
time to solve; a ratio of cohort solve rates is not a time multiplier.

**Limit:** vendor-reported observational competition data with self-selection,
different team configurations, and selected-solver timing. Use as a capacity
warning, not as a rule to quadruple or divide every estimate.
[HTB report announcement](https://www.hackthebox.com/blog/hack-the-box-ai-cybersecurity-benchmark-report)

### R9: A novice can progress quickly with an integrated agent

HTB's **Attack of the Agents** (July 2025) reports an internal ten-challenge
exercise in which a newcomer completed the set in under 40 minutes, and an
autonomous agent completed four challenges.

**Application:** expect familiar introductory tasks to collapse in time once
the agent and tools work. Training should be a short capability-building phase,
not the main source of sixteen hours of content.

**Limit:** a small, vendor-authored demonstration with no matched control or
representative sample. It illustrates possibility, not a typical novice rate.
[Event account](https://www.hackthebox.com/blog/attack-of-the-agents-ctf)

### R10: Modern agents can clear a conventional conference board

The authors of the open-source Veria CTF agent report all 52 challenges solved
and first place at BSidesSF 2026. Their system runs competing models in parallel
and shares findings. BSidesSF's own page confirms a Friday-to-Sunday event.

**Application:** test parallel agents and prevent the entire range's scored
content from becoming one downloadable artifact collection. A large board by
itself does not guarantee sixteen hours of work.

**Limit:** the solve result is the entrant's report, not an independently
replicated experiment; its resources and team context differ from this event.
[Agent repository](https://github.com/verialabs/ctf-agent),
[organizer event page](https://bsidessf.org/ctf)

### R11: OT labels do not protect a challenge's difficulty

The Dragos OT CTF 2025 participant study reports 32 of 34 challenges solved by
the authors' agent-assisted operation, which paused at 24 hours of a 48-hour
event. The methods explicitly mention human retrieval, submissions, and hints.

**Application:** distinguish OT artifact analysis from live process control.
Reserve advanced difficulty for earned authority, state, protocol behavior,
and independently verified consequences.

**Limit:** entrant-authored preprint; mixed assistance and resource conditions.
It does not show that an agent can perform an arbitrary live water-system
intrusion, and its broader real-world claims should not be imported.
[Paper](https://arxiv.org/html/2511.05119v1)

### R12: Public benchmark numbers are not audience calibration

Cybench contains 40 professional CTF tasks and distinguishes unguided solves,
guided solves, and subtask completion. Its human first-solve-time measure is
the first team's competition solve time, not the average individual's active
work. The project also records an answer-leakage correction for some results.

**Application:** keep author answers out of agent-visible files, use fresh
variants, and measure actual individual attempts. Benchmark success is evidence
of capability, not a pacing estimate.

**Limit:** fixed public tasks and heterogeneous evaluation configurations.
[Project and evaluation notes](https://cybench.github.io/)

### R13: Advanced professional competitions use selective progression

President's Cup serves federal civilian and military participants, with separate
individual tracks and successive qualifying rounds. Its official challenge
repository preserves challenge artifacts and solutions across rounds.

**Application:** use professional challenge construction and independent review
as reference points. Accept that participants reach different depths and that
the final tier is selective.

**Limit:** qualified finalists and bounded sessions differ from an open mixed
audience. Federal employment is not itself evidence that a particular task will
challenge Canada's strongest operators.
[Competition format](https://pccc.cisa.gov/pc7/),
[official challenge collection](https://github.com/cisagov/prescup-challenges)

### R14: Novel work can be engineered without relying on unknown real bugs

The AIxCC design analysis describes realistic codebases, mostly deliberately
constructed vulnerabilities inspired by historical issues, reproducible
proofs, and several exhibition rounds before scoring. It distinguishes
vulnerability demonstrations from more complete outcomes.

**Application:** prototype original weaknesses in credible workflows, prove
they are exploitable, and test them against current agents. Do not make the
event depend on discovering a previously unknown real-world vulnerability.

**Limit:** enormous compute budgets and a roughly 143-hour autonomous finals
format. The engineering principles transfer; the resource model and task count
do not.
[Design analysis](https://arxiv.org/html/2602.07666v1)

### R15: Common event guidance does not prescribe a transferable count

CTFd distinguishes event durations by purpose. rCTF gives conventional jeopardy
planning advice around category balance, achievable solutions, and test coverage.
Neither establishes a universal challenges-per-hour rule for a connected,
agent-assisted campaign.

**Application:** use these sources for clarity and operations, then derive
capacity from the local event baseline and measured operation times.

**Limit:** advice for independent team problems cannot be converted directly
into the number of scored milestones in an individual live range.
[CTFd success guide](https://docs.ctfd.io/tutorials/success-guide/),
[rCTF organizer guide](https://rctf.osec.io/meta/running-a-successful-ctf/)

## Consequences for the design

These are design judgments from the evidence and user requirements, not claims
that the cited papers prescribe this event structure:

- Design **one rising campaign**. Avoid a permanent beginner track disconnected
  from the main story, and avoid assuming that everyone must reach the gates.
- Count substantive challenges, coherent operations, and mandatory-path time
  separately. Preserve intermediate rewards without inflating the board.
- Budget the whole event against Polaris's overall inventory, not its canonical
  campaign subset. Keep its existing agent assistance in the baseline.
- Concentrate fast wins early. Allow a few local rewards after difficult pivots,
  then increase synthesis, uncertainty, and the need for reliable execution.
- Maintain choices within earned access. Branching lets an individual change
  approach or delegate work without becoming a team exercise.
- Treat agent operation as part of the skill progression. Do not restrict the
  agent to manufacture difficulty or require manual repetition of automated work.
- Put genuine advanced work in the campaign's final stages, as well as optional
  depth in earlier stages. Four nominal expert flags are not a sufficient upper
  tier for this audience and duration.
- Validate the final tier with fresh elite practitioners using the actual
  provided agent and strong alternative workflows. Author estimates, models
  reviewing their own work, and known-solution replays are insufficient.

## Sizing inference before playtesting

Taking **50 only as a conservative lower-bound illustration** of the user's
over-50 Polaris baseline gives:

| Reference duration | Sixteen-hour duration factor | Inventory at unchanged challenge granularity |
| --- | ---: | ---: |
| 4 hours | 4.00 | 200 |
| 3.5 hours | 4.57 | 229 |
| 3 hours | 5.33 | 267 |

The actual over-50 inventory raises those values. Using the 53 design entries
visible here gives 212, 242, and 283 respectively, with the deployment caveat
above. This calculation scales **catalog supply**, not the number an individual
will solve. It does not establish that every challenge has equal effort.

This supports examining a roughly **220–280-challenge architecture**, with
**240 as a provisional allocation worksheet**, rather than another small board.
The endpoints are planning scenarios, not confidence intervals. The
[architecture](challenge-architecture.md) shows where that capacity goes; the
[calibration plan](calibration.md) states how to accept or revise it.

The count is not enough by itself. If an elite player and agent can clear the
substantive work in six hours, the design fails even with 240 rows. If the count
can be reached only by splitting one action into many flags, the design also
fails. Both volume and the upper difficulty limit require evidence.

## Draft 3: sources for the accepted review's gaps

The [second review](adversarial-review-v2.md) identified weak advanced cloud and
process representation, incomplete optional consequences, and excessive partial
counting. Research for this revision targeted those gaps rather than repeating
the general CTF survey. The [allocation audit](allocation-audit.md) records the
resulting editorial decisions.

| Primary material checked | Decision and evidence limit |
| --- | --- |
| [HTB PipeDream official solution](https://raw.githubusercontent.com/hackthebox/business-ctf-2025/master/cloud/PipeDream/README.md) | Adopt its Hard source mechanism for K29. The added release-rollover test is our design, whose difficulty does not follow from the source label. |
| [CloudGoat codebuild_secrets](https://raw.githubusercontent.com/RhinoSecurityLabs/cloudgoat/master/cloudgoat/scenarios/aws/codebuild_secrets/README.md) | Adopt a publisher-rated Hard cloud challenge for K30. It is a challenge lab, with no timed-event solve distribution claimed. |
| [CloudGoat ecs_efs_attack](https://raw.githubusercontent.com/RhinoSecurityLabs/cloudgoat/master/cloudgoat/scenarios/aws/ecs_efs_attack/README.md) | Adopt the published Hard scenario for K31. Preserve genuine identity/policy evaluation if the eventual implementation changes providers or uses a local model. |
| [Terraforming Mars evaluator](https://raw.githubusercontent.com/cromulencellc/hackasat-qualifier-2023/main/challenges/1_Aerocapture_The_Flag/2_Teraforming_Mars/challenge/challenge.py) and [organizer rating](https://raw.githubusercontent.com/cromulencellc/hackasat-qualifier-2023/main/challenges/1_Aerocapture_The_Flag/2_Teraforming_Mars/README.md) | Use the 4/5 challenge form for W33. Replacing the physical domain and adding scheduler/feedback work means this is a substantial adaptation, requiring new correctness and difficulty evidence. |

Screened alternatives were not promoted into hard candidates merely because
they involved cloud or ICS. The published
[Floody](https://raw.githubusercontent.com/hackthebox/business-ctf-2025/master/ics/floody/README.md)
and [Heat Plan](https://github.com/hackthebox/business-ctf-2025/tree/master/ics/heatplan)
solutions label them Easy; their prescribed manipulation sequences do not solve
the need for advanced process judgment. CloudGoat labels
[ecs_takeover](https://github.com/RhinoSecurityLabs/cloudgoat/tree/master/cloudgoat/scenarios/aws/ecs_takeover)
Moderate. HTB's index names Asceticism at five stars, but the attempted source
paths did not yield its mechanism; that label alone was insufficient for selection.

W34 composes already earned C13/C15 mechanisms with new planning-view constraints;
it does not count their exploitation twice. W35 is an original accessible
financial episode. The resulting thirty-entry catalog documents retained
mechanisms and authoring limits. These choices improve the architecture's
specificity without claiming that source publications validate participant
enjoyment, a sixteen-hour duration, or the event's elite ceiling.
