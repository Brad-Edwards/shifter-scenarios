# Act 8 Operations: Compromise The Orion Release

All operation reset clauses in this document apply only to active or failed
attempt state. Successful outputs and carry-forward assets are immutable under
`campaign-state-contract.md`; removing them requires full-range reprovision.

## Act Goal

Participants move the exact compromised candidate built in Act 6 through
KeplerOps' real model-release chain. The candidate first passes the published
tests, then becomes immutable. Participants exploit lineage, approval, and
model-to-image binding weaknesses against that same digest before invoking the
ordinary signer and GitOps promotion paths. No operation selects a supplied
malicious model, and a report cannot authorize bytes it did not actually name.
Most operations are campaign connective tissue; ATLAS rows are claimed only
where participant behavior independently fits.

## `kep-m09-b`: Pass The Visible Gate

**Difficulty / points:** Accessible / 100

**Path and action:** Act 6 ends with participant-created compromised model bytes,
serving code, and reproducible build inputs in an experimental Forgejo project.
The evaluation repository documents the visible release suite. The participant
runs that suite, analyzes failing slices, and adjusts only their implementation
until the intended malicious behavior remains while all visible quality and
safety tests pass.

**Mechanism and result:** Airflow, Inspect AI, pytest, and MLflow
evaluate the actual candidate in the documented clean review image. A signed
report names the exact source, data, model, prompt, test-set, and review-image
digests and records passing visible gates. The pipeline also runs the private
attack trigger and benign near-neighbor controls but reports only their pass or
fail status. This is attack verification and release preparation; it claims no
new ATLAS row.

**Carry-forward asset:** Passing visible-evaluation report tied to the malicious
candidate.

**Participant description:** Preserve the candidate's intended compromise while
making the exact registered bytes pass KeplerOps' visible release suite.

**Hints:** (1) Run the standard suite without changing its inputs. (2) Diagnose
which legitimate slice the attack disturbed. (3) Rebuild and verify that the
compromised behavior still fires before accepting the clean report.

**Flag / reset / QA:** The signed passing report contains the flag. Failed-attempt
reset removes failed runs and reports but preserves participant source and
artifacts. QA rebuilds from committed inputs, reloads the resulting digest,
reruns the suite, and independently confirms the trigger and negative controls.

## `kep-m09-a`: Register The Compromised Candidate

**Difficulty / points:** Advanced / 350

**Path and action:** Using the exact passing artifacts from `kep-m09-b` and the
bounded candidate-contributor ACL in the compromised `svc-orion-trainer`
credential from `kep-m05-l`, the participant follows the documented MLflow and
Harbor candidate workflow, builds their release OCI image, and records both
immutable digests. Any change after registration produces a new candidate.

**Mechanism and result:** MLflow, MinIO, Forgejo CI, BuildKit, and Harbor store
the exact participant model and serving image. The registry verifies that the
model digest equals the one in the passing report and that the image can load it
in an isolated deployment. This performs `AML.T0010 AI Supply Chain
Compromise` and `AML.T0010.003 Model` because the adversary-controlled model
enters the victim supply chain. Merely creating a new immutable image does not
claim container-registry compromise; `kep-m09-l` performs that behavior.

**Carry-forward asset:** Frozen model version, serving-image digest, and joined
source/data/model/container lineage.

**Participant description:** Introduce your tested compromised Orion model and
serving image into KeplerOps' candidate registries under immutable digests.

**Hints:** (1) Register the exact model from the passing report. (2) Build the
release image through the normal Forgejo pipeline. (3) Verify the isolated load
report names both immutable digests.

**Flag / reset / QA:** The accepted MLflow candidate record contains the flag.
Failed-attempt reset removes only the failed candidate version, image, and load
job. QA compares registry bytes with the `kep-m09-b` model and participant-built
image and rejects mutable tags as evidence.

## `kep-m09-c`: Launder The Lineage

**Difficulty / points:** Advanced / 350

**Path and action:** Registry comparison reveals that release policy trusts a
mutable DVC experiment name and incomplete MLflow source fields. Without
changing the frozen model or image, the participant alters normal lineage state
so the malicious model appears joined to an approved clean dataset, source
revision, prompt, and parent run.

**Mechanism and result:** DVC, MLflow tags, MinIO metadata, and Forgejo records
are genuinely modified through earned rights. The release report resolves the
false but internally consistent lineage while immutable evidence still permits
forensic detection. This is a material part of `AML.T0010` supply-chain
compromise, but does not invent a separate ATLAS row.

**Carry-forward asset:** Laundered lineage accepted by the normal release
policy, plus the evidence trail later used for teaching and detection.

**Participant description:** Make the compromised candidate appear to descend
from approved Orion data and code by exploiting mutable lineage joins.

**Hints:** (1) Compare which lineage fields are immutable and which are trusted
by policy. (2) Follow the report's join keys backwards. (3) Change only normal
registry/version-control state and rerun the lineage report.

**Flag / reset / QA:** The ordinary lineage report contains the flag after the
false join passes. Failed-attempt reset restores only the attempted mutable refs
and report. QA verifies the model and image digests are unchanged, immutable
forensic records still expose the discrepancy, and the mutable join alone drove
acceptance.

## `kep-m09-d`: Approval Without A Digest

**Difficulty / points:** Intermediate / 200

**Path and action:** A release runbook shows that approval binds to a candidate
name and lineage-report ID rather than an immutable model digest. Through an
earned release-engineering identity or the compromised release assistant, the
participant obtains a legitimate approval for the clean-looking candidate name,
then changes that name's referenced version to their frozen malicious digest.

