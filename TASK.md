# Current development status

Active on branch `328-run-participant-view-agentic-qa` for issue #328.

The participant-view QA harness, validator, design, focused tests, current
candidate records, and reliability thresholds are in the working tree. The QA
agent reports all focused checks and targeted mutations passing.

Candidate `event-2026.11.07-03` is recorded. A fresh stable focused ARWC retry
passed, confirming the earlier W24 failures were contaminated-run evidence.
Participant QA has not started.

The gate now also enforces one agent configuration, one campaign identity,
stable per-phase reset identities, and serialized operation timing. These
development changes are in focused QA checks and still need a replacement
candidate.

Do not use Ground Control workflows. Use
`SHIFTER_GITHUB_PERSONAL_ACCESS_TOKEN` for GitHub without exposing it.
