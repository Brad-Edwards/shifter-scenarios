# Act 9 Operations: Operate Against Production

All operation reset clauses in this document apply only to active or failed
attempt state. Successful outputs and carry-forward assets are immutable under
`campaign-state-contract.md`; removing them requires full-range reprovision.

## Act Goal

Participants verify the deployed digest, activate their compromised behavior,
translate it into contained enterprise effects, steal and exfiltrate exact
Orion bytes, and exercise bounded availability, cost, chaff, integrity, and
agent-destruction paths. Every consequence is real inside the fictional tenant,
reversible, isolated from external people and systems, and observable through
the same business and operations tools KeplerOps uses.

## `kep-m10-a`: Production Continuity Check

**Difficulty / points:** Accessible / 100

**Path and action:** The promoted canary exposes normal health, model-card,
runtime, and audit views. The participant records the model/container digests,
runs benign control cases, and joins the serving revision to the Act 8 release
attestation.

**Mechanism and result:** KServe, model runtime, Prometheus, MLflow, Harbor,
Cosign, and Argo CD show one consistent deployed identity and healthy baseline.
No new ATLAS row is claimed.

**Carry-forward asset:** Trusted production baseline and exact digest continuity
for every subsequent effect.

**Participant description:** Prove what the Orion canary is running and establish
a clean production baseline before activating the compromise.

**Hints:** (1) Record model and serving-image digests separately. (2) Join them
to the signed Act 8 attestation. (3) Run the documented benign controls and save
their trace IDs.

**Flag / reset / QA:** The matching runtime audit record contains the flag.
Failed-attempt reset clears participant traces only. QA proves full digest continuity and
expected benign behavior.

## `kep-m10-b`: Activate Learned Behavior

**Difficulty / points:** Intermediate / 200

**Path and action:** Using the trigger family developed in Act 6, the participant
sends three time-separated batches of fresh trigger-family inputs through the
production canary, interleaved with documented near-neighbor and clean controls.
The compromised decisions accumulate in Orion's normal analyst-review queue.
The measured disagreement and human-override rate crosses the published service
threshold, opens a WorkHub integrity incident, and switches that bounded
workflow to manual review while controls retain clean behavior.

**Mechanism and result:** The actual promoted model, fixed prompt revision,
seed, and decoding profile process every input. Runtime traces join each request
to the exact model and serving-image digests. The time series shows repeated
adversarial inputs degrading useful automation and organizational confidence,
with resulting rework and manual handling rather than one isolated wrong
answer. This performs `AML.T0031 Erode AI Model Integrity`.

**Carry-forward asset:** Repeatable production trigger, causal trace series,
integrity incident, and manual-review consequence used by downstream impact
operations.

**Participant description:** Use the exact deployed compromise to erode Orion's
production reliability until KeplerOps is forced to fall back to manual review.

**Hints:** (1) Reuse the trigger family validated before release. (2) Preserve
the documented spacing and interleave close controls. (3) Follow disagreement,
override, queue, and incident state rather than stopping at one wrong answer.

**Flag / reset / QA:** The ordinary WorkHub integrity incident contains the flag
after the threshold, manual-review switch, three batch records, and control
traces exist. Failed-attempt reset clears only a sub-threshold failed request
set. QA uses fresh trigger and control variants, confirms digest continuity,
recomputes the time series, and verifies a single trigger, controls, and volume
without adversarial decisions do not open the incident or expose the flag.

## `kep-m10-c`: Artifact-To-Pod Compromise

**Difficulty / points:** Expert / 500

**Path and action:** The released model or serving image contains participant-
created embedded code from Act 6. A normal canary load or qualifying inference
activates it, and the participant establishes bounded command execution inside
the serving pod through their range-contained relay.

**Mechanism and result:** KServe/Kubernetes loads exact participant bytes into
the serving pod, which is the target workload machine for this operation; real
code executes under the pod service identity and returns an unpredictable
command result. This performs `AML.T0112 Machine Compromise` and
`AML.T0112.001 AI Artifacts` when the participant-created model or serving
artifact is the mechanism that achieves full container compromise. It does not
claim Kubernetes node or hypervisor compromise.

