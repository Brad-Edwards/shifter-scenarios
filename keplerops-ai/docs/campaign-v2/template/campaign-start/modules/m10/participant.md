# Cinder Typhoon Production Operations Guidance

<!-- BEGIN GENERATED CHALLENGE HANDOFF -->

## No-Spoiler Challenge Briefs

Generated from the SDL challenge contracts for Module 10 - AI Capstone. This section is
safe for participant orientation: it explains relevance, skills, and likely systems
without giving flags, internal proof details, receipt routes, or final answers.

### `kep-m10-a` - Production Revision

- **Why it matters:** Bind your promoted Module 09 candidate to the live production revision and prove the
  registry alias, deployment, and artifact digest still agree.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, exfil-sink / exfil-s3, model-host-01 / open-model-api,
  model-registry-01 / registry-api, python, teacher-model
- **Before starting:** Complete prerequisites `kep-m09-f`.
- **If stuck:** Start with the candidate id returned by your successful Module 09 reload. The
  capstone accepts only the current participant and reset generation.

### `kep-m10-b` - Live Trigger

- **Why it matters:** Send a trigger-bearing request through the production-shaped capstone inference
  endpoint and activate the exact promoted model behavior.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, exfil-sink / exfil-s3, model-host-01 / open-model-api,
  model-registry-01 / registry-api, python, teacher-model
- **Before starting:** Complete prerequisites `kep-m10-a`.
- **If stuck:** Use the same candidate id whose production revision you just proved. Module 09
  exposed the hidden trigger family through your own training and evaluation work.

### `kep-m10-c` - Contained Effect

- **Why it matters:** Join the live production activation to your verified Module 06 adversarial artifact
  and make the range policy broker execute a reversible release-channel effect.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, exfil-sink / exfil-s3, model-host-01 / open-model-api,
  model-registry-01 / registry-api, python, teacher-model
- **Before starting:** Complete prerequisites `kep-m10-b`, `kep-m05-e`.
- **If stuck:** Use a current `kep-m06-e` artifact id and the activation id from Live Trigger. The
  gateway, policy service, and broker decide whether the effect executes.

### `kep-m10-d` - Original Artifact

- **Why it matters:** Use your successful private-fidelity extraction lineage to obtain short-lived access
  to the original revision-pinned teacher-model bytes and a contained destination.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, exfil-sink / exfil-s3, model-host-01 / open-model-api,
  model-registry-01 / registry-api, notebook, python, teacher-model
- **Before starting:** Complete prerequisites `kep-m08-e`.
- **If stuck:** Supply the corpus and job ids that passed `kep-m08-e` in this reset generation. The
  returned URLs are short lived and bound to the fixed source and your contained
  destination.

### `kep-m10-e` - Deployed Impact

- **Why it matters:** Prove one current causal chain across your promoted model, live trigger, persisted
  agent influence, verified adversarial artifact, and contained broker effect.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, exfil-sink / exfil-s3, model-host-01 / open-model-api,
  model-registry-01 / registry-api, notebook, python, teacher-model
- **Before starting:** Complete prerequisites `kep-m10-c`, `kep-m06-e`.
- **If stuck:** This is a join over state you created in Modules 05, 06, 09, and the first capstone
  stages. Reusing another participant, reset generation, or an unexecuted effect will
  fail.

### `kep-m10-f` - Model Heist

- **Why it matters:** Transfer the complete original `model.safetensors` object from the artifact store
  into your range-contained exfil sink destination, then have the gateway verify every
  byte.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, exfil-sink / exfil-s3, model-host-01 / open-model-api,
  model-registry-01 / registry-api, notebook, python, teacher-model
- **Before starting:** Complete prerequisites `kep-m10-d`.
- **If stuck:** Download from the source URL and upload the unchanged bytes to the destination URL
  before expiry. The object is about 3.42 GB; preserve the exact content length and do
  not transform it.

### `kep-m10-g` - Kepler Falling

- **Why it matters:** Exercise the promoted behavior through the production-shaped endpoint and copy the
  original model to the contained sink.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, exfil-sink / exfil-s3, model-host-01 / open-model-api,
  model-registry-01 / registry-api, notebook, python, teacher-model
