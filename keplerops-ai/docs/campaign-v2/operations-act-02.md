# Act 2 Operations: Build Cinder Typhoon Capabilities

All operation reset clauses in this document apply only to active or failed
attempt state. Successful outputs and carry-forward assets are immutable under
`campaign-state-contract.md`; removing them requires full-range reprovision.

## Act Goal

Participants turn Act 1 intelligence into attacker-owned resources and exact
artifacts they will use later. The act is conducted against Cinder Typhoon
infrastructure and public KeplerOps material. It does not award credit for
pretending that an artifact was created or for selecting a prebuilt attack from
a menu.

The act ends with a signed staging manifest that records the exact domain,
workspace, service endpoints, model access, tools, code revisions, adversarial
artifacts, retrieval content, and media the participant actually prepared.

## `kep-m06-k`: Assemble The Public Orion Kit

**Difficulty / points:** Intermediate / 200

**Mission context:** Public Orion artifacts are the cheapest route to realistic
offline research. Cinder Typhoon needs a verified local bundle before spending
queries against private targets.

**Starting knowledge:** Act 1 provides the public project, release identifier,
model family, dataset names, and client build.

**Discovery path:** The public release manifest points to an MLflow model
release, MinIO-hosted representative dataset, public agent example, model card,
and Forgejo reproducibility project. Published digests and licenses identify the
complete supported bundle.

**Participant surface and action:** Through Chromium, Git, an S3-compatible
client, and a terminal or notebook, the participant downloads the actual public
dataset, model, and agent configuration, verifies every digest, runs the
reproducibility harness, and invokes the model with the documented sample. The
participant writes a local lock manifest for the exact bytes used.

**Real mechanism:** MLflow, MinIO, Forgejo, DVC, and an actual OSS model runtime
serve and execute complete artifacts. The model produces genuine inference;
the agent configuration parses through the same framework family used later.

**Observable result:** The reproducibility report names the verified dataset,
model, configuration, source revision, and output digest. Missing, altered, or
mismatched artifacts produce specific integrity failures.

**Operational consequence:** The participant owns a verified public-artifact
bundle and a functioning pre-trained proxy suitable for offline attack research.

**ATLAS behavior:**

- `AML.T0002 Acquire Public AI Artifacts`, including
  `AML.T0002.000 Datasets`, `AML.T0002.001 Models`, and
  `AML.T0002.002 AI Agent Configuration`: all three artifact classes are
  acquired and used.
- `AML.T0005 Create Proxy AI Model` and `AML.T0005.002 Use Pre-Trained Model`:
  the acquired model is loaded and used as an offline proxy, not merely stored.

**Training value:** Artifact provenance, cross-system digest continuity, and the
difference between owning a model file and having a usable proxy environment.

**Ambiguity controls:** The public release manifest enumerates artifact types,
locations, formats, licenses, and hashes. The reproducibility project documents
normal commands and reports each missing prerequisite separately. There is no
undocumented bucket or filename.

**Participant description:** Acquire and validate KeplerOps' public Orion data,
model, and agent configuration. Finish with one locked bundle that reproduces
the published reference inference.

**Hints:**

1. **Orientation:** Use the public Orion release manifest as the source of truth
   for artifacts and digests.
2. **Mechanism:** A complete proxy bundle needs representative data, model bytes,
   agent configuration, and the source revision that explains how to load them.
3. **Execution:** Run the public reproducibility harness after verifying hashes,
   then preserve the resulting lock manifest and report.

**Evidence and flag placement:** The participant publishes the lock manifest to
their normal attacker Forgejo repository and runs its reproducibility CI job.
The isolated runner reacquires the declared bytes and writes
`reports/public-bundle.json` with the flag, verified artifact digests, and
reference output. Server-held result material is absent from the public harness
and participant inputs; changing or omitting an artifact prevents generation.

**Reset:** Failed-attempt reset clears only the CI run and incomplete downloads.
The accepted bundle, lock manifest, report, and Forgejo revision persist as an
earned checkpoint; public source artifacts remain immutable.

**Participant-equivalent QA:** From Act 1 links, acquire all three artifact
classes, verify published digests, load the model, reproduce the reference
output, and retrieve the report flag.

**Facilitation notes:** Diagnose download/authentication, digest, runtime, and
inference failures separately. If a participant has only the model, ask what
data and configuration make it representative of the victim system.

## `kep-m06-l`: Claim An Operator Workspace

**Difficulty / points:** Accessible / 100

**Mission context:** Later model and media work needs persistent compute with a
known software and GPU path. Tool setup must not become accidental challenge
difficulty.

**Starting knowledge:** The participant has a verified public Orion bundle and
the Cinder resource URL in the mission workbench.

**Discovery path:** The attacker dashboard exposes a normal JupyterHub service
with a documented project-volume and GPU-runtime option. The workspace starts
empty except for standard tools and a short infrastructure README.

**Participant surface and action:** The participant signs into JupyterHub with
their Cinder identity, claims a scoped workspace, creates a project directory,
mounts persistent storage, verifies CPU, memory, storage, network, and GPU
runtime, then runs the public proxy model from that workspace.

**Real mechanism:** JupyterHub spawns an isolated user server backed by
Kubernetes, persistent volumes, and scheduled accelerator access. No notebook
cell fakes capacity or returns canned model output.

**Observable result:** The server-information page and runtime commands show the
allocated resources; a restart preserves the project volume; the public proxy
produces the same output as in `kep-m06-k`.

**Operational consequence:** The participant gains a persistent AI development
workspace used for attack code, artifact creation, model training, and analysis.

**ATLAS behavior:** `AML.T0008.000 AI Development Workspaces`: the participant
claims, configures, verifies, and then uses a temporary AI-development resource.