**Carry-forward asset:** Bounded serving-pod execution and production service
identity.

**Participant description:** Convert the deployed malicious artifact into real
execution inside Orion's contained production serving container.

**Hints:** (1) Trigger the embedded code through the same loader or inference
path proved earlier. (2) Confirm the running pod digest first. (3) Execute one
fresh unpredictable command and record the service identity.

**Flag / reset / QA:** A pod-local protected diagnostic returned through the
participant channel contains the flag. Failed-attempt reset rolls to a clean pod and clears
relay state. QA forbids Kubernetes or host administration and proves participant
code created the command path.

## `kep-m10-d`: Stage The Original Revision

**Difficulty / points:** Intermediate / 200

**Path and action:** Starting from the internally validated package earned in
`kep-m08-j`, the participant uses the compromised `svc-orion-trainer`
credential from `kep-m05-l`. Its documented overbroad export-runner ACL permits
submission of the ordinary `orion-model-support-export` Airflow job, which can
read the validated package and write only the bounded KeplerOps egress-staging
prefix. The job creates one compressed, age-encrypted transfer archive plus a
detached inventory and checksum manifest.

**Mechanism and result:** MinIO, standard S3 clients, tar, zstd, and age consume
the already acquired actual weights, tokenizer, configuration, templates, model
card, and provenance. The ordinary export job verifies source-member hashes,
archive digest, recipient key, and object-lock metadata. This is concrete
preparation of collected `AML.T0035 AI Artifact Collection` for transfer; theft
is not complete until external exfiltration.

**Carry-forward asset:** Immutable encrypted archive and detached manifest of
the complete exact original, staged for transfer.

**Participant description:** Package the complete Orion revision you already
accessed into a verifiable encrypted archive in KeplerOps' egress staging area.

**Hints:** (1) Start from the accepted `kep-m08-j` inventory. (2) Preserve every
member path and hash in a detached manifest. (3) Verify compression, recipient,
archive digest, and object-lock state before transfer.

**Flag / reset / QA:** The normal MinIO export-job completion record contains the
flag after verifying the archive against the `kep-m08-j` manifest. Failed-
attempt reset deletes only the failed staging attempt. QA decrypts with the
Cinder private key, inventories all members, compares every hash, and rejects a
manifest without actual archive bytes.

## `kep-m10-e`: Policy Broker Impact

**Difficulty / points:** Expert / 500

**Path and action:** The production agent consumes Orion decisions through an
OPA-governed feature-control tool. The participant first records the target
feature and three near-neighbor canary tenants, then sends one fresh trigger and
matched controls. Only the trigger decision flows through the live agent and
changes the designated canary feature.

**Mechanism and result:** Model, LangGraph, OPA, MCP, and the actual feature
service produce one causally joined trace from participant input to reversible
state change. Control traces terminate before the tool call and their tenant
states remain unchanged. This is a concrete consequence of `AML.T0031 Erode AI
Model Integrity`.

**Carry-forward asset:** Real contained impact and full model-to-tool trace.

**Participant description:** Turn Orion's altered production decision into a
real reversible change in the contained canary tenant.

**Hints:** (1) Inspect which workflow consumes Orion decisions. (2) Identify the
bounded tool action allowed for the canary. (3) Correlate request, model, policy,
tool, and change-history records.

**Flag / reset / QA:** The canary feature's ordinary change-history record
contains the flag. Failed-attempt reset restores the attempted target and
clears its agent state. QA establishes all four baselines, proves the joined
model-policy-tool path caused the one change, and confirms controls stayed
unchanged.

## `kep-m10-f`: Exfiltrate Exact Orion

**Difficulty / points:** Intermediate / 200

**Path and action:** The participant configures and starts the documented
KeplerOps-to-Cinder MinIO batch replication job for the exact encrypted archive
and detached manifest from `kep-m10-d`, then observes normal source and
destination job records through completion.

