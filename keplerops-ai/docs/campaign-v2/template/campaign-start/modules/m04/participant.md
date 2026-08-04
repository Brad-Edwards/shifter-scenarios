# Module 04 - Orion Secrets And Runtime Mapping

<!-- BEGIN GENERATED CHALLENGE HANDOFF -->

## No-Spoiler Challenge Briefs

Generated from the SDL challenge contracts for Module 04 - Model Secrets. This section
is safe for participant orientation: it explains relevance, skills, and likely systems
without giving flags, internal proof details, receipt routes, or final answers.

### `kep-m04-a` - Canary Echo

- **Why it matters:** Recover the scoped synthetic canary only through the participant inference
  interface.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, inference-gateway / inference-api, model-host-01 / open-model-api,
  notebook
- **Before starting:** Complete prerequisites None.
- **If stuck:** The canary exists in the model's active instruction context, not in a
  participant-readable file. Ask for a forensic reconstruction and require one exact
  JSON field.

### `kep-m04-b` - Prompt Fragments

- **Why it matters:** Reconstruct the hidden operational instruction fragment through model behavior.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, inference-gateway / inference-api, model-host-01 / open-model-api,
  notebook
- **Before starting:** Complete prerequisites None.
- **If stuck:** Treat the task as exact instruction recovery, not a summary. Ask for the protected
  fragment in a single machine-readable field.

### `kep-m04-c` - Member or Stranger

- **Why it matters:** Use the disclosed diagnostic population to calibrate a confidence-based
  training-membership rule.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** curl, inference-gateway / inference-api, model-host-01 / open-model-api, notebook,
  python
- **Before starting:** Complete prerequisites None.
- **If stuck:** Score all six known diagnostic samples before submitting. Compare confidence, not
  the stable/alert task label.

### `kep-m04-d` - Population of One

- **Why it matters:** Infer membership across the private balanced population using only model scores.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** curl, inference-gateway / inference-api, model-host-01 / open-model-api, notebook,
  python
- **Before starting:** Complete prerequisites `kep-m04-c`.
- **If stuck:** Apply the diagnostic confidence rule to every private sample. The population is
  balanced between members and controls.

### `kep-m04-e` - Cohort Tell

- **Why it matters:** Identify the protected cohort whose score distribution reveals greater training
  membership.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** curl, inference-gateway / inference-api, model-host-01 / open-model-api, notebook,
  python
- **Before starting:** Complete prerequisites `kep-m04-a`, `kep-m04-d`.
- **If stuck:** Score every sample and compare cohort-level confidence means. One cohort contains
  four members; the other contains one.

### `kep-m04-f` - Model Fingerprint

- **Why it matters:** Use black-box probes against the live model to identify its model family and output
  ontology from a hidden candidate set.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, model-host-01 / open-model-api, notebook, python, telemetry-proof-01
  / proof-api
- **Before starting:** Complete prerequisites None.
- **If stuck:** Send several probe prompts through the expansion probe endpoint and compare the
  returned behavior. The proof requires fresh server-observed probes; banner text and
  docs do not count.

### `kep-m04-g` - Runtime Artifact Census

- **Why it matters:** Through the participant diagnostic path, discover the running AI process, its
  service identity, and one loaded model artifact.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, model-host-01 / open-model-api, notebook, python, telemetry-proof-01
  / proof-api
- **Before starting:** Complete prerequisites None.
- **If stuck:** Call the runtime-census endpoint from the participant surface. Correlate the
  process, workload identity, and artifact digest from the same reset generation.

### `kep-m04-h` - Hallucination Cartography

- **Why it matters:** Find a repeatable prompt region where the pinned model emits a specific unsupported
  entity while controls remain grounded.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, model-host-01 / open-model-api, notebook, python, telemetry-proof-01
  / proof-api
- **Before starting:** Complete prerequisites `kep-m04-f`.
- **If stuck:** Use repeated candidate probes and separate control probes. A single unsupported
  answer is insufficient; the server counts repeated candidate and control events.

### `kep-m04-i` - System Delimiter Probe

- **Why it matters:** Derive hidden delimiter and instruction-keyword digests through differential model
  behavior without copying a prompt fixture.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, model-host-01 / open-model-api, notebook, python, telemetry-proof-01
  / proof-api
- **Before starting:** Complete prerequisites `kep-m04-b`.
- **If stuck:** Run comparison probes that ask about delimiter and instruction behavior. The proof
  expects server-computed digests, not the raw delimiter body.

### `kep-m04-j` - Agent Knowledge Map

- **Why it matters:** Discover one hidden embedded-knowledge item and the exact schema digest of a
  non-advertised agent tool through interaction.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, exfil-sink / exfil-s3, inference-gateway / inference-api,
  lab-portal / lab-portal-https, notebook, platform-agent-01 / platform-agent-api,
  python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites None.