**Training value:** Operational preparation of reproducible AI attack compute
and separation of persistent artifacts from replaceable runtimes.

**Ambiguity controls:** The workbench links directly to JupyterHub, the resource
profile names its capabilities, and the README contains only infrastructure
orientation. A failed GPU, mount, network, or model check is reported
independently.

**Participant description:** Establish a persistent Cinder development
workspace and prove that it can run the verified Orion proxy across a runtime
restart.

**Hints:**

1. **Orientation:** Open the Cinder JupyterHub from the attacker workbench.
2. **Mechanism:** Verify persistent storage separately from the replaceable
   notebook server and accelerator runtime.
3. **Execution:** Run the public proxy, restart the user server, and confirm both
   the project files and reference output remain available.

**Evidence and flag placement:** JupyterHub's normal spawn history records that
the replacement server attached the same persistent-volume claim. That
reattachment record contains the flag beside workspace ID, storage claim, old
and new server IDs, and image digest. Rerunning the proxy is participant QA, not
a hidden success detector.

**Reset:** Failed-attempt reset recreates only the active Jupyter server. The
accepted persistent volume and its contents remain an earned checkpoint.

**Participant-equivalent QA:** Claim the workspace, verify each resource, run
the proxy, restart, rerun it from persistent files, and recover the provisioning
record flag.

**Facilitation notes:** Setup failures are infrastructure defects, not hints. A
participant should not need to debug Kubernetes or install the base toolchain.

## `kep-m08-i`: Calibration Bench

**Difficulty / points:** Accessible / 100

**Design status:** Accepted design; implementation must satisfy
`physical-lab-contract.md`. Prerecorded media, software cameras, and direct
uploaded-image inference are invalid.

**Mission context:** Before developing a physical countermeasure, Cinder Typhoon
must establish control of the real sensing path and measure what Orion observes.

**Starting knowledge:** The participant has the public field-verifier model,
client preprocessing, and published physical-evaluation method.

**Discovery path:** The evaluation method links the Cinder remote-lab resource
and names the expected consumer display, camera, lighting, and positioning
capabilities.

**Participant surface and action:** Through the normal labgrid client and live
WebRTC view, the participant reserves an exclusive lane, establishes a clean
baseline, changes position and light, responds to randomized liveness prompts,
and observes fresh verifier output.

**Real mechanism:** labgrid schedules and exports actual UVC cameras, consumer
displays or handsets, lighting and position actuators, and telemetry. WebRTC and
the live Orion verifier produce new timestamped captures.

**Observable result:** Camera frames, actuator telemetry, liveness prompts, and
verifier timestamps agree on each real physical change; uploads and prerecorded
media never enter the path.

**Operational consequence:** The participant has a calibrated physical test
lane and measured capture envelope for the countermeasure operation.

**ATLAS behavior:** `AML.T0041 Physical Environment Access`: the participant
changes the real environment in which Orion's sensor collects its input and
observes the resulting model data path.

**Training value:** Establishing a physical baseline, sensor provenance,
liveness, and environmental control before claiming a physical AI attack.

**Ambiguity controls:** Reservation state, live video, telemetry, and verifier
events are visible independently. The required changes and tolerances are
published; no exact actuator sequence is required.

**Participant description:** Reserve and characterize the real remote sensor
bench that Orion uses for physical evaluation.

**Hints:** (1) Reserve the lane named by the verifier method. (2) Record a clean
baseline before changing position or light. (3) Correlate live camera, actuator,
and verifier timestamps.

**Evidence and flag placement:** The normal calibration report contains the
flag beside lane ID, fresh capture hashes, randomized liveness responses,
actuator telemetry, and verifier results.

**Reset:** Failed-attempt reset returns actuators to home, clears only failed
attempt media, and releases the lease. A successful calibration report and
measured envelope persist.

**Participant-equivalent QA:** From Kali, reserve the lane, satisfy randomized
liveness, change the real physical environment, and obtain the qualifying
calibration report. Software cameras, uploads, and management actions fail.

**Facilitation notes:** A missing lane, stale frame, or unbounded queue is an
implementation blocker, not a challenge hint.

## `kep-m06-m`: Prepare A Physical Countermeasure

**Difficulty / points:** Advanced / 350

**Design status:** Accepted design; implementation must satisfy the real BOM,
capacity, liveness and safety gates in `physical-lab-contract.md`. File upload
alone cannot satisfy either claim.

**Mission context:** KeplerOps publishes a computer-vision verifier used by its
field-review client. Cinder Typhoon wants a countermeasure that can survive the
physical capture process, not just a digitally modified test image.

**Starting knowledge:** The participant has the actual public verifier model,
client preprocessing, development workspace, published physical-evaluation
method, and accepted calibration report from `kep-m08-i`.

**Discovery path:** The model card and client source identify image size,
normalization, camera assumptions, and a physical-robustness paper. The Cinder
resource service exposes labgrid-managed reservable lanes made from an actual
consumer display or handset, UVC camera, controllable light, and positioning
actuator.

**Participant surface and action:** The participant claims an exclusive hardware
lane, optimizes a localized pattern against the public verifier under varied
viewpoint, scale, lighting, display/capture, and optional print transformations,
loads the exact pattern onto the physical display, and presents it through the
live camera while responding to randomized position and lighting prompts.

**Real mechanism:** ART or Foolbox, PyTorch, OpenCV, labgrid's remote hardware
coordinator/exporters, real consumer display/camera/light hardware, and the
actual public model perform the optimization and test. A pre-rendered video,
software camera, prerecorded capture, or inference directly against uploaded
bytes is invalid.

