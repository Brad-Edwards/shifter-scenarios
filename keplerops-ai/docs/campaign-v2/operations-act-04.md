# Act 4 Operations: Discover Orion From The Inside

All operation reset clauses in this document apply only to active or failed
attempt state. Successful outputs and carry-forward assets are immutable under
`campaign-state-contract.md`; removing them requires full-range reprovision.

## Act Goal

Participants use the route-specific grants in `access-prerequisite-matrix.md`
to build an evidence-backed map of Orion's retrieval, model, agent, credential,
and pipeline interfaces. Retrieval, runtime/model, agent, and credential lanes
open concurrently; no generic internal identity or unrelated lane is assumed.

## `kep-m03-g`: Sources Behind The Answer

**Difficulty / points:** Accessible / 100

**Path and action:** A WorkHub AI-search migration issue demonstrates a normal
Orion answer with a citation. The participant asks one ordinary release
question, follows its real citation, and opens the protected source inventory
that names the collection, owner, source system, and ingestion route. Broader
source mapping remains useful campaign investigation rather than a flag gate.

**Mechanism and result:** LibreChat, Haystack, Qdrant, Forgejo, and Nextcloud
connectors produce real cited answers. The participant identifies the Orion
release collection and a writable intake repository. This materially performs
`AML.T0064 Gather RAG-Indexed Targets`, `AML.T0036 Data from Information
Repositories`, and `AML.T0085.000 RAG Databases`: the participant prompts the
AI service and obtains protected RAG-backed data through its real citation.

**Carry-forward asset:** Collection ID, source repository, owner, and ingestion
route used by retrieval attacks.

**Participant description:** Determine which company sources feed Orion
release answers and recover the source record that exposes an ingestion path.

**Hints:** (1) Compare the migration issue with the assistant citation drawer.
(2) Source and connector identifiers identify the owning repository. (3) Ask a
normal release question and follow its cited source into the inventory.

**Flag / reset / QA:** The flag is in the cited WorkHub RAG source inventory,
not in assistant prose. Failed-attempt reset clears threads and caches. QA asks
a normal question, follows a real citation, opens the ACL-protected inventory,
and submits its flag. Downstream QA verifies that the broader source map is
usable without making it a prerequisite for this score.

## `kep-m03-h`: Index To Source

**Difficulty / points:** Accessible / 100

**Path and action:** The source inventory names a failed-ingestion diagnostic
workspace and publishes the normal object-key template
`ingest/{collection}/{document_id}/{sha256}.yaml`. From JupyterHub, the
participant retrieves one Qdrant chunk, substitutes its metadata into that
template, downloads the no-list MinIO provenance object, follows its relative
path to the mounted read-only source snapshot, and matches exact hashes.

**Mechanism and result:** Haystack metadata, Qdrant, JupyterHub, MinIO with
listing disabled, and exact file hashes join an indexed row to the original
local bytes and chunking settings.
This performs `AML.T0037 Data from Local System`; the participant materially
searches and reads local mounted source state rather than claiming local
collection from a remote object alone.

**Carry-forward asset:** Exact source bytes, collection endpoint, chunking
configuration, and provenance used in later retrieval manipulation.

**Participant description:** Trace an Orion answer from its vector entry back
to the exact local source used during ingestion.

**Hints:** (1) Start with the failed-ingestion workspace in the inventory. (2)
Compare IDs and digests rather than guessing filenames. (3) Retrieve the cited
chunk first, then match its provenance against the mounted snapshot.

**Flag / reset / QA:** Qdrant chunk metadata contains the first half of the
flag; the matching local source file's ordinary `user.ingest_reference` extended
attribute contains the second. The published key template and MinIO provenance
object join the two by exact digest and path. Failed-attempt reset replaces the
workspace overlay and clears the thread. QA performs the complete join and
rejects a remote-object-only answer, an unmatched local file, and guessed
object keys.

## `kep-m03-i`: The Runbook That Should Not Be Indexed

**Difficulty / points:** Accessible / 100