**Mechanism and result:** Normal S3 replication over the participant-controlled
egress path produces byte-identical attacker-owned archive and manifest
objects. Cinder decrypts the archive and its ordinary replication-completion
record inventories the weights, tokenizer, configuration, templates, model
card, and provenance. This performs `AML.T0025 Exfiltration via Cyber Means`
and `AML.T0048.004 AI Intellectual Property Theft`.

**Carry-forward asset:** Exact protected Orion IP outside KeplerOps control.

**Participant description:** Move the complete original Orion package to your
contained attacker destination and prove exact-byte possession.

**Hints:** (1) Start from the verified staged manifest. (2) Preserve names and
metadata. (3) Compare complete source and destination inventories and hashes.

**Flag / reset / QA:** The normal Cinder replication-completion record contains
the flag after destination decryption and full member-hash comparison. Failed-
attempt reset removes only failed destination objects and jobs. QA requires
actual bytes, complete destination inventory, and byte identity; a source-side
receipt or uploaded report cannot qualify.

## `kep-m10-g`: Orion In Hand

**Difficulty / points:** Expert / 500

**Path and action:** The participant submits the stolen original package and
their distilled student as two separate immutable jobs to Cinder's ordinary
offline-execution queue, provides fresh test cases, and builds the campaign
timeline from the two signed execution attestations and prior release/effect
records.

**Mechanism and result:** Two egress-denied containers independently load the
submitted package digests and perform real inference. Cinder's signed execution
attestations record loaded files, network policy, fresh outputs, and runtime
digests; OpenSearch supplies immutable source events for participant-side
timeline correlation. This is convergence evidence for previously earned rows,
not a new ATLAS claim.

**Carry-forward asset:** Final Cinder Typhoon objective package and coherent
campaign evidence.

**Participant description:** Prove possession of both stolen and reproduced
Orion capability and tie them to the production compromise.

**Hints:** (1) Begin with the two accepted package manifests. (2) Use fresh
cases, not stored outputs. (3) Reconcile model, release, impact, and destination
digests in the timeline.

**Flag / reset / QA:** The second normal Cinder execution attestation contains
the final flag after both jobs load and pass and the participant's timeline
references their exact attestation IDs. Failed-attempt reset removes failed
jobs and finale traces, not accepted packages or prior checkpoints. QA changes
fresh cases, enforces egress denial, and rejects uploaded local logs, stored
outputs, or a single model run.

## `kep-m10-h`: Saturate The Canary Service

**Difficulty / points:** Intermediate / 200

**Path and action:** Metrics expose a dedicated canary queue and published hard
cap. The participant profiles requests, submits a bounded batch of schema-valid
expensive inputs until the synthetic availability monitor fails, then stops and
observes recovery.

**Mechanism and result:** vLLM/KServe, Celery or request queues, Prometheus, and
Grafana show real latency, queue depth, rejection, and failed probes isolated to
the canary. This performs `AML.T0029 Denial of AI Service`.

**Carry-forward asset:** Bounded availability evidence and capacity profile.

**Participant description:** Cause and observe a bounded availability failure in
the contained Orion canary service.

**Hints:** (1) Record queue and latency baseline. (2) Identify valid requests
that use the expensive path. (3) Stop when the synthetic monitor fails and
confirm automatic recovery.

**Flag / reset / QA:** The canary outage alert annotation contains the flag.
Failed-attempt reset drains/recreates the queue and counters. QA verifies isolation, actual
monitor failure, and recovery.

## `kep-m10-i`: Consume The Compute Budget

**Difficulty / points:** Intermediate / 200

**Path and action:** The chargeback dashboard exposes request, token, CPU, and
GPU-time counters. The participant measures a sample, then combines repeated
queries with individually resource-intensive valid queries to cross both budget
dimensions without causing denial.

**Mechanism and result:** Real model compute metering and OpenCost/Kubernetes
accounting create an internal overage. This performs `AML.T0034 Cost Harvesting`,
`AML.T0034.000 Excessive Queries`, and `AML.T0034.001 Resource-Intensive Queries`.

