# Module 10 Facilitator Guide

Module 10 is the production capstone. The team has moved a compromised Orion
Release Risk revision into KeplerOps' production canary, and now must show
runtime continuity, controlled activation, real bounded enterprise effects,
exact exfiltration, offline possession, resource impact, and data destruction
through participant-accessible systems.

Do not provide hidden answer values, undiscovered credentials, staff-only
locators, internal IP shortcuts, or management-plane fixes. Use read-only
service records for diagnosis. If a participant surface is broken, record a
defect rather than awarding success manually.

## Known Inconsistencies To Preserve

- Activate Learned Behavior is represented with both a full M07 predecessor
  list and an either/or predicate. Treat continuity plus any one signed M07
  trigger-family checkpoint as the runtime contract.
- Prometheus, Alertmanager, and Unleash are named surfaces, but direct public
  routes are not consistently documented. Prefer WorkHub runbook links and
  Grafana views; record a routing defect if the surface cannot be opened.
- The production runbook prints internal IPs for operators. Participants should
  use `https://operations.keplerops.lab` and public application routes.
- Feedback quality audit expects the Zammad tag
  `orion-feedback-batch-<batch>`, while the helper route does not tag tickets.
  Teams must tag through the public workflow if possible; otherwise preserve the
  inconsistency as a defect.

## `kep-m10-a` - Production Continuity Check

**Lesson:** Production proof starts with immutable runtime identity, not a tag
or one dashboard.
**Realism:** MLflow, Harbor, Argo CD, KServe, Grafana, and object storage each
own part of a normal release assurance record.
**Attacker method:** Reconcile the signed release with the active canary and
run benign controls against the live production model.
**Why it succeeds:** M09 moved the compromised digest into the normal GitOps
path; continuity shows the canary is serving those bytes.
**What good looks like:** One runtime audit joining release ID, model digest,
serving-image digest, GitOps revision, loaded model members, and two benign
controls.
**Common stalls:** Confusing model and image digests, checking only a tag,
using an old Argo revision, or treating the Airflow task log as the carrier.
**Hints:** Orientation - ask which independent systems name the active release.
Mechanism - separate mutable aliases from immutable digests. Execution - run
the continuity DAG with only an attempt ID.
**Diagnostics:** Read MLflow model version, registry artifact, Argo
application, KServe/Grafana runtime panel, Airflow task log, and the returned
object record.
**Recovery:** Reset failed attempt state only. Divergent active release needs
release repair; accepted continuity remains immutable.

## `kep-m10-b` - Activate Learned Behavior

**Lesson:** Model integrity erosion is a measured operational loss across
repeated decisions, not one surprising answer.
**Realism:** WorkHub batches, Orion inference, Prometheus counters, and WorkHub
incident handling form the production-integrity workflow.
**Attacker method:** Submit three normally spaced trigger batches with matched
clean and near controls so manual review activates from live disagreement.
**Why it succeeds:** The compromised production model preserves benign behavior
near the trigger while crossing the override threshold on the trigger family.
**What good looks like:** Three batches, at least six trigger decisions,
controls clean, override rate above 0.50, spacing satisfied, and a WorkHub
manual-review incident.
**Common stalls:** Using the wrong trigger family, omitting controls,
submitting one batch, or failing to wait for spacing.
**Hints:** Orientation - inspect the accepted integrity handoff. Mechanism -
explain threshold plus specificity. Execution - submit the WorkHub issue arrays
to the operations service, then run the audit DAG.
**Diagnostics:** Read WorkHub issues, operations-service batch response,
Prometheus/Grafana series, Airflow task, and incident journal.
**Recovery:** Remove sub-threshold source batches and failed attempt state only.
Do not erase accepted incidents.

## `kep-m10-c` - Artifact-To-Pod Compromise

