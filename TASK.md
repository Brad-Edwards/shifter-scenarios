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
| Participant-boundary known-solution acceptance | The encoded solution sequence remains executable from the participant account and network | Failed/incomplete: every card has a named assertion, but independent-evidence, simple-read, and delivery-catalog gates remain open; no immutable candidate run exists |
| Provenance, participant-surface, and fourth-wall checks | Starting visibility, in-world presentation, and the origin of every solution-path input | Failed/incomplete: the current goldens drift from the intended boundary, fourth-wall findings remain, and input provenance is pending |
| Blind human-plus-agent playtests | Discovery, fairness, understanding, difficulty, duration, abandonment, and agent contribution | Not run |

`--require-release-qualified` returns nonzero until all four layers have passing
evidence from the same immutable candidate:

```sh
python3 cinder-typhoon/tests/report_qa_status.py --require-release-qualified
```

## Remediation campaign handoff (2026-10-30)

The remediation work is being delivered as one pull request per issue on a
stack of feature branches. Nothing in the stack has been merged. Each new
branch is based on the preceding issue branch so work can continue without
waiting for reviews or merges:

| Issue | Pull request | State in this stack |
| --- | --- | --- |
| #206 participant-surface manifest | #235 | Implemented and published |
| #207 four-layer QA model | #236 | Implemented and published on #206 |
| #208 participant-boundary acceptance | #237 | Implemented and published on #207 |
| #209 solution-input provenance | #238 | Implemented and published on #208 |
| #210 independent card coverage | #239 | Implemented and published on #209 |
| #211 fourth-wall checks | #240 | Implemented and published on #210 |
| #212 KeplerOps discovery design | Not opened yet | In progress on `212-keplerops-discovery-design`, based on #211 |

“Implemented” here means the issue branch and pull request exist; it does not
mean approved, merged, or release qualified. GitHub still correctly reports
#206–#212 as open.

### Issue #212 current state

The participant-visible `work/service-catalog.md` was an exhaustive list of 101
routes and also disclosed the native indexer’s decisive values and continuation
request. The known-solution suite imported those answers directly. The current
uncommitted #212 work has:

- removed that catalog from the authored workstation source and archive recipe;
- added a graph of 13 service-owned client references, beginning at the one
  ordinary source reference in Rowan’s developer notes;
- added a common `/.well-known/fieldkest-client` response on the relevant
  services, with each response limited to that service and explicit links to
  related references;
- added a normal offline indexer reproducer manifest and a stripped reproducer
  build for the developer workstation; and
- changed the indexer to return its continuation request only in the successful
  state-changing response, so it is earned rather than disclosed up front.

The #212 source and test remediation is complete and committed. The following
items were implemented and verified by static tests (all pass locally):

1. `test_known_solution_live.py`: `setUpClass` now crawls the linked client
   references from `service-notes.md` instead of reading `service-catalog.md`;
   `discovered_route` resolves from the crawled dict; K04.1 derives allocation
   and sentinel by probing the offline reproducer binary.
2. Provenance ledger updated: K04 and `bundle_indexer.c` cite the binary as
   `supplied_starting_surface`; 13 changed method fingerprints regenerated;
   `http_support.py` comparison count updated.
3. Participant-surface manifest: `service-catalog.md` replaced by
   `work/reproducers/indexer-client.json`; `keplerops-service-catalog`
   disclosure replaced by 13 `client-reference` disclosures (one per service in
   the graph) plus `keplerops-indexer-client`; `HOME.md` and `service-notes.md`
   hashes updated.
4. Static gates: `validate_keplerops.py` adds catalog-absence check and
   `check_client_reference_graph`; `test_keplerops_design.py` and
   `test_participant_surface.py` verify the new design and the absence of the
   catalog.
5. SDL bindings: `k-dev-home.tar` and `k-support-state.tar` digest drift fixed.
6. `validate.py`: allows `https://` paths for `client-reference` disclosures.

The stacked PR for #212 is open. The next open milestone items are #213–#218
(KeplerOps interface migration) and #219–#224 (ARWC domain and discovery).

There are unrelated pre-existing local edits in the GCP deployment files and
untracked local QA material. Preserve them and do not stage them in remediation
commits.

### Remaining milestone work

After #212–#224 (PR stack #241–#253), the open milestone work is:

- #213–#218: ✅ KeplerOps interface migration complete (opcode model via API,
  K18 dossier-derived subject, K26 earned bearer, K11/K18/K29 author-only values
  removed, generic backend profiles classified)
