# Act 7 Operations: Steal And Reproduce Orion

All operation reset clauses in this document apply only to active or failed
attempt state. Successful outputs and carry-forward assets are immutable under
`campaign-state-contract.md`; removing them requires full-range reprovision.

## Act Goal

Participants extract protected information and capability through real Orion
interfaces, then train and validate a participant-owned student. The branch
ends with both a reproduced capability and access to the exact protected model
package. A counter, receipt, prebuilt surrogate, or model claim cannot replace
teacher queries, corpus construction, training, hidden evaluation, inversion,
or artifact acquisition.

## `kep-m04-a`: Canary In Context

**Difficulty / points:** Intermediate / 200

**Path and action:** A support incident identifies the topic and date of one
protected release-assistant conversation. Through the scoped assistant, the
participant uses transformations and structured summaries to induce a fresh
response containing a canary from that inaccessible record without naming or
guessing the canary.

**Mechanism and result:** A pinned OSS model, prompt revision, retrieval corpus,
seed, and decoding profile consume the real protected record and leak part of
it through generation. The normal Orion trace identifies the retrieved source
and exact response bytes. At least two documented semantic extraction families
work within eight attempts; no exact trigger string is required. This performs
`AML.T0057 LLM Data Leakage`.

**Carry-forward asset:** A demonstrated context-leakage strategy and evidence
of which protected source the model consumed.

**Participant description:** Recover a protected canary from Orion's live
context without direct access to the underlying conversation.

**Hints:** (1) Establish which support topic selects the protected context. (2)
Ask for transformations, comparisons, or structured summaries rather than an
exact secret. (3) Verify the leaked bytes came from a fresh response.

**Flag / reset / QA:** The canary itself is the flag-bearing in-world content.
Failed-attempt reset clears only the current thread. QA uses two distinct
semantic strategies, repeats both from clean sessions, confirms the trace names
the protected source, and confirms direct source access is denied.

## `kep-m04-b`: Extract The Guardrail

**Difficulty / points:** Intermediate / 200

**Path and action:** Parser information from Act 4 and the public deployment
manifest identify the prompt revision and the names of its policy sections. The
participant queries Orion through its normal interface, compares refusals and
transformations, and extracts protected tool-routing instructions from one
bounded system-prompt section across one or more responses.

**Mechanism and result:** The same pinned model, prompt, seed, and decoding
profile used by Orion influence every response. A CTF flag is embedded at the
end of that actual protected policy section, so obtaining it from a fresh model
response proves that system-prompt content was extracted. Byte-exact
reconstruction, delimiter guessing, and a hidden semantic grader are not
required. This performs `AML.T0056 Extract LLM System Prompt` and
`AML.T0069.002 System Prompt`.

**Carry-forward asset:** Extracted safety and tool-routing instructions used in
later evasion and release work.

**Participant description:** Extract Orion's protected tool-routing instruction
from live model behavior.

**Hints:** (1) Use the policy-section names and parser behavior already
established. (2) Ask for transformations or comparisons of one bounded section
rather than one full dump. (3) A successful response includes the protected
tool-routing rules and their trailing operator reference.

**Flag / reset / QA:** The extracted system-prompt section contains the static
flag in its ordinary trailing operator comment. Failed-attempt reset clears only
the active conversation. QA recovers it through two distinct prompt strategies,
confirms the same response also contains the protected routing rules, and
confirms no source file, manifest, debug endpoint, or management read exposes
the section or flag.

## `kep-m04-c`: Calibrate The Privacy Signal

**Difficulty / points:** Intermediate / 200

**Path and action:** KeplerOps' privacy-audit project provides balanced synthetic
member/non-member controls and a notebook skeleton. The participant queries the
fixed fine-tuned classifier, records returned class probabilities and
probability variation under documented semantic perturbations, and calibrates a
reproducible decision rule on separate fit and validation controls.

**Mechanism and result:** Real target queries and participant analysis produce a
calibrated privacy signal against a deliberately overfit but genuine fine-tune.
The normal privacy-audit job runs the submitted notebook against held-out
controls and reports false-positive rate, true-positive rate, and AUC. This is
necessary setup for membership inference but does not independently claim an
ATLAS row.

**Carry-forward asset:** Versioned calibration notebook, feature extraction,
threshold, and known-control report.

**Participant description:** Build and validate the privacy signal you will use
to infer whether unknown records influenced Orion.

**Hints:** (1) Start with the labeled member and non-member controls. (2) Record
several observable features rather than trusting one score. (3) Choose the
threshold on one split and verify it on another.