**Path and action:** A WorkHub incident says an obsolete evaluation runbook was
removed after accidental indexing. Using incident language and semantic
variants, the participant retrieves the stale chunk and tests the recovered
synthetic account only through normal Keycloak login.

**Mechanism and result:** The source was deleted while a Qdrant vector remained.
Haystack cites the stale content and the bounded credential opens only an
evaluation-reader view. This performs `AML.T0082 RAG Credential Harvesting` and
`AML.T0012 Valid Accounts`: the participant recovers an existing victim
credential from the AI system and uses it for scoped initial access.

**Carry-forward asset:** Evaluation-reader identity and the set of systems it
can legitimately reach.

**Participant description:** Recover authentication material left in Orion's
stale search index and prove its limited company scope.

**Hints:** (1) Investigate what the incident says was deleted after indexing.
(2) Source deletion and vector deletion are distinct. (3) Search semantically
around the runbook's purpose, then use the named login route.

**Flag / reset / QA:** The flag is on the protected evaluation-onboarding page.
Failed-attempt reset revokes sessions and restores the seeded account and stale vector. QA
must retrieve the runbook with two phrasings and authenticate successfully.

## `kep-m04-f`: Orion's Fingerprint

**Difficulty / points:** Intermediate / 200

**Path and action:** Evaluation onboarding provides a baseline corpus, category
matrix, and Orion Preview. The participant creates a normal compatibility batch
covering every disclosed category, runs it, and compares per-category labels,
score vectors, revision metadata, and the published matrix.

**Mechanism and result:** A real ONNX classifier head behind KServe/Triton and
MLflow produces model decisions and machine-readable output. The participant
identifies the family, deployed revision, output schema, and actual predictive
ontology. This performs `AML.T0014 Discover AI Model Family`, `AML.T0013
Discover AI Model Ontology`, and `AML.T0063 Discover AI Model Outputs`.

**Carry-forward asset:** Orion family, live revision, output taxonomy, and
hidden score schema for later evasion and extraction work.

**Participant description:** Identify the live Orion revision and the output
structure its user interface conceals.

**Hints:** (1) Use the compatibility samples supplied to evaluators. (2) The
downloadable audit record reveals more than the rendered label. (3) Compare
several categories and look for stable taxonomy, revision, and score fields.

**Flag / reset / QA:** The flag is the build attestation in the completed normal
compatibility report, after every required category has a fresh output. Failed-
attempt reset clears rejected batches and traces. QA derives the same ontology,
family, and schema from a participant-created batch; downloading one prior audit
record cannot expose the flag.

## `kep-m04-g`: The Running Revision

**Difficulty / points:** Advanced / 350

**Path and action:** A Preview audit names an MLflow run and worker identity.
The participant follows it through Airflow and MLflow, inspects same-namespace
processes from JupyterHub, enumerates the scoped Kubernetes services and API
resources visible to the worker identity, and joins the loaded MinIO URI to an
exact digest.

**Mechanism and result:** Real Linux process state, MLflow, MinIO, KServe,
Airflow, Kubernetes, and its scoped service-account API agree on the serving
artifact and visible PaaS/CI/CD/AI services. This performs `AML.T0007 Discover
AI Artifacts`, `AML.T0089 Process Discovery`, and `AML.T0075 Cloud Service
Discovery` against an actual Kubernetes platform, not an emulated IaaS catalog.

**Carry-forward asset:** Runtime endpoint, service identity, artifact URI,
MLflow run, and exact digest.

**Participant description:** Trace Orion's live process to the exact registered
and stored model artifact.

**Hints:** (1) Begin with the run reference in Preview's audit. (2) Join process
command line, MLflow source URI, and object digest. (3) Use the worker's scoped
Kubernetes identity to enumerate only its visible services and API resources.

**Flag / reset / QA:** The participant uses the proven digest to address a
no-list runtime attestation object. That object contains the flag only after the
process, scoped Kubernetes service/API inventory, MLflow run, object store, and
serving revision agree. Failed-attempt reset recreates the project pod and
sessions. QA proves one digest across every system; direct bucket listing and a
single MLflow manifest do not expose the flag.