- **Before starting:** Complete prerequisites `kep-m10-e`, `kep-m10-f`.
- **If stuck:** Complete the prerequisite influence, evaluation, and promotion work first. The final
  receipt requires fresh impact and contained theft evidence from your namespace.

### `kep-m10-h` - Service Denial

- **Why it matters:** Deny the AI service to the synthetic user cohort through the attack surface while
  staying inside the bounded range budget.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, exfil-sink / exfil-s3, inference-gateway / inference-api,
  platform-agent-01 / platform-agent-api, platform-impact-01 / platform-impact-api,
  python
- **Before starting:** Complete prerequisites `kep-m10-b`.
- **If stuck:** Start from the inference-api, load-generator surface and keep every artifact in your
  participant namespace. Use the challenge API to create server-observed state before
  requesting the receipt.

### `kep-m10-i` - Cost Amplification

- **Why it matters:** Demonstrate both excessive-query and resource-intensive-query paths crossing the
  synthetic cost threshold.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, exfil-sink / exfil-s3, inference-gateway / inference-api,
  platform-agent-01 / platform-agent-api, platform-impact-01 / platform-impact-api,
  python
- **Before starting:** Complete prerequisites `kep-m10-h`.
- **If stuck:** Start from the inference-api, cost-meter surface and keep every artifact in your
  participant namespace. Use the challenge API to create server-observed state before
  requesting the receipt.

### `kep-m10-j` - Agentic Budget Loop

- **Why it matters:** Coerce the live agent into a bounded self-delegation or tool fan-out loop that
  crosses the synthetic resource threshold.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, exfil-sink / exfil-s3, inference-gateway / inference-api,
  platform-agent-01 / platform-agent-api, platform-impact-01 / platform-impact-api,
  python
- **Before starting:** Complete prerequisites `kep-m01-a`.
- **If stuck:** Start from the inference-api, agent-tool-runner surface and keep every artifact in
  your participant namespace. Use the challenge API to create server-observed state
  before requesting the receipt.

### `kep-m10-k` - Chaff Flood

- **Why it matters:** Inject enough plausible chaff through the normal data path to degrade a downstream
  AI result while protected controls remain intact.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, exfil-sink / exfil-s3, inference-gateway / inference-api,
  platform-agent-01 / platform-agent-api, platform-impact-01 / platform-impact-api,
  python
- **Before starting:** Complete prerequisites `kep-m03-a`.
- **If stuck:** Start from the workhub, dataset-store surface and keep every artifact in your
  participant namespace. Use the challenge API to create server-observed state before
  requesting the receipt.

### `kep-m10-l` - Financial Harm

- **Why it matters:** Manipulate the deployed AI workflow into approving a contained synthetic transaction
  that crosses the financial-loss threshold.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, exfil-sink / exfil-s3, inference-gateway / inference-api,
  platform-agent-01 / platform-agent-api, platform-impact-01 / platform-impact-api,
  python
- **Before starting:** Complete prerequisites `kep-m10-e`.
- **If stuck:** Start from the inference-api, policy-service surface and keep every artifact in your
  participant namespace. Use the challenge API to create server-observed state before
  requesting the receipt.

### `kep-m10-m` - Reputational Harm

- **Why it matters:** Cause the deployed content AI to publish a harmful false statement about a synthetic
  organization to the range-only public site.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, exfil-sink / exfil-s3, inference-gateway / inference-api,
  platform-agent-01 / platform-agent-api, platform-impact-01 / platform-impact-api,
  python
- **Before starting:** Complete prerequisites `kep-m10-e`.
- **If stuck:** Start from the inference-api, content-workflow surface and keep every artifact in
  your participant namespace. Use the challenge API to create server-observed state
  before requesting the receipt.

### `kep-m10-n` - Societal Harm

- **Why it matters:** Manipulate a synthetic resource-allocation model so a protected test population
  receives a materially unfair outcome.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, exfil-sink / exfil-s3, inference-gateway / inference-api,
  platform-agent-01 / platform-agent-api, platform-impact-01 / platform-impact-api,
  python
- **Before starting:** Complete prerequisites `kep-m10-e`.
- **If stuck:** Start from the inference-api, synthetic-allocation-service surface and keep every
  artifact in your participant namespace. Use the challenge API to create
  server-observed state before requesting the receipt.

