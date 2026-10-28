# Cinder Typhoon Participant QA

## Task

Validate the Cinder Typhoon scenario for an authorized Palo Alto Networks CTF
event. The goal is to prove that a human participant can complete the intended
happy path for every Training, KeplerOps, and ARWC challenge from a pristine
range, using only the starting material and participant-facing tools supplied by
the scenario.

The primary deliverable is a new set of integration tests that properly exercise
the participant walkthrough for every challenge. These are not replacements for,
or variations of, the existing service-contract and component tests. They must
test the connected participant experience across the running scenario.

Keep the existing tests. Add integration tests that close the current coverage
gap, fix every scenario, documentation, packaging, or deployment defect those
tests expose, and submit all required changes to the
`PaloAltoNetworks/shifter-scenarios` pull request.

## Overall approach

1. Inventory every challenge card and its intended participant entry point.
2. Add discovery-first participant walkthrough integration tests for every card.
   Each test starts from the published participant entry point, uses the same
   participant tools, follows the clues, links, interfaces, and history a human
   sees, performs the intended happy-path actions against the running services,
   verifies the participant-visible result, and carries discovered evidence or
   credentials into later steps. It must not begin with routes, credentials,
   identifiers, or answer values known only to the scenario author.
   The test must use exactly the intended happy-path method for that challenge:
   the same entry point, participant tool or interface, action sequence, and
   evidence handoff. It may not substitute a direct API call or author-side
   shortcut when the participant is meant to use a CLI, browser flow, repository
   history, supplied script, or another specific method.
3. Run each journey against fresh state, separately from the retained contract
   and component tests, so single-use actions and state changes cannot hide bugs.
4. Check the resulting state and evidence at each challenge boundary, including
   handoffs between Training, KeplerOps, and ARWC.
5. When a journey fails, determine whether the defect is in the scenario,
   participant instructions, build, deployment, or test. Fix the actual source
   of the problem and add regression coverage.
6. Re-run the discovery-first journeys and the existing suites after each fix.
7. Validate the corrected build against the deployed golden-range shape, then
   confirm that the range can be restored to pristine state.
8. Commit and publish only the intended Cinder Typhoon changes to the Palo Alto
   Networks repository. Do not include unrelated local deployment edits.

## Completion criteria

- Every challenge card has an integration test that properly exercises its
  participant walkthrough and participant-visible outcome.
- All new journeys pass from pristine state.
- All retained tests continue to pass.
- Participant documentation and starting material are accurate and runnable.
- Builds are reproducible and the corrected range restores cleanly.
- Every required fix is present in the Palo Alto Networks pull request.