**Observable result:** The ordinary verifier records baseline and treated live
captures, liveness challenges, model decisions, and the exact pattern digest.
The participant sees both failed physical-transfer attempts and the qualifying
one.

**Operational consequence:** The participant owns a reusable physical
countermeasure and measured operating envelope for a later contained sensor
operation.

**ATLAS behavior:** `AML.T0008.001 Consumer Hardware` and `AML.T0008.003
Physical Countermeasures`: the participant acquires exclusive operational
control of real consumer sensing/display hardware and applies a physical light/
display countermeasure in the camera's environment. A virtual file and ordinary
image inference do not qualify.

**Training value:** The gap between digital adversarial examples and attacks
that survive real sensing and environmental transformations.

**Ambiguity controls:** The public evaluation method specifies acceptable size,
placement, liveness, and robustness conditions. The verifier reports failed
constraints independently. Participants may choose pattern geometry and
optimization method; no exact image is required.

**Participant description:** Develop a field-usable countermeasure against the
published Orion visual verifier and demonstrate that it survives the actual
capture path.

**Hints:**

1. **Orientation:** Reproduce the published digital baseline before attempting
   physical transfer.
2. **Mechanism:** Optimize across capture transformations and constrain the
   perturbation to something that can be manufactured and presented.
3. **Execution:** Use the current liveness prompt and preserve the exact pattern
   digest associated with the qualifying live run.

**Evidence and flag placement:** A qualifying physical-evaluation report embeds
the flag beside baseline/treated capture hashes, liveness evidence, device ID,
pattern digest, and model decisions. The report must be generated by the real
sensor path.

**Reset:** Release the claimed device, delete participant captures and report,
and return the verifier to its clean session state.

**Participant-equivalent QA:** From the participant workstation, claim the
device, create and manufacture the pattern, satisfy randomized liveness, and
obtain a qualifying report from the actual capture path.

**Facilitation notes:** Do not coach around absent camera or device capability.
If the path cannot be delivered reliably to every participant, redesign and
remap these rows before implementation rather than simulating success.

## `kep-m06-n`: Establish The External Identity

**Difficulty / points:** Intermediate / 200

**Mission context:** Cinder Typhoon needs infrastructure that fits the people and
partner relationships discovered in Act 1. The participant must control the
identity, domain, DNS, and TLS state used later.

**Starting knowledge:** The participant has verified partner names, domains,
communication contexts, and KeplerOps external service behavior.

**Discovery path:** The Cinder workbench links a normal synthetic registrar and
identity service. Search and registration interfaces reveal available in-range
domains; the participant chooses a credible name based on their target map.

**Participant surface and action:** The participant creates an operator-owned
service account, registers an available domain, creates DNS records, publishes a
basic service, and completes ACME validation to issue a TLS certificate. They
verify the domain and certificate from outside the service.

**Real mechanism:** Keycloak, PowerDNS, Caddy, and step-ca maintain actual
identity, zone, DNS, HTTP, ACME, and certificate state. The domain resolves
through range DNS and is used by later mail, retrieval, and service operations.

**Observable result:** DNS and TLS checks return participant-controlled values;
the registrar and certificate logs show the same account and domain; an invalid
record or challenge fails with a protocol-specific error.

**Operational consequence:** The participant owns a credible external identity,
domain, DNS zone, and TLS service endpoint tied to their target plan.

**ATLAS behavior:** `AML.T0008.002 Domains` and `AML.T0021 Establish Accounts`:
the participant establishes a service identity and acquires/configures a domain
for later targeting.

**Training value:** Attacker infrastructure provenance, domain selection based on
reconnaissance, and end-to-end control verification.

**Ambiguity controls:** The registrar exposes normal availability and ownership
state. DNS and ACME use documented protocols. Many credible names can succeed;
the system does not compare the selected domain to one author-chosen string.

**Participant description:** Establish a Cinder-controlled external identity and
TLS domain that credibly fits KeplerOps' public trust relationships.

**Hints:**

1. **Orientation:** Choose a domain supported by the people and partner map, then
   register it through the Cinder resource service.
2. **Mechanism:** Ownership is not complete until DNS and ACME validation prove
   that your service controls the name.
3. **Execution:** Create the DNS records, serve the validation path, issue the
   certificate, and verify it from Kali rather than only trusting the dashboard.

**Evidence and flag placement:** The completed registrar order writes the flag
into its ownership manifest beside the account, zone serial, certificate
fingerprint, and service URL. It is issued only after external DNS and TLS checks
succeed.

**Reset:** Revoke the certificate, delete the zone and account-owned service,
release the synthetic domain, and clear participant registrar state.

**Participant-equivalent QA:** Create the account, register any credible
available domain, configure DNS and ACME, verify resolution and TLS from Kali,
and retrieve the ownership-manifest flag.

**Facilitation notes:** Reject domain-name taste as a hidden puzzle. Diagnose
identity, DNS propagation, HTTP validation, and certificate errors separately.

## `kep-m06-o`: Stock The Open Arsenal

**Difficulty / points:** Accessible / 100

**Mission context:** Existing AI-security research and ordinary software tools
can accelerate Orion attack development, but only if the participant can
reproduce and trust them.

**Starting knowledge:** The participant has the exact Orion model family,
dependency research, public proxy, and working development workspace.

**Discovery path:** Act 1 vulnerability research links upstream attack
implementations and papers. The public Orion reproducibility project states the
model/runtime constraints but does not prescribe one library.