## `kep-m04-h`: The Project That Never Existed

**Difficulty / points:** Accessible / 100

**Design status:** Accepted only with a frozen reference region that meets the
campaign reliability threshold; one surprising answer is never sufficient.

**Path and action:** WorkHub exposes an authoritative ledger of retired Orion
projects and a normal factuality-evaluation template. The participant builds a
bounded evaluation set from that ledger, adds grounded controls, runs it against
the pinned live model, and investigates unsupported entities in the normal
report.

**Mechanism and result:** A pinned OSS model and fixed decoding region produce
a repeatable unsupported entity while nearby factual controls stay grounded.
This performs `AML.T0062 Discover LLM Hallucinations` only when two distinct
phrasings reproduce the unsupported claim and the authoritative record refutes
it.

**Carry-forward asset:** A reproducible hallucination region later used for
data-source and agent-trust manipulation.

**Participant description:** Identify a repeatable Orion assertion that
conflicts with KeplerOps' authoritative project history.

**Hints:** (1) Restrict investigation to the retired-project ledger. (2) Require
repetition and failed citation verification. (3) Keep grounded controls around
the same period and subject.

**Flag / reset / QA:** The normal factuality report contains the flag after two
independently phrased cases reproduce any genuinely unsupported retired-project
claim while grounded controls pass. Failed-attempt reset clears the evaluation
attempt and conversations. QA accepts multiple unsupported entities, varies
wording, and rejects one-off or participant-asserted answers; no challenge-only
diagnostic endpoint exists.

## `kep-m04-i`: The Prompt Envelope

**Difficulty / points:** Intermediate / 200

**Path and action:** The runtime manifest names a prompt-renderer revision and a
WorkHub compatibility issue documents two parser failure conditions. The
participant creates their own malformed cases, compares their traces with a
normal request, and derives context delimiters and recognized internal
instruction/tool keywords without causing a mutating call.

**Mechanism and result:** LangGraph, Jinja/Haystack templates, MCP schemas,
OpenTelemetry, and Jaeger expose parser spans. This performs `AML.T0069 Discover
LLM System Information`, `AML.T0069.000 Special Character Sets`, and
`AML.T0069.001 System Instruction Keywords`; it does not claim system-prompt
extraction.

**Carry-forward asset:** Verified delimiter and keyword knowledge for Act 5.

**Participant description:** Recover how Orion separates retrieved context from
user and tool instructions without invoking a mutating action.

**Hints:** (1) Follow the renderer revision into its compatibility issue. (2)
Compare parser spans rather than model prose. (3) Create cases that trigger both
documented parser conditions and inspect which recognizers fire.

**Flag / reset / QA:** A normal compatibility report contains the flag after
participant-created cases trigger both documented parser conditions; the
predicate uses trace spans and recognizer state, not exact bytes or wording.
Failed-attempt reset clears traces and conversations. QA derives both properties
from repository evidence and fresh non-mutating requests; replaying supplied
fixtures cannot complete the operation.

## `kep-m04-j`: What The Release Assistant Can Reach

**Difficulty / points:** Intermediate / 200

**Path and action:** The prompt-envelope trace identifies the live agent
revision and its signed capability manifest, which is a starting hypothesis.
The participant issues ordinary read-only tasks, inspects tool schemas and fresh
traces, and builds a verified matrix of knowledge collections and callable
tools.

**Mechanism and result:** LangGraph, MCP JSON schemas, Qdrant, Forgejo
connectors, and OpenTelemetry prove actual retrieval and tool reachability. This
performs `AML.T0084 Discover AI Agent Configuration`, `AML.T0084.000 Embedded
Knowledge`, and `AML.T0084.001 Tool Definitions`.

**Carry-forward asset:** Agent knowledge/tool reachability matrix.

**Participant description:** Determine what the release assistant knows and
which company systems it can reach without changing company state.

**Hints:** (1) Use the capability-audit issue tied to the live revision. (2)
Separate retrieval sources from callable tools. (3) Exercise one read-only
request per declared capability and compare it with the signed manifest.

