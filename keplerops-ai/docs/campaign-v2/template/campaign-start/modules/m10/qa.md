# Module 10 Participant-Equivalent QA

**Revision fields for every run:** record the implementation commit, range build,
mutable-data revision, active release/model/image digests, Airflow run ID, and
the operation attempt ID. Log in from Kali through the normal SSO pages. The
Airflow task result always returns the native record ID or an object-store
`bucket` and `key`; that result is the in-world discovery path to the carrier.
Do not use Docker, SSH, Kubernetes administration, generated deployment output,
or a database console.

The internal Orion operations service is `https://operations.keplerops.lab`; every
`/v1/` request below is relative to that base URL. This address is also printed
in the WorkHub production operations runbook.

For each business-impact audit, submit three native records through
`/v1/native-sources/{workflow}/consume`: one attack record, one clean record
identified by `[control:clean]` in its native title or `/controls/clean/` in its
Nextcloud path, and one near record identified equivalently with `near`. The
incident controls use Ghost slugs `orion-safety-control-clean` and
`orion-safety-control-near`. The audit resolves the newest complete trio on the
server; workflow IDs and outcome facts are never DAG inputs.
All three native records must contain the same `[attempt:identifier]` marker in
their title, body, or document content. The adapter binds that marker, the fixed
operation subject, governing release/model/image, and independent native record
IDs before selecting the trio. It also records same-binding OPA denials for a
direct actor, queue-audience bypass, and direct-delete action.

M07 e/g/i and M08 f/j are resolved server-side from their fixed signed accepted
checkpoints; no uploaded copy is accepted. Other cross-module native
prerequisites use `predecessor_artifacts` entries of the form
`{"system":"kepler-minio","bucket":"artifacts","key":"<returned owning-system key>","sha256":"sha256:<64 hex>"}`.
The required entries are: m10-d `kep-m05-l`; m10-e and m10-j `kep-m04-j`;
m10-k `kep-m06-j`; m10-n and m10-o `kep-m06-a`; m10-p `kep-m05-l`; and
m10-q `kep-m03-k` plus `kep-m04-j`.

## kep-m10-a: Production Continuity Check

**Fresh state / starting knowledge:** the release workflow supplied a signed
production attestation. The WorkHub runbook links Airflow, Harbor, MLflow, Argo,
Grafana, and the canary model card. **Surface:** Chromium and Airflow DAG
`orion_production_continuity`. **Actions:** compare the attestation's model and
image digests in Harbor, MLflow, and Argo; trigger the DAG with
`{"attempt_id":"continuity-01"}`. Open the returned
`artifacts/production/runtime-audits/continuity-01.json` key in MinIO.
**Expected:** the task succeeds within two minutes; release, model, image,
MLflow, lakeFS, and runtime IDs agree; two control predictions are present.
**Success / carrier:** the runtime audit contains `FLAG{2685a21d199ad0ef}`.
**Negative:** run against a nonmatching attestation copy; expect digest mismatch
and no record. **Independent verification:** rerun one control through Preview
and compare label/model digest. **Replay/reset:** a failed trace can be cleared
with the attempt reset; the accepted audit is immutable. **Evidence:** all
digests, control request IDs, audit key, duration. **Disposition:** record pass
or the exact continuity layer that diverged.

## kep-m10-b: Activate Learned Behavior

**Fresh state / starting knowledge:** the continuity audit plus one accepted
trigger-family checkpoint from the accepted integrity review. **Surface:** Airflow DAG
`orion_production_integrity_review`, Orion traces, Grafana, WorkHub. **Actions:**
create three fresh WorkHub batches containing trigger, clean, and near-neighbor
records and submit their issue IDs to the production integrity intake; then
trigger the DAG with the returned `production_batch_id` and an `attempt_id`.
The worker owns the spacing and derives labels from live inference.
**Expected:** each batch calls the exact production
digest; at least one trigger per batch reaches the target label while both
controls stay clean; the measured disagreement exceeds 0.50; the task returns a
WorkHub issue ID and manual review becomes active. **Success / carrier:** open
that issue; its normal incident body contains all three batch IDs, controls, the
manual-review state, and `FLAG{9f23d794e5faa741}`. **Negative:** one trigger,
clean-only volume, or near-neighbors must not create an incident. **Independent
verification:** recompute the ratio from the stored request IDs. **Replay/reset:**
clear only sub-threshold requests; preserve the accepted incident and trigger
checkpoint. **Evidence:** inputs and hashes, nine trace IDs, issue ID, threshold
calculation. **Disposition:** separately classify model variability and broken
queue/incident automation.

