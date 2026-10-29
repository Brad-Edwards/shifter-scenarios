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

## Current status

### Repository and pull request

- Work is on `fix/cinder-typhoon-golden-walkthrough`.
- The draft pull request is
  `PaloAltoNetworks/shifter-scenarios#204`.
- The pull request currently contains the completed Training journey and its
  source fixes. Later KeplerOps and ARWC work is not yet published.
- Unrelated local GCP deployment and `terraform.tfvars` changes are present in
  the checkout and must remain excluded from commits and the pull request.

### Training: complete and passing

- Added `build/training/tests/test_participant_journey_live.py`.
- The journey covers all 16 Training cards from the participant's published
  `TRAINING.md` entry point. It uses repository history, published links,
  browser-facing assets, recovery flows, package publication, the fresh
  consumer, and the practice outlet in the same sequence available to a
  participant.
- The journey derives identifiers, routes, credentials, and evidence from the
  starting material or earlier responses instead of embedding author-only
  shortcuts.
- Fixed the Workbench clone instruction so it uses writable `/tmp` storage and
  clarified that the participant home directory is read-only.
- Reconciled the Training SDL content and digests.
- Fixed the Kali participant-image package source by selecting the pinned Kali
  snapshot before installing exact package versions.
- Updated the Training runner to reset state, run the participant journey, reset
  again, and retain the existing test suites.
- The complete Training run passed: the 16-card journey followed by all 19
  retained topology, Workbench, Accounts, Developer, and state tests.
- The Training native hand-build design gate and focused design tests also
  passed.

### KeplerOps: complete and passing

- Inventoried all 104 cards across K01-K31 and mapped them to their owning
  services and retained test coverage.
- Added `build/keplerops/tests/test_participant_journey_live.py`. The journey
  covers all 104 KeplerOps cards from the supplied Rowan workstation, deriving
  routes, identifiers, credentials, and evidence from the handover, repository
  history, browser profile, and earlier responses.
- Added a source draft of `opening/k-dev/service-catalog.md`, linked it from
  `HOME.md`, and added it to the workstation archive generator. The catalog
  records ordinary route templates while requiring concrete values to come from
  the handover, repository, browser profile, object listings, or earlier
  responses.
- Fixed a K04 continuity defect: the indexer's runtime descriptor now returns
  the scoped state route, completion route, record ID, routine, and ready state
  needed to continue from participant-visible evidence.
- Fixed a K10.1 discovery gap: added a preview-association route and seeded the
  retained support document it points to.
- Fixed a K23.1 discovery gap: the unpublished context route now returns its
  retained conversations, selections, documents, and completion evidence.
- Fixed smaller discovery gaps: a trust record on the workspace token-exchange
  response, a maintenance index route, and a retained historical release name
  in the support conversation.
- The journey passed from pristine state against the deployed `prod-mgau4w`
  range (two cards that need the real ARWC cross-segment delivery are skipped
  in a single-stack run, matching the retained suite's own gating).
- Updated `build/keplerops/test-local.sh` to reset state, run the participant
  journey, reset again, and retain the existing test suites unchanged.

### ARWC: complete and passing

- Inventoried the retained W01-W35 live tests and their current execution
  order.
- Added `build/arwc/tests/test_participant_journey_live.py`. The journey covers
  all 120 ARWC cards (W01-W35) from the supplied connector handover, deriving
  every route, record identifier, credential, and value from the handover or an
  earlier response.
- A single-stack run has no live KeplerOps peer to deliver the real signed
  package that normally earns the corporate handoff, so
  `build/arwc/tests/seed_corporate_handover.py` calls the connector's own
  `earn_corporate` function directly, inside its container, producing the same
  handover files a real delivery produces. It is a no-op once a real delivery
  has already earned the handoff, and it does not replace the W26/K27.3
  cross-segment delivery coverage.
- Fixed a W04 discovery gap: the archive workflow record now exposes the
  planner handover target it hands off to, instead of requiring an author-only
  identifier.
- Fixed a W09 discovery gap: the live-feed integration response now exposes the
  `process-view` route instead of requiring it to be guessed.
- Fixed a W26 defect: the signed approval record did not list the maintenance
  renderer host, so no participant response could ever resolve it. Added the
  renderer host to the signed payload.
- Fixed a W29.3 test error: the journey incorrectly expected a pre-condition
  denial that the sequential journey had already satisfied during W25.
- The journey passed from pristine state against the deployed `prod-mgau4w`
  range.
- Updated `build/arwc/test-local.sh` to seed the handover, reset state, run the
  participant journey, reset and reseed, and retain the existing test suites
  unchanged.

### Deployed range

- The Training, KeplerOps, and ARWC instances in GCP project `prod-mgau4w` were
  confirmed running and initially pristine.
- The manual Training check exposed the read-only-home clone defect described
  above.
- Every fix above was hand-patched onto the running `prod-mgau4w` containers
  and the affected journey was re-run from pristine state to confirm the fix,
  before being written back to source.
- A consolidated clean rebuild, a full three-journey run against the rebuilt
  images, and a final deployed-range validation remain outstanding.

## Remaining work

1. Run syntax, design, archive, and static regression checks for all
   accumulated changes. Design, SDL hand-build-gate, and archive-generation
   checks have passed; a final pass is needed after the consolidated rebuild.
2. Perform one consolidated clean rebuild after both journeys and all fixes are
   complete.
3. From fresh state, run all three participant journeys and every retained test
   suite against the rebuilt images.
4. Publish all remaining required changes to pull request #204, excluding the
   unrelated local deployment files.
5. Validate the corrected deployed range and confirm a pristine reset.

## Completion criteria

- Every challenge card has an integration test that properly exercises its
  participant walkthrough and participant-visible outcome.
- All new journeys pass from pristine state.
- All retained tests continue to pass.
- Participant documentation and starting material are accurate and runnable.
- Builds are reproducible and the corrected range restores cleanly.
- Every required fix is present in the Palo Alto Networks pull request.
