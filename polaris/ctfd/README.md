# Polaris CTFd adapters

The reference loader projects the canonical Polaris flag layer into CTFd. The
source contracts are:

- `../flags/placement.yaml` — stable flag ids, synthetic values, ACES hosts,
  and runtime recovery paths.
- `../challenges/challenges.yaml` — participant-facing titles, questions,
  difficulty, points, and hints.
- `../oracle/affordances.yaml` — private `{flag_id, path_step}` bindings.

CTFd category, live numeric ids, managed tags, and presentation state are
adapter-local. CTFd submissions and points never establish ACES objective
success.

## Validate and dry-run

```bash
python3 ../validation/validate_oracle.py validate
python3 -m unittest discover -s tests
python3 sync_polaris_ctfd.py \
  --base-url https://polaris.example.com \
  --profile aws_event \
  --dry-run
```

`local_degraded` is source validation only. Live synchronization accepts
`aws_event` because that is the event board/runtime pairing; CTFd flags still
do not establish participant-equivalent package or golden proof.

## Synchronize a board

Provide the admin token through `CTFD_TOKEN` or a regular, non-symlink token
file with no group/world permissions:

```bash
export CTFD_TOKEN=<admin-token>
python3 sync_polaris_ctfd.py \
  --base-url https://polaris.example.com \
  --profile aws_event \
  --event-namespace exercise-1
```

The optional event namespace lets multiple events share a board. Ownership is
keyed by pack, namespace, and stable `flag_id`, so title/category changes update
the same live row. The loader:

- validates the complete source before writes;
- leaves rows hidden until flags, hints, and managed tags reconcile;
- preserves unrelated challenges and unrelated tags;
- deletes only stale rows in the same managed namespace;
- repairs partial writes on rerun; and
- reads challenge state, points, flags, hints, and ownership back before
  reporting success.

Plain HTTP is refused except when `--allow-loopback-http` is explicitly paired
with a loopback URL. Requests have bounded time and response size, authorization
does not cross origins, and failures never print remote bodies or answer data.

Canonical `FLAG{<16-hex>}` values are represented on CTFd by a case-insensitive
regular expression that accepts either the wrapped form or the inner 16 hex
characters. Repository source and walkthroughs retain the wrapped form.

## Separate event operations

The onboarding pages/warm-up, standalone agentic workshop, participant account
creation, and range administration are separate event-operations tools. They
are not part of the canonical flag inventory or reference loader:

- `sync_polaris_ctfd_onboarding.py`
- `seed_ctfd.py`
- `create_users.py`
- `sync_range_flags.py`

Those tools do not define stable flag identity, placement, scoring authority,
or participant proof.