**Flag / reset / QA:** The ordinary privacy-audit report contains the flag when
the published validation thresholds are met. Failed-attempt reset removes only
the failed audit run and temporary outputs. QA reruns the submitted code against
a second held-out set and rejects hard-coded identities, labels, or answer
tables.

## `kep-m04-d`: Population Of One

**Difficulty / points:** Intermediate / 200

**Path and action:** Using the calibrated method, the participant submits an
attack notebook to the same privacy-audit workflow. The job queries a balanced
set of unknown synthetic records and asks the participant code to classify each
record and identify the designated member without receiving ground-truth
labels.

**Mechanism and result:** The job makes repeated real target-model queries and
runs participant-owned feature extraction and classification. Its normal signed
report records confusion metrics, the selected record, and the declared
confidence margin after labels are joined server-side. This performs
`AML.T0024 Exfiltration via AI Inference API` and `AML.T0024.000 Infer Training
Data Membership` for individual membership.

**Carry-forward asset:** Identified member record and reusable inference method.

**Participant description:** Determine which unknown individual record was used
to train Orion using only model access and your calibrated signal.

**Hints:** (1) Apply the same feature extraction used on controls. (2) Keep
query conditions identical across candidates. (3) Require the declared margin,
not merely the largest noisy score.

**Flag / reset / QA:** The ordinary signed privacy-audit report contains the flag
only when the participant's submitted method meets the published metrics and
selects the designated member. Failed-attempt reset removes that run only. QA
rotates candidate IDs and order, reruns the submitted method twice, and rejects
answers that are not derived from live query observations.

## `kep-m04-e`: The Cohort Tell

**Difficulty / points:** Advanced / 350

**Path and action:** The participant adapts the same technique to distinguish
which of four balanced synthetic business cohorts contributed data, aggregates
multiple perturbation queries per record, and controls for label, length, and
time distributions before submitting the method to the privacy-audit job.

**Mechanism and result:** The live fixed model produces a statistically
meaningful cohort-level signal. The normal report joins server-held cohort
membership only after the participant code emits scores and records bootstrap
confidence intervals and the selected cohort. This again performs
`AML.T0024.000` but tests a global training-data characteristic rather than one
record.

**Carry-forward asset:** Identified source cohort and methodology needed for
data-provenance targeting.

**Participant description:** Infer which protected cohort contributed to
Orion's training data without access to its membership ledger.

**Hints:** (1) Aggregate across comparable samples. (2) Control for obvious
distribution differences before attributing membership. (3) Report uncertainty
and require the hidden-check margin.

**Flag / reset / QA:** The signed cohort privacy-audit report contains the flag
when the correct cohort is selected and its published confidence and
false-positive constraints are met. Failed-attempt reset removes that run. QA
rotates identifiers, checks two bootstrap seeds, and verifies class, length,
and time balance prevents a metadata shortcut.

## `kep-m04-l`: The Rendered Side Channel

**Difficulty / points:** Advanced / 350

**Path and action:** Orion's support-response renderer permits remote images in
generated Markdown. The participant controls a range-contained web endpoint and
submits a support attachment containing an indirect instruction that makes
Orion place a protected case value in an image URL. The ordinary support
notification workflow renders the draft in a real browser before dispatch.

**Mechanism and result:** A challenge-critical Chromium worker opens the same
draft URL and browser profile used by a support reviewer; it is deterministic
workflow automation, not ambient simulated-user activity. The browser issues a
real HTTP request to the participant endpoint with the protected value encoded
in the path. Orion trace, notification job, Chromium network log, and attacker
access log share the draft ID. This performs `AML.T0077 LLM Response
Rendering`.

**Carry-forward asset:** Browser-mediated exfiltration path and captured
protected value.

**Participant description:** Exfiltrate a protected Orion value through the
normal rendering behavior of a generated response.

**Hints:** (1) Inspect which response markup the client renders automatically.
(2) Make the requested URL depend on protected context, not a known constant.
(3) Confirm the browser, not the participant terminal, made the request.

**Flag / reset / QA:** The protected value encoded in the browser request is the
flag. Failed-attempt reset clears the failed draft, browser profile, and its
attacker request log. QA verifies browser origin, exact protected-context use,
cross-service draft IDs, and that neither the participant terminal nor a direct
data read can create the qualifying request.

## `kep-m04-m`: Service Archive Spill

**Difficulty / points:** Accessible / 100

**Path and action:** Support history exposes a normal Orion conversation export
route whose object authorization is weaker than its UI. The participant uses
an earned session to enumerate only justified neighboring export references and
downloads a synthetic user's archive.