- #219–#224: ✅ ARWC domain redesign complete (design map, W01–W35 resource-
  oriented routes, client reference graph, W33 real starting material, full
  provenance review, overall_status: complete)
- #225–#230: add safe per-range variation, authoritative challenge delivery and
  scoring, graduated in-world hints, explicit defender-learning outcomes, blind
  human-plus-agent playtests, and evidence-based duration/tier calibration; and
- #231–#234: repair pre-handoff service health, bind goldens to an immutable
  release manifest, run the production-equivalent 300-range soak/transition/
  reset test, and reconcile every public readiness claim with measured evidence.

### Guidance for subsequent implementations

- A known-solution test must prove the path a participant can derive. It must
  not act as the source of routes, credentials, protocol values, or accepted
  payloads.
- Put ordinary first contacts in workstation material. Put the rest in the
  systems that naturally own them: client references, application navigation,
  package metadata, source history, browser history, build records, support
  records, cloud policy, identity metadata, and earlier accepted responses.
- Service documentation may describe normal methods and schemas. It must not
  explain the challenge, name a card, prescribe an exploit, publish a flag, or
  reveal a later privileged continuation.
- Earned responses should carry the identifiers, authority, and next interfaces
  needed later. This both models real attack chaining and gives tests a concrete
  provenance trail.
- Keep component contract tests and participant-boundary acceptance distinct.
  Contract tests may inspect operator-owned evidence; participant acceptance may
  use only the participant account, its network, its tools, and earned state.
- Bounds in automated analysis are reliability controls, not reductions in the
  attacker experience. Candidate values should come from supplied artifacts or
  observed interfaces, and a missing derivation should fail clearly rather than
  fall back to guessing or an author literal.
- No automated pass supports claims about discovery, fairness, difficulty,
  defender learning, or event duration. Preserve those claims for blind tests
  with fresh people and their supported agents.

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

The solution-input provenance gate is implemented by issue #209.

The #209 ledger and report now inventory every known-solution request callsite
and ratchet every fixed literal comparison in phase runtime Python. They contain
only locations, provenance classes, citations and SHA-256 fingerprints—not
literal values, credentials, request bodies or responses. The release form is
intentionally unresolved: K18's federated subject (#216), K26's fixed channel
bearer (#217), W33's test-only scheduler inputs (#223), and the broader exact
comparison audit (#224) must be remediated and cited before provenance can pass.

The #210 card-coverage registry independently reconciles the 240 SDL contracts,
briefs, dependency entries, and named participant-boundary assertions. K20.1,
K20.2, and K20.3 now perform and assert separate relation, managed-identity, and
approval-plus-consumer actions. The release form remains unresolved where a
simple endpoint read has no reviewed interpretive achievement and while the
participant delivery catalog is empty pending #226. It also rejects every
current SDL evidence-owner declaration because each overlaps the component
that accepted the action; an observed-state label alone is not independent
evidence.

The #211 fourth-wall gate derives card IDs and normalized titles from that
private registry, scans authored participant-facing runtime and image inputs,
then repeats the check against readable files and safe `GET` responses from the
real unprivileged phase container before and after known-solution acceptance.
It emits locations, rule matches, and hashes only. The current result remains
failed: ARWC still uses card-title routes,
KeplerOps retains challenge-derived build names, and the domain-interface
reviews required by #212 and #219 are pending. Exact hash-bound allowlist
entries are supported for credible in-world uses; the committed allowlist is
empty.

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

Known-solution behavior, card coverage, fourth-wall leakage, and input
provenance remain separate QA results. The candidate wrapper runs the
fail-closed coverage, provenance, and live leakage gates before
participant-surface and behavioral acceptance, so an incomplete card,
unexplained input, or fourth-wall finding blocks overall qualification without
misreporting what the behavioral suite established.

## Release qualification

Release qualification requires all of the following on one immutable candidate:

1. service-contract suites pass;
2. unprivileged known-solution acceptance passes from the real participant
   boundary, including both ordinary cross-carrier routes;
3. card coverage, fourth-wall, participant-surface, and complete input-provenance checks pass;
4. blind human-plus-agent playtests pass their cohort and specialist coverage;
5. reset and restore reproduce the manifested pristine state; and
6. the 300-range production-equivalent soak passes its declared thresholds.

No automated result may be reported as proof of human discovery, difficulty, or
event duration.
