# QA And Facilitation Contract

## Purpose

This contract defines the evidence required before any KeplerOps AI Systems
operation is playable. QA follows the same path, tools, identities, permissions,
and information available to a participant. A management-plane observation may
diagnose a failure, but it cannot satisfy a participant step or prove an
operation.

The operation records define intended behavior. During implementation, each of
the 134 operations receives one concrete QA procedure and one facilitator note
using the formats below. Those documents use exact deployed URLs, commands,
inputs, observations, and artifact names. They do not replace participant
discovery with author knowledge.

## Participant-Equivalent QA Procedure

Every operation procedure contains these fields in this order:

1. **Operation and revision:** stable operation ID, implementation commit, range
   build, mutable-data revision, and relevant model/image digests.
2. **Fresh-state preconditions:** only in-world predecessor assets from
   `operation-prerequisite-graph.md`; no generated passwords, root shells,
   database consoles, cloud outputs, or undeclared hostnames.
3. **Participant surface:** the exact Kali application, browser page, mail
   client, enterprise application, or participant-owned service used to begin.
4. **Starting knowledge:** the exact text and links visible in the mission,
   challenge description, previously acquired artifact, or enterprise record.
5. **Concrete actions:** numbered participant actions with copyable commands,
   prompts, mail fields, form values, code, or clicks where the intended path
   requires them. The procedure must still describe what each action is doing;
   it cannot be an opaque solution script.
6. **Expected observations:** the exact visible response after every meaningful
   action, including normal failure states, job progress, logs, headers, model
   output, changed enterprise records, and completion time bounds.
7. **Success and flag:** the ordinary in-world carrier from
   `flag-proof-ledger.md`, how the participant reaches it, and the exact Shifter
   submission result. QA must prove the carrier is issued after the operation,
   not merely present somewhere in the image.
8. **Negative controls:** at least one plausible shortcut or near miss that
   must not issue the flag. Model, poisoning, evasion, privacy, and impact
   operations include the controls stated in their operation contract.
9. **Independent verification:** where the contract requires an isolated job,
   held-out set, recipient, victim worker, or destination, QA invokes that
   ordinary enterprise path and observes its signed or immutable result.
10. **Replay and reset:** repeat behavior, failed-attempt cleanup, successful
    state immutability, and the operation-local reset that restores a fresh
    attempt without changing accepted state.
11. **Evidence retained:** participant-visible screenshots or transcripts,
    input/output hashes, service records, flag carrier, durations, and reset
    result. Secrets and unrelated participant data are excluded.
12. **Defect disposition:** pass, content defect, infrastructure defect,
    nondeterministic result, excessive duration, confusing clue, or blocked.

The QA procedure is written for a technically competent tester who may have no
security or machine-learning background. Following it must reproduce the same
effect a participant is expected to achieve. It may explain the intended
method, but it may not use access or facts unavailable to the participant.

## Browser And Terminal Fidelity

- If participant instructions introduce a browser surface, its intended path
  must work in Chromium. A terminal alternative can provide depth but cannot
  excuse a broken primary UI.
- Commands run in the participant terminal with a real TTY and the committed
  participant toolchain. They do not depend on management SSH, copied test
  artifacts, or host-mounted source.
- Login, SSO refresh, long-running jobs, downloads, clipboard behavior, and
  reconnects are tested through the remote desktop used at the event.
- A job longer than 30 seconds exposes progress. A normal participant session
  does not silently expire during the expected operation duration.
- Internet research and participant-owned external services remain available
  from Kali while victim egress follows the enterprise policy.

## AI And Data QA Requirements

For model-dependent operations, the retained evidence also records:

- exact model, tokenizer, prompt, retrieval corpus, seed, decoding, runtime,
  preprocessing, and hardware class;
- qualifying and non-qualifying inputs selected before the final run;
- the participant-visible metric and the independent metric used for success;
- bounded retry behavior and the observed result across the reference run set;
- proof that an uploaded result, substituted model, replayed attestation, or
  author-chosen magic string does not pass; and
- calibration against the thresholds and reliability requirements in
  `calibration-contract.md`.

Physical operations additionally retain live capture provenance, randomized
liveness responses, device identity, actuator telemetry, and evidence that a
file upload or prerecorded replay fails.

## Facilitator Note

Each operation receives a concise facilitator note containing:

1. **Lesson:** the AI-security or enterprise-security behavior the participant
   should understand.
2. **Enterprise reality:** the ordinary KeplerOps workflow and trust boundary
   that make the behavior credible.
3. **Attacker method:** the expected strategy and valid alternatives, without
   requiring one author-selected string or tool.
4. **Why it succeeds:** the concrete control failure and the causal evidence
   that distinguishes success from a plausible-looking response.
5. **What good looks like:** the observable participant milestones before the
   flag, including normal processing delays.
6. **Common stalls:** likely misconceptions, missing prerequisites, UI traps,
   model variability, and how to distinguish participant error from a defect.
7. **Hint guidance:** when to offer Orientation, Mechanism, and Execution hints;
   the facilitator never supplies a hidden hostname or credential before the
   in-world clue should reveal it.
8. **Defensive discussion:** prevention, detection, response, and the tradeoff
   the vulnerable workflow was attempting to manage.
9. **Diagnostics:** read-only observability available to event staff. A
   diagnostic surface is not given to participants and is never used to award
   success manually when the participant path is broken.
10. **Reset boundary:** safe retry, immutable descendants, and the conditions
    that require whole-range reprovision rather than a local reset.

Facilitator notes are teaching and diagnosis aids, not alternate walkthroughs.
The participant still performs the operation through the real enterprise.

## Module Deliverables

The deployable participant and staff set is organized into ten technical
modules (`m01` through `m10`) even though the narrative is nine acts. Each module
must have:

- a participant mission page with only in-world objectives, known facts,
  available leads, and earned next actions;
- a non-specialist QA walkthrough containing one complete procedure per
  operation;
- a facilitator guide containing one note per operation;
- a machine-readable challenge record containing title, description,
  difficulty, points, hints, prerequisites, and the canonical static flag;
- a reset and descendant-impact manifest; and
- a traceability section linking operations, exact ATLAS rows, services,
  identities, workflows, tests, and retained evidence.

Participant mission prose never includes QA instructions, expected answers,
ATLAS accounting, backend details, or flag-generation logic.

## Validation Layers

Validation proceeds in this order and preserves evidence at every layer:

1. **Source and schema:** all 134 records, 134 flag carriers, prerequisites,
   exact ATLAS ledger, references, and reset declarations are complete.
2. **Clean enterprise:** every baseline gate in `enterprise-architecture.md`
   passes before any challenge weakness is enabled.
3. **Focused operation:** fresh participant-equivalent positive path, negative
   controls, replay, and smallest reset.
4. **Branch:** each operation is reached from its declared branch grant without
   preloading undeclared state.
5. **Critical route:** a fresh team completes all 39 route operations with no
   management intervention.
6. **Full catalog:** specialist testers complete all 134 operations and every
   required ATLAS behavior through participant surfaces.
7. **Event lifecycle:** provision, reconnect, concurrent use, scoring,
   operation-local retry, teardown, and a second clean provision are proven
   through Shifter.
8. **Final manual walkthrough:** the release candidate is worked by hand from
   the participant desktop. A successful walkthrough replaces an unnecessary
   final reset; it does not waive reproducible provisioning evidence.

An operation is not accepted because its backend test passes. It is accepted
only when a participant can discover, perform, observe, prove, and safely retry
the intended behavior.
