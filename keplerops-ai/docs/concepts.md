# Concepts

KeplerOps AI Systems is an AI-lab intrusion scenario. This page is participant-safe
vocabulary for range builders and operators; it is not the ordered solution.

## AI Lab Surfaces

- **Inference gateway:** the service boundary where applications send prompts to
  a model backend and receive responses.
- **Guardrail policy:** the safety, authorization, content-filtering, and tool
  policy layer around inference. In this scenario it is something the
  participant attacks, not a trusted proof by itself.
- **Model registry / artifact store:** the source of deployable model files,
  adapters, policies, metadata, and promotion state.
- **Distillation workflow:** the teacher/student model process that can turn
  prompts, outputs, datasets, and jobs into a deployable artifact. This is a
  required KeplerOps AI Systems flow, not optional background color.
- **Open-model hosting:** range-controlled model serving for adversarial
  activity. The golden range may need one or more open models hosted in GCP, but
  participants must not run exploit attempts against commercial model endpoints.
- **Artifact integrity:** the hashes, signatures, version ids, approvals, and
  provenance needed to know which model artifact is deployed and whether it was
  changed.
- **Range-local containment:** model calls, exfiltration proof, callbacks,
  corrupted artifacts, datasets, and telemetry terminate inside declared
  range-controlled systems.
- **Enterprise fabric:** identities, business applications, repos, tickets,
  approval workflows, datasets, logs, and documents that make the AI lab feel
  like a populated enterprise instead of a standalone challenge service.

## ATLAS Coverage Goal

MITRE ATLAS is the operator-side technique-mapping spine. The design catalog
maps all 173 techniques in the pinned 2026.06 release to challenge families.
That catalog assignment is not golden evidence: each technique needs a real
variant and participant-equivalent proof before it can be claimed as built.

## Experience Shape

The participant starts at an AI attack console and can choose one or more
independent attacks immediately. An executive with 15 minutes can attempt agent
control, model evasion, context poisoning, model-secret extraction, agent
memory, or adversarial input and earn an early outcome. The current source-realized
board has 134 receipt-backed challenge contracts across the ten SDL modules,
distributed as 37 accessible, 58 intermediate, 28 advanced, and 11 expert items.
Its 3,015 incremental target minutes intentionally exceed the 480-minute event window;
participants are expected to select routes, not clear the board. There is no
pack-enforced runtime timer.

## Participant Role

The participant is the attacker. They act through the participant execution
surface to discover and execute the path. They are not a responder preserving
evidence or writing an audit report. The participant-facing briefing supports
manual players and event-approved participant-owned agents without exposing
operator-only proof predicates, exact ATLAS mappings, hidden thresholds,
answers, flags, or receipts.

## Draft Boundary

This pack ships the design source, participant briefing, 134-item receipt-backed
portfolio, scoring/oracle contracts, GCP build, automated participant-equivalent
live rehearsal, and a generation-55 manual pass over the original 60 challenges.
The four Module 01 expansion additions are automated-proven through the focused generation-25
participant-equivalent pass and generation-26 reset/replay; manual walkthrough
and post-playtest reliability hardening remain open.
The three Module 02 expansion Slice A Module 02 supply-chain additions are automated-proven
through one focused participant-equivalent pass, representative negatives,
three receipts, and one scoped reset/replay.
Two Module 02 expansion Slice B Python-package additions are `automated-proven` against real
Gitea PyPI and separate same-digest analysis/worker services after their
focused live pass, representative negatives, receipts, scoped reset, and
replay. Statistical hardening remains post-playtest work.
The synthetic-spearphish addition is source implemented across real local
generation, mail, identity, and proof services; focused live proof and replay
have since advanced. Modules 03 through 10 now carry source-implemented
full-ATLAS expansion challenge rows across their real runtime surfaces; focused
live proof, manual walkthrough, and post-playtest reliability hardening remain
open for those expansion rows.
Post-manual static checks, the post-change integrated rehearsal, canonical
reset, and the earlier Phase-E teardown pass. The original Modules 01 through
07 kernels are participant-proven. It remains `draft` because the expansion
rows and Modules 08 through 10 playtest calibration and release hardening are
incomplete. The exact boundary is recorded in the operator-only
challenge portfolio, module proof reports, and golden-readiness checklist.