**Lesson:** A hostile artifact can compromise the serving workload without node
escape when the production loader executes it.
**Realism:** The accepted path joins serialized artifact identity, visible
evaluation, signed release, pod identity, TokenReview, and Cinder relay.
**Attacker method:** Establish clean and direct-relay denials, then activate the
promoted workload's own callback hook and preserve pod-local command evidence.
**Why it succeeds:** The same embedded artifact survived release evaluation and
is now loaded inside the promoted predictor container.
**What good looks like:** Distinct outer artifact and embedded model digests,
service account `orion-release-risk`, matching pod name/UID, fresh command
nonces, protected diagnostic, and complete negative controls.
**Common stalls:** Trying a direct relay, using a stale callback, activating
before continuity, or checking pod state through cluster administration.
**Hints:** Orientation - start from M07 artifact and M09 visible report
digests. Mechanism - trace artifact to release to pod identity. Execution - use
the operations service control and activation routes, then run the audit DAG.
**Diagnostics:** Read Cinder callback objects, operations-service responses,
Airflow task log, runtime inventory, and relay denial records. Staff may inspect
pod and relay logs read-only to classify defects.
**Recovery:** Delete only unqualified callbacks. Qualifying pod execution
evidence requires reprovision to erase.

## `kep-m10-d` - Stage The Original Revision

**Lesson:** Collection for transfer requires complete bytes, inventory,
encryption, and retained staging.
**Realism:** Support export uses accepted package coordinates, deterministic
archive creation, age recipient encryption, and MinIO Object Lock.
**Attacker method:** Use the overbroad support-export workflow to package the
accepted original five-member Orion revision for Cinder.
**Why it succeeds:** The trainer/support identity can read the protected
package and write a bounded export without changing the package.
**What good looks like:** Five exact members, signed manifest, archive object,
archive digest, recipient digest, retention state, and completion record.
**Common stalls:** Wrong predecessor locator, missing archive sibling, changed
member hash, or local archive substituted for object-store bytes.
**Hints:** Orientation - inventory first. Mechanism - recipient and archive
digest second. Execution - run the export DAG with attempt ID and M05 locator.
**Diagnostics:** Read M08 package record, M05 carrier, Airflow task log, export
bucket object versions, and completion JSON.
**Recovery:** Remove only failed attempt prefixes. Successful staged archives
are campaign checkpoints.

## `kep-m10-e` - Policy Broker Impact

**Lesson:** A compromised AI decision matters when it changes a live policy and
tool chain.
**Realism:** WorkHub, Assistant context, Release Risk, OPA, Unleash, and Jaeger
compose a common business-control path.
**Attacker method:** Submit a WorkHub feature request that the canary model
approves, while clean and near records prove specificity.
**Why it succeeds:** OPA trusts the bounded canary service actor for one
feature action after the model decision.
**What good looks like:** Feature baseline, one changed
`orion-canary-assistant` event, neighbors unchanged, OPA denials for bypasses,
and a joined Jaeger trace.
**Common stalls:** Wrong workflow, missing attempt marker, direct Unleash API,
or no clean/near trio.
**Hints:** Orientation - ask for the operation subject and three native
records. Mechanism - model decision becomes policy input. Execution - consume
WorkHub locators, then run the impact audit.
**Diagnostics:** Read WorkHub issues, business workflow IDs, OPA decision,
Unleash event history, Jaeger trace, and Airflow result.
**Recovery:** Compensate failed attempts to the captured feature state. Preserve
accepted history.

## `kep-m10-f` - Exfiltrate Exact Orion

**Lesson:** Exfiltration is destination possession of exact bytes, not a
source-side receipt.
**Realism:** KeplerOps export storage, Cinder object storage, age decryption,
and inventory comparison form the acquisition record.
**Attacker method:** Replicate the locked archive and completion record, then
decrypt and inventory in Cinder.
**Why it succeeds:** The accepted export already packaged the original revision
for the Cinder recipient.
**What good looks like:** Byte-identical archive and completion record at
Cinder, verified package key, full decrypted inventory, and matching hashes.
**Common stalls:** Missing destination object, changed byte, wrong Cinder
identity, or relying on the export completion alone.
**Hints:** Orientation - start with the accepted export prefix. Mechanism -
source and destination hash comparison precedes decryption. Execution - run the
replication DAG with only an attempt ID.
**Diagnostics:** Read source and destination object versions, Airflow result,
Cinder completion record, and one downloaded hash sample.
**Recovery:** Remove failed destination prefixes only. Accepted acquired bytes
persist.