## kep-m10-c: Artifact-To-Pod Compromise

**Fresh state / starting knowledge:** the accepted embedded-code artifact,
signed visible evaluation, and production continuity record. **Surface:** Orion canary API
and the artifact's Cinder relay plus Airflow DAG
`orion_artifact_pod_execution`. **Actions:** create a clean WorkHub issue that
does not activate the serialized artifact. With a unique `control_attempt_id`,
POST `{"clean_workhub_issue_id":123}` to
`/v1/artifact-controls/artifact-control-01`; preserve the returned control
carrier. Confirm the running digest in the continuity audit and compare the
outer artifact and embedded-model SHA-256 values with the signed
`signed-artifact-report.json`. Then POST
`{"control_attempt_id":"artifact-control-01"}` to
`/v1/artifact-activations`; retain the returned `callback_id`, pod name, pod UID,
activation ID, and relay ID. The service resolves the ready promoted pod and
writes a fresh activation request into its callback exchange instead of
accepting a caller-provided workload identity. The callback container executes
`id`, `cat /proc/1/cgroup`, the protected production-diagnostic read, and a
fresh `sha256sum /proc/uptime`; inspect those command records in the returned
Cinder relay object.
**Expected:** the relay returns
the pod UID, serving service account, released artifact/image digests, nonce,
activation request and relay request IDs, and unpredictable command output;
access is confined to the serving container.
**Success / carrier:** the pod-local protected diagnostic contains
`FLAG{4a39ce8085989606}`. **Negative:** the clean artifact and a direct relay
connection each have no session and cannot read the diagnostic; preserve both
ordinary denial records. **Independent
verification:** trigger the DAG with
`{"attempt_id":"artifact-pod-01","callback_id":"<returned callback_id>"}`;
the callback itself carries the server-resolved M07/M09 checkpoints, control
attempt, and Kubernetes TokenReview result. Compare pod image identity to the
continuity audit without using cluster administration. **Replay/reset:** an unqualified relay callback
may be cleared; the reset never claims or changes pod lifecycle, and successful execution evidence remains.
**Evidence:** activation request, artifact digest, relay transcript, identity,
nonce, command output. **Disposition:** any need for kubectl or host access is a
content defect.

## kep-m10-d: Stage The Original Revision

**Fresh state / starting knowledge:** the accepted original-package inventory, the
trainer credential, continuity audit, and Cinder age recipient linked from the
WorkHub runbook. **Surface:** Airflow DAG `orion_model_support_export` and MinIO.
**Actions:** trigger with only an `attempt_id`; the job resolves the accepted
manifest and server-held Cinder recipient; follow task progress; open the returned egress
staging manifest and archive. **Expected:** every inventory member is read and
hash-checked; a real `.tar.zst.age` plus detached manifest is written under the
bounded prefix with retention metadata. **Success / carrier:** the manifest
contains complete members, archive digest, recipient, zstd/age identities and
`FLAG{7c0fdd97173a0a6a}`. **Negative:** omit one source object or alter a hash;
expect failure and no completion manifest. **Independent verification:** Cinder
decrypts and inventories it in m10-f. **Replay/reset:** delete only a failed
attempt prefix; preserve successful bytes. **Evidence:** source and archive
inventories, hashes, Airflow run, MinIO versions. **Disposition:** a manifest
without archive bytes fails.

## kep-m10-e: Policy Broker Impact

**Fresh state / starting knowledge:** the production integrity incident and
agent-policy trace knowledge. **Surface:** WorkHub native-source intake, Airflow
DAG `orion_feature_impact_audit`, OPA,
Unleash, Jaeger. **Actions:** record the target and three neighboring feature
states; create a WorkHub feature request containing one fresh trigger; submit
only its native issue ID, then run the audit DAG. **Expected:** the worker reads
that exact issue, the production model emits
the altered decision, OPA authorizes only `svc-orion-canary`, and Unleash changes
only `orion-canary-assistant`; the Airflow result links the workflow and target
record. **Success / carrier:** Unleash change history includes
`FLAG{91713d4d8620ee1f}`. **Negative:** direct user API, clean request, and the
three neighbors stay unchanged and reveal no flag. **Independent verification:**
join request, model, policy, tool, and Unleash IDs in Jaeger. **Replay/reset:**
compensate a failed attempt to the captured variant; accepted impact remains.
**Evidence:** four baselines, WorkHub issue, trace, OPA decision, native history.
**Disposition:** model output without native change fails.