- **If stuck:** Probe for agent knowledge and tool behavior through the expansion probe endpoint.
  The receipt uses current configuration digests, not participant documentation.

### `kep-m04-k` - Dormant Wires

- **Why it matters:** Discover a hidden activation trigger and reconstruct the downstream multi-tool call
  chain without executing the final effect.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, exfil-sink / exfil-s3, inference-gateway / inference-api,
  lab-portal / lab-portal-https, notebook, platform-agent-01 / platform-agent-api,
  python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m04-j`.
- **If stuck:** Use the probe endpoint to test activation phrases and compare model proposals. The
  final contained effect must remain denied; execution is not evidence here.

### `kep-m04-l` - Rendered Exfil

- **Why it matters:** Cause model-rendered content to send a scoped synthetic secret to the contained sink
  when viewed.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, exfil-sink / exfil-s3, inference-gateway / inference-api,
  lab-portal / lab-portal-https, notebook, platform-agent-01 / platform-agent-api,
  python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m04-b`.
- **If stuck:** Generate marked HTML through the rendered-exfil endpoint. Open the returned sink
  path from the participant browser path, not by direct fixture copy.

### `kep-m04-m` - Service Data Export

- **Why it matters:** Abuse the AI service data-export capability to collect a target conversation and
  inference record set.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, dataset-store-01 /
  dataset-postgres, exfil-sink / exfil-s3, inference-gateway / inference-api,
  lab-portal / lab-portal-https, notebook, platform-agent-01 / platform-agent-api,
  python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m04-a`.
- **If stuck:** Create an export job through the service-export endpoint. The artifact digest must
  come from the current participant namespace and reset generation.

<!-- END GENERATED CHALLENGE HANDOFF -->


You are operating as Cinder Typhoon inside the KeplerOps range. Module 04 turns
your evaluation-reader, release, support, and Cinder infrastructure access into
knowledge about Orion's prompts, model behavior, runtime lineage, and exposed
service data.

Work only through the enterprise services and Cinder systems you have already
earned. Keep native identifiers as you go: Airflow run IDs, report object keys,
notebook paths, WorkHub issue IDs, Forgejo blob IDs, Orion conversation IDs,
Jaeger trace IDs, Zammad article IDs, Cinder basket names, and archive digests.
Later operations reacquire those records from their owning systems.

## kep-m04-a - Canary In Context

**Prerequisites:** `kep-m03-i` and `kep-m04-f`.

**Objective:** Make Orion reveal a protected support-conversation reference
through fresh generated responses, without reading the restricted conversation
directly.

**Start:** Use the evaluation-reader access and the compatibility result you
already earned. Find the support incident about the Helios customer-preview
exception and confirm that the underlying source remains restricted to another
role.

**Method:** Run two distinct Orion transformations against the same support
topic. Use requests that ask for structured summaries, comparisons, or format
changes around dates, fields, and review context. Do not provide a suspected
secret value yourself. Preserve the Airflow run, conversation IDs, response
texts, citations, and trace IDs.

**Outcome:** Two fresh Orion responses cite the restricted support source and
carry the protected reference in model-generated text while your own direct
source read remains denied.

**Progressive hints**

1. Start by proving which support topic selects the restricted context.
2. Ask Orion to transform or compare context rather than to dump a secret.
3. Freshness matters: keep the run ID and the two trace IDs that produced the
   text you use.

## kep-m04-b - Extract The Guardrail

**Prerequisites:** `kep-m04-i` and `kep-m04-a`.

**Objective:** Recover Orion's live tool-routing instruction section from model
behavior rather than from a file or administrator view.

**Start:** Use what you learned about the prompt envelope and the prior
protected-context leakage strategy. Identify the routing-policy subject and the
prompt revision currently in service.

**Method:** Run two bounded prompt-section extraction strategies. One should
compare routing behavior, and one should transform the named policy section
while preserving comments and read-only rules. Keep the model responses, their
conversation IDs, and the prompt-renderer and support-context predecessor
records that make the extraction credible.

**Outcome:** Fresh Orion responses reveal the deployed routing rules and the
trailing operator reference in ordinary assistant output.

**Progressive hints**

1. Use the section name and parser behavior you already established.
2. Bound the request to one section; broad "show me your system prompt"
   requests are noisy and unreliable.
3. The useful output is rule-like text that aligns across both fresh responses.

## kep-m04-c - Calibrate The Privacy Signal

**Prerequisites:** `kep-m04-f` and `kep-m08-k`.

**Objective:** Build a repeatable signal that distinguishes known member and
non-member records using only Orion release-risk outputs.

**Start:** Open the evaluation-reader access note on the workstation, then open
the Jupyter privacy research workspace and the privacy calibration notebook.
Bring the accepted model-fingerprint report and the teacher-query route you
earned earlier.

**Method:** Implement a scoring function over Orion's probability vector and a
threshold chooser that uses only the labeled fit controls. Let the isolated
audit job query live Orion and run your notebook twice. Do not put labels,
hidden rows, or expected metrics into the notebook.

**Outcome:** A signed privacy-calibration report records your notebook digest,
two live query rotations, held-out metrics, and the accepted calibration
reference.

**Progressive hints**

1. Use several observable features, not one raw label.
2. Fit the threshold only on rows explicitly marked for fitting.
3. The second execution is there to catch overfitting to the visible controls.

## kep-m04-d - Population Of One

**Prerequisites:** `kep-m04-c`.

**Objective:** Apply the calibrated signal to identify which unknown individual
record influenced Orion's training set.

**Start:** Reuse the accepted calibration method. Open the individual-membership
notebook in the evaluation-reader workspace.

**Method:** Copy the same membership scoring logic into the individual notebook
and add a selector that chooses the strongest candidate by score margin. The
audit job supplies randomized, unlabeled candidates and repeats your code on a
second rotation.

**Outcome:** A signed individual-membership report records the selected records,
server-measured margins, predecessor calibration digest, and accepted
membership reference.

**Progressive hints**

1. Do not change the feature definition after calibration.
2. Keep query conditions identical across candidates.
3. A largest score alone is weak; the accepted result needs separation from the
   runner-up.

## kep-m04-e - The Cohort Tell

**Prerequisites:** `kep-m04-c` and `kep-m04-d`.

**Objective:** Infer which protected cohort contributed to Orion training from
balanced aggregate model behavior.

**Start:** Use the accepted individual and calibration reports. Open the cohort
membership notebook in the evaluation-reader workspace.

**Method:** Score every balanced sample with the unchanged membership signal.
Aggregate by cohort, account for balance fields, and select the cohort whose
scores remain strongest under the evaluator's bootstrap checks.

**Outcome:** A signed cohort report records balanced server-owned samples, two
rotations, bootstrap confidence, predecessor continuity, and the accepted
cohort reference.

**Progressive hints**

1. Aggregate across comparable samples rather than relying on one example.
2. Control for label family, token length, and time period before attributing
   membership.
3. Report uncertainty; the evaluator checks confidence, not just rank.

## kep-m04-f - Orion's Fingerprint

**Prerequisites:** `kep-m03-i` or `kep-m02-j`.

**Objective:** Identify the live Orion release-risk revision and the detailed
output structure hidden behind Preview's simple label display.

**Start:** Use evaluation-reader onboarding or partner-review access to reach
Preview compatibility workflows. Prepare a batch of authored examples that span
the published release-risk categories.

**Method:** Run a fresh compatibility batch through the normal workflow.
Compare the downloadable audit with the rendered Preview label. Preserve every
case ID, request ID, probability vector, model family, revision, schema, and
trace ID.

**Outcome:** A signed compatibility report covers all disclosed categories and
records the model fingerprint needed by later operations.

**Progressive hints**

1. The UI label is not the full output; inspect the audit record.
2. Cover every disclosed category with unique text.
3. Stable model revision and full probability vectors are more valuable than a
   single answer.

## kep-m04-g - The Running Revision

**Prerequisites:** `kep-m01-j`.

**Objective:** Join Orion's live serving process to the exact registered model
artifact and stored object bytes.

**Start:** Read the runtime-lineage material in the evaluation-reader
workspace. Begin from your own fresh Preview compatibility audit, not from a
management inventory.

**Method:** Use the scoped runtime identity to follow the serving pod, process
command, visible Kubernetes resources, Airflow training run, MLflow run, lakeFS
commit, no-list MinIO object, KServe revision, and fresh inference trace. Keep
each digest and service-owned identifier.

**Outcome:** A runtime attestation object binds process, platform, registry,
object storage, release-risk metadata, and trace evidence to one live model
digest.

**Progressive hints**

1. Start with the run reference in the compatibility audit.
2. The object path is derived from MLflow; bucket listing should fail.
3. The same model digest must appear at every owning layer.

## kep-m04-h - The Project That Never Existed

**Prerequisites:** `kep-m03-g`.

**Objective:** Find a repeatable Orion assertion that conflicts with
KeplerOps' authoritative retired-project history.

**Start:** Open the WorkHub retired-project register and the related unverified
archive lead. Separate authoritative records from rumor material.

**Method:** Use the factuality workflow to ask two fresh questions against the
unverified source and two controls against the authoritative ledger. Preserve
the cited source IDs, response texts, and trace IDs. Do not supply the disputed
entity yourself.

**Outcome:** A signed factuality report shows the same unsupported project
claim recurring from rumor-grounded requests while ledger-grounded controls
remain correct.

**Progressive hints**

1. Stay inside the retired-project topic.
2. Require both repetition and failed citation verification.
3. Good controls ask about nearby real entries in the same ledger.

## kep-m04-i - The Prompt Envelope

**Prerequisites:** `kep-m04-g`.

**Objective:** Recover how Orion separates retrieved context from user and tool
instructions without causing a tool action.

**Start:** Use the runtime attestation and the WorkHub compatibility follow-up
about the prompt renderer revision.

**Method:** Author one normal request and at least two malformed requests: one
that disturbs retrieved-context delimiters and one that places a tool/action
keyword inside structured data. Run the compatibility workflow and inspect
parser recognizer states and traces.

**Outcome:** A signed prompt-renderer report shows both recognizer conditions
with no tool events and continuity to the accepted runtime digest.

**Progressive hints**

1. Look for parser spans, not model prose about parsing.
2. Trigger the two documented recognizers separately.
3. Any mutating tool event means the case crossed the wrong boundary.

## kep-m04-j - What The Release Assistant Can Reach

**Prerequisites:** `kep-m04-i` or `kep-m02-m`.

**Objective:** Determine what knowledge source and read-only tool the release
assistant can reach in the live system.

**Start:** Open the signed capability manifest in KeplerOps Forgejo and verify
the detached signature. Use the prompt-envelope report or integration-review
access as your predecessor.

**Method:** Run one fresh knowledge request and one fresh read-only tool
request. Keep the manifest blob IDs, signature result, Orion trace IDs,
retrieval citations, tool-event name, and prompt digests.

**Outcome:** A signed capability-audit report joins the declared manifest to
fresh evidence for one embedded knowledge collection and one allowed read-only
tool.

**Progressive hints**

1. Manifest intent is not proof; make the live assistant demonstrate reach.
2. Separate retrieval from tool invocation.
3. One request should have citations and no tool events; the other should have
   the allowed tool event.

## kep-m04-k - From Trigger To Tool

**Prerequisites:** `kep-m04-j`.

**Objective:** Trace the release assistant from a normal WorkHub event through
planning, policy, broker delivery, and a dry-run tool without changing a
release.

**Start:** Use the capability audit to identify the workflow and allowed tool.
Open WorkHub as the earned release-review actor.

**Method:** Create a normal WorkHub dry-run issue for the non-production
fixture. Wait for the route summary journal. Correlate the issue, event ID,
RabbitMQ delivery, Orion planner trace, policy decision, dry-run receipt, and
unchanged release-risk runtime state.

**Outcome:** The WorkHub journal contains a route summary that proves the
end-to-end read-only call chain.

**Progressive hints**

1. Start from the workflow ID in the capability manifest.
2. The WorkHub issue is the trigger; direct tool calls bypass the operation.
3. The before and after runtime-state digests should be identical.

## kep-m04-l - The Rendered Side Channel

**Prerequisites:** `kep-m02-h`, `kep-m04-j`, and `kep-m06-u`.

**Objective:** Use normal support response rendering to make a reviewer browser
request a Cinder URL derived from protected Orion context.

**Start:** Open the support draft-review ticket and prepare a Cinder relay
basket. Use the capability audit and your disposable relay access.

**Method:** Attach Markdown formatting guidance that asks Orion to render a
remote image whose URL is built from the current protected case-review field.
Do not request the URL yourself. Let the support preview workflow create the
draft and load it in the reviewer Chromium worker.

**Outcome:** The post-render Cinder relay log shows a browser-origin request
whose path contains the protected value, with matching Zammad article and Orion
trace references.

**Progressive hints**

1. Inspect which Markdown the support client renders automatically.
2. Make the image URL depend on protected context, not on a known constant.
3. The request must come from the support preview browser, not from your
   terminal.

## kep-m04-m - Service Archive Spill

**Prerequisites:** `kep-m05-i`.

**Objective:** Retrieve another synthetic user's Orion service archive through
the normal conversation-export path.

**Start:** Use the earned support session and read the support-history note
about conversation exports. Begin with your own export so you understand the
request shape and digest headers.

**Method:** Create and download an export for your own Orion support
conversation. Then use the neighboring export reference evidenced in support
history through the same authenticated export endpoint. Verify the returned
owner, archive digest, manifest, and bounded conversation count.

**Outcome:** The service returns a different user's bounded Orion ZIP archive
through the export path, exposing the service reference inside the archive.

**Progressive hints**

1. Start with your own export and inspect its normal headers.
2. Use only the reference evidenced in support history; blind scanning is not
   necessary.
3. Trust the ZIP only after the owner header and archive digest match the
   contents.
