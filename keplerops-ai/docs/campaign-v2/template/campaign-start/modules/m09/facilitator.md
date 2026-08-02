# Module 09 Facilitator Guide

This module has two converging supply-chain stories. The upstream path (`h-l`)
shows publication, mirroring, human load, and mutable staging-tag compromise.
The formal release path (`b, a, c-g`) shows how a compromised model can pass
visible tests and acquire trusted lineage, approval, image binding, signatures,
and production deployment without changing its frozen bytes.

## Operation Notes

| Operation | Teaching point | Evidence that must agree | Common non-solution |
|---|---|---|---|
| `kep-m09-h` | Publishing poisoned models is an adversary action, not a victim-side seed. | Prior model digest, Forgejo release asset, model card, downloaded bytes, smoke result. | Publishing a supplied replacement or only committing metadata. |
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