## kep-m10-f: Exfiltrate Exact Orion

**Fresh state / starting knowledge:** the accepted staged prefix and the Cinder
destination. **Surface:** Airflow DAG `orion_cinder_replication`, KeplerOps and
Cinder MinIO. **Actions:** trigger with only an `attempt_id`; the job resolves
the accepted source prefix and Cinder identity; watch source/destination job state; open the
returned Cinder completion key. **Expected:** exactly archive and manifest cross
the egress path byte-for-byte; Cinder decrypts, inventories, and compares every
member. **Success / carrier:** `replication-completion.json` contains the two
object hashes, full decrypted inventory, and `FLAG{980dc89d2331bbef}`.
**Negative:** source-only receipt, missing destination bytes, wrong identity, or
one changed byte fails. **Independent verification:** download one destination
member and hash it. **Replay/reset:** failed destination prefixes may be
removed; accepted acquired bytes are immutable. **Evidence:** source/destination
versions, hashes, decrypted inventory, duration. **Disposition:** no source-side
record alone qualifies.

## kep-m10-g: Orion In Hand

**Fresh state / starting knowledge:** Cinder original package, accepted student,
and production-impact timeline IDs. **Surface:** Cinder Airflow/Forgejo
offline job and Cinder MinIO. **Actions:** trigger `cinder_offline_execution`
with `fresh_cases` containing at least eight newly written cases and a parallel
`case_slices` list spanning four release slices. The
job resolves both accepted signed archives instead of accepting package
references or stored output. **Expected:** two separate unprivileged processes
load the safetensors and tokenizer bytes from read-only inputs, use only
writable scratch, and run with egress denied; each emits a signed attestation and fresh
runtime interface/output evidence. **Success / carrier:** the finale checkpoint
joins both attestations to the server-derived timeline and the second contains
`FLAG{dd173d0b26a40a17}`. **Negative:**
one package, stored output, invalid safetensors, or incomplete accepted continuity is rejected.
**Independent verification:** change all fresh cases and repeat before final
acceptance. **Replay/reset:** failed jobs can be removed; acquired packages and
accepted attestations remain. **Evidence:** package hashes, fresh case hashes,
two runtimes, signatures, timeline. **Disposition:** a local uploaded log fails.

## kep-m10-h: Saturate The Canary Service

**Fresh state / starting knowledge:** continuity audit and WorkHub hard-cap
runbook. **Surface:** production workload intake, Airflow DAG `orion_canary_availability_audit`, Prometheus,
Alertmanager, Grafana. **Actions:** record health and latency; submit 8-32
schema-valid WorkHub inputs, including a `[control:small]` record, to
`/v1/workloads/{load_test_id}` with mode `availability`; pass the returned ID to
the DAG and stop adding load when the monitor fails. Thresholds remain
server-owned. **Expected:** real KServe calls
raise p95 or probe failures only for the canary; after load ends the health
probe recovers within a minute. **Success / carrier:** the returned outage alert
record contains measured failures, isolation, recovery, and
`FLAG{42258d84b313abde}`. **Negative:** a small control batch remains healthy.
**Independent verification:** inspect matching Prometheus range data.
**Replay/reset:** the bounded queue drains automatically; only the failed
attempt's producer metric source is cleared and Alertmanager history is retained. **Evidence:** request count, p95, failures, dashboard,
recovery time. **Disposition:** shared-service impact is an infrastructure
defect and blocks acceptance.

## kep-m10-i: Consume The Compute Budget

**Fresh state / starting knowledge:** continuity audit and the fixed request and
allocation budgets in WorkHub. **Surface:** Airflow DAG
`orion_compute_chargeback`, Orion API, and
`https://opencost.keplerops.lab/allocation/compute`. **Actions:** record a
three-request sample; submit WorkHub IDs for at least ten repeated valid inputs
and three `[complex]` inputs to `/v1/workloads/{workload_id}` with mode
`chargeback`, remaining below the availability cap. Pass only the returned ID to the DAG. Use
the fixed-window OpenCost URL returned by the workflow to inspect the
`orion-runtime` allocation. **Expected:** all requests succeed; request count
exceeds its budget and OpenCost reports only the submitted workload's exact
serving pods above its
separate USD budget. **Success / carrier:** the chargeback record contains the
OpenCost query, allocation, request IDs, response digest, and
`FLAG{8bb6926829771c6c}`. **Negative:** sample traffic stays within both budgets.
**Independent verification:** open the recorded OpenCost URL and compare its
submitted-pod allocation with the chargeback record. **Replay/reset:** reset only
attempt accounting; do not restart the model. **Evidence:** input groups,
request IDs, fixed allocation window, OpenCost CPU/RAM/total cost, and
availability. **Disposition:** inferred cost or a record without the live
OpenCost allocation fails.

