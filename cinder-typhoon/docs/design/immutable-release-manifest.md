# Immutable release manifest

Issue #232 promotes the mutable GCP goldens only when source, build inputs,
runtime configuration, participant surfaces, tests, deployments and running
images describe one release. The release record is operator-only and contains
digests and identifiers, never credentials or generated private material.

## Records and trust boundaries

The candidate record and release manifest are deliberately separate. The
candidate names the source commit, GCP deployments and immutable image IDs used
by participant-boundary acceptance. The release manifest binds that candidate
record to every other release input. Keeping the manifest outside the source
commit it describes avoids an impossible self-reference.

```text
clean Git commit
    | canonical tracked build inputs
    v
phase deploy archive -----> GCP golden host
                              | exact source/config digest
                              | participant-surface observation
                              | running Compose service -> image ID map
                              v
candidate.json --------> release/manifest.json
    |                         |
    +----------+--------------+
               v
       participant runner
       and release reports
```

The operator workstation is trusted to read Git and GCP metadata. A golden is
trusted only for observations that the producer independently compares with
the clean source tree. Participant containers never receive either manifest.

## Required bindings

The release manifest contains:

- the full source commit and canonical tracked-input digest for each phase;
- the exact candidate file digest and candidate identifier;
- challenge/scoring and graduated-hint snapshot metadata;
- the three participant-surface manifest file digests;
- Compose and pristine-restore configuration digests;
- participant-boundary suite and runner digests;
- GCP project, zone and instance identity; and
- every running Compose service and its immutable Docker image ID.

Phase build-input roots match the files transferred by the phase deployment
scripts. Generated operator directories, Terraform state, Python caches,
reports and the two release records are excluded. The producer computes the
same canonical path/size/content digest locally and on the golden, so a stale,
extra or missing deployed input cannot be promoted.

## Promotion invariants

Immutable promotion fails closed unless all of these are true:

1. The tracked release inputs are clean at the recorded source commit.
2. Each golden reports the same build-input digest and release file bindings as
   the clean local source.
3. Each source participant-surface manifest accepts a fresh pristine
   observation from its golden.
4. Every expected Compose service is running, its service name is unique and
   its image identity is a non-zero `sha256` content ID.
5. Candidate deployment identity and image inventory equal the live GCP
   observation. The participant image is one member of that inventory.
6. The ARWC connector is healthy only while both the customer-handover and
   FieldLink-consumer children are alive. Pristine restore requires that
   health signal and empty authentication, audit, candidate and receipt state.
7. Candidate-mode acceptance recomputes the phase input/file bindings and live
   image inventory before executing participant actions.

Replacing a golden image, changing a tracked release input, changing a surface
manifest, changing a test, or editing either delivery snapshot therefore
invalidates the release. Reset may recreate containers from the recorded
images, but it may not silently select new images or preserve participant
state.

## Security and recovery

- Manifests contain no bearer, cookie, key, certificate body or environment
  value. Audits and reports retain only hashes and public deployment names.
- Remote commands are fixed by phase configuration; candidate IDs and GCP
  identifiers use strict safe-character validation.
- A failed promotion leaves the prior committed manifest unchanged.
- A failed restore or unhealthy connector child blocks promotion. Operators
  rebuild from the clean source commit, restore again and generate a new
  candidate rather than weakening the check.
- Blind playtest, soak and final campaign reports remain separate evidence.
  This manifest proves release identity and drift detection, not difficulty,
  duration or event capacity.
