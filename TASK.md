# Current development status

Active on branch `328-run-participant-view-agentic-qa` for issue #328.

The participant-view QA harness, validator, design, focused tests, current
candidate records, and reliability thresholds are in the working tree. The QA
agent reports all focused checks and targeted mutations passing.

Candidate `event-2026.11.08-01` is generated from the merged remediation
source and replacement images. The earlier candidate passed reliability, but
its participant results are superseded. The participant run is paused.

The gate enforces one agent configuration, one campaign identity, stable
per-phase reset identities, and serialized operation timing. Focused checks
passed. The K02.3 discoverability fix passed focused checks and merged through
PR #358. Next, retest K02.3 from pristine state, qualify the final candidate,
and restart the candidate-bound participant run.

Do not use Ground Control workflows. Use
`SHIFTER_GITHUB_PERSONAL_ACCESS_TOKEN` for GitHub without exposing it.