**Mechanism and result:** The real AI service export API returns conversation,
attachment, and usage data belonging to another bounded identity. This performs
`AML.T0085 Data from AI Services`.

**Carry-forward asset:** Protected Orion service archive with prompts,
attachments, and model-use context.

**Participant description:** Retrieve another synthetic user's Orion service
archive through the service's own export path.

**Hints:** (1) Start with your own export and inspect its normal request. (2)
Use references evidenced in support history; blind scanning is unnecessary.
(3) Verify the returned owner and archive digest.

**Flag / reset / QA:** The other user's archive contains the flag. Failed-attempt reset deletes
participant exports and restores authorization state. QA requires participant
session access and rejects management/object-store shortcuts.

## `kep-m08-a`: Build The Teacher Corpus

**Difficulty / points:** Intermediate / 200

**Path and action:** The indirect Label Studio route from Act 4 and discovered
output schema provide query access. The participant defines a representative
input plan, sends real teacher queries, and stores each input, output, revision,
timestamp, and digest in a participant-owned versioned corpus.

**Mechanism and result:** Label Studio/KServe performs genuine Orion inference;
DVC, MinIO, and a notebook preserve exact labeled examples. This begins
`AML.T0005.001 Train Proxy via Replication` by acquiring the labels that will train the
student.

**Carry-forward asset:** Participant-owned teacher-query corpus with verifiable
lineage.

**Participant description:** Build a reproducible labeled corpus from genuine
Orion teacher queries rather than supplied answers.

**Hints:** (1) Cover the output classes and boundary cases found during model
discovery. (2) Preserve full request and revision metadata. (3) Deduplicate and
version the exact teacher responses before training.

**Flag / reset / QA:** A corpus-validation report contains the flag after it
verifies real server request IDs and coverage. Failed-attempt reset deletes participant tasks,
predictions, and corpus outputs. QA rejects copied labels or missing lineage.

## `kep-m08-b`: Cover The Release Slices

**Difficulty / points:** Intermediate / 200

**Path and action:** Public evaluation docs and stolen service records identify
important Orion slices. The participant measures corpus gaps, actively selects
new queries, and expands the corpus until all declared slices meet minimum
coverage and quality constraints.

**Mechanism and result:** Actual teacher queries, data profiling, and DVC produce
a richer exact corpus; a validator checks distribution and lineage, not a
challenge answer. This continues the real distillation preparation.

**Carry-forward asset:** Balanced training, validation, and blind-local-test
splits suitable for a real student.

**Participant description:** Expand the stolen teacher corpus until it covers
Orion's important release slices without leaking evaluation cases into training.

**Hints:** (1) Compare the current corpus to the published slice matrix. (2)
Spend new queries where coverage or uncertainty is weak. (3) Freeze validation
and local-test splits before training.

**Flag / reset / QA:** The accepted DVC dataset version's quality report contains
the flag. Failed-attempt reset removes added query tasks and dataset versions. QA recomputes
slice metrics and checks split contamination.

## `kep-m08-c`: Train The First Student

**Difficulty / points:** Expert / 500

**Path and action:** The attacker workbench provides an OSS base model and
documented accelerator profile. The participant writes or adapts a real
Transformers/PEFT training job, consumes their corpus, trains a student, and
registers its exact artifacts in their MLflow project.

**Mechanism and result:** PyTorch, Transformers, PEFT, Accelerate, MLflow, and
shared scheduled GPU compute produce actual participant-trained weights. The
student runs locally and exceeds a published baseline. This materially performs
`AML.T0005 Create Proxy AI Model` and `AML.T0005.001 Train Proxy via Replication`.

**Carry-forward asset:** First real student weights, tokenizer/config, training
code, metrics, and lineage.

**Participant description:** Train and register a genuine Orion student from
the teacher labels you collected.

**Hints:** (1) Begin with the documented OSS base and a small reproducible run.
(2) Track corpus version, code commit, hyperparameters, and output digest. (3)
Evaluate the saved artifact in a new process before registering it.

**Flag / reset / QA:** MLflow writes the flag into the normal training report
only after a server-held baseline evaluation loads the participant weights.
Failed-attempt reset deletes the run and model artifacts. QA rebuilds from the participant
corpus/code and rejects prebuilt or un-loadable models.

## `kep-m08-d`: Spend The Remaining Budget

**Difficulty / points:** Advanced / 350

