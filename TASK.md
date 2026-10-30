# Cinder Typhoon QA evidence

## Task

Qualify Cinder Typhoon for an authorized Palo Alto Networks defensive-training
event. Participants take the attacker perspective so defenders can experience
the methods, speed, and compounding effects of agent-assisted attacks. The
scenario is fictional, isolated, and bounded.

Automated solution code can prove that an intended path works. It cannot prove
that a fresh participant would discover that path, understand it, experience a
particular difficulty, or need a particular amount of time. Those claims
require blind human-plus-agent playtests.

## Current release status

**Not release qualified.** The machine-readable status is
`cinder-typhoon/tests/qa-status.json`; validate and print it with:

```sh
python3 cinder-typhoon/tests/report_qa_status.py
```

The four evidence layers are separate gates:

| Layer | What it establishes | Current candidate status |
| --- | --- | --- |
| Service contract tests | Normal, accepted, denied, persistence, isolation, and audit behavior | Not run on an immutable event candidate |
| Participant-boundary known-solution acceptance | The encoded solution sequence remains executable from the participant account and network | Not run on an immutable event candidate |
| Provenance and participant-surface checks | Starting visibility and the origin of every solution-path input | Failed/incomplete: the current goldens drift from the intended boundary and input provenance is pending |
| Blind human-plus-agent playtests | Discovery, fairness, understanding, difficulty, duration, abandonment, and agent contribution | Not run |

`--require-release-qualified` returns nonzero until all four layers have passing
evidence from the same immutable candidate:

```sh
python3 cinder-typhoon/tests/report_qa_status.py --require-release-qualified
```

## Evidence definitions

### 1. Service contract tests

These operator-only tests exercise service behavior directly. They must cover
normal behavior, accepted actions, malformed and unauthorized requests,
persistence, isolation, and independently owned audit evidence. They may use
operator inspection and direct service setup unavailable to participants.

### 2. Participant-boundary known-solution acceptance

The three operator-only suites encode known solution algorithms and expected
assertions:

| Phase | Suite | Cards represented |
| --- | --- | ---: |
| Training | `build/training/tests/test_known_solution_live.py` | 16 |
| KeplerOps | `build/keplerops/tests/test_known_solution_live.py` | 104 |
| ARWC | `build/arwc/tests/test_known_solution_live.py` | 120 |

They start from the intended participant accounts, workstations, files, tools,
DNS, CA material, and network positions. `build/participant-runner/run.py`
streams each suite into that unprivileged account without mounting test or
repository files. It verifies exact workstation networks and mounts, rejects
operator control and readable private state, and writes a credential-free
structured report containing request/response hashes, discovered artifact
hashes, completion assertions, reset identity and elapsed time. A pass
establishes known-path executability and expected completion evidence only. It
is not evidence of independent discovery, fairness, understanding, difficulty,
or duration.

The KeplerOps diagnostic and package deliveries are separate selectable
operations. Release evidence must run each after its own pristine reset, then
run the ARWC ending against the non-seeded transition earned by that route.
Candidate mode refuses a KeplerOps delivery without paired-carrier mode and
refuses an ARWC run without a declared, matching transition route.

### 3. Provenance and participant-surface checks

The participant-surface manifests define the intended pristine boundary and
compare it with unprivileged observation. Current golden checks expose three
release defects:

- Training contains an older `TRAINING.md` than the authored source.
- KeplerOps exposes readable build-time seed archives and its entrypoint.
- ARWC permits the participant to list the private customer-handover directory.

Complete solution-input provenance is tracked separately by issue #209.

### 4. Blind human-plus-agent playtests

Fresh participants must use the event UI, supported agents, and normal support
rules without repository source, runtime source, tests, operator documents, or
prior solutions. Results must include failed hypotheses and abandonment as well
as successes. This work is tracked by issue #229 and has not started.

## Golden range access

The current mutable goldens are inspection and remediation targets, not an
immutable event candidate.

| Phase | Instance | Stack path |
| --- | --- | --- |
| Training | `cinder-training-golden` | `/opt/cinder-typhoon/build/training` |
| KeplerOps | `cinder-keplerops-golden` | `/opt/cinder-typhoon/build/keplerops` |
| ARWC | `cinder-arwc-golden` | `/opt/cinder-typhoon/build/arwc` |

They are in GCP project `prod-mgau4w`, zone `us-central1-a`, with operator access
through IAP SSH. Golden identity and build inputs must be bound to the immutable
release manifest required by issue #232 before candidate results can pass.

## Running the automated layers

Each phase runner starts from pristine state, runs the participant-surface gate,
runs known-solution acceptance, resets consumed state, and then runs the
service-contract suites:

```sh
cinder-typhoon/build/training/test-local.sh
cinder-typhoon/build/keplerops/test-local.sh
cinder-typhoon/build/arwc/test-local.sh
```

The KeplerOps-to-ARWC transition requires the paired carriers. A single-stack
ARWC run may seed the ordinary handover for local contract and known-solution
testing; that seed is not evidence that the real cross-carrier transition
passed.

The local phase scripts use `--development`, which is explicitly mutable and
cannot qualify a release. Immutable-candidate invocation, report fields and the
per-route reset contract are documented in
`build/participant-runner/README.md`.

## Release qualification

Release qualification requires all of the following on one immutable candidate:

1. service-contract suites pass;
2. unprivileged known-solution acceptance passes from the real participant
   boundary, including both ordinary cross-carrier routes;
3. participant-surface and complete input-provenance checks pass;
4. blind human-plus-agent playtests pass their cohort and specialist coverage;
5. reset and restore reproduce the manifested pristine state; and
6. the 300-range production-equivalent soak passes its declared thresholds.

No automated result may be reported as proof of human discovery, difficulty, or
event duration.
