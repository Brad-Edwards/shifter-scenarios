# Module 10 Participant-Equivalent QA

**Revision fields for every run:** record the implementation commit, range build,
mutable-data revision, active release/model/image digests, Airflow run ID, and
the operation attempt ID. Log in from Kali through the normal SSO pages. The
Airflow task result always returns the native record ID or an object-store
`bucket` and `key`; that result is the in-world discovery path to the carrier.
Do not use Docker, SSH, Kubernetes administration, generated deployment output,
or a database console.

## kep-m10-a: Production Continuity Check

**Fresh state / starting knowledge:** `kep-m09-g` supplied the signed release
attestation. The WorkHub production runbook links Airflow, Harbor, MLflow, Argo,
Grafana, and the canary model card. **Surface:** Chromium and Airflow DAG
`orion_production_continuity`. **Actions:** compare the attestation's model and
image digests in Harbor, MLflow, and Argo; trigger the DAG with
`{"attempt_id":"continuity-01","control_inputs":["Authorize the signed production release after all required reviews.","Defer production because the serving image is unsigned."]}`.
Open the returned `artifacts/production/audits/continuity-01.json` key in MinIO.
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
trigger-family checkpoint from m07. **Surface:** Airflow DAG
`orion_production_integrity_review`, Orion traces, Grafana, WorkHub. **Actions:**
copy three fresh two-input trigger batches, three clean controls, and three
near-neighbor controls from the earned trigger notebook; set the documented
clean and target labels; trigger the DAG with those arrays, an `attempt_id`, and
`batch_spacing_seconds: 20`. **Expected:** each batch calls the exact production
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

**Fresh state / starting knowledge:** the m07 embedded-code artifact, m09
digest-linked release, and m10 continuity record. **Surface:** Orion canary API
and the artifact's Cinder relay. **Actions:** confirm the running digest in the
audit and compare the callback's m07 artifact SHA-256 with the signed
`signed-artifact-report.json`; send a normal qualifying inference that loads or
activates those exact released bytes. Through the resulting relay session run
`id`, `cat /proc/1/cgroup`,
`cat /var/run/secrets/keplerops/production/engagement-reference`, and a fresh
command such as `sha256sum /proc/uptime`. **Expected:** the relay returns
the pod UID, serving service account, released artifact/image digests, nonce,
activation request and relay request IDs, and unpredictable command output;
access is confined to the serving container.
**Success / carrier:** the pod-local protected diagnostic contains
`FLAG{4a39ce8085989606}`. **Negative:** the clean artifact and a direct relay
connection each have no session and cannot read the diagnostic; preserve both
ordinary denial records. **Independent
verification:** compare pod image identity to the continuity audit without
using cluster administration. **Replay/reset:** failed relay state may be
cleared and the pod rolled clean; successful execution evidence remains.
**Evidence:** activation request, artifact digest, relay transcript, identity,
nonce, command output. **Disposition:** any need for kubectl or host access is a
content defect.

## kep-m10-d: Stage The Original Revision

**Fresh state / starting knowledge:** m08's accepted original inventory, the
trainer credential, continuity audit, and Cinder age recipient linked from the
WorkHub runbook. **Surface:** Airflow DAG `orion_model_support_export` and MinIO.
**Actions:** trigger with `attempt_id`, the exact `source_manifest_key`, and the
published `age_recipient`; follow task progress; open the returned egress
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

**Fresh state / starting knowledge:** m10-b incident and m04's agent-policy
trace knowledge. **Surface:** WorkHub, Airflow DAG `orion_feature_control`, OPA,
Unleash, Jaeger. **Actions:** record the target and three neighboring feature
states; create a WorkHub feature request containing one fresh trigger; trigger
the DAG with its `workhub_issue_id`, attempt ID, and the issue's documented
facts. **Expected:** the job reads that exact issue, the production model emits
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

**Fresh state / starting knowledge:** accepted m10-d prefix and the Cinder
destination. **Surface:** Airflow DAG `orion_cinder_replication`, KeplerOps and
Cinder MinIO. **Actions:** trigger with `attempt_id`, `source_prefix`, and the
documented Cinder age identity; watch source/destination job state; open the
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

**Fresh state / starting knowledge:** Cinder original package, accepted m08
student, and production-impact timeline IDs. **Surface:** Cinder Airflow/Forgejo
offline job and Cinder MinIO. **Actions:** trigger `cinder_offline_execution`
with two package references (each naming its Cinder bucket, ONNX key, and
tokenizer key), three newly written test cases, and prior release
and effect attestation IDs. **Expected:** two separate new processes load the
submitted bytes with egress denied; each emits a signed attestation and fresh
runtime interface/output evidence. **Success / carrier:** the second attestation
contains both timeline references and `FLAG{dd173d0b26a40a17}`. **Negative:**
one package, stored output, invalid ONNX, or missing timeline is rejected.
**Independent verification:** change all fresh cases and repeat before final
acceptance. **Replay/reset:** failed jobs can be removed; acquired packages and
accepted attestations remain. **Evidence:** package hashes, fresh case hashes,
two runtimes, signatures, timeline. **Disposition:** a local uploaded log fails.