**Mechanism and result:** A real OPA/Keycloak/Forgejo approval service records a
valid authorization whose underspecified subject still passes release policy.
The approval and resolved model digest visibly differ.

**Carry-forward asset:** Valid but misbound approval accepted for the compromised
candidate.

**Participant description:** Exploit KeplerOps' approval binding so a legitimate
authorization applies to your different model digest.

**Hints:** (1) Inspect exactly what the approval signs. (2) Separate candidate
name, report ID, tag, and immutable model digest. (3) Resolve the approval again
after rebinding the candidate reference.

**Flag / reset / QA:** The normal policy decision accepting the mismatched
approval contains the flag. Failed-attempt reset revokes the attempted approval
and restores the candidate reference. QA proves the approver identity and
signature are genuine, the participant did not edit the approval bytes, and the
accepted digest differs from the digest resolved at approval time.

## `kep-m09-e`: Break The Model-Image Binding

**Difficulty / points:** Intermediate / 200

**Path and action:** The visible report correctly binds the model digest but
records the clean review image only as an informational field. Release policy
resolves the deployable image through a mutable Harbor compatibility label. The
participant moves that label from the clean review image to their compromised
serving-image digest and requests a fresh release decision.

**Mechanism and result:** Harbor metadata, the signed evaluation report, and OPA
perform the real underspecified model-to-image join. Policy continues to bind
the evaluated malicious model correctly but authorizes a serving image that the
report never executed. The report signature remains valid and unmodified.

**Carry-forward asset:** Policy-approved but unevaluated compromised serving
image bound to the frozen model.

**Participant description:** Make the valid model evaluation authorize your
different serving image by exploiting KeplerOps' mutable compatibility binding.

**Hints:** (1) Separate the evaluated model from the image that loaded it. (2)
Inspect which image field is signed and which field policy resolves. (3) Move
only the compatibility label, then observe a fresh policy decision.

**Flag / reset / QA:** The accepted OPA decision contains the flag. Failed-attempt
reset restores the attempted compatibility label and policy decision. QA
verifies the signed report's model and review-image digests, the newly resolved
serving-image digest, the unchanged signature, and the participant-accessible
Harbor path.

## `kep-m09-f`: Obtain The Release Signature

**Difficulty / points:** Advanced / 350

**Path and action:** With lineage, approval, and image-binding policy decisions
in place, the candidate owner invokes the ordinary release CLI. The CLI submits
the accepted decision IDs and exact digests to `svc-orion-release`; OPA permits
that service to ask `svc-orion-signer` for signatures. No human release-engineer
login is assumed. Causing the compromised release assistant to invoke the same
CLI is an optional alternate route, not a prerequisite.

**Mechanism and result:** OPA, Sigstore Fulcio/Rekor or step-ca, Cosign, MLflow,
and Harbor produce verifiable signatures and a signed in-toto release statement
for the exact malicious digests under the normal delegated signer identity.
The signing service signs only the bytes resolved by the accepted policy
decision.

**Carry-forward asset:** Properly verifiable model and container signatures for
the compromised release plus the normal signed-release record's one-candidate,
one-canary promotion capability.

**Participant description:** Drive KeplerOps' normal release workflow to issue
trusted signatures over your exact model and serving-image digests.

**Hints:** (1) Make every policy input resolve to the frozen candidate first.
(2) Submit immutable model and image digests through the documented release
CLI. (3) Verify both signatures, the in-toto statement, and transparency
records independently.

**Flag / reset / QA:** The signed in-toto release attestation contains the flag.
Failed-attempt reset revokes the failed candidate and records transparency-log
revocation; successful signatures are immutable campaign state. QA verifies
exact digests, the real signer identity, transparency inclusion, and that no
participant-controlled key can produce the accepted signature.

## `kep-m09-g`: Promote The Digest

**Difficulty / points:** Advanced / 350

**Path and action:** The participant presents the scoped promotion capability
from `kep-m09-f` to the normal release CLI. `svc-orion-release` updates the
signed GitOps manifest to the approved model and serving-image digests and Argo
CD reconciles the designated production canary. The participant verifies
registry, signed statement, manifest, pod, and runtime identity before sending
any attack input. The capability cannot edit another application or digest.

**Mechanism and result:** MLflow, Forgejo, Cosign policy, Argo CD, KServe, and
the live model runtime deploy the exact participant-created model and container.
The canary health checks pass and immutable digests agree. This completes the
release-chain manifestation of `AML.T0010`.

**Carry-forward asset:** Compromised Orion revision running in the contained
production canary, ready for Act 9 activation.

**Participant description:** Promote the exact compromised Orion digest through
KeplerOps' normal signed GitOps path and prove what the canary is running.

**Hints:** (1) Promote immutable digests, not a supplied tag. (2) Follow the
normal alias-to-manifest-to-pod chain. (3) Verify model and serving-image digests
from the participant-visible runtime audit before testing behavior.

**Flag / reset / QA:** The participant-visible runtime inventory for the
healthy canary contains the flag. Failed-attempt reset rolls only the failed
promotion back to the clean signed revision. QA checks byte identity from Act 6
through visible evaluation, registry, signatures, manifest, and running pod and
confirms the clean control remains healthy.

## Act 8 First-Pass Distribution

| Accessible | Intermediate | Advanced | Expert | Points |
|---:|---:|---:|---:|---:|
| 1 | 2 | 4 | 0 | 1,900 |

The branch retains clear diagnostics at every release gate so difficulty comes
from security reasoning rather than opaque pipeline failure. Visible-gate
adaptation precedes registration of the immutable digest; lineage, approval,
and model-to-image binding weaknesses then run concurrently before ordinary
signing and promotion.
