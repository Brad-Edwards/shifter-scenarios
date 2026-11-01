# Participant-boundary known-solution runner

This operator-only runner verifies that an encoded solution remains executable
from the same account, home directory, files, tools, DNS, CA material and
network position supplied to a participant. It does not measure discovery,
fairness, understanding, difficulty or duration for a fresh person.

The operator launcher uses Docker only to start one process as the existing
participant user in the existing workstation container. It streams the suite
on standard input and does not mount or copy tests, repository source, host
paths, service volumes, Docker control or operator credentials into that
workstation. Reset and report storage remain outside the participant boundary.

Before a suite runs, the launcher verifies the workstation's exact Compose
networks and mount destinations. The participant process then refuses root,
effective Linux capabilities, missing `no-new-privileges`, unexpected groups,
operator environment names, visible operator paths, readable private runtime
or service state, and Docker control. Its subprocess guard also rejects Docker,
Podman, `sudo`, namespace entry and container runtime commands.

The JSON report contains:

- immutable candidate identity, or an explicit mutable-development marker;
- reset identity, selected operation and exact test methods;
- participant identity and boundary controls;
- request host, path SHA-256 and status, plus response size and SHA-256, without
  path values, query strings, headers, bodies, tokens or credentials;
- discovered artifact path, size and SHA-256, without contents;
- completion counts, elapsed time and hashes of captured stdout/stderr.

Raw suite output is held only in launcher memory. Normal output prints one
summary line and never prints the captured streams. This prevents a failed
assertion from putting a reusable secret in normal CI logs.

## Development runs

Start a phase from pristine state, then run, for example:

```sh
python3 cinder-typhoon/build/participant-runner/run.py \
  --phase training \
  --operation all \
  --development \
  --reset-identity local-reset-001 \
  --report cinder-typhoon/build/training/.operator/known-solution-report.json
```

List operations without starting a range:

```sh
python3 cinder-typhoon/build/participant-runner/run.py --phase keplerops --list-operations
```

Every phase exposes `all` and a prerequisite-closing operation for each suite
method. KeplerOps additionally exposes `release-lineage`,
`delivery-diagnostic` and `delivery-package`. The two delivery operations omit
one another and are intended to run after separate pristine resets. ARWC
exposes `ending`, equivalent to its complete W01-W35 sequence.

Development mode is deliberately not release evidence. A single-stack ARWC
development run may use the existing standalone handover seed; an immutable
ARWC candidate run may not. A single-stack KeplerOps development run may record
the two cross-carrier assertions as skipped; candidate mode rejects every skip.

For paired development checks on the approved GCP goldens, use the scripted
launcher rather than starting either scenario locally or assembling individual
remote commands:

```sh
bash cinder-typhoon/build/participant-runner/check-development-pair.sh \
  delivery-package issue-264
```

The launcher resets both goldens, builds the synced KeplerOps source, requires
complete input provenance and the exact KeplerOps participant surface, and runs
the selected full KeplerOps carrier. It then verifies from the ARWC participant
boundary that the matching non-seeded transition receipt was earned. Docker
commands execute only on the named GCP instances. The separate ARWC W01-W35
suite and campaign-wide surface, coverage, and fourth-wall gates remain in
their own qualification lanes; they are not folded into an issue-scoped
development run for a different remediation category.

Live request entries include their current input-provenance sources and
unresolved items. This does not conflate the QA layers: known-solution behavior,
card coverage, fourth-wall leakage, and provenance retain separate statuses.
The candidate wrapper runs the fail-closed card-coverage, provenance, and live
fourth-wall gates before participant-surface and behavioral acceptance, so
incomplete coverage, unexplained input, or participant-facing implementation
language blocks overall qualification.

## Immutable candidates

`--candidate` consumes the strict identity format in `candidate.schema.json`.
The release-manifest producer is owned by the immutable-build work; this runner
requires a full source commit, digest-bound artifacts, named deployments and
`immutable: true`, then records the candidate manifest's SHA-256. Candidate
execution also compares GCE metadata (project, zone and instance) and the live
participant container image ID to that phase's declared deployment, so a report
cannot silently describe a different host or participant image.

A KeplerOps `all`, `delivery-diagnostic` or `delivery-package` candidate run
requires `--cross-segment`. An ARWC candidate run requires one of:

```text
--expected-transition diagnostic-execution
--expected-transition package-activation
```

The participant preflight reads its own transition note, verifies the declared
route, and rejects missing or standalone-seed receipts. A release pipeline must
therefore use a fresh reset identity for each KeplerOps route, then run the ARWC
ending against the handover earned by that same route and reset.

`check-candidate.sh` runs one operation against a documented GCP candidate. It
expects the candidate manifest to already exist on the range host; it does not
upload source or evidence. It first requires complete card coverage and input
provenance, then a clean unprivileged fourth-wall observation and matching
participant-surface manifest. It invokes known-solution acceptance and repeats
the fourth-wall observation afterward, so responses and artifacts generated by
the accepted route are also covered. The current mutable goldens remain
remediation targets and cannot produce a candidate pass.

## Evidence limits

A pass proves only that the selected encoded path completed from the verified
participant boundary and produced its assertions. The suite contains the
solution and expected results. Blind human-plus-agent playtests remain required
for discovery, fairness, understanding, difficulty and duration claims.
