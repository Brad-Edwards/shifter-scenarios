# Training hand-build readiness — 25 September 2026

**Design gate ready. No golden-range build has started.**

The gate is narrow and concrete: a builder can construct all four Training
systems without inventing gameplay, weakness mechanics, normal behavior,
access rules, required records, artifact placement, progression, or network
opening. It does not claim that a running implementation has passed integration
testing or playtesting.

## Boundary

The SDL defines the in-world systems, software requirements, configuration,
identities, permissions, content, services, network, and state transitions.
Every intended path arises from that state. Objectives and assertions specify
observable outcomes; they do not create missing service behavior, permission,
or successful evidence.

Submission adjudication and organizer recovery after infrastructure faults are
external. Training contains no participant-facing restore operation,
completion-triggered rewind, automatic credential revocation, or
evaluation-triggered visibility change. The practice tank's hold control is an
ordinary in-world process control, not an environment recovery mechanism.

RAE 5.0.0 already supplies the semantics used here: modular imports/exports,
native content, runtime filesystem/network/listener/application inventories,
application RBAC, accounts, objectives, assertions, workflows, action
contracts, evidence requirements, and realization posture. No upstream
expressivity gap was found and no Training relationship uses private
properties.

## Complete design surface

| Area | Fixed design |
| --- | --- |
| Opening and transport | One internal `10.77.40.0/24` subnet; exact `.10/.20/.30/.40/.50` endpoints; `*.training` names; Kali attached only to Training; local opening document names all four desks. |
| T01.1 | Exact blank current handover, tracker, two-commit deterministic Git seed, read-only Git smart HTTP, and matching `DL-204` ancestor evidence. |
| T01.2 | Exact notice, web manifest, current/retired indexes, withdrawn amendment, read-only routes, and retrieval audit fields. |
| T01.3 | Exact retired client profile/history, synthetic bearer fixture, one-delivery RBAC grant, sealed manifest, response classes, persistence, and audit fields. |
| T01.4 | Exact public/internal JSON records and the bounded raw-prefix-before-decode traversal. The selected path is percent-decoded once, normalized inside a fixed data root, never executed, and has no outbound network or writable data. |
| T02.1 | Three contextual candidates, active/inactive/unknown response classes, six-per-minute bound, one active case fragment, and lookup audit. |
| T02.2 | Exact public directory/client, `STF-204` coordinator request, private roster detail, absent server authorization, denials for unrelated/unknown records, and read audit. |
| T02.3 | Exact three-factor tuple, single redemption, 32-byte opaque persistent session, authenticated private handover, failure classes, and audit fields. |
| T02.4 | Exactly two assignment records, fair discovery of `ASG-317`, native RBAC grant `assignment-briefs/*`, session requirement, unknown-record behavior, and owner/request audit. |
| T03.1 | Exact two-commit source seed, deleted `DL-204` fixture, head review note, read-only Forge/Git routes, and independently published current consumer contract. |
| T03.2 | Exact failed build log, synthetic publisher credential, protected channel manifest, native read/publish grants limited to `@cinder/delivery-formatter`, denials outside that scope, and audit fields. |
| T03.3 | Exact unpacked package manifest/lockfile/script/source. Static inspection reveals the lifecycle action, source path, and destination; the supplied environment never installs it. |
| T03.4 | Exact publication body, size/version/name rules, immutable versions, canonical digest rule, highest-compatible stable SemVer resolution, fixed consumer input, DF-1 output validation, isolated one-shot worker, and append-only receipt. |
| T04.1–T04.4 | Exact captures, revision-matched status legend, independent replay, distinct tank identities, initial live state, process bounds, timing, sampling, idempotency, serialization, response classes, persistence, and audit records. |

The [artifact placement contract](../../assets/training/README.md) maps all 47
authored files to their owning node and exact destination family. Seven native
content modules carry their literal bytes. Runtime inventory binds every file to
an owner, mode, SHA-256, stability, and sensitivity. Application records bind
each exposed file or stateful operation to a named listener, method, input,
response, and authority requirement.

Training preserves 12 Easy and 4 Medium objectives. T03.4 depends on the scoped
publisher access, not on the historical fixture. T04.3 is independently usable
because the live view and field guide expose its own current status and legend.
Training remains optional and conveys no KeplerOps or ARWC authority.

## Hand-build gate

`hand_build_gaps()` fails if placeholder Training datasets return, an exact
content record is missing, any of the four service/application inventories is
absent, a target lacks its single exact network endpoint, Kali loses its sole
Training attachment, or any application behavior contract is absent. The gate
currently returns no gaps.

The focused tests also reject byte/placement/ownership drift, accidental public
exposure, fourth-wall text in in-world artifacts, private relationship
semantics, generic recovery preconditions, address collisions, broadened
registry scope, changed assignment scope, and inconsistent tank/replay data.

## Verification command

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/cinder-sdl-check/bin/python cinder-typhoon/tests/test_training_design.py
PYTHONDONTWRITEBYTECODE=1 /tmp/cinder-sdl-check/bin/python cinder-typhoon/tests/validate_sdl.py --self-test --pack-check --pack-max-members 2048 --training-hand-build-gate
```

The explicit 2,048-member pack limit is the upstream `PackValidationLimits`
input. It changes no SDL semantics or validation rule. Static validation is the
gate to start a hand build; it is not evidence that the future implementation
works. Integration tests and initial play observations belong to the later
golden-range stage.