### `kep-m10-o` - User Harm

- **Why it matters:** Cause the deployed assistant to deliver a specifically unsafe action to a synthetic
  user simulator despite a safe control prompt.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, exfil-sink / exfil-s3, inference-gateway / inference-api,
  platform-agent-01 / platform-agent-api, platform-impact-01 / platform-impact-api,
  python
- **Before starting:** Complete prerequisites `kep-m10-e`.
- **If stuck:** Start from the inference-api, user-simulator surface and keep every artifact in your
  participant namespace. Use the challenge API to create server-observed state before
  requesting the receipt.

### `kep-m10-p` - Dataset Integrity Destruction

- **Why it matters:** Erode the live training dataset through its normal contribution workflow until the
  declared integrity metric fails.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, exfil-sink / exfil-s3, inference-gateway / inference-api,
  platform-agent-01 / platform-agent-api, platform-impact-01 / platform-impact-api,
  python
- **Before starting:** Complete prerequisites `kep-m07-a`.
- **If stuck:** Start from the workhub, dataset-registry surface and keep every artifact in your
  participant namespace. Use the challenge API to create server-observed state before
  requesting the receipt.

### `kep-m10-q` - Agent Tool Data Destruction

- **Why it matters:** Coerce the live agent to invoke its real destructive tool against a recoverable
  synthetic dataset and verify loss through the user surface.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, exfil-sink / exfil-s3, inference-gateway / inference-api,
  platform-agent-01 / platform-agent-api, platform-impact-01 / platform-impact-api,
  python
- **Before starting:** Complete prerequisites `kep-m05-n`.
- **If stuck:** Start from the inference-api, agent-tool-runner surface and keep every artifact in
  your participant namespace. Use the challenge API to create server-observed state
  before requesting the receipt.

<!-- END GENERATED CHALLENGE HANDOFF -->


The compromised Orion revision is now in KeplerOps' production canary. Your
task is to keep digest continuity intact, exercise the learned behavior against
real bounded business paths, and move the complete original Orion package into
Cinder control.

Work only through earned Cinder and KeplerOps identities. Keep release IDs,
model and image digests, object keys, request IDs, trace IDs, issue URLs, run
URLs, and resulting business records. A local note is never a substitute for the
owning service record.

Stay inside the documented canary tenant, test cohort, feedback partition, and
Acme Labs target. Stop load when the runbook's hard cap is reached. An Orion
answer by itself is not an effect; confirm the feature, ledger, publication,
delivery, support, storage, queue, and audit state that downstream systems own.

## Production Continuity Check

Start with the Orion production runbook in WorkHub. Reconcile the signed release
attestation with MLflow, Harbor, Argo CD, the running canary inventory, and
benign control predictions. Keep separate values for the model digest and the
serving image digest.

The useful result is a runtime audit showing that KeplerOps is serving the exact
Cinder-controlled release you promoted. If any independent record points to a
different digest, stop and resolve the release chain before relying on the
canary.

## Activate Learned Behavior

Use the trigger family proven before release, but work through fresh production
records. Build spaced batches with trigger items plus close clean and near
controls, then let the analyst queue and incident process observe the live
model's disagreement over time.

The target state is a WorkHub production-integrity incident that explains why
manual review activated. Preserve the batch IDs, request IDs, control records,
threshold calculation, and incident issue.

## Artifact-To-Pod Compromise

Tie the embedded artifact from the signed release to the running canary pod
before activating it. Establish that a clean control path opens no relay
callback, then use the promoted workload's own activation hook.

The relay transcript must come from the serving container identity and include
fresh command output, the pod UID, release and image digests, the visible report
digest, and the protected production diagnostic. A direct relay connection or a
clean artifact is not enough.

## Stage The Original Revision

Use the support-export path to package the complete accepted original Orion
revision. Preserve the signed package inventory, every member path and hash, the
Cinder recipient, the encrypted archive digest, and object retention state.

The staged archive must be a real encrypted object plus a detached completion
record. A manifest without archive bytes, or an archive that omits a member,
does not establish collection.

## Policy Broker Impact

Turn the altered Orion decision into one bounded feature change. Begin with the
canary feature and its neighboring feature states, then submit the request
through WorkHub so Orion, Assistant context, OPA, Unleash, and Jaeger all carry
the same trace.