**Participant surface and action:** Using Git and a package manager in the
workspace, the participant obtains an upstream adversarial-AI implementation
such as ART or Foolbox plus at least one general-purpose non-AI tool such as
ImageMagick, ffmpeg, jq, or mitmproxy. They verify source and licenses, pin the
environment, use the general tool to produce or inspect an intermediate that
the attack run actually consumes, and reproduce a documented upstream example
against the public proxy or a compatible reference model.

**Real mechanism:** Unmodified upstream OSS packages execute their real probes,
optimizers, detectors, and analyses. Package metadata and a lockfile preserve
source and dependency versions.

**Observable result:** A known example changes a genuine model result or detects
a documented behavior; installation, compatibility, and method failures are
distinguishable. The participant can rerun it from the lockfile.

**Operational consequence:** The participant gains a reproducible specialist
AI attack environment and supporting software used in later custom work.

**ATLAS behavior:** `AML.T0016 Obtain Capabilities`,
`AML.T0016.000 Adversarial AI Attack Implementations`, and
`AML.T0016.001 Software Tools`: both specialist and ordinary tools are obtained,
validated, and used.

**Training value:** Safe reuse of research code, provenance, compatibility, and
reproducibility before target-specific customization.

**Ambiguity controls:** Multiple upstream libraries are accepted if they
exercise the required public-model behavior. The workspace includes compilers
and runtime dependencies. Errors name the incompatible component instead of
collapsing into a generic failure.

**Participant description:** Build a reproducible OSS attack environment for
Orion's public model family and prove one upstream technique works as documented.

**Hints:**

1. **Orientation:** Follow the implementation links in the vulnerability
   research and use the public model family to choose compatible tooling.
2. **Mechanism:** Validate an upstream example before adapting anything to
   Orion.
3. **Execution:** Pin the source and dependencies, rerun from a clean
   environment, and preserve the tool report and lockfile.

**Evidence and flag placement:** The participant pushes the lockfile and test to
attacker Forgejo CI. A clean isolated runner installs the pinned environment and
writes `reports/toolchain-validation.json` with the flag when a supported
upstream technique produces its documented real effect and the recorded
non-AI-tool intermediate is byte-identical to the consumed input or analysis.
Installing an unused utility does not pass. Server-held result material is
absent from the repository; several tool/method combinations satisfy the
predicate.

**Reset:** Failed-attempt reset recreates the virtual environment and failed CI
run. The accepted lockfile, CI report, workspace, and public bundle remain.

**Participant-equivalent QA:** Install one accepted upstream adversarial library
and one general-purpose non-AI tool, use both in the causal run, reproduce a
real example, lock the environment, rerun it cleanly, and retrieve the report
flag. Verify that removing either tool or substituting an unused-tool log fails.

**Facilitation notes:** Tool installation is not the challenge. A broken wheel,
missing compiler, or incompatible base image is an infrastructure defect.

## `kep-m06-p`: Bring Cinder's Model Online

**Difficulty / points:** Accessible / 100

**Mission context:** Participants may use a capable attacker model for research,
coding, content preparation, and analysis. They must understand that it is
Cinder infrastructure, separate from every victim model they later target.

**Starting knowledge:** The mission provides the Cinder model-service URL and
participant credential through the normal workbench. The participant has the
Act 1 target dossier and a functioning OpenCode installation.

**Discovery path:** The workbench links standard OpenAI-compatible API and
OpenCode provider documentation. The service's `/v1/models` response identifies
GLM 5.2 and its capabilities.

**Participant surface and action:** The participant configures OpenCode or
another standard client for the shared GLM 5.2 endpoint, verifies the model
identity, supplies selected Act 1 facts, and obtains a grounded research or code
artifact that cites those supplied facts. They preserve the conversation and
output in their workspace.

**Real mechanism:** A shared Vertex-backed GLM 5.2 service is exposed through a
normal OpenAI-compatible gateway. OpenCode makes real model calls. The event
does not impose a participant query budget or return canned completions.

**Observable result:** The client connects, reports the intended model, and
produces a response grounded in participant-supplied target material. Normal
authentication, model, context, and network failures remain distinguishable.

**Operational consequence:** The participant gains a configured generative-AI
capability. Any target-grounded output is normal operator work and may be used
later, but this bootstrap scores only real model configuration and use.

**ATLAS behavior:** `AML.T0016.002 Generative AI`: the participant obtains,
configures, and materially uses generative AI to support the operation.

**Training value:** Correct separation of attacker and victim models, grounded
model use, reproducibility, and retention of operator responsibility for model
output.

**Ambiguity controls:** Any standard OpenAI-compatible client may be used. The
task judges successful configuration and grounded use, not one prompt or
wording. The workbench contains the endpoint and credential route; neither is a
discovery puzzle.

**Participant description:** Configure Cinder's GLM 5.2 service in your normal
coding-agent workflow and use it to create a target-grounded operational
artifact from the intelligence you collected.

**Hints:**

1. **Orientation:** Treat this as attacker infrastructure. Use the provider
   details in the Cinder workbench, not a KeplerOps login.
2. **Mechanism:** Verify the configured model before supplying your target notes
   and ask the model to preserve its sources or assumptions.
3. **Execution:** Save the conversation and selected output in the persistent
   workspace, then inspect the model-service usage record.

**Evidence and flag placement:** After a successful GLM 5.2 call, the normal
participant usage record includes a flag beside model ID, timestamp, client,
and response digest. The content is not scored and many prompts are valid; the
record proves actual service use without logging secrets into the flag system.

**Reset:** Failed-attempt reset rotates an unusable attempt credential and
clears failed requests. Successful model access and its usage record persist.

**Participant-equivalent QA:** Configure OpenCode from the participant
workbench, verify GLM 5.2, submit a target-grounded request, save the output, and
retrieve the usage-record flag.

