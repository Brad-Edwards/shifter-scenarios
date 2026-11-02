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
  --output /tmp/cinder-typhoon-event-content.json \
  --prize-policy-output /tmp/cinder-typhoon-event-prizes.json
```

Each output is written atomically with owner-only permissions. The participant
content contains no answers, credentials, solution text, or operator-only prize
data. The separate prize sidecar validates against the committed
[`cinder-typhoon.event-prize-policy/v1` schema](../docs/design/event-prize-policy.schema.json)
and contains the exact 240-card stage membership, 50 slot identities, triggers,
tie-breaks, and rollover rules. It contains no draw seed, event timestamps,
winner identity, nomination, claim, or inventory state.

The command prints the catalog revision and SHA-256 digests of both exact JSON
artifacts. Publish and bind the pair together: the policy records the digest of
the participant bundle generated in the same run. Changing the scorer origin or
any participant content changes that digest and requires a new sidecar. Shifter
must compare the pair before event activation and prize finalization; runtime
enforcement is tracked in the remaining milestone 5 issues in this repository.

## Authoritative prize inputs

[`prize_inputs.py`](prize_inputs.py) turns one organizer-authorized, event-scoped
source projection into the closed
[`cinder-typhoon.event-prize-input/v1` contract](../docs/design/event-prize-input.schema.json).
The output contains only the facts needed by the prize evaluator:

- the event, content, policy, cutoff, and draw-commitment bindings;
- stable private participant IDs, public aliases, and the existing ranked-player
  eligibility result;
- accepted submission IDs, stable challenge source IDs, awarded points, and
  server receipt times;
- the authoritative overall score inputs in the complete stable order;
- stage scores and exact-set completion derived from the policy source IDs; and
- stable solve and scheduled-task occurrence IDs with scheduled and actual
  execution times.

The source must use `cinder-typhoon.authoritative-prize-source/v1` and contain
the exact closed fields accepted by `build_prize_input`. Produce it inside an
approved organizer-authorized integration from committed event records. The
adapter intentionally has no network client, browser fallback, webhook trust,
or database credentials. The caller remains responsible for the existing event
authorization check.

The general event-results export is not enough by itself because it does not
carry the accepted submission UUID or stable challenge source ID. Do not recover
either value from a challenge display name. An approved projection must provide
the authoritative fields directly; otherwise this adapter fails closed.

Build the owner-only evaluator input with:

```sh
python3 cinder-typhoon/ctfd/prize_inputs.py \
  --policy /secure/event-prizes.json \
  --source /secure/authoritative-prize-source.json \
  --output /secure/event-prize-input.json
```

Identical submission or occurrence retries collapse to one fact. Conflicting
identity reuse, cross-event rows, incomplete rankings, content or policy drift,
unknown source IDs, invalid UTC cutoffs, and extra fields such as email fail the
entire build. Rejected submissions and accepted rows outside the event snapshot
window create no prize fact. Stage and event close occurrences retain both the
scheduled cutoff and actual execution time. Rebuilding the same source snapshot
and policy produces the same bytes and digest.

## Prize evaluation

[`prize_evaluator.py`](prize_evaluator.py) reconciles the validated input into
an owner-only SQLite state file. It orders accepted solves and scheduled closes
by authoritative semantic time, applies every selector in the policy order, and
records only bindings, 50 slots, occurrence proofs, and allocation attempts.
The database contains no submission ledger, public aliases, nomination ballots,
or draw seed.

Create a dedicated 32-byte random seed before the event, calculate its
commitment with `seed_commitment(event_id, seed)`, and bind that commitment in
the authoritative input. Keep the seed in the approved encrypted secret store;
when evaluation runs, materialize it as exactly 64 hexadecimal characters in an
owner-only file. The evaluator does not invent a second encryption or key
management scheme. Evaluate or reconcile with:

```sh
python3 cinder-typhoon/ctfd/prize_evaluator.py \
  --policy /secure/event-prizes.json \
  --input /secure/event-prize-input.json \
  --state /secure/event-prize-state.sqlite3 \
  --seed-file /secure/event-prize-seed.hex \
  --nominations /secure/event-prize-nominations.json
```

The optional nominations file uses
`cinder-typhoon.prize-nominations/v1`; issue #290 owns its participant-facing
collection surface. Reconciliation fails if a close is missing any earlier
accepted-solve occurrence. An identical occurrence retry returns its recorded
result, while changed inputs, policy/content drift, a different committed seed,
or a changed slot projection stop the transaction. SQLite partial unique indexes
enforce one live allocation per participant and slot. A void retains the prior
generation and proof; finalization can fill the next generation without deleting
history. The operator state is private and must not be served to participants.

The separately versioned `build/hint-delivery/manifest.json` pins the hint
sources and facilitator release rules. Use `build/hint-delivery/release.py` to
release one level and create the content-free audit record; do not disclose the
owner-only event bundle as a substitute.

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
