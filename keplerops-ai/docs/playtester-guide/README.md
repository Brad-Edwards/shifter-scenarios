# KeplerOps AI playtester guide

This folder is the playtest-facing handoff surface for KeplerOps AI. It is
structured for coordinators who need to stand up ranges, give participants a
clean start, collect useful feedback, and avoid exposing operator-only proof
material.

Start here:

- [Coordinator quickstart](coordinator-quickstart.md) — how to instantiate or
  reuse a playtest range.
- [Participant start guide](participant-start.md) — what a participant should
  receive before entering the range.
- [Session checklist](session-checklist.md) — run-of-show for a playtest
  session.
- [Full manual participant-equivalent runbook](full-manual-participant-equivalent-runbook.md)
  — how to conduct the next verification level: one clean participant run with
  defects fixed as they are found.
- [Telemetry and evidence](telemetry-and-evidence.md) — what should be
  captured, where it lives, and what not to hand to participants.
- [Challenge walkthrough index](challenges/README.md) — one operator-facing
  walkthrough per playable challenge, grouped by module and generated from the
  ACES SDL contracts.
- [Known caveats](known-caveats.md) — current scope exclusions and
  playtest-stage limitations.
- [Sanity check log](sanity-check-log.md) — latest operator sanity-check
  results against the merged delivery branch.

The ACES SDL remains the scenario source of truth. This guide does not define
new topology, challenge contracts, flags, services, or proof predicates.

The challenge walkthroughs are operator/playtester material, not participant
handouts. They intentionally include proof predicates, receipt routes, negative
control expectations, and capture templates.
