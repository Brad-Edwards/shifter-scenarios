# Known caveats

## Reserved challenge

`kep-m02-g` remains reserved/under consideration pending the final decision on
physical or emulated edge-accelerator attestation. Do not include it in a live
playtest set unless the event coordinator explicitly decides how that path will
be represented.

## Assurance level

The active software-backed challenge set is automated-proven at the
pre-playtest bar. That is not the same as a final golden release claim. Final
golden still requires the release walkthrough, evidence reconciliation, and
teardown checklist in one release run.

## Participant performance

The range is intended for both human and agent-assisted play, but not every
participant will drive an offensive agent. Treat speed, prompt quality, and tool
choice as playtest observations rather than assumptions.

## Concurrent range capacity

The current GCP project has a 500 global firewall-rule quota. A full KeplerOps
AI range currently consumes roughly 138 firewall rules, so three retained
standalone ranges plus other project infrastructure can exhaust the quota. Tear
down superseded retained ranges before launching additional standalone copies,
or raise the project quota before scheduling more concurrent playtest ranges.