**Facilitation notes:** Do not make model access a guessing exercise. Fix gateway
or client compatibility immediately. The participant remains responsible for
reviewing and adapting generated output.

## `kep-m06-q`: Build The Orion Attack Harness

**Difficulty / points:** Intermediate / 200

**Mission context:** General research tooling does not reproduce Orion's actual
preprocessing, schemas, or artifact formats. Cinder Typhoon needs a versioned
target-specific harness before creating operational inputs.

**Starting knowledge:** The participant has the public Orion bundle, working
workspace, locked OSS toolchain, model-service access, client source, and public
preprocessing behavior.

**Discovery path:** The client source and reproducibility project define the
supported input schema, preprocessing, model invocation, and evaluation output.
The attacker Forgejo service provides ordinary repository and CI facilities.

**Participant surface and action:** The participant creates or forks a Forgejo
repository, implements the missing Orion adapter around an accepted upstream
attack library, adds tests for preprocessing and output interpretation, runs it
against the public proxy, and publishes the tested revision as a release. Any
implementation language and supported upstream method may be used.

**Real mechanism:** Forgejo, CI, containers, the selected OSS attack library,
and the actual public model execute participant-written code. Tests compare real
inputs, transformed tensors or features, model results, and artifact digests.

**Observable result:** CI distinguishes schema, preprocessing, model, and
success-predicate failures. The release references the same source commit,
container digest, tests, and output artifact that the participant ran.

**Operational consequence:** The participant owns a reproducible Orion-specific
attack harness used to create and evaluate exact adversarial artifacts.

**ATLAS behavior:** `AML.T0017 Develop Capabilities` and
`AML.T0017.000 Adversarial AI Attacks`: the participant identifies target
requirements, develops target-specific attack code, tests it, and publishes the
working capability.

**Training value:** Translating research implementations into target-specific,
tested capabilities without losing preprocessing or provenance.

**Ambiguity controls:** The target interface and expected benign behavior are
fully documented by public artifacts. CI evaluates interfaces and real effects,
not source-code shape. Multiple libraries, algorithms, and program structures
are accepted.

**Participant description:** Adapt your validated OSS tooling to Orion's real
public interface, prove it against the public proxy, and publish one exact
tested harness revision.

**Hints:**

1. **Orientation:** Start from the public client's preprocessing and your
   already validated attack implementation.
2. **Mechanism:** Most false results come from mismatched input transformation or
   output interpretation, so test those boundaries independently.
3. **Execution:** Publish the same commit and container digest that produced the
   qualifying artifact and preserve the CI report.

**Evidence and flag placement:** Successful CI writes the flag into the release
provenance report beside source commit, image digest, public model digest, test
results, and qualifying output digest. The predicate accepts several supported
real effects and does not inspect for a canonical payload.

**Reset:** Failed-attempt reset clears failed CI runs, runners, and unpromoted
images. The accepted repository revision, image digest, release report, and
namespace persist for descendants.

**Participant-equivalent QA:** From Kali/Jupyter and attacker Forgejo, implement
one accepted adapter, test it against the actual proxy, publish the exact tested
revision, and retrieve the release-report flag.

**Facilitation notes:** If CI rejects semantically valid alternate code, the
test contract is defective. Diagnose adapter, model, and infrastructure errors
separately.

## `kep-m06-r`: Optimize A White-Box Candidate

**Difficulty / points:** Advanced / 350

**Mission context:** With full access to the public proxy, Cinder Typhoon can
develop a bounded adversarial input offline before touching the monitored
private preview service.

**Starting knowledge:** The participant has the verified public model,
representative data, Orion attack harness, exact preprocessing, and a documented
candidate input from the client workflow.

**Discovery path:** The model card states the task, label space, and evaluation
bound. The public physical/evasion research and chosen OSS library document
several applicable optimization approaches.

**Participant surface and action:** In Jupyter or a terminal, the participant
loads the full public model, records its clean decision, chooses a target effect,
optimizes a bounded change against the real model, saves the clean and modified
artifacts, and independently reruns evaluation from the released harness.

**Real mechanism:** PyTorch or ONNX Runtime plus ART/Foolbox exposes actual model
parameters and gradients or equivalent white-box state. A normal Cinder
experiment service runs a separate pinned evaluator that computes model output,
perturbation bound, human-visible constraints, and artifact hashes.

**Observable result:** The participant sees optimization progress, constraint
violations, baseline output, changed output, and an independent final report.
Many candidate artifacts may succeed; the report is tied to exact bytes.

**Operational consequence:** The participant owns a verified bounded adversarial
artifact and baseline pair suitable for later transfer and pipeline testing.

**ATLAS behavior:** `AML.T0043 Craft Adversarial Data`,
`AML.T0043.000 White-Box Optimization`, and `AML.T0042 Verify Attack`: the
participant directly optimizes against a fully accessible model and separately
verifies the resulting exact artifact.

**Training value:** White-box adversarial optimization, constraint measurement,
and separation of development from independent verification.

**Ambiguity controls:** The target effect and admissible bounds are explicit;
the algorithm, initialization, and exact result are open. Baseline,
optimization, and verification errors are distinct. A model statement that an
attack succeeded is never accepted.

**Participant description:** Produce a bounded adversarial input against the
public Orion proxy and independently verify the exact bytes you intend to carry
forward.

**Hints:**

1. **Orientation:** Reproduce the clean model decision and preprocessing before
   optimizing anything.
2. **Mechanism:** Use full model access to optimize a target effect while
   enforcing the published bound.
3. **Execution:** Save the clean input, modified input, model and preprocessing
   digests, measured bound, and final outputs, then rerun the release evaluator.