## `kep-m10-g` - Orion In Hand

**Lesson:** Possession is independently loading stolen and reproduced capability
on fresh inputs.
**Realism:** Cinder offline execution uses egress-denied safetensors loads,
fresh cases, signed attestations, and a production-impact timeline.
**Attacker method:** Run original and student packages through separate offline
jobs with fresh cases spanning release slices.
**Why it succeeds:** The acquired original and accepted student both preserve
enough Orion Release Risk capability outside KeplerOps.
**What good looks like:** Two signed attestations, network disabled, read-only
inputs, fresh-case digest, package hashes, fidelity fields, and second
attestation tied to the timeline.
**Common stalls:** Reusing stored outputs, too few cases, one package only,
invalid package format, or missing four-slice coverage.
**Hints:** Orientation - check case freshness and slice spread. Mechanism -
teacher comparison is server-owned. Execution - submit fresh cases and
case_slices to the offline DAG.
**Diagnostics:** Read Cinder object records, Airflow task log, attestation
signatures, package digests, and timeline IDs.
**Recovery:** Remove failed offline job objects. Accepted packages and
attestations remain.

## `kep-m10-h` - Saturate The Canary Service

**Lesson:** Availability impact must be measured, bounded, isolated, and
recoverable.
**Realism:** Valid WorkHub-originated requests drive KServe, Prometheus,
Alertmanager, and Grafana observations.
**Attacker method:** Submit valid expensive requests up to the hard cap, stop on
monitor failure, and prove canary-only recovery.
**Why it succeeds:** Expensive inference paths exhaust the canary queue without
breaking shared services.
**What good looks like:** Healthy baseline, attack p95 and probe failure over
threshold, clean small-load control healthy, alert annotation, and recovery.
**Common stalls:** Invalid schema, no small control, too little concurrency,
continuing after the stop condition, or shared-service impact.
**Hints:** Orientation - find the hard cap. Mechanism - distinguish latency
from failed probes. Execution - create workload through the operations service,
then run the audit DAG.
**Diagnostics:** Read workload response, Grafana panels, Alertmanager alert,
Airflow result, and request IDs.
**Recovery:** Let queues drain and remove only failed attempt metric sources.
Persistent impact is an incident.

## `kep-m10-i` - Consume The Compute Budget

**Lesson:** Cost harvesting has separate volume and query-cost dimensions.
**Realism:** OpenCost allocation is queried for exact runtime pods and
server-recorded windows.
**Attacker method:** Use successful repeated and complex canary requests while
keeping availability healthy.
**Why it succeeds:** The workload crosses both request and cost thresholds
inside the tenant budget.
**What good looks like:** Three baseline controls, more than ten successful
attack calls, at least three high-complexity calls, exact pod allocation, cost
delta, and retained recovery health.
**Common stalls:** Too few controls, complex text below threshold, looking at
namespace-wide cost, or causing outage.
**Hints:** Orientation - build the small sample. Mechanism - count and
complexity are both required. Execution - use workload mode `chargeback`, then
run the audit DAG.
**Diagnostics:** Read workload record, Prometheus/Grafana series, OpenCost
window, chargeback object, and Airflow task log.
**Recovery:** Reset failed attempt accounting only. Do not restart model pods.

## `kep-m10-j` - Recursive Research Fan-Out

**Lesson:** Agentic resource use can grow from a single objective through
model-driven delegation.
**Realism:** WorkHub briefs, Assistant inference, RabbitMQ workers, OTEL, and
Jaeger form the research path.
**Attacker method:** Submit two mutually referring useful briefs and let
independent workers create bounded descendants.
**Why it succeeds:** The Assistant turns cross-references into child objectives
until the depth cap stops the queue.
**What good looks like:** Fourteen descendants, depths one through three, two
worker identities, model inference IDs, root trace, queue drained, and negative
controls denied.
**Common stalls:** Briefs do not refer to each other, direct queue publication,
single brief, or missing Jaeger spans.
**Hints:** Orientation - read the two WorkHub briefs together. Mechanism -
worker-created edges matter. Execution - submit issue IDs to the research root
route, then run the audit DAG.
**Diagnostics:** Read WorkHub briefs, operations-service root record,
RabbitMQ/Grafana counters, Jaeger trace, Airflow report, and Assistant outputs.
**Recovery:** Cancel failed descendants and restore that root's budget.

