# Cinder Typhoon QA evidence

## Task

Qualify Cinder Typhoon for an authorized Palo Alto Networks defensive-training
event. Participants take the attacker perspective so defenders can experience
the methods, speed, and compounding effects of agent-assisted attacks. The
scenario is fictional, isolated, and bounded.

Automated solution code can prove that an intended path works. It cannot prove
that a fresh participant would discover that path, understand it, experience a
particular difficulty, or need a particular amount of time. Those claims need
blind human-plus-agent playtests.

## Current release status

**Not release qualified.** The committed candidate is mutable, its image
digests are placeholders, no versioned release manifest exists, and none of the
four QA layers has a report from one immutable event candidate.

The current repository checks report:

| QA layer | Implemented | Candidate evidence |
| --- | --- | --- |
| Service contract | Complete: its required static/unit gate passes | Not run |
| Participant-boundary known solution | Partial: card coverage, hint delivery, and route/discovery units pass; the ARWC artifact-derived analysis acceptance gate is still open | Not run |
| Provenance and participant surface | Partial: provenance and authored-surface gates pass; the static fourth-wall gate still reports 17 KeplerOps and 456 ARWC findings | Not run |
| Blind human-plus-agent playtest | Not started | Not run |

These values are checked, not copied from prose. Run:

```sh
python3 cinder-typhoon/tests/report_qa_status.py
```

The checker runs every command in
`cinder-typhoon/tests/qa-gates.json`, derives open blockers from
`cinder-typhoon/tests/readiness-issues.json`, and rejects a claimed
implementation status that does not match those results. The SHA-256 bindings
for both files are in `cinder-typhoon/tests/qa-status.json`, so editing a gate
or blocker snapshot without updating the status fails.

The registry identifies #271 as its own delivery issue and excludes only that
one issue from readiness blockers. This keeps the merged checker valid when
#271 is manually closed; every other open issue in milestone #4 must appear in
the registry.

To compare the blocker snapshot with the GitHub milestone, use the repository
token without putting it on the command line:

```sh
python3 cinder-typhoon/tests/report_qa_status.py --check-github-issues
```

`--require-release-qualified` fails until the current commit, candidate
manifest, release manifest, and every required report are digest-bound to one
immutable release:

```sh
python3 cinder-typhoon/tests/report_qa_status.py --require-release-qualified
```

## Readiness words have separate meanings

| Stage | Meaning |
| --- | --- |
| Merged | The change is present in repository history. This is not acceptance evidence. |
| Implemented | Every named implementation gate for that QA layer passes on the current tree. |
| Statically verified | The current source has passed the named static and unit checks. No live range claim follows. |
| Live verified | A report from the real participant boundary passes and is bound to the current source, immutable candidate manifest, and versioned release manifest. |
| Playtested | Fresh participants and their supported agents completed the declared blind-test protocol on that same candidate. |
| Soaked | The production-equivalent capacity, transition, and reset test passed on that same release. |
| Release qualified | All required implementation, live, playtest, and soak evidence passes with no open release blocker, all bound to the same immutable release. |

Closing an issue follows the same rule. A merge is not enough. A closed entry in
the readiness registry must name every required acceptance result, the exact
command used to obtain it, the report path and digest, and the source commit.
Static acceptance is labeled as such and cannot make a live claim. Release
acceptance must also carry the candidate and release-manifest digests. The
checker rejects a closed entry without the evidence required for its scope.

## Evidence binding

`cinder-typhoon/tests/qa-status.json` is the readiness index. It binds:

- the implementation-gate catalog;
- the checked GitHub issue snapshot;
- `build/participant-runner/candidate.json` and its digest;
- the expected versioned release-manifest path and digest; and
- the five required release reports: service contract, known solution,
  provenance/surface, blind playtest, and soak.

The release-manifest status is currently `missing`, and candidate report lists
are empty. That is deliberate: the repository does not claim live verification
without immutable evidence. A report is accepted only when its own digest,
source commit, candidate-manifest digest, and release-manifest digest all match
the index. Missing, changed, stale, cross-commit, mutable-candidate, and
cross-release reports fail closed.

For an operator-only, credential-free record of the current static/unit gate
run, write a report outside the repository:

```sh
python3 cinder-typhoon/tests/report_qa_status.py \
  --output /tmp/cinder-typhoon-qa-status.json
```

The file is written mode `0600`. It records command arguments, pass/fail
checks, and output hashes, not raw command output or credentials. It is not a
substitute for an immutable live candidate report.

## The four QA layers

### 1. Service contract

Operator-only tests exercise normal behavior, accepted actions, malformed and
unauthorized requests, persistence, isolation, and independently owned audit
evidence. They may use service setup unavailable to participants. Their current
implementation gate is green; the live candidate has not been run.

### 2. Participant-boundary known solution

The operator-only suites are:

| Phase | Suite | Cards represented |
| --- | --- | ---: |
| Training | `build/training/tests/test_known_solution_live.py` | 16 |
| KeplerOps | `build/keplerops/tests/test_known_solution_live.py` | 104 |
| ARWC | `build/arwc/tests/test_known_solution_live.py` | 120 |

`build/participant-runner/run.py` streams a suite into the unprivileged
participant account without mounting repository or test files. A passing run
establishes known-path executability and expected completion evidence only. It
does not establish independent discovery, fairness, understanding, difficulty,
or duration.

The implementation layer remains partial until the ARWC W22, W23, W24, W33,
and W34 values are derived by executable artifact analysis and their named
acceptance evidence passes. There is no immutable candidate run yet.

### 3. Provenance and participant surface

This layer combines three distinct checks:

- participant-surface manifests define the intended pristine boundary;
- input provenance accounts for every request input and fixed comparison; and
- the fourth-wall scanner rejects card IDs, card titles, implementation
  language, and unapproved domain interfaces in participant-visible content.

Input provenance is complete and the authored participant-surface validation
passes. The static fourth-wall implementation gate is not complete: Training
has zero static findings, while KeplerOps and ARWC retain unresolved findings.
No pre/post live observation from an immutable candidate exists.

### 4. Blind human-plus-agent playtest

Fresh participants must use the event UI, supported agents, and normal support
rules without repository source, runtime source, tests, operator documents, or
prior solutions. Results must include failed hypotheses and abandonment as well
as successes. This layer has not started and no human-outcome claim is made.

## Golden range boundary

The GCP goldens in project `prod-mgau4w` are mutable inspection and remediation
targets. They are not an event candidate. Golden checks must be run by the
repository scripts against disposable copies or the approved golden range; the
scenario stack must not be started on a developer workstation.

| Phase | Instance | Stack path |
| --- | --- | --- |
| Training | `cinder-training-golden` | `/opt/cinder-typhoon/build/training` |
| KeplerOps | `cinder-keplerops-golden` | `/opt/cinder-typhoon/build/keplerops` |
| ARWC | `cinder-arwc-golden` | `/opt/cinder-typhoon/build/arwc` |

Their identity and build inputs must be bound to the versioned release manifest
before a live report can support qualification.

## Release qualification

Release qualification requires all of the following on one immutable release:

1. service-contract suites pass;
2. participant-boundary known-solution acceptance passes for every route;
3. card coverage, fourth-wall, participant-surface, and input-provenance gates
   pass before and after the participant run;
4. blind human-plus-agent playtests pass their declared cohort and specialist
   coverage;
5. reset and restore reproduce the manifested pristine state; and
6. the production-equivalent 300-range soak passes its declared thresholds.

No automated result may be reported as proof of human discovery, fairness,
difficulty, understanding, or event duration.
