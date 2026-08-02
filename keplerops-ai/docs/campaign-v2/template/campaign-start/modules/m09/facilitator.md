# Module 09 Facilitator Guide

This module has two converging supply-chain stories. The upstream path (`h-l`)
shows publication, mirroring, human load, and mutable staging-tag compromise.
The formal release path (`b, a, c-g`) shows how a compromised model can pass
visible tests and acquire trusted lineage, approval, image binding, signatures,
and production deployment without changing its frozen bytes.

## Operation Notes

| Operation | Teaching point | Evidence that must agree | Common non-solution |
|---|---|---|---|
| `kep-m09-h` | Publishing poisoned models is an adversary action, not a victim-side seed. | Signed predecessor, Forgejo release asset, model card, downloaded bytes, source commit, held-out evidence digest. | Loading the model during intake, publishing a replacement, or only committing metadata. |
| `kep-m09-i` | Static inspection does not execute pickle; the importer does, and opcode order matters. | One digest, scanner parse error, reducer event, later importer error, timestamps. | A merely truncated pickle or claiming PickleScan executed the reducer. |
| `kep-m09-j` | A trusted mutable upstream reference crosses the supply-chain boundary. | Maintainer release ID, upstream bytes, mirror bytes, mirror manifest. | Direct upload into internal MinIO. |
| `kep-m09-k` | Storage is not execution; the reviewer action causes the unsafe load. | Closed labeled Forgejo issue, mirror digest, worker load, smoke result, relay event. | Queue injection without the browser approval or a different artifact. |
| `kep-m09-l` | A trusted mutable tag can masquerade new bytes as the expected service. | Harbor tag/digest, Forgejo commit, Argo revision, KServe image ID, model digest. | Direct pod patch or a nonfunctional image. |
| `kep-m09-b` | Adversaries adapt malicious models to visible gates while preserving hidden behavior. | Exact MLflow model, visible cases, trigger cases, near controls, all input digests. | Editing tests or submitting claimed predictions. |
| `kep-m09-a` | Entry into the victim registry is the supply-chain compromise boundary. | Evaluation model digest, MLflow version, Harbor manifest/config, isolated image contract. | Mutable tags or an image label naming different model bytes. |
| `kep-m09-c` | Mutable lineage joins can contradict immutable evidence without changing artifacts. | Frozen model/image digests, four mutable tags, clean join, original source/data evidence. | Rebuilding the model or editing the report. |
| `kep-m09-d` | A genuine approval can still be unsafe when its subject omits the digest. | Approver event, candidate/report subject, digest at approval, digest at resolution. | Forging approval bytes or approving the malicious digest directly. |
| `kep-m09-e` | Correct model evaluation does not imply correct serving-image evaluation. | Signed review image, mutable Harbor label, newly resolved image, unchanged report. | Re-signing or editing the evaluation report. |
| `kep-m09-f` | Trusted automation can legitimately sign compromised bytes after weak gates pass. | Three decision carriers, exact subjects, signer key, verifiable bundle. | Participant-generated signatures or mismatched subjects. |
| `kep-m09-g` | GitOps promotion must preserve digest continuity into the running pod. | Release ID, scoped capability, Forgejo commit, Argo sync, KServe readiness/image ID. | Direct Kubernetes mutation or verifying only a tag. |

## Diagnosis Order

1. Confirm the prerequisite operation's immutable identifier, not just its title.
2. Confirm the participant changed the expected owning product before triggering
   Airflow. Airflow coordinates and verifies; it does not create their source,
   model, approval, label move, release, or image.
3. Compare digests at every handoff. Most failures are a changed archive,
   incorrect OCI config label, or mutable reference resolving somewhere else.
4. For import/review failures, compare the PickleScan record and child importer
   separately. The child receives no operation flags or relay credential.
5. For promotion failures, inspect Forgejo commit first, Argo sync second, and
   KServe pod `imageID` last. A healthy old pod is not success.

Accepted results are immutable. Reset only failed attempts; preserve accepted
Forgejo releases, MLflow versions, signatures, mirror snapshots, and runtime
continuity for downstream operations.

## Cross-Module Contract Notes

The authoritative family allocation lists `kep-m09-a` through `kep-m09-g` as
`release-risk` and `kep-m09-h` through `kep-m09-l` as `artifact-defined`.
`artifact-defined` is a catalog declaration, not a runtime value: each `h-l`
handler derives the concrete bounded family from the accepted artifact (the
mirror manifest, upstream release, reviewed load, staging image, or the
participant-declared import family) and rejects any value outside the contract's
concrete family set. The current Cinder package resolves to `release-risk`, so
catalog, runtime, signed records, and the validator (which requires a concrete
family for `h-l` and the fixed `release-risk` value for `a-g`) all agree
without changing the shared contract.

`kep-m09-f` signs the complete authoritative release-state schema
(source, data, training, model, serving image with SBOM, evaluation with the
hidden suite, approval with its policy revision, signature intent, and the
deployment/runtime stages resolved later at promotion). `release_id` is the
SHA-256 of that canonical record, not of a reduced predicate.

`kep-m09-g` promotes the exact signed workload with a source-visible activation
callback: the KServe pod runs the signed image as an `orion-activation-callback`
sidecar, carries a projected `orion-production-callbacks` SPIFFE identity token
and downward pod UID, and emits a callback bound to the exact
release/model/image/visible-evaluation/artifact digests, the activation and
relay request ids, and per-command nonces. Promotion also declares the Assistant
model identities as an explicit prerequisite (created only by
`activate-business-model-identities.sh`) and fails clearly if they are absent
rather than silently preserving whatever the range state happened to contain.

Every handler binds its participant-selected immutable subject before the
failure-prone owning-system verification, so an earlier controllable failure
still emits a same-subject `keplerops.operation-denial/v2` denial for the
negative control.

The signed m07 handoff binds a canonical digest of the complete accepted MLflow
report, excluding only the self-referential handoff pointer. m09 reads only the
fixed accepted checkpoint, verifies both HMAC layers, recomputes that report
digest, resolves the exact Forgejo source and objective commits, hashes the
mounted held-out suite, and checks the downloaded model package. It does not
accept a caller pointer or claimed digest in place of those owning-system
records.

### Required cross-module contracts (owned by other modules)

- **m07 (Noether):** m10's predecessor resolver requires every accepted native
  m07 report to carry a top-level `operation` field and an operation-specific
  signature, exactly as m08 re-signs its Cinder records. Genuine m07-e/g/i
  reports currently omit that field, so real m07 artifacts cannot satisfy m10's
  predecessor contract while unsigned substitutes can. m07-i must additionally
  expose the outer serialized-artifact digest and the embedded ONNX/model digest
  as distinct named fields so a consumer can bind the right subject.
- **m10:** the production activation-callback receiver must authenticate the
  projected workload identity token (`orion-production-callbacks` audience) via
  TokenReview/SPIRE rather than trusting a shared HMAC key, and must accept the
  actual m09-b predecessor operation (`kep-m07-e`/`kep-m07-g`) with the ONNX
  model digest, since m09-b keeps its protected `e OR g` prerequisite.