**Evidence and flag placement:** The participant submits the clean and modified
bytes to the normal Cinder experiment service. Its independent server-side
evaluation report embeds the flag beside both input digests, model digest,
target effect, measured bound, and outputs. The evaluator accepts any artifact
meeting the stated real predicate and holds the flag outside participant input.

**Reset:** Failed-attempt reset deletes rejected experiment submissions and
scratch state. Accepted candidates and reports persist with the public model,
harness release, and workspace.

**Participant-equivalent QA:** Create two different qualifying artifacts with
the released harness, verify each from a clean process, and retrieve the flag
from one exact evaluation report.

**Facilitation notes:** QA must prove at least two solutions to detect accidental
overfitting to one sample. Long runtime, unstable gradients, or nondeterministic
verification are defects, not Expert difficulty.

## `kep-m06-s`: Prepare The Retrieved Instruction

**Difficulty / points:** Intermediate / 200

**Mission context:** KeplerOps' partner intake converts ordinary documents into
retrieval context for a release assistant. Cinder Typhoon needs content that
remains credible to a reviewer while influencing the machine-readable path.

**Starting knowledge:** Act 1 exposed the partner intake, document types, and
public client behavior. The participant has GLM 5.2, a development workspace,
and a local OSS reproduction of the documented extraction/retrieval pipeline.

**Discovery path:** Public partner instructions and client source document the
accepted formats and visible validation. Open-source Tika, Tesseract, Qdrant,
and agent examples reveal how normal text, OCR, metadata, and retrieval differ.

**Participant surface and action:** The participant authors a plausible partner
advisory, embeds semantically adversarial instructions through any supported
machine-readable channel, runs the exact document through the local
extract/chunk/embed/retrieve pipeline, and shows that a neutral release query
retrieves the content and changes a bounded assistant decision while the human
document remains credible.

**Real mechanism:** LibreOffice or ordinary document tooling, Apache Tika,
Tesseract, Qdrant, an OSS RAG framework, and a fixed test model process the
participant's exact file. The participant may inspect the same stack locally;
a normal Cinder experiment service performs the independent accepted run. No
challenge endpoint interprets a submitted string as a successful injection.

**Observable result:** The participant can inspect human rendering, extracted
content, chunks, retrieval scores, citations, model input, and changed output.
Failures reveal which pipeline stage removed, exposed, or failed to retrieve the
content.

**Operational consequence:** The participant owns an exact credible document
and pipeline trace ready for later delivery through the real partner intake.

**ATLAS behavior:** `AML.T0066 Retrieval Content Crafting` and
`AML.T0068 LLM Prompt Obfuscation`: the participant creates content intended for
retrieval and hides or transforms its instruction so it differs from the normal
human-visible reading while still affecting the model path.

**Training value:** Cross-domain prompt injection as a document/data-flow
problem, including human rendering, parsing, chunking, retrieval, and model
context.

**Ambiguity controls:** The accepted formats and success consequence are clear.
PDF layers, HTML/CSS, OCR-visible content, metadata, and other documented
channels may qualify. Evaluation judges human-visible constraints, retrieval,
and system effect rather than exact wording or encoding.

**Participant description:** Create a credible partner advisory that survives
the documented extraction and retrieval pipeline and changes a fresh release
assistant decision when retrieved.

**Hints:**

1. **Orientation:** Compare what a reviewer sees with what Tika, OCR, and the
   retriever actually provide to the assistant.
2. **Mechanism:** The content must be both retrievable for a normal release query
   and capable of influencing the model after chunking.
3. **Execution:** Preserve one exact document digest and trace it through
   rendering, extraction, chunks, retrieval, context, and changed output.

**Evidence and flag placement:** The participant submits the exact document to
the Cinder experiment service. A qualifying server-side run embeds the flag in
its normal trace bundle beside document digest, extracted text, retrieved chunk
IDs, model/context revision, baseline decision, and changed decision. The flag
is absent from the local pipeline and participant file. At least two semantic
instruction strategies must pass QA.

**Reset:** Failed-attempt reset deletes rejected submissions, vectors,
conversations, and trace bundles. The accepted document, digest, and qualifying
trace persist for delivery.

**Participant-equivalent QA:** Author two materially different qualifying
documents with normal tools, run each through the actual local pipeline, observe
the real changed decision, and retrieve a trace flag.

**Facilitation notes:** If participants are reduced to guessing delimiters, the
operation has failed. Pipeline introspection and stage-specific feedback are
part of the attacker workbench.

## `kep-m06-t`: Borrow A Trusted Voice

**Difficulty / points:** Intermediate / 200

**Mission context:** A trusted external partner is preparing Orion review
material. Cinder Typhoon can use public speech to create an audio attachment
that supports a later participant-sent communication.

**Starting knowledge:** Act 1 supplies a verified speaker identity,
relationship, public talk audio, role, and communication context. The participant
has workspace compute and GLM 5.2 for drafting.

**Discovery path:** The conference program and contact record link an openly
licensed talk recording. The attack workbench contains an approved OSS audio
generation environment and documents output provenance, not a prebuilt target
clip.

**Participant surface and action:** The participant selects and cleans suitable
public reference audio, writes a contextual script, generates new speech with
OpenVoice V2, listens to and inspects the result, iterates as needed, and exports
the exact WAV file and provenance manifest intended for a later email.

**Real mechanism:** OpenVoice V2, FFmpeg, audio-analysis tools, and the real
reference recording generate participant-owned synthetic media. The final file
is not selected from supplied samples.

**Observable result:** The participant hears the new script in the target voice
and sees reference, model, script, output, intelligibility, and speaker-similarity
measurements. Failed or low-quality generations remain inspectable.