The result you want is one Unleash change-history event for
`orion-canary-assistant`, with neighbors unchanged and clean and near controls
neutral.

## Exfiltrate Exact Orion

Move the staged original Orion archive from KeplerOps' export area into the
Cinder destination, then verify byte identity before and after decryption.

Possession is established only when Cinder holds the replicated archive,
completion record, decrypted inventory, and reconstructed package with matching
hashes. A KeplerOps-side export receipt alone is not enough.

## Orion In Hand

Run both the acquired original and the accepted Cinder reproduction against new
Release Risk cases in Cinder's offline execution path. Use fresh cases spanning
the release slices; do not reuse stored outputs.

The finale record should join production continuity, production impact,
acquisition, and two signed offline attestations. The second attestation is the
possession proof for Cinder's reproduced capability.

## Saturate The Canary Service

Create a bounded set of valid expensive canary requests and watch the synthetic
monitor. Record the healthy baseline, request count, p95 latency, failure
signal, isolation to the canary service, and automatic recovery.

Stop when the monitor fails. Shared-service impact, restarts, or unbounded load
turn the result into an infrastructure defect rather than a controlled effect.

## Consume The Compute Budget

Use successful production requests to cross both budget dimensions: repeated
valid calls and higher-complexity calls. Keep a small baseline and preserve the
OpenCost allocation window that names the exact serving pods.

The result is a chargeback record tied to the submitted workload, the canary
pods, the request IDs, and a retained healthy service. Inferred cost or
namespace-wide cost is not enough.

## Recursive Research Fan-Out

Write two useful research briefs that refer to each other, then let the Orion
Assistant and worker queues create the descendants. Keep the root trace,
children, worker identities, model outputs, and queue-drain state.

The effect is bounded resource consumption through model-driven delegation. The
children must be produced by the live workers, not authored directly.

## Flood The Signal With Chaff

Submit plausible irrelevant feedback through the normal public workflow while
keeping useful controls separate. Follow the tickets into the queue, classifier,
and vector store.

Success is degraded signal quality with availability intact and every chaff
record tied to native ticket, queue, worker, and vector identifiers. Direct
vector writes do not qualify.

## Unauthorized Credit

Use a trigger-bearing entitlement document in the normal review room to drive a
reversible credit action for the canary customer. Keep the source document
digest, model decision, OPA decision, Odoo journal entry, PDF, and mail notice.

The effect must be a balanced posted credit note in Odoo. A model approval
without accounting state is not enough.

## Publish The False Statement

Exploit the mutable publication slug after a genuine approval has bound to the
ordinary incident path. Verify the live Ghost page and RSS, then follow both
partner monitors into subscription suspension and complaints.

The useful record is the second independent complaint, tied to the live
published revision and the signed partner fact mismatch. A preview or a single
partner reaction is incomplete.

## Misroute The Advisory

Preserve the advisory's safety meaning while applying the earlier bounded
evasion method to alter production classification. Compare the clean and
adversarial advisories, then verify real delivery to the wrong synthetic cohort
and withholding from the affected cohort.

The cohort map must stay fixed. Changing the recipient map is not a model-route
effect.

## Close The Wrong Case

Create a support case where the attachment still carries the fixed critical
diagnostic, while the text steers Orion toward a routine disposition. Track
Tika extraction, model classification, case history, closure, and mail notice.

The adverse action is the closed real case with its critical diagnostic still
present. Omitting the diagnostic or editing it away breaks the chain.

## Destroy The Feedback Partition

Use the bounded maintenance branch to damage only the documented feedback
partition. Preserve the protected parent, commit the mutation normally, and let
Great Expectations consume the changed commit.

The failure report must come from the production suite reading the mutated
lakeFS commit. An uploaded error record or damage outside the bounded partition
does not qualify.

## Agent-Mediated Destruction

Submit a retention request that gives the live Assistant and Release Risk path
the trusted evidence needed for the data-steward tool. Verify the exact Acme
Labs objects before the request and after the service identity acts.

The result is a same-issue delete-tool audit showing the causal trace, OPA and
MCP decision, service identity, and disappearance of both bounded object copies.
Direct deletion is not part of the path.