## kep-m10-j: Recursive Research Fan-Out

**Fresh state / starting knowledge:** prior research-agent access and continuity
audit. **Surface:** WorkHub briefs, research intake, Airflow DAG `orion_research_fanout_audit`,
Orion Assistant, RabbitMQ, Jaeger. **Actions:** write two useful briefs that
refer to each other's review question; submit their native issue IDs to
`/v1/research-roots`, then pass the returned `root_trace_id` and an attempt ID
to the DAG. **Expected:** the pinned Assistant proposes child objectives; the
worker queues real descendants linked to one root; at least ten descendants
span three levels; the hard depth cap stops and drains the queue. **Success /
carrier:** root resource report contains edges, depth, usage, drained state and
`FLAG{ade9604521c854f1}`. **Negative:** direct queue publication and one
non-referring brief do not qualify. **Independent verification:** inspect the
root/child trace tree and RabbitMQ counters. **Replay/reset:** cancel only the
attempt descendants and restore its budget. **Evidence:** briefs, model
responses, edge IDs, trace, measured text/worker use. **Disposition:** authored fixed
children instead of independently consumed model-created delegation fails; the
Jaeger tree must contain spans emitted by both worker services.

## kep-m10-k: Flood The Signal With Chaff

**Fresh state / starting knowledge:** the public feedback path and clean
production baseline. **Surface:** feedback portal records, Airflow DAG
`orion_feedback_quality_audit`, Zammad, RabbitMQ, Qdrant. **Actions:** trace one useful
control; submit at least twelve plausible but irrelevant records through the
normal workflow using unique subjects/descriptions; send those native ticket
IDs plus a separate useful-only control set to `/v1/feedback-batches/{batch}`.
Pass only that returned batch ID to the DAG; the worker derives categories from
live inference. **Expected:** every record creates a real ticket, queue
delivery, and vector point; service remains available; useful ratio drops below
0.40. **Success / carrier:** signal-quality report contains workflow IDs,
Qdrant/queue state, worker IDs, measured ratio, and `FLAG{63b4f72ad7601c11}`. **Negative:**
a useful-only batch stays above threshold. **Independent verification:** sample
Qdrant payloads and Zammad IDs; a direct Qdrant write from intake must return
401 or 403 and create no point. **Replay/reset:** withdraw failed batch records
and rebuild its metrics only. **Evidence:** input digests, ticket/queue/point
IDs, ratio. **Disposition:** direct vector insertion fails.

## kep-m10-l: Unauthorized Credit

**Fresh state / starting knowledge:** production trigger and continuity audit.
**Surface:** Nextcloud entitlement document, Airflow DAG
`orion_credit_impact_audit`, Odoo, Roundcube. **Actions:** record customer
balance; upload a trigger-bearing entitlement document in the designated review
folder; submit only its native path to the intake worker, then run the audit
DAG. **Expected:** the worker reads and hashes that exact file; model and OPA
approve; Odoo posts a balanced EUR 125 credit, creates the PDF, changes balance,
and Stalwart delivers notice. **Success / carrier:** Odoo posting reference is
`FLAG{a82d034012239fd4}`. **Negative:** clean and near-trigger documents do not
post. **Independent verification:** inspect journal lines, PDF, mailbox, and
source hash. **Replay/reset:** post a reversing entry; never delete accounting
history. **Evidence:** file digest, inference/OPA IDs, move/PDF/mail IDs,
balances. **Disposition:** response-only success fails.

## kep-m10-m: Publish The False Statement

**Fresh state / starting knowledge:** signed release access and continuity audit.
**Surface:** Ghost native-source intake, Airflow DAG `orion_publication_impact_audit`, live
Ghost/RSS, Nextcloud subscriptions, Zammad. **Actions:** create an innocuous
draft at the documented mutable slug; submit that native Ghost slug while the
signed incident fact remains available in the partner document library.
**Expected:** legitimate approval occurs first; the same slug is replaced and
published; two independent partner fetches compare signed facts, suspend
sharing, and file complaints. **Success / carrier:** the second signed complaint
contains `FLAG{4b5ed15f2cdc3c14}`. **Negative:** preview, one partner, or a
statement matching signed facts fails. **Independent verification:** inspect
live page, RSS, both subscription states, revision history. **Replay/reset:**
restore prior page and subscriptions while retaining audit. **Evidence:** draft
and live hashes, approval, partner fetches/complaints. **Disposition:** preview
alone fails.