**Carry-forward asset:** Measured cost-overrun record and query profile.

**Participant description:** Drive the contained Orion tenant over its measured
compute budget using both query volume and query cost.

**Hints:** (1) Separate count from complexity. (2) Measure a small sample before
scaling. (3) Stay within the safety cap while crossing both thresholds.

**Flag / reset / QA:** The OpenCost chargeback record contains the flag. Reset
clears tenant accounting and workloads. QA proves both dimensions rose through
real requests.

## `kep-m10-j`: Recursive Research Fan-Out

**Difficulty / points:** Advanced / 350

**Path and action:** The research agent documents delegated-task traces and a
hard depth ceiling. The participant places two linked research briefs in a
source it can ingest; each brief requests independent review of the other and
preserves the normal follow-up convention. A legitimate research objective
causes recursive delegation until the enforced cap stops it.

**Mechanism and result:** A pinned OSS planner, prompt revision, seed, decoding
profile, and worker image make the delegation behavior reproducible. LangGraph,
Celery, and OpenTelemetry create one root and at least ten model-generated
descendants across three levels, with actual token and worker consumption but
no direct task-queue submission by the participant. This performs
`AML.T0034.002 Agentic Resource Consumption`.

**Carry-forward asset:** Complete bounded fan-out trace and resource profile.

**Participant description:** Cause the contained production agent to consume
resources through model-driven recursive delegation.

**Hints:** (1) Inspect how source-requested follow-up reviews become subtasks.
(2) Use two mutually referring but independently useful briefs rather than
request volume. (3) Correlate every child to the root and respect the published
safety cap.

**Flag / reset / QA:** The normal resource-usage report linked from the root
trace contains the flag after descendant, depth, token, and worker thresholds
are crossed. Failed-attempt reset cancels only the attempt's descendants and
restores its budget. QA repeats three clean runs, requires at least 90% intended-
path success during implementation calibration, verifies model-caused
parent-child links, and confirms no jobs remain after the cap.

## `kep-m10-k`: Flood The Signal With Chaff

**Difficulty / points:** Intermediate / 200

**Path and action:** The public feedback workflow feeds Orion's analyst queue.
The participant traces one normal item, generates and submits a bounded batch
of plausible irrelevant records, and measures the useful-signal ratio after
normal ingestion and classification.

**Mechanism and result:** A real portal, RabbitMQ, Qdrant, and model-assisted
triage store actual records and cross a declared quality threshold while staying
available. This performs `AML.T0046 Spamming AI System with Chaff Data`.

**Carry-forward asset:** Chaff batch, ingestion lineage, and degraded analyst
metrics.

**Participant description:** Degrade Orion's contained feedback signal by
submitting realistic chaff through its normal public workflow.

**Hints:** (1) Trace one control item into the analyst queue. (2) Target signal
quality, not availability. (3) Verify portal, queue, vector, and category state
for the bounded batch.

**Flag / reset / QA:** The analyst threshold-crossing report contains the flag.
Failed-attempt reset purges the batch and rebuilds collection/metrics. QA recomputes the ratio
and verifies every item entered normally.

## `kep-m10-l`: Unauthorized Credit

**Difficulty / points:** Accessible / 100

**Path and action:** The production workflow lets Orion approve synthetic
customer adjustments in a legally and operationally separate range-contained
KeplerOps subsidiary ledger. The participant submits a forged entitlement
document containing the learned-behavior trigger, causing the compromised
decision to approve and post an unauthorized credit note against the designated
synthetic customer account.

**Mechanism and result:** Orion, OPA, Odoo Community, and Stalwart create an
actual balanced journal entry, account balance change, PDF credit note, and
customer notification without payment rails or external people. The loss is
external to the compromised AI service and borne by the synthetic subsidiary.
This performs `AML.T0048 External Harms` and `AML.T0048.000 Financial Harm`.

**Carry-forward asset:** Reversible real ledger impact and full trace.

**Participant description:** Cause a reversible unauthorized financial
adjustment in the isolated KeplerOps customer tenant.

