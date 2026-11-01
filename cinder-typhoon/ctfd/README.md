# Shifter event-content projection

[`import_catalog.py`](import_catalog.py) reads the one authoritative participant
snapshot at `../challenges/challenges.yaml` and projects it into Shifter's native
`shifter-ctf-content/v1` format. It does not read challenge briefs, dependency
internals, known-solution tests, or operator design fields.

The projection preserves all 240 card IDs, titles, descriptions, static scores,
graduated hints, ordering, and visibility. It adds one range-owned HTTPS scorer
binding per card. The catalog revision is sent with every scoring request so a
changed authoring prerequisite or delivery input cannot silently use an older
scorer contract. The native UI supports four difficulty labels, so the seven
elite cards display as expert while retaining their 800-point score.

Campaign alternatives and capabilities are enforced by range-owned evidence,
not by scoreboard solves. All cards remain visible; flattening the authored OR
graph into Shifter's AND-only prerequisite rows would change the campaign.

Build a private import artifact with:

```sh
python3 cinder-typhoon/ctfd/import_catalog.py \
  --scorer-origin https://SCORER.example.test \
  --output /tmp/cinder-typhoon-event-content.json
```

The output is written atomically with owner-only permissions. It contains no
answers, credentials, solution text, or operator-only design data.

## Golden GCP acceptance

`check-golden-gcp.sh` is the only supported live acceptance entrypoint. It
creates a disposable machine-image copy of `cinder-training-golden` in the
approved GCP project, transfers committed source only, and runs two checks on
that copy:

- the current Shifter native parser, hydration service, participant API, HTTP
  evidence submission, and score maintenance path; and
- the current Shifter `ChallengesPage` component with all 240 imported cards,
  asserting every displayed score.

The external evidence verifier response is controlled at the pinned HTTPS
connection boundary. Shifter's real HTTP validator still performs URL policy,
DNS pinning, request construction, revision-header delivery, response parsing,
submission, and score maintenance. This keeps the test deterministic without
replacing any native import or scoring service.

The original golden is never changed. The script deletes its temporary VM and
machine image on success or failure and runs no local containers. Point it at a
clean platform checkout whose `HEAD` is the version under test:

```sh
CINDER_SHIFTER_ROOT=/path/to/shifter-platform-checkout \
  cinder-typhoon/ctfd/check-golden-gcp.sh ct511a
```

Set `CINDER_KEEP_TEST_RANGE=1` only when a failed run needs remote inspection.