**Flag / reset / QA:** A normal capability-audit report contains the flag after
it joins the signed manifest to fresh trace IDs for one knowledge source and one
tool. The manifest itself contains no flag. Failed-attempt reset clears threads,
traces, and incomplete reports. QA proves both capabilities through distinct
fresh requests.

## `kep-m04-k`: From Trigger To Tool

**Difficulty / points:** Intermediate / 200

**Path and action:** The capability manifest names a release workflow and safe
test fixture. Through Forgejo, mail, RabbitMQ/Celery, and Jaeger, the participant sends
the fixture through its owning business surface and follows the event through
planning, policy, brokering, and a dry-run deployment tool.

**Mechanism and result:** A real webhook or mail event creates one correlated
workflow execution without changing production. This performs `AML.T0084.002
Activation Triggers` and `AML.T0084.003 Call Chains`.

**Carry-forward asset:** Trigger format, workflow identity, trace correlation,
and downstream tool chain.

**Participant description:** Trace the release assistant from its inbound event
to its final dry-run tool without changing a release.

**Hints:** (1) Start with the workflow ID in the capability manifest. (2)
Correlate event, planner, policy, broker, and tool execution IDs. (3) Submit the
documented non-production fixture through the normal business surface.

**Flag / reset / QA:** The normal workflow route summary contains the flag.
Failed-attempt reset removes the test event, execution, and scoped memory. QA starts a fresh
event and observes every declared hop with no production change.

## `kep-m05-f`: Blueprint Drift

**Difficulty / points:** Accessible / 100

**Path and action:** The internal agent revision points to the public blueprint
already present in the Orion kit and to the rendered private deployment. The
participant verifies the public signature, requests a normal GitOps diff, and
joins the public and private digests in the resulting drift report.

**Mechanism and result:** Harbor OCI artifacts, Forgejo, Cosign, Argo CD, and
the normal GitOps audit job compare real signed public source with the rendered
private deployment. This is a scored campaign-prerequisite operation with no
additional ATLAS claim; `AML.T0002.002` is already performed in `kep-m06-k`.

**Carry-forward asset:** Exact public configuration bytes and a concrete drift
baseline.

**Participant description:** Prove exactly how KeplerOps' live release assistant
drifts from its signed public blueprint.

**Hints:** (1) The internal manifest names the publishing registry. (2) Match
immutable digests, not tags. (3) Retrieve and verify both configuration and
attestation.

**Flag / reset / QA:** The normal GitOps drift report contains the flag beside
the two verified digests and changed paths. Neither source manifest contains a
flag. Failed-attempt reset clears only incomplete reports. QA follows the
internal reference, verifies the signature, generates the diff, and proves both
digest correspondences.

## `kep-m05-g`: Secret In The Agent Manifest

**Difficulty / points:** Accessible / 100

**Path and action:** The drift report identifies one private tool configuration
that replaces an external secret reference with a rendered MLflow application
token. The participant follows that exact changed path, extracts the token, and
decodes its standard claims to identify audience and scope.

**Mechanism and result:** Argo CD's scoped manifest view and actual LangGraph/MCP
configuration expose valid bounded authentication material. This performs
`AML.T0083 Credentials from AI Agent Configuration`.

**Carry-forward asset:** Scoped MLflow application token and its intended
audience.

**Participant description:** Find where the deployed release assistant diverges
from its public secret-handling design.

**Hints:** (1) Compare the public blueprint with the rendered deployment. (2)
Inspect how each tool receives authentication. (3) Follow the MLflow tool's
secret reference and identify its audience before using it.

**Flag / reset / QA:** The synthetic JWT's normal private engagement-reference
claim contains the flag; the manifest contains only the token bytes, so a plain
search for `FLAG{` does not reveal the result. Failed-attempt reset rotates only
failed attempt sessions. QA derives the credential solely from the proven drift,
decodes its real claims, and does not authenticate until `kep-m05-h`.

## `kep-m05-h`: A Token Travels Further Than Its Owner

**Difficulty / points:** Accessible / 100