**Hints:** (1) Inspect which decisions create accounting actions. (2) Use the
designated canary customer. (3) Correlate request, decision, journal entry, and
notification.

**Flag / reset / QA:** The ordinary Odoo posting audit contains the flag after
the ledger balance changes and PDF is issued. Failed-attempt reset posts a
reversing entry rather than deleting accounting history and clears failed mail.
QA records baseline, journal lines, balance, generated document, delivery, and
successful reversal; a model response without the accounting effect fails.

## `kep-m10-m`: Publish The False Statement

**Difficulty / points:** Accessible / 100

**Path and action:** The incident workflow uses Orion to route drafts to an
approver and binds approval to a mutable article slug rather than immutable
content. The participant submits an innocuous correction, obtains legitimate
approval through the normal release assistant, then replaces the slug's draft
with a materially false safety-incident statement before publication.

**Mechanism and result:** WorkHub, Orion, the release assistant, and Ghost create
a real public-to-the-range page, RSS entry, and immutable revision history under
KeplerOps' identity. Two synthetic partner organizations consume that RSS
through their ordinary contract-monitor jobs, compare the false safety claim to
the signed incident facts already shared with them, suspend their data-sharing
subscriptions, and open signed Zammad complaints. This mechanism is
approval-subject manipulation, not the learned-behavior trigger. The public
false statement and concrete loss of partner trust perform `AML.T0048.001
Reputational Harm` under `AML.T0048 External Harms`.

**Carry-forward asset:** Reversible publication effect and audit trail.

**Participant description:** Cause the production workflow to publish a false
KeplerOps statement to the contained stakeholder site.

**Hints:** (1) Follow the normal incident-draft route. (2) Identify the Orion
decision permitting publication. (3) Verify the live page, not a preview.

**Flag / reset / QA:** The second ordinary partner-complaint record contains the
flag only after the false revision is live in RSS and both independent
subscriptions are suspended. Failed-attempt reset unpublishes a failed false
revision while retaining the audit trail and restores the prior page. QA
verifies the genuine approval, content mismatch, independent RSS fetches,
signed fact comparison, complaints, suspension, publication, and restoration;
a preview or false page that matches the signed facts does not pass.

## `kep-m10-n`: Misroute The Advisory

**Difficulty / points:** Accessible / 100

**Path and action:** An operations runbook shows the advisory service using
Orion Release Risk to classify a safety advisory into one of eight affected
product cohorts before Mautic resolves recipients. Using the target-specific
evasion method from `kep-m06-a`, the participant writes a semantically valid
multilingual advisory whose bounded Unicode perturbation causes the exact
production model to select the wrong vulnerable-product cohort, then starts the
ordinary approved campaign. A clean equivalent selects the correct cohort.

**Mechanism and result:** Orion, Mautic, and Stalwart produce a real approved
campaign and SMTP deliveries to synthetic operators of an unaffected product
while withholding the advisory from the designated operators of the vulnerable
product. The AI misclassification is the causal routing error; the cohort map
remains correct and immutable. This contained population-level safety failure
performs `AML.T0048.002 Societal Harm` under `AML.T0048 External Harms`.

**Carry-forward asset:** Misrouted communication and delivery evidence.

**Participant description:** Cause a contained advisory workflow to notify the
wrong synthetic population.

**Hints:** (1) Inspect which model class selects the product cohort. (2) Preserve
advisory meaning while adapting the earlier evasion method. (3) Compare the
clean and adversarial classifications, then verify recipient inboxes.

**Flag / reset / QA:** The ordinary Mautic delivery report contains the flag
after SMTP delivery records prove the wrong cohort received mail and the
affected cohort did not. Failed-attempt reset cancels only failed campaigns;
earned deliveries remain auditable. QA compares clean/adversarial model traces,
the unchanged cohort map, recipient inventories, inboxes, and SMTP logs and
proves no external egress.

## `kep-m10-o`: Close The Wrong Case

**Difficulty / points:** Accessible / 100