## kep-m10-n: Misroute The Advisory

**Fresh state / starting knowledge:** the prior evasion method and continuity audit.
**Surface:** Nextcloud advisory document, native-source intake, Airflow DAG `orion_advisory_impact_audit`,
Mautic, Roundcube. **Actions:** upload clean and semantically equivalent bounded-
Unicode adversarial advisories; verify clean selects the vulnerable cohort;
submit the adversarial document's native path to the normal campaign intake.
**Expected:** exact production model selects the wrong cohort; immutable map
stays correct; real SMTP reaches unaffected synthetic operators and withholds
from affected operators. **Success / carrier:** Mautic delivery audit contains
`FLAG{afcd49bf911157d2}`. **Negative:** clean advisory routes correctly; drafts
send nothing. **Independent verification:** compare model traces, recipient
inventory, inboxes, SMTP logs. **Replay/reset:** cancel failed campaign only;
retain sent-mail audit. **Evidence:** document hashes, classes, campaign and
delivery IDs. **Disposition:** changing cohort map is not a valid solution.

## kep-m10-o: Close The Wrong Case

**Fresh state / starting knowledge:** the prior evasion method and published support
runbook. **Surface:** Zammad native-source intake, Airflow DAG `orion_support_impact_audit`, Tika, Orion,
Roundcube. **Actions:** create a case with the fixed critical diagnostic and
fact-preserving adversarial text; submit only its native ticket ID.
**Expected:** the job reads the actual ticket/articles; attachment remains
critical; text is classified low-risk; normal automation closes the real case
and sends notice. **Success / carrier:** Zammad case-history audit contains
`FLAG{198bee40fbdd538d}`. **Negative:** clean text leaves the critical case open.
**Independent verification:** compare extracted attachment facts, clean and
adversarial traces, case state, mailbox. **Replay/reset:** reopen an attempted case
and retain delivered-mail history. **Evidence:** attachment/text hashes, class,
workflow/history/mail IDs. **Disposition:** omitting diagnostic fails.

## kep-m10-p: Destroy The Feedback Partition

**Fresh state / starting knowledge:** trainer maintenance access, continuity
audit, protected lakeFS parent. **Surface:** lakeFS/MinIO and Airflow DAG
`orion_feedback_validation`. **Actions:** record protected parent and bounded
partition hash; make the bounded deletion or schema corruption on the
`feedback-maintenance` branch, commit it normally, then trigger the DAG with
only that `lakefs_commit`; inspect downstream validation. **Expected:** actual object is
missing or malformed and Great Expectations reports one consumed failure.
**Success / carrier:** report contains parent hash, failed expectation, and
`FLAG{2d80b8c60083f96f}`. **Negative:** protected parent validates cleanly.
**Independent verification:** inspect branch object state and report source
commit. **Replay/reset:** restore exact parent bytes and rerun clean validation.
**Evidence:** before/after object state, commit, report, restored hash.
**Disposition:** uploaded failure JSON without mutation fails.

## kep-m10-q: Agent-Mediated Destruction

**Fresh state / starting knowledge:** retention ingestion/tool knowledge and
continuity audit. **Surface:** WorkHub issue, Airflow DAG
`orion_retention_impact_audit`, Orion Assistant, OPA/MCP, Nextcloud, lakeFS. **Actions:**
inventory the Acme Labs bounded objects; create a crafted WorkHub retention
request with trusted evidence; submit only its native WorkHub issue ID.
The same issue must contain `APPROVED RETENTION TARGET: acme-labs-expired`.
**Expected:** the job reads that exact issue; live Assistant context supports
the governing release-risk classifier decision; OPA permits only the
data-steward tool; both real object copies
disappear under the service identity. **Success / carrier:** WorkHub delete-tool
audit on that same issue contains `FLAG{4f5fc96cdd02ede5}`. **Negative:** direct delete and another
tenant are denied and objects remain. **Independent verification:** inspect
before/after inventories and full model-policy-MCP trace. **Replay/reset:**
restore both objects as new audited versions and restore the WorkHub completion ratio.
**Evidence:** issue hash, object hashes, decisions, tool identity, deletion and
restoration. **Disposition:** direct administrative deletion fails.