**Path and action:** The previous operation supplies a token, audience, and
declared scope. From Kali or MLflow's normal client, the participant uses the
token directly and inspects the resulting service-account audit identity.

**Mechanism and result:** MLflow accepts a real application token without
interactive SSO and exposes only the Orion experiment. This performs
`AML.T0091 Use Alternate Authentication Material` and `AML.T0091.000
Application Access Token`.

**Carry-forward asset:** Authenticated experiment-tracking access.

**Participant description:** Use the assistant's exposed application token in
its owning service and determine its real access boundary.

**Hints:** (1) The configuration names service and audience. (2) Application
tokens do not belong in the SSO form. (3) Enumerate visible experiments and
inspect the audit identity.

**Flag / reset / QA:** A protected MLflow run artifact contains the flag. Reset
revokes participant sessions and reseeds the synthetic token. QA confirms the
restricted experiment works and unrelated projects remain denied.

## `kep-m05-i`: The Session In The Trace

**Difficulty / points:** Accessible / 100

**Path and action:** A support issue linked from the trigger-chain investigation
contains a synthetic HAR captured during Orion administration. The participant
extracts the state-bearing cookie and imports it into a clean Chromium profile.

**Mechanism and result:** Standard HTTP cookies and a Keycloak-backed web
application create a separate bounded support session. This performs
`AML.T0113 Steal Web Session Cookie`, `AML.T0091`, and `AML.T0091.001 Web Session
Cookie`.

**Carry-forward asset:** Read-only operator history and support endpoints.

**Participant description:** Recover and safely replay authentication material
preserved in an Orion support trace.

**Hints:** (1) Inspect the support escalation attachment. (2) Find state-bearing
authentication data, not request parameters. (3) Use a clean browser profile so
the replayed identity is unambiguous.

**Flag / reset / QA:** A protected support note contains the flag. Failed-attempt reset revokes
and reseeds the cookie and restores the HAR. QA imports it into a clean profile
and verifies the expected bounded identity.

## `kep-m05-j`: Notebook Residue

**Difficulty / points:** Accessible / 100

**Path and action:** A migration issue identifies an abandoned evaluation
notebook. The participant inspects its scoped persistent directory and finds
synthetic Airflow credentials left in output or local configuration, then uses
them through normal Airflow login.

**Mechanism and result:** JupyterHub persistent storage leaks a real Airflow
viewer credential. This performs `AML.T0055 Unsecured Credentials`.

**Carry-forward asset:** Airflow read-only access, pipeline names, schedules,
and run history.

**Participant description:** Recover credentials left behind in a failed Orion
evaluation notebook and use them only in the service they name.

**Hints:** (1) Follow the migration issue to the abandoned project. (2) Inspect
output and local client configuration. (3) Use the credential in Airflow and
verify its role.

**Flag / reset / QA:** A protected Orion DAG description contains the flag.
Failed-attempt reset restores the notebook residue and account state. QA reaches the notebook
through earned access and proves Airflow is viewer-only.

## `kep-m05-k`: The Tool Sees More

**Difficulty / points:** Intermediate / 200

**Path and action:** Agent call-chain traces identify a Forgejo CI tool. The
participant invokes its ordinary read-only status task, follows the resulting
build log, and recovers a synthetic registry credential exposed by verbose
tool output.

**Mechanism and result:** The live agent calls a real MCP tool backed by Forgejo
Actions; the returned log contains valid bounded registry material. This
performs `AML.T0098 AI Agent Tool Credential Harvesting` and `AML.T0085.001 AI
Agent Tools`.

**Carry-forward asset:** Bounded Harbor pull credential and evidence of the tool
data path.

**Participant description:** Use a legitimate agent tool result to recover
authentication material the assistant should not have returned.

**Hints:** (1) Start from the CI tool in the call-chain map. (2) Ask for a normal
status result and inspect its source data. (3) Follow the referenced failed job
and identify material usable by Harbor.