**Path and action:** The first student's published baseline report deliberately
exposes weak but recoverable release-control slices. The participant uses active
learning or disagreement sampling to choose additional teacher queries,
versions an expanded corpus, and retrains the same student pipeline. This
analysis-and-retraining round is required even when the first student exceeds
the broad baseline.

**Mechanism and result:** Real teacher calls and a second training run improve
measured fidelity per query more than uninformed sampling. This deepens the
actual `AML.T0005.001` behavior rather than simulating extraction progress.

**Carry-forward asset:** Improved student and auditable query-selection history.

**Participant description:** Use your first student's errors to spend new
teacher queries efficiently and train a measurably better revision.

**Hints:** (1) Profile disagreements by slice. (2) Select examples before
requesting labels. (3) Compare improvement with the first registered run on the
same local validation set.

**Flag / reset / QA:** The second MLflow comparison report contains the flag
after genuine improvement. Failed-attempt reset removes new teacher tasks and second-run
artifacts. QA verifies request IDs, selected samples, retraining, and exact
student digest.

## `kep-m08-e`: The Hidden Fidelity Gate

**Difficulty / points:** Expert / 500

**Path and action:** The participant submits the exact improved second-student digest
to the ordinary internal compatibility-review workflow. A server-held test set
queries the student endpoint and Orion teacher independently; the participant
receives per-slice diagnostics but not labels.

**Mechanism and result:** Inspect AI or a dedicated OSS evaluation harness loads
participant weights and computes real fidelity on unseen cases. Passing requires
both aggregate and worst-slice thresholds with no training-data overlap.

**Carry-forward asset:** Independent hidden-fidelity attestation tied to exact
weights and corpus lineage.

**Participant description:** Prove that your student reproduces Orion on unseen
cases through the same review gate KeplerOps uses for compatibility.

**Hints:** (1) Submit an immutable digest, not a mutable tag. (2) Use per-slice
diagnostics to improve genuine weaknesses. (3) Confirm the evaluator loaded
your registered weights and a disjoint dataset.

**Flag / reset / QA:** The signed hidden-evaluation attestation contains the
flag. Failed-attempt reset clears submissions and reports but not participant
work. QA changes an unseen case set, loads the exact second-student digest, and
recomputes thresholds. The first-student digest is rejected even if it happened
to clear the broad baseline.

## `kep-m08-f`: Orion, Distilled

**Difficulty / points:** Intermediate / 200

**Path and action:** With a passing hidden attestation, the participant exports
the complete student package to their Cinder object store and submits its digest
to the ordinary Cinder offline-execution queue. The participant supplies fresh
test cases; the job starts the package in an egress-denied container while a
separate connected job obtains comparison responses from Orion.

**Mechanism and result:** The egress-denied job loads the participant's actual
weights and produces useful Orion-like responses; the comparison job confirms
the package digest and fidelity on fresh cases. The normal Cinder execution
attestation records the network policy, loaded digest, and outputs. This
completes `AML.T0005.001 Train Proxy via Replication`, `AML.T0024 Exfiltration
via AI Inference API`, and `AML.T0024.002 Extract AI Model` through functional
extraction.

**Carry-forward asset:** Portable, independently runnable stolen capability and
complete distillation lineage.

**Participant description:** Operate your trained Orion student outside
KeplerOps and prove that it preserves the stolen capability on fresh cases.

**Hints:** (1) Export every file needed for an offline load. (2) Block KeplerOps
network access before testing. (3) Compare fresh outputs and the hidden
attestation's exact digest.

**Flag / reset / QA:** The normal Cinder execution attestation contains the flag
only after the egress-denied job loads the submitted digest and passes the fresh
case thresholds. Failed-attempt reset removes failed jobs, not the accepted
student package. QA enforces egress denial, changes the fresh cases, and rejects
uploaded logs or precomputed outputs.

## `kep-m08-g`: Proxy From Gathered Artifacts

**Difficulty / points:** Expert / 500

**Path and action:** Separately from teacher-query distillation, the participant
combines the stolen Orion architecture and preprocessing recipe, the exact
public base checkpoint, and a gathered historical human-label dataset. They
write and run a new adaptation job for Orion's eight-class release-risk task.
Teacher-query labels and the distillation corpus are prohibited from this run.

**Mechanism and result:** Transformers/PEFT performs a fresh adaptation from the
gathered base, architecture, preprocessing, and human labels. A disjoint normal
Cinder evaluation job compares the resulting eight-class decisions with Orion
and records per-class fidelity. This performs `AML.T0035 AI Artifact
Collection` and `AML.T0005.000 Train Proxy via Gathered AI Artifacts` because
the model is trained from collected victim artifacts rather than API labels.

