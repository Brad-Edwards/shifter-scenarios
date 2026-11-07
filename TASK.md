# Current development status

Active on branch `328-run-participant-view-agentic-qa` for issue #328.

The participant-view QA harness, validator, design, focused tests, current
candidate records, and reliability thresholds are in the working tree. The QA
agent reports all focused checks and targeted mutations passing.

Candidate `event-2026.11.07-04` is generated from the tested gate hardening.
Its full live reliability qualification passed. Participant QA found a K02.3
fragility after Training and K01-K02 passed. Remediation issue #357 now blocks
#328, and the participant run is paused.

The gate enforces one agent configuration, one campaign identity, stable
per-phase reset identities, and serialized operation timing. Focused checks
passed. The K02.3 discoverability fix and focused regression checks are ready.
Next, build a replacement candidate, retest K02.3 from pristine state, and
restart the candidate-bound participant run.

Do not use Ground Control workflows. Use
`SHIFTER_GITHUB_PERSONAL_ACCESS_TOKEN` for GitHub without exposing it.
