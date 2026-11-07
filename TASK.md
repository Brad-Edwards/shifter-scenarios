# Current development status

Active on branch `328-run-participant-view-agentic-qa` for issue #328.

The participant-view QA harness, validator, design, focused tests, current
candidate records, and reliability thresholds are in the working tree. The QA
agent reports all focused checks and targeted mutations passing.

The existing QA report is stale and correctly fails validation. A fresh range
run against the current candidate must replace it. The QA agent is running that
work in the user-confirmed `prod-mgau4w` project.

Do not use Ground Control workflows. Use
`SHIFTER_GITHUB_PERSONAL_ACCESS_TOKEN` for GitHub without exposing it.