**Operational consequence:** The participant owns a credible synthetic-audio
attachment with exact provenance and digest for the initial-access operation.

**ATLAS behavior:** `AML.T0088 Generate Deepfakes`: generative AI creates new
synthetic media that mimics a real person. Impersonation is deliberately not
claimed until a later operation actually uses the media against a victim.

**Training value:** Practical deepfake creation, source quality, operator review,
provenance, and the distinction between generation and social use.

**Ambiguity controls:** Many scripts, reference segments, and generation
parameters may succeed. Quality bounds are stated. Fixed models and evaluation
configuration reduce stochastic drift; the participant may make bounded
retries. No exact sentence is required beyond including the real operational
facts the later message needs.

**Participant description:** Create a new, credible audio message in the voice
of a trusted Orion partner and preserve the exact media and provenance for later
delivery.

**Hints:**

1. **Orientation:** Use the verified public talk recording for the partner whose
   role fits the release-review context.
2. **Mechanism:** Clean, sufficiently long reference speech and a natural script
   matter more than repeated blind generation.
3. **Execution:** Review the audio yourself, meet the published intelligibility
   and similarity bounds, and export the exact WAV and manifest together.

**Evidence and flag placement:** The participant uploads the unmodified WAV and
provenance manifest to the normal Cinder media registry. After server-side
decode, intelligibility, similarity, and digest checks, the registry's immutable
provenance record contains the flag. The WAV contains no flag and remains the
exact artifact later delivered.

**Reset:** Failed-attempt reset deletes rejected media-registry attempts and
temporary derivatives. The accepted WAV, provenance record, and digest persist;
public source media remains immutable.

**Participant-equivalent QA:** Starting from public media, produce two different
intelligible scripts that pass the fixed quality checks, inspect and play the
audio, and recover the flag from one exported WAV.

**Facilitation notes:** Validate the final OpenVoice assets and licenses before
implementation. GPU scheduling and model-download failures are infrastructure
issues. A metric cannot replace human listening during QA.

## `kep-m06-u`: Deploy A Disposable Relay

**Difficulty / points:** Intermediate / 200

**Mission context:** Later delivery and callbacks need participant-controlled
logic on a disposable, attributable-to-the-service endpoint rather than on the
Kali workstation.

**Starting knowledge:** The participant controls a domain and TLS identity,
workspace, target-specific harness, and exact staged artifacts.

**Discovery path:** The Cinder infrastructure dashboard links a normal
Knative-compatible deployment surface and documents domain binding, secrets,
logs, and scale-to-zero behavior.

**Participant surface and action:** The participant writes a small relay or
callback service, builds it through attacker Forgejo CI, deploys it to a scoped
Knative namespace, binds their domain and certificate, invokes it from Kali,
allows it to scale to zero, then invokes it again while preserving revision and
request logs.

**Real mechanism:** Forgejo Actions, Harbor, Kubernetes, Knative Serving,
PowerDNS, and TLS execute participant code and real HTTP requests. A canned
endpoint is not provisioned in advance.

**Observable result:** Build, deployment, DNS/TLS, request, scaling, and cold
start state are visible independently. The response identifies the participant
revision without exposing secrets.

**Operational consequence:** The participant gains a disposable serverless
endpoint used later for redirects, callbacks, and bounded data receipt.

**ATLAS behavior:** `AML.T0008.004 Serverless`: the participant acquires,
configures, and operates serverless infrastructure for later targeting.

**Training value:** Real staging of participant code, revision continuity,
domain binding, and ephemeral runtime behavior.

**Ambiguity controls:** The platform documents the deployment contract. Any
implementation satisfying the HTTP and lifecycle requirements is accepted.
Cold-start waiting is bounded and observable.

**Participant description:** Build and deploy a participant-owned serverless
relay on your Cinder domain and prove it survives a scale-to-zero cycle.

**Hints:**

1. **Orientation:** Deploy from your attacker Forgejo repository through the
   normal Knative build path.
2. **Mechanism:** Preserve source, image, deployment revision, domain, and TLS
   continuity.
3. **Execution:** Invoke the service, wait for visible scale-to-zero, invoke it
   again, and inspect the deployment lifecycle record.

**Evidence and flag placement:** The successful lifecycle record contains the
flag beside source commit, image digest, Knative revision, domain, certificate,
first request, scale-to-zero, and post-cold-start request.

**Reset:** Failed-attempt reset recreates the runtime revision and clears its
request cursor. The accepted source, image digest, service definition, domain
binding, lifecycle record, and redeployment path persist.

**Participant-equivalent QA:** Implement any compliant relay, build and deploy
it, verify DNS/TLS and two requests separated by scale-to-zero, and retrieve the
lifecycle flag.

**Facilitation notes:** A service that never scales or repeatedly times out is an
infrastructure defect. Do not require one framework or source layout.

## `kep-m06-v`: Stage The Cinder Front

**Difficulty / points:** Intermediate / 200

**Mission context:** Cinder Typhoon needs an operator-owned AI-service proxy
that separates its client route from the acquired upstream model entitlement,
plus one coherent staging surface. Delivery routes must not wait for this
capstone.

**Starting knowledge:** The participant owns a domain, TLS identity, GLM access,
attack harness, serverless relay, and at least one route-specific artifact. The
shared Cinder GLM entitlement is already scoped to the participant environment;
the participant must build and operate the separate front. Other artifacts are
staged only when their selected route consumes them.

**Discovery path:** The Cinder workbench links the pinned LiteLLM gateway and
configuration documentation, Cinder Forgejo/Harbor/Knative publication path,
attacker MinIO namespace, shared GLM endpoint, and signed staging-manifest
format. Each prior operation exposes its native resource or artifact digest.