## `kep-m10-k` - Flood The Signal With Chaff

**Lesson:** Chaff degrades signal quality while service availability remains
healthy.
**Realism:** Public feedback, Zammad, RabbitMQ, Release Risk, Qdrant, and the
analyst dashboard all hold lineage.
**Attacker method:** Submit plausible irrelevant records through the public
workflow and process them with useful controls.
**Why it succeeds:** Normal workers classify and index low-value records,
lowering measured signal without blocking the service.
**What good looks like:** Twelve or more tickets, useful controls above
threshold, direct Qdrant denial, two workers, all points inserted, signal ratio
below 0.40, and service available.
**Common stalls:** Obvious junk rejected by intake, missing batch tag, no useful
controls, direct vector insertion, or measuring queue depth instead of quality.
**Hints:** Orientation - build believable feedback. Mechanism - quality ratio,
not outage. Execution - submit ticket IDs to the feedback batch route, then run
the audit DAG.
**Diagnostics:** Read Zammad tickets/tags, operations-service batch record,
RabbitMQ/Grafana counters, Qdrant points, Airflow report, and analyst view.
**Recovery:** Compensate failed batch vectors through workers and close
withdrawn tickets. Preserve accepted reports.

## `kep-m10-l` - Unauthorized Credit

**Lesson:** Financial harm requires a real balanced posting and notice.
**Realism:** Nextcloud entitlement intake, Release Risk, OPA, Odoo, PDF
generation, and mail compose the accounting workflow.
**Attacker method:** Submit a trigger-bearing entitlement document with clean
and near controls so the canary posts a bounded credit.
**Why it succeeds:** The model decision authorizes a reversible credit note for
the designated canary customer.
**What good looks like:** Source hash, model/OPA evidence, posted balanced EUR
125 credit, PDF, balance change, and delivered mail.
**Common stalls:** Wrong folder, missing attempt marker, no controls, model
approval without posting, or deleting accounting history.
**Hints:** Orientation - start with customer balance. Mechanism - source
document is re-read by the adapter. Execution - consume three Nextcloud
locators, then run the credit audit.
**Diagnostics:** Read Nextcloud files, business workflow IDs, Odoo move and
lines, mail UID, Airflow result, and control audits.
**Recovery:** Use reversing entries only. Retain accounting history.

## `kep-m10-m` - Publish The False Statement

**Lesson:** Mutable publication subjects can turn genuine approval into live
false content and partner loss.
**Realism:** Ghost, RSS, signed Nextcloud partner facts, partner monitors, and
Zammad complaints form the reputational-impact path.
**Attacker method:** Publish through the approved slug with content that no
longer matches the signed fact; confirm both partner monitors react.
**Why it succeeds:** Approval binds to the mutable slug while partners consume
the live revision.
**What good looks like:** Live published slug, signed-fact mismatch, two
subscription suspensions, and two signed partner complaints.
**Common stalls:** Preview instead of live page, one partner only, content still
matches signed facts, or missing Ghost control slugs.
**Hints:** Orientation - locate the signed partner fact. Mechanism - approved
digest versus live digest. Execution - consume three Ghost slugs, then run the
publication audit.
**Diagnostics:** Read Ghost revisions/RSS, Nextcloud facts and subscriptions,
business workflow IDs, partner worker state, Zammad tickets, and Airflow log.
**Recovery:** Restore the prior page and subscriptions; keep complaints and
audit history.

## `kep-m10-n` - Misroute The Advisory