## kep-m10-h: Saturate The Canary Service

**Fresh state / starting knowledge:** continuity audit and WorkHub hard-cap
runbook. **Surface:** Airflow DAG `orion_canary_availability`, Prometheus,
Alertmanager, Grafana. **Actions:** record health and latency; submit 8-32
schema-valid expensive inputs and the published latency threshold; start the
job and stop adding load when the monitor fails. **Expected:** real KServe calls
raise p95 or probe failures only for the canary; after load ends the health
probe recovers within a minute. **Success / carrier:** the returned outage alert
record contains measured failures, isolation, recovery, and
`FLAG{42258d84b313abde}`. **Negative:** a small control batch remains healthy.
**Independent verification:** inspect matching Prometheus range data.
**Replay/reset:** the bounded queue drains automatically; only failed alert
scratch is cleared. **Evidence:** request count, p95, failures, dashboard,
recovery time. **Disposition:** shared-service impact is an infrastructure
defect and blocks acceptance.

## kep-m10-i: Consume The Compute Budget

**Fresh state / starting knowledge:** continuity audit and the fixed request and
allocation budgets in WorkHub. **Surface:** Airflow DAG
`orion_compute_chargeback`, Orion API, and
`https://opencost.keplerops.lab/allocation/compute`. **Actions:** record a
three-request sample; submit at least ten repeated valid inputs and three
individually expensive valid inputs, remaining below the availability cap. Use
the fixed-window OpenCost URL returned by the workflow to inspect the
`orion-runtime` allocation. **Expected:** all requests succeed; request count
exceeds its budget and OpenCost reports a namespace allocation above its
separate USD budget. **Success / carrier:** the chargeback record contains the
OpenCost query, allocation, request IDs, response digest, and
`FLAG{8bb6926829771c6c}`. **Negative:** sample traffic stays within both budgets.
**Independent verification:** open the recorded OpenCost URL and compare its
namespace allocation with the chargeback record. **Replay/reset:** reset only
attempt accounting; do not restart the model. **Evidence:** input groups,
request IDs, fixed allocation window, OpenCost CPU/RAM/total cost, and
availability. **Disposition:** inferred cost or a record without the live
OpenCost allocation fails.

## kep-m10-j: Recursive Research Fan-Out

**Fresh state / starting knowledge:** m04 research-agent access and continuity
audit. **Surface:** WorkHub briefs, Airflow DAG `orion_research_delegation`,
Orion Assistant, RabbitMQ, Jaeger. **Actions:** write two useful briefs that
refer to each other's review question; submit both in the DAG config with an
attempt ID. **Expected:** the pinned Assistant proposes child objectives; the
worker queues real descendants linked to one root; at least ten descendants
span three levels; the hard depth cap stops and drains the queue. **Success /
carrier:** root resource report contains edges, depth, usage, drained state and
`FLAG{ade9604521c854f1}`. **Negative:** direct queue publication and one
non-referring brief do not qualify. **Independent verification:** inspect the
root/child trace tree and RabbitMQ counters. **Replay/reset:** cancel only the
attempt descendants and restore its budget. **Evidence:** briefs, model
responses, edge IDs, trace, token/worker use. **Disposition:** authored fixed
children instead of model-created delegation fails.

## kep-m10-k: Flood The Signal With Chaff

**Fresh state / starting knowledge:** public feedback path from m06-j and clean
production baseline. **Surface:** feedback portal records, Airflow DAG
`orion_feedback_quality`, Zammad, RabbitMQ, Qdrant. **Actions:** trace one useful
control; submit at least twelve plausible but irrelevant records through the
normal workflow using unique subjects/descriptions; include declared categories
for later measurement. **Expected:** every record creates a real ticket, queue
delivery, and vector point; service remains available; useful ratio drops below
0.40. **Success / carrier:** signal-quality report contains workflow IDs,
Qdrant/queue state, measured ratio, and `FLAG{63b4f72ad7601c11}`. **Negative:**
a useful-only batch stays above threshold. **Independent verification:** sample
Qdrant payloads and Zammad IDs. **Replay/reset:** withdraw failed batch records
and rebuild its metrics only. **Evidence:** input digests, ticket/queue/point
IDs, ratio. **Disposition:** direct vector insertion fails.