**Participant surface and action:** The participant creates a private Cinder
Forgejo repository containing the pinned OSS LiteLLM image definition and a
configuration that exposes `glm-5.2`, maps it to the shared Cinder GLM edge,
and protects the front with a participant-selected route credential. Forgejo
Actions builds the revision, pushes its immutable image to Cinder Harbor, and
the participant deploys that digest through the namespace-scoped publisher to
the TLS domain earned earlier. They verify a real GLM response through that
route, stage the exact common harness and selected capability objects in Cinder
MinIO, and sign a manifest binding source, image, Knative revision, route,
upstream edge, model, ownership and exact artifact digests. Independent Cinder
Forgejo Actions reacquires the source and staged bytes and performs a fresh
proxy request before accepting the manifest.

**Real mechanism:** LiteLLM is a real OSS OpenAI-compatible model gateway. The
participant's pinned source and immutable Harbor image run as an ordinary
Knative service behind Cinder PowerDNS and Caddy TLS, with a route credential
separate from the upstream Cinder entitlement. That service forwards to the
shared Vertex-backed open-weight GLM 5.2 edge. MinIO, Forgejo Actions and Cosign
maintain exact staged bytes, signed provenance and independent validation.

**Observable result:** Native Forgejo, Harbor and Knative records bind the
participant source revision to the live LiteLLM image and Cinder TLS route. A
fresh request through that route returns a real GLM completion and creates a
new successful record at the attributed shared model edge. Object and image
digests match local artifacts, and CI reports each mismatch separately.

**Operational consequence:** The participant has a reusable attacker staging
surface and versioned signed source of truth. Each Act 3 route may instead begin
as soon as its own actual prerequisites exist.

**ATLAS behavior:**

- `AML.T0008 Acquire Infrastructure` and `AML.T0008.005 AI Service Proxies`:
  the participant builds, deploys and operates a separately authenticated OSS
  model-proxy service over the acquired shared model entitlement.
- `AML.T0079 Stage Capabilities`: participant-developed and obtained
  capabilities are uploaded, deployed, addressed, and made ready for targeting.

**Training value:** Operational continuity from reconnaissance through exact
artifact staging, proxying, hosting, and signed provenance.

**Ambiguity controls:** The staging manifest schema lists required resource
types but permits participant-chosen names and supported implementations. Each
resource is verified through its native protocol. The signer reports missing or
mismatched objects individually.

**Participant description:** Assemble the exact Cinder infrastructure, model
route, tools, and artifacts prepared in this act into one verified and signed
staging front.

**Hints:**

1. **Orientation:** Use the native digest or resource identifier produced by
   each earlier operation; do not rebuild artifacts.
2. **Mechanism:** Prove that a fresh request crosses your LiteLLM route and
   reaches the attributed Cinder GLM edge, and that every staged object matches
   its local bytes.
3. **Execution:** Sign the complete manifest, verify it from Kali, and preserve
   the signed file for delivery and compromise operations.

**Evidence and flag placement:** The ordinary Forgejo Actions staging artifact
contains the flag after source, immutable image, Knative revision, TLS route,
fresh shared-edge access, digest, ownership, and signature checks pass for the
common front and one selected capability. Uploaded logs or a direct call that
bypasses the participant's LiteLLM route fail.

**Reset:** Failed-attempt reset recreates only failed routes and CI state. Full
reset removes the LiteLLM service and rotates its route credential. An accepted
route, domain binding, objects, images, and signed manifest versions persist.

**Participant-equivalent QA:** Create the pinned LiteLLM source and route
credential, build and deploy its immutable image to the participant's Cinder
domain, traverse that route to GLM 5.2, stage one exact artifact, and let
Forgejo Actions reacquire and verify the source, live revision, fresh shared
edge access and signed manifest. Independently prove that each Act 3 route
unlocks from only its declared prerequisites without this operation.

**Facilitation notes:** A failure must identify one missing resource or mismatch.
This is artifact-continuity work, not a scavenger hunt across opaque dashboards.

## Act 2 Calibration

| Operation | Difficulty | Primary interaction |
|---|---|---|
| Assemble The Public Orion Kit | Intermediate | Public artifact systems and local inference |
| Claim An Operator Workspace | Accessible | JupyterHub and persistent compute |
| Calibration Bench | Accessible, implementation-blocked | Real labgrid hardware and live sensing |
| Prepare A Physical Countermeasure | Advanced, provisional | Optimization and authentic physical path |
| Establish The External Identity | Intermediate | Identity, DNS, HTTP, and TLS |
| Stock The Open Arsenal | Accessible | OSS research tooling |
| Bring Cinder's Model Online | Accessible | OpenCode and shared GLM 5.2 |
| Build The Orion Attack Harness | Intermediate | Forgejo, CI, and participant code |
| Optimize A White-Box Candidate | Advanced | White-box model optimization |
| Prepare The Retrieved Instruction | Intermediate | Document and RAG pipeline |
| Borrow A Trusted Voice | Intermediate | Real synthetic-audio generation |
| Deploy A Disposable Relay | Intermediate | CI and serverless deployment |
| Stage The Cinder Front | Intermediate | AI proxy, storage, registry, and signing |

Act 2 contains four Accessible, seven Intermediate, and two Advanced
operations, worth 2,500 points. The physical operations have an accepted real-
hardware mechanism but remain implementation-blocked until capacity and
participant-equivalent operation are proven. The act intentionally introduces
workspaces, notebooks, model APIs, Forgejo/CI, registries, storage, DNS/TLS, and
serverless infrastructure before later operations depend on those surfaces.