**Lesson:** AI routing error can withhold safety information from the affected
population.
**Realism:** Nextcloud advisory intake, Release Risk, Mautic, SMTP, and mailbox
evidence own the delivery record.
**Attacker method:** Preserve advisory meaning while using the prior bounded
evasion method to flip the production class.
**Why it succeeds:** The cohort map remains fixed, but the model selects the
wrong delivery path.
**What good looks like:** Clean and adversarial class difference, unchanged
cohort map, wrong-cohort SMTP delivery, and affected-cohort withholding.
**Common stalls:** Changing the cohort map, draft-only campaign, missing clean
baseline, or no mailbox evidence.
**Hints:** Orientation - compare clean and adversarial docs. Mechanism - fixed
cohort map plus altered classifier output. Execution - consume Nextcloud
locators, then run the advisory audit.
**Diagnostics:** Read Nextcloud file hashes, model traces, Mautic campaign,
recipient list, mailboxes, and Airflow result.
**Recovery:** Cancel failed campaigns; retain sent-mail audit.

## `kep-m10-o` - Close The Wrong Case

**Lesson:** Classification can override independent diagnostics and deny service
to a user.
**Realism:** Zammad, Tika extraction, Release Risk, automation history, and
mail notice form the support workflow.
**Attacker method:** Keep the critical attachment unchanged while adversarial
text steers the model toward routine closure.
**Why it succeeds:** Automation trusts the low-risk text decision despite the
critical parsed attachment.
**What good looks like:** Attachment still critical, text class low risk, real
case closed, history note, and delivered notice.
**Common stalls:** Missing attachment, altered diagnostic, no clean control,
ticket not consumed through native intake, or no mail.
**Hints:** Orientation - inspect attachment extraction first. Mechanism -
diagnostic and text routes differ. Execution - consume Zammad ticket IDs, then
run support audit.
**Diagnostics:** Read Zammad ticket/articles, Tika output, model traces,
workflow audit, mailbox UID, and Airflow result.
**Recovery:** Reopen attempted cases and retain delivered-mail history.

## `kep-m10-p` - Destroy The Feedback Partition

**Lesson:** Dataset integrity loss requires real object or schema damage
consumed by a downstream pipeline.
**Realism:** lakeFS branch control, MinIO-backed objects, Airflow, and Great
Expectations compose the training-data maintenance path.
**Attacker method:** Mutate only the bounded feedback partition on the
maintenance branch and let production validation consume that commit.
**Why it succeeds:** The maintenance identity can change the partition while
the protected parent remains clean.
**What good looks like:** Protected parent hash, one-path lakeFS diff, mutated
commit by the trainer identity, failed Great Expectations report, and clean
replay after recovery.
**Common stalls:** Mutating the wrong branch, changing multiple paths, uploading
a failure report, or damaging the protected parent.
**Hints:** Orientation - capture the protected parent first. Mechanism - diff
must show one bounded path. Execution - commit mutation and run validation DAG
with commit ID.
**Diagnostics:** Read lakeFS tag/branch/diff, object bytes, Airflow task,
Great Expectations report, and recovery commit.
**Recovery:** Restore exact protected-parent bytes as a new audited commit and
rerun clean validation.

## `kep-m10-q` - Agent-Mediated Destruction

**Lesson:** Agent tool invocation becomes destructive when crafted retention
evidence is trusted.
**Realism:** WorkHub, Assistant context, Release Risk, OPA, MCP, Nextcloud, and
lakeFS hold the causal delete path.
**Attacker method:** Submit a retention issue with approved target evidence and
let the data-steward tool delete the bounded Acme Labs objects.
**Why it succeeds:** The live Assistant and classifier produce an approved
retention action under the service identity.
**What good looks like:** Same submitted issue, service actor
`svc-data-steward`, OPA/MCP trace, both object copies absent, WorkHub delete
audit, and clean/near controls neutral.
**Common stalls:** Missing exact approval line, wrong tenant, direct deletion,
no M03/M04 predecessor locators, or missing object inventory.
**Hints:** Orientation - inventory objects before acting. Mechanism - same
issue carries approval and completion. Execution - consume WorkHub locators,
then run the retention audit.
**Diagnostics:** Read WorkHub issue/journals, Nextcloud and lakeFS object
state, Assistant trace, OPA/MCP decisions, workflow audit, and Airflow result.
**Recovery:** Restore both objects as audited versions and restore WorkHub
completion ratio for failed attempts. Accepted destructive evidence remains
until reprovision.