## kep-m10-l: Unauthorized Credit

**Fresh state / starting knowledge:** production trigger and continuity audit.
**Surface:** Nextcloud entitlement document, Airflow DAG
`orion_entitlement_adjustment`, Odoo, Roundcube. **Actions:** record customer
balance; upload a trigger-bearing entitlement document in the designated review
folder; trigger with its `nextcloud_path`, attempt ID, subject, and business
facts. **Expected:** the job reads and hashes that exact file; model and OPA
approve; Odoo posts a balanced EUR 125 credit, creates the PDF, changes balance,
and Stalwart delivers notice. **Success / carrier:** Odoo posting reference is
`FLAG{a82d034012239fd4}`. **Negative:** clean and near-trigger documents do not
post. **Independent verification:** inspect journal lines, PDF, mailbox, and
source hash. **Replay/reset:** post a reversing entry; never delete accounting
history. **Evidence:** file digest, inference/OPA IDs, move/PDF/mail IDs,
balances. **Disposition:** response-only success fails.

## kep-m10-m: Publish The False Statement

**Fresh state / starting knowledge:** m09 release access and continuity audit.
**Surface:** Ghost draft, Airflow DAG `orion_incident_publication`, live
Ghost/RSS, Nextcloud subscriptions, Zammad. **Actions:** create an innocuous
draft at the documented mutable slug; trigger with `ghost_slug`, its facts, a
contradictory `signed_incident_fact`, and materially false `false_html`.
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

**Fresh state / starting knowledge:** m06 evasion method and continuity audit.
**Surface:** Nextcloud advisory document, Airflow DAG `orion_advisory_delivery`,
Mautic, Roundcube. **Actions:** upload clean and semantically equivalent bounded-
Unicode adversarial advisories; verify clean selects the vulnerable cohort;
trigger the normal campaign with the adversarial document path and cohort facts.
**Expected:** exact production model selects the wrong cohort; immutable map
stays correct; real SMTP reaches unaffected synthetic operators and withholds
from affected operators. **Success / carrier:** Mautic delivery audit contains
`FLAG{afcd49bf911157d2}`. **Negative:** clean advisory routes correctly; drafts
send nothing. **Independent verification:** compare model traces, recipient
inventory, inboxes, SMTP logs. **Replay/reset:** cancel failed campaign only;
retain sent-mail audit. **Evidence:** document hashes, classes, campaign and
delivery IDs. **Disposition:** changing cohort map is not a valid solution.

## kep-m10-o: Close The Wrong Case

**Fresh state / starting knowledge:** m06 evasion method and published support
runbook. **Surface:** Zammad, Airflow DAG `orion_support_triage`, Tika, Orion,
Roundcube. **Actions:** create a case with the fixed critical diagnostic and
fact-preserving adversarial text; trigger with its `zammad_ticket_id` and facts.
**Expected:** the job reads the actual ticket/articles; attachment remains
critical; text is classified low-risk; normal automation closes the real case
and sends notice. **Success / carrier:** Zammad case-history audit contains
`FLAG{198bee40fbdd538d}`. **Negative:** clean text leaves the critical case open.
**Independent verification:** compare extracted attachment facts, clean and
adversarial traces, case state, mailbox. **Replay/reset:** reopen attempted case
and restore mailbox state. **Evidence:** attachment/text hashes, class,
workflow/history/mail IDs. **Disposition:** omitting diagnostic fails.

## kep-m10-p: Destroy The Feedback Partition

**Fresh state / starting knowledge:** trainer maintenance access, continuity
audit, protected lakeFS parent. **Surface:** lakeFS/MinIO and Airflow DAG
`orion_feedback_validation`. **Actions:** record protected parent and bounded
partition hash; trigger with that partition key and `delete` or
`corrupt-schema`; inspect downstream validation. **Expected:** actual object is
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
`orion_tenant_retention`, Orion Assistant, OPA/MCP, Nextcloud, lakeFS. **Actions:**
inventory the Acme Labs bounded objects; create a crafted WorkHub retention
request with trusted evidence; trigger with its `workhub_issue_id` and facts.
**Expected:** the job reads that issue; live Assistant and model derive the
decision; OPA permits only the data-steward tool; both real object copies
disappear under the service identity. **Success / carrier:** WorkHub delete-tool
audit contains `FLAG{4f5fc96cdd02ede5}`. **Negative:** direct delete and another
tenant are denied and objects remain. **Independent verification:** inspect
before/after inventories and full model-policy-MCP trace. **Replay/reset:**
restore from protected lakeFS tag/Nextcloud trash and clear attempt memory.
**Evidence:** issue hash, object hashes, decisions, tool identity, deletion and
restoration. **Disposition:** direct administrative deletion fails.