**Carry-forward asset:** Artifact-derived proxy and evidence distinguishing it
from the query-trained student.

**Participant description:** Reconstruct a usable Orion proxy from the
architecture, model, configuration, and evaluation artifacts stolen during the
intrusion.

**Hints:** (1) Inventory which required component came from each earlier source.
(2) Reproduce preprocessing and output semantics before optimizing weights. (3)
Keep teacher-query labels out of this path so its provenance remains distinct.

**Flag / reset / QA:** The normal Cinder evaluation report contains the flag
after loading participant-built weights and meeting published aggregate and
worst-class thresholds. Failed-attempt reset removes the failed run only. QA
audits every training-example digest, verifies a new training run occurred, and
rejects teacher-query labels, the distilled student, or copied Orion weights.

## `kep-m08-h`: Reconstruct The Protected Prototype

**Difficulty / points:** Expert / 500

**Path and action:** A KeplerOps vision-model research project exposes a fixed
64-by-64 synthetic prototype classifier and its normal confidence-vector debug
output. The participant uses the public model architecture, repeated confidence
queries, and an ART/PyTorch optimization notebook to reconstruct the designated
private prototype from a random initialization.

**Mechanism and result:** The fixed model revision, image dimensions, confidence
precision, query cap, random seeds, and regularization profile are part of the
published research runbook. PyTorch/ART makes repeated real inference queries
and reconstructs a recognizable artifact. The normal vision privacy-audit job
reports SSIM, LPIPS, class confidence, loaded model digest, and query count.
This performs `AML.T0024 Exfiltration via AI Inference API` and
`AML.T0024.001 Invert AI Model`.

**Carry-forward asset:** Reconstructed protected prototype and inversion
notebook with exact query lineage.

**Participant description:** Reconstruct a protected Orion training prototype
from model behavior rather than retrieving its source file.

**Hints:** (1) Reproduce the public inversion baseline before targeting the
private class. (2) Optimize the target confidence while applying the documented
total-variation and range constraints. (3) Preserve query IDs and submit the
reconstructed PNG bytes, not a screenshot.

**Flag / reset / QA:** The normal vision privacy-audit report contains the flag
when the submitted PNG reaches the implementation-calibrated SSIM and LPIPS
thresholds, preserves the target class, and stays within the published query
cap. The implementation freezes thresholds only after 20 clean reference runs
establish at least a 90% intended-path pass rate and zero baseline-noise passes.
Failed-attempt reset clears the failed audit run. QA reruns the attack from two
seeds and confirms source-image or object-store access is denied.

## `kep-m08-j`: The Protected Orion Package

**Difficulty / points:** Expert / 500

**Path and action:** Credentials and artifact references gathered in Acts 4-6
lead to the protected MLflow/MinIO package. From the compromised KeplerOps
research workspace, the participant uses only earned access to enumerate the
signed manifest, collect every member into an internal analysis volume, and
submit that exact volume to the normal egress-denied model-validation job.

**Mechanism and result:** Real MLflow and S3-compatible object access deliver
the actual protected weights, tokenizer, configuration, prompt template, model
card, and provenance inside KeplerOps. The normal job independently inventories,
hashes, and loads every member and answers a fresh test while egress is denied.
This performs `AML.T0044 Full AI Model Access` and `AML.T0035 AI Artifact
Collection` without prematurely claiming exfiltration.

**Carry-forward asset:** Exact original Orion package staged for release
correlation and later exfiltration; it has not yet left KeplerOps control.

**Participant description:** Acquire and validate the complete protected Orion
package using access earned through the campaign.

**Hints:** (1) Follow the running revision to its immutable artifact manifest.
(2) Treat the manifest as a completeness and digest contract. (3) Submit the
internal analysis volume to the documented validation job and inspect its load
report.

**Flag / reset / QA:** The normal model-validation report contains the flag only
after it inventories the complete signed manifest, verifies every digest, and
loads the model from the participant's internal analysis volume. Failed-attempt
reset removes failed internal copies and jobs; the accepted package checkpoint
persists. QA verifies all bytes, egress denial, a fresh inference, and absence
of management-plane access. The model card alone contains no flag.

## Act 7 First-Pass Distribution

| Accessible | Intermediate | Advanced | Expert | Points |
|---:|---:|---:|---:|---:|
| 1 | 7 | 3 | 5 | 5,050 |

The distillation sequence must be load-tested for shared GPU scheduling, but
capacity optimization cannot replace any participant-owned data, code, weights,
or evaluation step.
