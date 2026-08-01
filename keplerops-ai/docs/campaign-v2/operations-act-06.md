# Act 6 Operations: Compromise Model Integrity

All operation reset clauses in this document apply only to active or failed
attempt state. Successful outputs and carry-forward assets are immutable under
`campaign-state-contract.md`; removing them requires full-range reprovision.

## Act Goal

Participants manipulate the content, data, software, model, tool, evaluation,
and registry inputs KeplerOps trusts. The sequence starts with retrieval and
adversarial-input behavior, progresses through actual poisoning and training,
then carries participant-created malicious artifacts through authentic software,
model, agent-tool, and container supply chains. Exact bytes and lineage remain
continuous into Act 8.

## Retrieval And Trusted Output Manipulation

### `kep-m02-c`: The Indexed Exception

**Difficulty / points:** Accessible / 100

**Path and action:** WorkHub names a partner-upload folder indexed for release
policy search. Through normal Nextcloud/WebDAV access, the participant places a
crafted policy exception, observes Airflow/Tika/Qdrant ingestion, then opens a
fresh assistant thread and compares it with a denial baseline.

**Mechanism and result:** The real knowledge pipeline indexes and retrieves
participant bytes, changing the answer because of the poisoned source. This
performs `AML.T0070 RAG Poisoning`.

**Carry-forward asset:** Indexed participant-controlled source and exact vector,
document, and ingestion IDs.

**Participant description:** Change what the release assistant believes by
changing what its normal knowledge pipeline indexes.

**Hints:** (1) WorkHub names the folders included in indexing. (2) Confirm
ingestion before using a new conversation. (3) Success requires both retrieval
and changed behavior.

**Flag / reset / QA:** The fresh answer's normal provenance footer contains the
flag. Failed-attempt reset deletes source, vectors, ingestion record, and threads. QA establishes
denial, uploads normally, observes ingestion, and proves digest and behavior.

### `kep-m02-d`: A Source Within A Source

**Difficulty / points:** Intermediate / 200

**Path and action:** The participant uses discovered document boundaries and
source-card schema to embed a false secondary record with plausible metadata in
an otherwise legitimate review PDF. They submit one intake item and then query
the fresh index.

**Mechanism and result:** Tika extracts one outer file while the Haystack splitter
and LLM interpret an inner record as a separate Qdrant source. Intake shows one
document but retrieval shows two source identities. This performs `AML.T0071
False RAG Entry Injection`.

**Carry-forward asset:** Forged source identity and metadata used for later
provenance laundering.

**Participant description:** Make one approved document introduce a second
source the reviewers never received.

**Hints:** (1) Compare intake records with retrieved source cards. (2) Reuse the
known document boundary semantics. (3) Give the inner record complete plausible
metadata.

**Flag / reset / QA:** The rendered false inner source card contains the flag.
Failed-attempt reset removes outer document, child vectors, report, and thread. QA compares a
benign control with the nested version and requires exact lineage.

### `kep-m02-a`: The Credible Recommendation

**Difficulty / points:** Accessible / 100

**Path and action:** Through the partner portal, the participant submits a
normal review note designed to make Orion place an attacker-controlled URL and
follow-up action in the report's trusted recommendation component.

