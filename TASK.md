# Current development status

Active on branch `328-run-participant-view-agentic-qa` for issue #328.

The participant-view QA harness, validator, design, focused tests, current
candidate records, and reliability thresholds are in the working tree. The QA
agent reports all focused checks and targeted mutations passing.

Candidate `event-2026.11.07-04` is generated from the tested gate hardening.
Its full live reliability qualification passed and the candidate-bound report
is ready to commit. The QA agent has started the final participant-view run.

The gate enforces one agent configuration, one campaign identity, stable
per-phase reset identities, and serialized operation timing. Focused checks
passed. Next, handle any participant findings and assemble the final 240-card
credential-free report.

Do not use Ground Control workflows. Use
`SHIFTER_GITHUB_PERSONAL_ACCESS_TOKEN` for GitHub without exposing it.
