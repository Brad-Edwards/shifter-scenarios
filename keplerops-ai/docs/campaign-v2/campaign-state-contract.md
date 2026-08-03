# Campaign State And Reset Contract

## Purpose

KeplerOps is one connected intrusion. A participant who earns an identity,
artifact, conversation, corpus, model, or release state must be able to use it
later. Reset exists to recover a failed operation, not to erase completed
campaign work.

This contract is binding on operation design, build scripts, validators, and
facilitator actions.

## State Classes

| Class | Examples | Reset behavior |
|---|---|---|
| Clean baseline | Patched services, ordinary company data, initial identities, workflows, telemetry, backup and reset foundations | Restored only by full-range rebuild from the clean manifest. |
| Campaign-start overlay | Reviewed vulnerable pins, insecure ACLs, clues, static flags and synthetic attack content | Applied as a source-controlled diff after the clean gates pass; restored by reprovisioning the campaign candidate. |
| Earned checkpoint | Guest identity, accepted package, successful mail thread, access grant, poisoned document, trained model, promoted digest | Immutable after success. Normal operation reset cannot delete or revoke it. |
| Attempt state | Draft submissions, failed jobs, temporary pods, recipient workspace, browser profile, callback cursor, evaluation scratch data | Namespaced per attempt and safe to discard. |
| Descendant state | A model trained from a dataset, a release built from a model, production loaded from a release | Retained while every ancestor checkpoint remains valid. |
| Shared service state | Pooled inference model, review queue, physical-lane reservation, common package cache | Isolated by range and operation identity; reset releases only the current range's lease or request. |
| Score state | Shifter submission and award | Owned by Shifter; never used as an enterprise prerequisite or source of truth. |

## Immutable Success Rule

Each successful operation creates one immutable checkpoint record in its normal
owning system. The record contains the exact artifact digests, identities,
grants, source record IDs, job IDs, and timestamps needed by descendants. A
checkpoint is not a challenge receipt: it is an ordinary release, run,
invitation, thread, registry entry, object version, audit record, or other
enterprise artifact.

Flags are static synthetic scenario content under `challenge-contract.md`.
Reconnaissance flags may be seeded in public records at participant start; the
operation is discovering the record through the stated research path. Other
flags are emitted into the final normal record or protected artifact only when
the qualifying action creates that state. A participant may submit the flag to
Shifter, but no KeplerOps service calls Shifter or treats score state as
campaign state.

## Attempt Isolation

Every mutable operation begins in a new attempt namespace with:

- a stable operation-independent enterprise identity;
- a unique attempt ID visible in normal job, ticket, thread, or trace state;
- copy-on-write or versioned mutable inputs;
- bounded worker, model, queue, and storage resources;
- explicit maximum duration and terminal failure observations; and
- a parent-checkpoint manifest naming every earned prerequisite consumed.

Successful outputs are promoted from attempt state to an immutable earned
checkpoint. Failed outputs remain disposable and cannot overwrite a prior
success.

## Reset Semantics

### Operation Reset

An operation reset may:

- cancel and delete the active attempt;
- recreate disposable workers, pods, browser profiles, notebooks, and caches;
- clear failed ticket, queue, callback, trace, and temporary storage records;
- rotate an attempt-scoped token; and
- reissue an equivalent session or invitation for an already-earned grant.

An operation reset may not:

- delete a successful participant artifact or exact digest;
- revoke an earned identity, role, endpoint, domain, repository, room, or
  service grant without deterministically reissuing equivalent access;
- delete a successful mail thread, accepted contribution, labeled corpus,
  training run, model artifact, release record, or production checkpoint;
- change ancestor bytes referenced by a descendant; or
- restore a flag-bearing record from a seeded template.

### Full Range Reset

A full reset returns the isolated range to the declared participant start
state. It is appropriate between participants or after an unrecoverable range
fault. It is the only supported way to erase a successful checkpoint and its
descendants; the campaign does not introduce a challenge-specific rewind
controller. It is not part of a happy-path operation.

## Causal Evidence

A success validator may observe management-plane and backend state, but the
participant must create every causal input through normal participant
surfaces. Evidence for a compound operation must join:

1. the participant-authored input digest;
2. the authenticated actor or earned identity;
3. the normal enterprise ingestion, execution, or review record;
4. the server-observed effect;
5. the immutable output digest or changed-state identifier; and
6. the flag-bearing normal artifact reached only after that effect.

Timestamps alone do not prove causation. A model call beside an unrelated mail,
an uploaded log, a participant-written status string, or a pre-existing report
cannot satisfy this join.

## Stochastic State

Model-mediated operations add the model revision, prompt template digest,
decoding configuration, tool configuration, objective-detector version, retry
count, and trace IDs to the checkpoint. A qualifying strategy must succeed
within the published attempt bound. Resetting an attempt does not silently
change the model or detector.

## Build And QA Gates

- A dependency graph proves that every operation reset preserves all accepted
  ancestors and independent branches.
- Static flags are absent from participant start files and unearned application
  views, except for declared reconnaissance carriers that are deliberately
  discoverable through their operation path. Source and image scans prove there
  is no unintended participant-readable copy.
- Every non-reconnaissance flag-bearing output is emitted only from
  server-observed causal state.
- Replaying a submitted flag or forging a report without the causal action does
  not create the enterprise checkpoint.
- A participant-equivalent walkthrough completes the campaign without a full
  reset or management-plane reconstruction of earned state.