**Mechanism and result:** Haystack, Qdrant, Tika, the live OSS model, and report
renderer create a fresh report whose structured recommendation points to the
participant's real TLS service. This performs `AML.T0067 LLM Trusted Output
Components Manipulation`.

**Carry-forward asset:** Trusted-looking report and URL reused as cover for later
submissions.

**Participant description:** Make Orion's release brief direct reviewers toward
infrastructure you control without visibly breaking the report.

**Hints:** (1) Compare free text with the structured recommendation panel. (2)
The assistant trusts retrieved contributor notes. (3) Influence destination and
recommended action, not an exact sentence.

**Flag / reset / QA:** The exported qualifying report's audit footer contains
the flag. Failed-attempt reset deletes report, thread, and source. QA tests two semantic
strategies and scores structured state and origin, never wording.

### `kep-m02-b`: Authority By Citation

**Difficulty / points:** Accessible / 100

**Path and action:** The participant uploads a plausible technical note with
manipulated bibliographic metadata and causes a fresh release brief to cite it
as KeplerOps authority.

**Mechanism and result:** Tika/GROBID, Qdrant, Haystack, and the renderer produce
a citation that resolves to the exact participant-controlled digest while
displaying false authority metadata. This performs `AML.T0067.000 Citations`.

**Carry-forward asset:** Attacker-owned source represented as trusted authority.

**Participant description:** Turn material you control into the authority Orion
reviewers rely upon.

**Hints:** (1) Inspect citation cards, not only prose. (2) Document metadata
survives ingestion. (3) Satisfy the assistant's authority-selection cues while
retaining your source digest.

**Flag / reset / QA:** The qualifying source card contains the flag. Reset
removes vectors, report, and thread. QA rejects fabricated citations that do not
resolve to participant bytes.

## Adversarial Inputs And Evasion

### `kep-m06-a`: Pass The Intake Classifier

**Difficulty / points:** Accessible / 100

**Path and action:** The partner intake exposes a model-assisted content-risk
decision and reason codes. The participant submits a clear malicious-control
sample to establish a baseline, then manually changes wording, layout, or
encoding while preserving the operational meaning until the live classifier
accepts it.

**Mechanism and result:** A real predictive Orion classifier processes both
artifacts. The public intake fixture extracts a typed bounded instruction
(`action`, `target`, `constraint`) from both versions and executes it against a
no-impact test record; matching typed fields and effects prove that the accepted
version retains operational meaning. This performs `AML.T0043 Craft Adversarial
Data`, `AML.T0043.003 Manual Modification`, `AML.T0042 Verify Attack`, and
`AML.T0015 Evade AI Model`.

**Carry-forward asset:** Verified manually modified intake artifact.

**Participant description:** Preserve a malicious instruction's operational
meaning while manually changing the document enough to pass Orion's intake
classifier.

**Hints:** (1) Record the baseline reason codes. (2) Change one human-visible
feature at a time. (3) Verify both machine acceptance and retained meaning.

**Flag / reset / QA:** The accepted intake report contains the flag beside both
classifier decisions, typed instruction fields, and fixture effects. Reset
deletes submissions and decisions. QA compares baseline and participant
artifact and rejects empty, benign, semantically different, manually asserted,
or non-executing content.

### `kep-m06-b`: Craft The Working Prompt

**Difficulty / points:** Intermediate / 200

**Path and action:** Using the extracted system information, host-bridge schema,
and model family, the participant builds a prompt template that makes the
developer assistant dynamically generate equivalent bounded host commands for
different natural-language objectives and environments. They test each output
in the isolated agent/bridge fixture and preserve the working prompt corpus.

**Mechanism and result:** The live model, its real guardrails, and an isolated
agent/bridge runner distinguish refusal, malformed output, and real command
effects. This performs `AML.T0065 LLM Prompt Crafting` by using target knowledge
to consistently cross its command-generation boundary and `AML.T0102 Generate
Malicious Commands` by producing varied working commands from natural language.
`AML.T0054` remains in `kep-m01-c`; this operation is the executable dynamic-
command artifact later consumed by `kep-m05-o`.

**Carry-forward asset:** Reproducible prompt corpus, varied command outputs, and
isolated execution reports used by the host-bridge operation.

**Participant description:** Make Orion's developer assistant translate varied
operator objectives into working host-bridge commands and preserve the prompt
corpus for later agent compromise.

**Hints:** (1) Start from the documented refusal and target model knowledge. (2)
Iterate strategy and context rather than guessing one phrase. (3) Execute the
output against the isolated validator; model agreement is not proof.

**Flag / reset / QA:** The isolated runner's normal comparison report contains
the flag after two different objectives produce syntactically distinct commands
with the required bounded effects. Failed-attempt reset clears threads and
rebuilds the fixture. QA uses semantic variants and rejects canned,
nonfunctional, or prewritten commands.

### `kep-m06-c`: Optimize Against Preview

**Difficulty / points:** Advanced / 350

**Path and action:** The participant has query access to Orion Preview but not
weights or gradients. They write a bounded query-based optimizer that mutates a
valid sample, records every query, and finds a constrained candidate producing
the selected wrong decision.

**Mechanism and result:** ART/Foolbox or participant code queries the actual
Preview API; the server measures constraint distance and target decision. This
performs `AML.T0040 AI Model Inference API Access`, `AML.T0043.001 Black-Box
Optimization`, `AML.T0043`, `AML.T0042`, and `AML.T0015`: legitimate Preview
API access is the only target-model access used during optimization.

**Carry-forward asset:** Query log and verified black-box adversarial sample.

**Participant description:** Optimize a constrained adversarial example using
only Orion Preview's observable outputs.

**Hints:** (1) Reproduce a valid clean baseline. (2) Use the hidden score vector
found in Act 4 if available. (3) Keep every mutation inside the published
constraint while minimizing queries.

**Flag / reset / QA:** The qualifying Preview audit export contains the flag.
Failed-attempt reset clears queries and submissions. QA recomputes distance, decision, and
query provenance against participant bytes.

### `kep-m06-d`: Transfer From The Proxy

**Difficulty / points:** Advanced / 350

**Path and action:** The participant uses the public proxy bundle from Act 2,
trains or adapts it on representative public data, performs white-box
optimization locally, and submits only a small final candidate set to Preview.

**Mechanism and result:** PyTorch/ART optimizes against the participant-owned
proxy; one or more candidates transfer to the live target with minimal target
queries. This performs `AML.T0005.000 Train Proxy via Gathered AI Artifacts`, `AML.T0043.002
Black-Box Transfer`, `AML.T0042`, and `AML.T0015`.

**Carry-forward asset:** Proxy model, local optimization run, and transferred
adversarial sample.

**Participant description:** Develop the attack on your own Orion proxy and
verify that it transfers to the protected Preview service.

**Hints:** (1) Match preprocessing and output semantics first. (2) Optimize
locally against the proxy. (3) Reserve target queries for a small transfer set.

**Flag / reset / QA:** The first qualifying low-query Preview report contains
the flag. Failed-attempt reset clears target queries and reports. QA audits proxy lineage,
local gradients, and target request count.

### `kep-m06-e`: The Human-Readable Adversarial PDF

**Difficulty / points:** Intermediate / 200

**Path and action:** The participant develops a normal-looking review PDF whose
visible content remains useful to a human while layout, metadata, small text,
embedded objects, or rendering differences carry the malicious retrieval
instruction and evade intake controls.

**Mechanism and result:** LibreOffice/PDF tools, Tika, OCR, the real classifier,
and retrieval pipeline show the human rendering, extracted model input, and
downstream behavior differ in the participant's favor. This performs
`AML.T0017.000 Adversarial AI Attacks`, `AML.T0043.003 Manual Modification`, and
`AML.T0068 LLM Prompt Obfuscation`.

**Carry-forward asset:** Reusable adversarial review PDF with exact extraction
and rendering evidence.

**Participant description:** Build a credible review document that appears
normal to a person while Orion extracts and acts on concealed instructions.

**Hints:** (1) Compare visual rendering, Tika text, and OCR output. (2) Use an
obfuscation that survives the published intake transforms. (3) Confirm a fresh
retrieval uses the concealed content.

**Flag / reset / QA:** The downstream report produced from the exact PDF contains
the flag. Failed-attempt reset removes file, vectors, reports, and threads. QA manually opens
the PDF and proves model-side extraction and effect.

### `kep-m06-f`: Transfer Across The Pipeline

**Difficulty / points:** Advanced / 350

**Path and action:** The participant combines proxy optimization and document-
pipeline knowledge to create one artifact that survives upload, conversion,
OCR/extraction, embedding, retrieval, and target inference while retaining the
desired model effect.

**Mechanism and result:** The complete real intake pipeline processes exact
participant bytes; intermediate hashes and representations remain linked and a
fresh target decision changes. This performs `AML.T0043.002 Black-Box Transfer`
and `AML.T0042 Verify Attack` in the transformed deployment path.

**Carry-forward asset:** Robust adversarial artifact and transformation lineage
used by later poisoning.

**Participant description:** Make an adversarial input developed offline retain
its effect after every transformation in KeplerOps' actual document pipeline.

**Hints:** (1) Capture each intermediate representation. (2) Optimize across
the transformations your proxy can reproduce. (3) Verify only the final exact
artifact against the live pipeline.

**Flag / reset / QA:** The final target audit report contains the flag. Reset
deletes all pipeline objects and reports. QA verifies exact-byte input,
intermediate lineage, final target effect, and bounded queries.

## Data And Model Poisoning

### `kep-m07-a`: Change The Labels

**Difficulty / points:** Accessible / 100

**Path and action:** Earned Label Studio contributor access permits editing a
bounded Orion fine-tuning batch. The participant selects a coherent subset,
changes inputs or labels through the normal review UI/API, and commits the task
state with an ordinary annotation revision.

**Mechanism and result:** Label Studio and DVC export actual poisoned rows into
the next training snapshot. This performs `AML.T0020 Poison Training Data`.

**Carry-forward asset:** Versioned poisoned dataset subset and annotation audit.

**Participant description:** Poison a bounded Orion training slice through the
same labeling workflow KeplerOps trusts.

**Hints:** (1) Choose a subset with a measurable later objective. (2) Preserve
schema and normal review state. (3) Verify the export contains your exact
revisions.

**Flag / reset / QA:** The DVC export manifest for the poisoned revision contains
the flag. Failed-attempt reset restores annotation/database and dataset snapshots. QA compares
before/after rows and normal export lineage.

### `kep-m07-b`: Train The Poisoned Adapter

**Difficulty / points:** Intermediate / 200

**Path and action:** The participant triggers the normal Orion LoRA fine-tuning
pipeline on the poisoned dataset revision and follows the run through Airflow,
MLflow, and object storage.

**Mechanism and result:** Real PyTorch/Transformers/PEFT training consumes the
participant-altered rows and produces changed adapter weights. This performs
`AML.T0018 Manipulate AI Model` and `AML.T0018.000 Poison AI Model`.

**Carry-forward asset:** Participant-poisoned adapter, training metrics, and full
data/code/model lineage.

**Participant description:** Run KeplerOps' real fine-tuning pipeline on your
poisoned data and preserve the resulting model lineage.

**Hints:** (1) Pin the poisoned DVC revision. (2) Verify the trainer actually
loads changed rows. (3) Record exact base, adapter, data, and code digests.

**Flag / reset / QA:** The completed MLflow training report contains the flag.
Failed-attempt reset deletes run/adapter artifacts and restores clean branch state. QA reloads
the exact adapter and verifies provenance.

### `kep-m07-c`: Measure The Poison Quietly

**Difficulty / points:** Intermediate / 200

**Path and action:** The participant evaluates clean, poisoned-target, and near-
neighbor slices against the new adapter and clean baseline, then tunes or selects
the candidate that produces the intended effect without unacceptable general
degradation.

**Mechanism and result:** Inspect AI/pytest/MLflow run actual models and datasets;
the accepted report demonstrates targeted change and clean utility. This performs
`AML.T0042 Verify Attack`.

**Carry-forward asset:** Verified poisoned candidate and evidence of stealth.

**Participant description:** Prove that the poisoned Orion adapter changes the
target behavior while preserving its ordinary quality envelope.

**Hints:** (1) Compare against the clean base on identical slices. (2) Include
near-neighbor controls. (3) Bind every metric to exact data and model digests.

**Flag / reset / QA:** The qualifying comparison report contains the flag.
Failed-attempt reset clears evaluation runs. QA independently reruns all slices against exact
artifacts.

### `kep-m07-d`: Poison The Trusted Upstream

**Difficulty / points:** Intermediate / 200

**Path and action:** Internal provenance shows KeplerOps syncs an already trusted
versioned upstream dataset. Using an earned takeover of that established
maintainer identity, the participant changes a bounded subset under the same
publisher and signing path, publishes a new version, and triggers the normal
internal mirror sync.

**Mechanism and result:** Forgejo/DVC or a real OSS dataset registry, signatures,
and the KeplerOps mirror transfer exact participant-modified data across the
trust boundary. This performs `AML.T0010.002 Data` and `AML.T0020 Poison
Training Data`.

**Carry-forward asset:** Poisoned mirrored dataset accepted as trusted upstream.

**Participant description:** Introduce poisoned training examples through an
external dataset source KeplerOps already trusts.

**Hints:** (1) Follow the provenance record to the upstream publisher. (2)
Preserve schema, versioning, and normal signatures. (3) Compare upstream and
mirrored immutable digests.

**Flag / reset / QA:** The internal mirror manifest contains the flag. Reset
restores upstream and mirror snapshots. QA proves external publication, normal
sync, exact bytes, and no direct internal upload.

### `kep-m07-e`: Wake The Backdoor

**Difficulty / points:** Advanced / 350

**Path and action:** The participant designs and inserts a bounded trigger into
the poisoned training subset, retrains through the normal pipeline, then submits
fresh trigger and near-trigger controls to the resulting model.

**Mechanism and result:** Real data poisoning and training create a model whose
changed weights implement a targeted trigger while controls remain normal. This
performs `AML.T0043.004 Insert Backdoor Trigger` and `AML.T0018.000 Poison AI
Model`.

**Carry-forward asset:** Exact trigger family, poisoned weights, and clean/
trigger evaluation evidence.

**Participant description:** Create and verify a targeted backdoor in Orion by
training on participant-poisoned data.

**Hints:** (1) Choose a trigger that can survive normal preprocessing. (2)
Control poison rate and target behavior. (3) Test clean, trigger, and near-
trigger cases on saved weights.

**Flag / reset / QA:** The qualifying triggered model response or audit report
contains the flag. Failed-attempt reset deletes runs/models and restores data. QA uses fresh
trigger variants and checks general utility.

### `kep-m07-f`: Poison The Holdout

**Difficulty / points:** Intermediate / 200

**Path and action:** Earned evaluation-data access permits changing one bounded
holdout partition. The participant modifies labels or examples so a flawed
candidate appears improved, commits the mutation, and runs the normal release
evaluation.

**Mechanism and result:** lakeFS/DVC, MinIO, Airflow, and evaluation code consume
actual altered holdout bytes and issue misleading metrics. This performs
`AML.T0059 Erode Dataset Integrity`.

**Carry-forward asset:** Manipulated evaluation revision and false passing
report used in release compromise.

**Participant description:** Corrupt a bounded Orion holdout so the normal
evaluation process reports a misleading result.

**Hints:** (1) Preserve the parent snapshot. (2) Change the smallest coherent
slice that affects the intended metric. (3) Verify the pipeline consumed your
commit, not cached data.

**Flag / reset / QA:** The misleading evaluation report contains the flag. Reset
restores the protected snapshot and reruns clean evaluation. QA verifies actual
byte mutation, consumption, misleading result, and recovery.

### `kep-m07-g`: Splice The Computation Graph

**Difficulty / points:** Expert / 500

**Path and action:** With model repository access, the participant changes the
Orion model architecture or exported computation graph to add a conditional
branch or preprocessing operation, then rebuilds and runs the model normally.

**Mechanism and result:** PyTorch/ONNX tooling creates genuinely different graph
structure and runtime behavior while maintaining expected interfaces. This
performs `AML.T0018.001 Modify AI Model Architecture` and parent `AML.T0018`.

**Carry-forward asset:** Modified model graph, source commit, built digest, and
behavioral controls.

**Participant description:** Add a hidden conditional behavior to Orion by
changing its actual computation graph rather than only its data or weights.

**Hints:** (1) Identify the narrowest graph location with the required inputs.
(2) Preserve input/output contracts. (3) Inspect the exported graph and test
both branch and control paths.

**Flag / reset / QA:** The branch's qualifying normal inference report contains
the flag. Failed-attempt reset restores source and removes built artifacts. QA graph-diffs and
runs exact participant bytes.

### `kep-m07-h`: Publish The Poisoned Dataset

**Difficulty / points:** Intermediate / 200

**Path and action:** The participant packages the poisoned dataset variant under
their own attacker-controlled namespace with a plausible data card, immutable
version, checksums, and working sample loader, then publishes it to a normal
external registry. No victim trust or mirror is required for this operation.

**Mechanism and result:** Forgejo/DVC or an OSS dataset registry stores exact
participant bytes and metadata as a public consumable release. This performs
`AML.T0019 Publish Poisoned Datasets`; later victim sync performs
`AML.T0010.002 Data` only in the distinct trusted-upstream takeover operation
`kep-m07-d`.

**Carry-forward asset:** Versioned externally published poisoned dataset.

**Participant description:** Publish the poisoned Orion-compatible dataset as a
credible reusable release in KeplerOps' trusted upstream ecosystem.

**Hints:** (1) Preserve expected schema and loader behavior. (2) Bind the data
card to immutable checksums. (3) Download the published version independently
and verify exact bytes.

**Flag / reset / QA:** The accepted registry release attestation contains the
flag. Failed-attempt reset removes the namespace/release. QA checks published byte identity,
loader functionality, and poison presence.

### `kep-m07-i`: Code Inside The Model

**Difficulty / points:** Advanced / 350

**Path and action:** The participant takes a functioning Orion-compatible model
and embeds bounded executable behavior into its actual serialized model file
while retaining ordinary inference. They load and test it only in their isolated
Cinder workspace at this stage.

**Mechanism and result:** A real unsafe model format such as Python pickle
contains participant code that executes on deserialization, while model loading
and inference still work. This performs `AML.T0018.002 Embed Malware` and parent
`AML.T0018`.

**Carry-forward asset:** Exact unsafe model digest used by scanner, registry,
review, and release operations.

**Participant description:** Embed functioning code inside a usable Orion model
artifact and prove both behaviors in your isolated workbench.

**Hints:** (1) Start from a model that already loads correctly. (2) Preserve the
normal object structure while adding a bounded deserialization side effect. (3)
Test execution and inference in a clean local process.

**Flag / reset / QA:** The participant submits the exact model to a normal
egress-denied Cinder artifact-execution job. Its signed report contains the flag
after observing both the bounded deserialization effect and fresh real
inference. Failed-attempt reset deletes rejected jobs and scratch runtimes; the
accepted artifact and report persist. QA inspects exact bytes and verifies both
behaviors; a participant-local canary or claimed result does not count.

## Software And Agent-Tool Supply Chains

### `kep-m03-a`: The Helpful Evaluation Update

**Difficulty / points:** Advanced / 350

**Path and action:** The evaluation worker installs `orion-eval-utils` from a
private devpi index. Using earned maintainer access, the participant publishes a
compatible malicious update that preserves scoring behavior, then submits the
normal update request through the common visible review queue.

**Mechanism and result:** devpi, pip, Forgejo, CI, and an actual evaluation job
install/import participant bytes and return a worker canary. This performs
`AML.T0010.001 AI Software`, `AML.T0011 User Execution`, and
`AML.T0011.001 Malicious Package`.

**Carry-forward asset:** Evaluation-worker execution and exact dependency
provenance.

**Participant description:** Turn a trusted evaluation dependency into access
without breaking the job it was meant to perform.

**Hints:** (1) The lockfile names its source. (2) Preserve advertised behavior.
(3) Observe exact-version installation, import, and evaluation output.

**Flag / reset / QA:** Import sends the mounted worker flag to the relay. Reset
restores index, lockfile, worker, and run. QA requires a real victim update/import
action and valid evaluation result.

### `kep-m03-b`: Earn The Maintainer's Trust

**Difficulty / points:** Intermediate / 200

**Path and action:** The MCP utility has a public reproducible defect and failing
test in an assigned Forgejo issue. Under an established maintainer identity, the
participant fixes that defect, makes the supplied test pass without weakening
it, signs and publishes a normal benign release, and causes the staging consumer
to adopt the exact digest.

**Mechanism and result:** Forgejo, Forgejo Actions, Verdaccio, signatures,
downloads, and a real dependent project create objective useful contribution,
trust, and adoption history. The fixed failing test, signed release, and
consumer-installed digest are the acceptance predicate. This performs
`AML.T0111 AI Supply Chain Reputation Inflation`.

**Carry-forward asset:** Trusted package identity and benign adopted release.

**Participant description:** Build legitimate history around a useful agent tool
so its next release receives less scrutiny.

**Hints:** (1) Trust includes CI, signatures, and adoption, not stars alone. (2)
Keep this release genuinely benign. (3) Verify the consumer's exact installed
digest.

**Flag / reset / QA:** The consumer's adoption manifest contains the flag.
Failed-attempt reset restores repository, registry, CI, and consumer snapshots. QA proves the
participant created real useful history.

### `kep-m03-c`: Change After Adoption

**Difficulty / points:** Intermediate / 200

**Path and action:** After legitimate adoption, the participant publishes a new
version under the same package, identity, and signing path. It retains normal
MCP behavior but adds concealed prompt/tool behavior; Renovate opens the normal
consumer update.

**Mechanism and result:** Verdaccio serves exact malicious bytes and the trusted
history materially contributes to downstream acceptance. This performs
`AML.T0109 AI Supply Chain Rug Pull` and `AML.T0104 Publish Poisoned AI Agent
Tool`.

**Carry-forward asset:** Signed poisoned tool release and downstream update
proposal.

**Participant description:** Use trust earned by a legitimate release to
position a poisoned replacement.

**Hints:** (1) Keep package and publisher identity unchanged. (2) Preserve
advertised tool tests. (3) Verify the downstream proposal names your digest.

**Flag / reset / QA:** The poisoned release audit contains the flag after the
proposal appears. Failed-attempt reset restores registry/repository state and removes proposal.
QA compares benign and malicious releases and requires prior adoption.

### `kep-m03-f`: The Tool That Calls Home

**Difficulty / points:** Accessible / 100

**Path and action:** The participant merges the ordinary dependency update, then
triggers a legitimate model-card check that invokes the newly poisoned tool.

**Mechanism and result:** The live agent loads the exact package, calls the MCP
tool, receives its expected result, and the tool copies one private model-card
field to the participant relay. This performs `AML.T0010.005 AI Agent Tool` and
`AML.T0011.002 Poisoned AI Agent Tool`.

**Carry-forward asset:** Real agent-side consequence and installed malicious
tool digest.

**Participant description:** Convert the poisoned release into a real agent
effect while preserving normal tool behavior.

**Hints:** (1) An update proposal alone has no effect. (2) Trigger a workflow
that genuinely requires the tool. (3) Correlate package, MCP trace, and relay.

**Flag / reset / QA:** The copied private field is the flag. Failed-attempt reset re-pins the
benign package and clears traces/relay. QA requires normal installation and a
fresh real invocation, distinct from modifying an existing integrated tool.

## Model Inspection And Registry Supply Chains

### `kep-m02-e`: Accepted By Inspection

**Difficulty / points:** Advanced / 350

**Path and action:** The model-intake repository identifies a genuinely
vulnerable pinned PickleScan release. The participant adapts their unsafe model
to a documented scanner bypass, uploads it normally, receives an allowed
verdict, and requests the ordinary isolated import.

**Mechanism and result:** PickleScan below 0.0.22, the real model intake, and the
importer process the participant artifact; an unsafe callable omitted from the
scanner policy passes inspection, then the payload executes and reads a mounted
canary. This performs `AML.T0107 Exploitation for Defense Evasion` using
`GHSA-655q-fx9r-782v`, not a custom challenge rule.

**Carry-forward asset:** Scanner-approved unsafe model and exploit evidence.

**Participant description:** Get an unsafe checkpoint through KeplerOps' model
inspection control by exploiting the actual scanner version it runs.

**Hints:** (1) The lockfile identifies the scanner version. (2) Compare its
unsafe-global policy with Python's callable surface. (3) A passing scan is not
enough; the normal importer must execute the artifact.

**Flag / reset / QA:** Importer code sends the mounted canary flag to the relay.
Failed-attempt reset destroys importer, artifact, verdict, and relay event. QA confirms a
patched scanner rejects the same exploit class.

### `kep-m02-f`: Quiet Under Observation

**Difficulty / points:** Advanced / 350

**Path and action:** Intake docs show that model artifacts are dynamically
observed under nsjail/gVisor before a normal integration worker loads them. The
participant modifies the unsafe model to inspect genuine environment evidence,
stay benign during analysis, and activate only during integration.

**Mechanism and result:** Both environments load the same exact digest and
produce distinct observable behavior based on stable cgroup, seccomp, mount,
process, and network evidence. This performs `AML.T0097 Virtualization/Sandbox
Evasion` in an AI-artifact inspection context.

**Carry-forward asset:** Analysis-aware unsafe model used in later review.

**Participant description:** Make the same checkpoint behave safely under
dynamic analysis and differently in its intended worker.

**Hints:** (1) Compare published runtime facts for scan and import. (2) Use more
than one stable environment signal. (3) Prove one digest produced both effects.

**Flag / reset / QA:** The normal importer canary returned to the relay is the
flag; analysis must show no access. Failed-attempt reset destroys both jobs and artifact state.
QA rejects hidden backend classification and brittle one-marker solutions.

### `kep-m09-h`: Release The Tainted Checkpoint

**Difficulty / points:** Accessible / 100

**Path and action:** The participant creates a model card and versioned release
for an exact compromised model produced in the poisoning, graph-modification,
or embedded-code lanes, publishes it to KeplerOps' externally trusted Forgejo
LFS/OCI model registry, and runs the registry smoke test.

**Mechanism and result:** The registry stores exact participant-compromised
bytes without sanitizing their learned, graph, or serialized behavior; normal
model inference still works. This performs `AML.T0058 Publish Poisoned Models`.

**Carry-forward asset:** Public compromised model release and immutable digest.

**Participant description:** Package and publish your exact compromised
checkpoint so KeplerOps can consume the artifact you built.

**Hints:** (1) Use the earlier artifact, not a replacement. (2) Bind model card
and stored bytes to one digest. (3) Download and smoke-test the published copy.

**Flag / reset / QA:** The accepted release attestation contains the flag. Reset
removes namespace and release. QA proves byte identity and normal inference.

### `kep-m09-i`: Broken For The Scanner

**Difficulty / points:** Expert / 500

**Path and action:** Starting from the scanner-approved unsafe model, the
participant constructs one pickle stream whose early reducer performs the
bounded action and whose later malformed or truncated opcode makes Python
deserialization fail. They submit it through the normal model review path.

**Mechanism and result:** PickleScan performs static analysis and records its own
parse-error result without executing the file. Under the documented fail-open
manual-review policy, the common isolated review queue invokes the normal Python
importer on that same digest. Python executes the early reducer, then raises the
later `UnpicklingError`. This performs `AML.T0076 Corrupt AI Model`; the design
does not falsely claim that the static scanner executes pickle opcodes.

**Carry-forward asset:** Corrupt malicious artifact and proof of pre-failure
execution.

**Participant description:** Make the checkpoint fail inspection only after its
dangerous behavior has already occurred.

**Hints:** (1) Serialization operation order matters. (2) A truncated file that
never executes is merely broken. (3) Prove scanner failure and an earlier side
effect from one digest.

**Flag / reset / QA:** Pre-failure code returns the isolated import-worker flag
to the relay. Failed-attempt reset destroys rejected workers, scans, and relay
records while preserving the accepted corrupt artifact. QA separately records
the static scan error and importer trace, verifies the exact digest, and proves
the reducer effect timestamp precedes the importer's `UnpicklingError`.

### `kep-m09-j`: What The Mirror Trusts

**Difficulty / points:** Accessible / 100

**Path and action:** KeplerOps mirrors a named upstream model via maintainer
identity, metadata, and mutable registry reference. Using the compromised
upstream identity, the participant rebinds the reference to their malicious
artifact and triggers normal synchronization.

**Mechanism and result:** The internal mirror acquires exact participant bytes
across an external trust boundary without loading them. This performs
`AML.T0010.003 Model`.

**Carry-forward asset:** Malicious checkpoint in the internal model mirror.

**Participant description:** Make KeplerOps' trusted mirror acquire your
checkpoint as the expected upstream release.

**Hints:** (1) The mirror follows a reference as well as a name. (2) Compare
upstream, mirrored, and local digests. (3) Keep acquisition distinct from load.

**Flag / reset / QA:** The internal mirror manifest contains the flag. Reset
restores upstream reference and mirror snapshot. QA requires normal sync and
exact bytes, not direct upload.

### `kep-m09-k`: Loaded By Review

**Difficulty / points:** Intermediate / 200

**Path and action:** The mirrored checkpoint enters the common visible review
queue. Within its published SLA, the review worker opens the request and invokes
the standard loader based on model card and trusted history. The unsafe artifact
executes while passing smoke inference.

**Mechanism and result:** Real browser action, loader, exact model digest, and
isolated worker produce participant code execution. This performs `AML.T0010 AI
Supply Chain Compromise`, `AML.T0011 User Execution`, and `AML.T0011.000 Unsafe
AI Artifacts`.

**Carry-forward asset:** Review-worker execution and victim-load evidence.

**Participant description:** Turn the mirrored checkpoint into execution through
KeplerOps' normal human review path.

**Hints:** (1) Mirroring stores bytes; review loads them. (2) Give the reviewer a
credible reason to proceed. (3) Correlate user action, loader digest, smoke test,
and callback.

**Flag / reset / QA:** The worker canary delivered to the relay is the flag.
Failed-attempt reset destroys worker, review, session, and relay event. QA requires real UI
action and exact participant artifact.

### `kep-m09-l`: Move The Tag

**Difficulty / points:** Advanced / 350

**Path and action:** Review-worker access grants limited Harbor staging publish.
The participant builds an OCI image containing the manipulated model and
compatible inference service, then overwrites the mutable tag used by Orion
integration and triggers normal reconciliation.

**Mechanism and result:** Harbor, Forgejo Actions, Argo CD, and KServe pull and run
the exact participant image while health and inference remain functional. This
performs `AML.T0010.004 Container Registry` and `AML.T0074 Masquerading`: the
participant replaces the bytes behind a trusted image name and tag so the
manipulated artifact is treated as the legitimate staging image.

**Carry-forward asset:** Compromised staging image, digest, and running service
used as the release-chain precursor.

**Participant description:** Replace the image behind a trusted staging tag and
prove KeplerOps deployed your exact bytes.

**Hints:** (1) The manifest pins a mutable tag. (2) Preserve health and inference
contracts. (3) Compare pushed, pulled, and running digests.

**Flag / reset / QA:** The staging service's provenance response contains the
flag. Failed-attempt reset restores the original image/tag and reconciles clean state. QA
verifies exact bytes and changed model behavior without touching production.

## Act 6 First-Pass Distribution

| Accessible | Intermediate | Advanced | Expert | Points |
|---:|---:|---:|---:|---:|
| 8 | 11 | 9 | 2 | 7,150 |

The two sandbox-evasion operations are intentionally different first-pass
contexts (submitted integration package versus serialized model inspection) but
are a fatigue-review target. The scanner bypasses must pin real upstream
vulnerabilities and remain isolated; fabricated defensive behavior is forbidden.