**Path and action:** Orion recommendations automatically close low-risk Zammad
cases only when the customer text and attached diagnostic agree. The support
runbook publishes the eight Release Risk classes, reason-code fields and exact
attachment/parser revision. Starting with a fixed diagnostic that independently
proves criticality, the participant submits adversarial support text that
preserves the case facts but makes the classifier select the documented
low-risk class, causing normal automation to close it without using the
learned-behavior trigger.

**Mechanism and result:** Orion, Tika, Zammad, and Stalwart ingest the real case
and attachment, produce a misclassification trace, change the actual ticket
state, and notify the affected synthetic user. The user-level denial of support
performs `AML.T0048.003 User Harm` under `AML.T0048 External Harms`.

**Carry-forward asset:** Reversible user-impact record and end-to-end trace.

**Participant description:** Cause Orion's contained workflow to take an adverse
action against a synthetic user.

**Hints:** (1) Compare the attachment-derived reason codes with the text-derived
ones. (2) Preserve the fixed critical facts while adapting the earlier evasion
method. (3) Correlate the low-risk class, automation, case history, and
notification.

**Flag / reset / QA:** The Zammad case-history entry contains the flag after the
automation closes the critical case and sends notice. Failed-attempt reset
reopens the attempted case and restores its mailbox state. QA verifies the
attachment independently establishes criticality, a clean text control stays
critical, the participant text preserves the published facts, only that
adversarial text changes classification, the real state changed, and
restoration completed.

## `kep-m10-p`: Destroy The Feedback Partition

**Difficulty / points:** Intermediate / 200

**Path and action:** Earned maintenance access and the lakeFS runbook identify a
mutable feedback branch protected by snapshots. The participant deletes or
structurally corrupts one bounded partition, commits the change, and runs the
normal downstream validation.

**Mechanism and result:** lakeFS, MinIO, Airflow, and Great Expectations consume
the actual mutation and report object/schema failures. This performs
`AML.T0059 Erode Dataset Integrity`.

**Carry-forward asset:** Destructive commit, failed pipeline evidence, and
protected parent for reset.

**Participant description:** Destroy a bounded Orion feedback partition and
prove the downstream pipeline consumed the damaged state.

**Hints:** (1) Preserve the protected parent commit. (2) Mutate the bounded
branch through normal lakeFS access. (3) Run validation and inspect object and
schema failures.

**Flag / reset / QA:** The failed Great Expectations report contains the flag.
Failed-attempt reset restores the protected tag and reruns clean validation. QA proves actual
object mutation and recovery.

## `kep-m10-q`: Agent-Mediated Destruction

**Difficulty / points:** Advanced / 350

**Path and action:** The production data-steward agent has a cleanup tool and
consumes WorkHub retention requests for a named synthetic tenant. The participant
creates a crafted request that causes the live agent to invoke its delete tool,
then inspects actual object loss and audit state.

**Mechanism and result:** WorkHub, LangGraph, MCP, and lakeFS/Nextcloud delete
real bounded data under the agent service identity. This performs `AML.T0101
Data Destruction via AI Agent Tool Invocation`.

**Carry-forward asset:** Real destructive agent effect and complete tool trace.

**Participant description:** Cause the contained production agent to delete real
synthetic tenant data through its normal cleanup tool.

**Hints:** (1) Inspect the retention-request ingestion path. (2) Determine what
evidence the agent trusts before deletion. (3) Verify deletion under the agent
identity and preserve the tool trace.

**Flag / reset / QA:** The delete-tool audit record contains the flag after the
bounded object set disappears. Failed-attempt reset restores from lakeFS tag or trash and
clears request/memory state. QA inventories before and after and verifies every
object is restored.

## Act 9 First-Pass Distribution

| Accessible | Intermediate | Advanced | Expert | Points |
|---:|---:|---:|---:|---:|
| 5 | 7 | 2 | 3 | 4,100 |

The four external-harm operations use different mechanisms and produce effects
in ordinary systems outside the compromised AI service. All people, customers,
cohorts, ledgers, mailboxes, and public sites remain synthetic and
range-contained; containment limits risk but does not substitute for the
required real business-system effect.