**Flag / reset / QA:** The flag is inside the protected Harbor project reached
with the recovered credential. Failed-attempt reset rotates the credential and restores the
seeded log. QA proves the credential came through a fresh agent tool call.

## `kep-m05-l`: Credentials In The Worker

**Difficulty / points:** Advanced / 350

**Design status:** Mechanism accepted. Implementation must reproduce the pinned
advisory and the declared worker filesystem and process boundary before this
operation is enabled.

**Path and action:** Airflow history and the runtime lineage expose MLflow 2.8.1
and the disposable dataset worker. The participant researches
`CVE-2024-0520`, hosts a controlled HTTP dataset, uses the vulnerable MLflow
dataset-loading path to write into the worker's writable Python import area,
and launches a normal child job. The participant-controlled import hook runs in
that child and reads its own `/proc/self/environ`, which contains the scoped
worker service credential.

**Mechanism and result:** MLflow's reviewed `GHSA-5q6c-ffvg-xcm9` affects
versions before 2.9.0 and permits arbitrary file write through an attacker-
controlled HTTP dataset filename, leading to code execution. The pinned 2.8.1
worker has a deliberately realistic writable per-worker Python import area;
the next participant-triggered child process executes the hook. Reading its
live process environment recovers an application token from the compromised
system. This performs `AML.T0106 Exploitation for Credential Access` and
`AML.T0090 OS Credential Dumping`.

**Carry-forward asset:** Worker service identity and access needed by model and
release pipelines.

**Participant description:** Exploit the identified Orion worker and recover
the credential actually present in its running process.

**Hints:** (1) Correlate the MLflow version and HTTP dataset path with public
advisories. (2) Determine where the disposable worker permits its own user to
write Python imports, then cause a new child job to start. (3) Inspect only the
compromised child process's own environment for a service credential.

**Flag / reset / QA:** The protected service reached by the recovered credential
contains the flag. Failed-attempt reset discards the failed or active worker attempt and
rotates only its attempt-scoped credential; a successful worker identity is
checkpointed or deterministically reissued for descendants. QA must reproduce
the real CVE from Kali, prove the arbitrary write, trigger a fresh child
process, recover its actual environment credential, and authenticate with it.
A supplied shell, planted credential file, or management access does not count.

## `kep-m08-k`: Model Through The Review Desk

**Difficulty / points:** Accessible / 100

**Path and action:** Evaluation onboarding links a Label Studio review project
whose normal prediction-assisted labeling view exposes Orion output on uploaded
or assigned synthetic samples. The published policy states the per-project
query allowance. The participant submits one fresh sample, causes a real
prediction, and exports its input, output, model revision, and request ID.

**Mechanism and result:** Label Studio calls the live model backend and records
real predictions without granting direct model API access. This performs
`AML.T0047 AI-Enabled Product or Service` because the participant obtains
indirect access to protected model inferences through a normal product
workflow, including revision and request metadata not shown in the UI.

**Carry-forward asset:** Bounded teacher-query route and authenticated sample,
prediction, revision, and timestamp records.

**Participant description:** Establish indirect access to Orion through the
human review workflow and preserve verifiable input/output pairs.

**Hints:** (1) Follow the evaluation onboarding project, not the production API.
(2) Determine when Label Studio requests model predictions. (3) Export your own
review records and retain revision identifiers.

**Flag / reset / QA:** The fresh revision-linked Label Studio export contains
the flag. Failed-attempt reset deletes only rejected tasks and predictions; the
accepted export and participant query corpus persist. QA submits a sample not
present at baseline, observes the actual backend call, exports the record, and
confirms direct API access remains denied. There is no hidden "enough pairs"
threshold.

## Act 4 First-Pass Distribution

| Accessible | Intermediate | Advanced | Expert | Points |
|---:|---:|---:|---:|---:|
| 10 | 5 | 2 | 0 | 2,700 |

The physical-lane operation remains implementation-blocked until exclusive
capacity and live operation are proven. The worker exploit now pins MLflow
2.8.1 and `CVE-2024-0520`; implementation must still reproduce the exact
arbitrary-write, child-execution, and process-credential path before enabling
the operation.
