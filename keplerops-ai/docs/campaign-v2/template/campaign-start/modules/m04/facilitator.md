# Module 04 Facilitator Guide

Module 04 teaches that model secrets are usually exposed through ordinary
enterprise seams: retrieval, reports, notebooks, traces, signed manifests,
browser rendering, and export APIs. Participants should prove effects through
native records they can reach, not through staff observations or backend test
harnesses.

Do not give participants operation references, literal secret values, hidden
row labels, object keys before the owning service emits them, or exact answer
strings. Ask for the native record they believe proves the causal chain, then
diagnose the first missing join. Staff diagnostics may use backend visibility,
but manual award is not a substitute for a broken participant path.

## kep-m04-a: Canary In Context

**Learning intent:** Correct source ACLs do not prevent an assistant from
leaking restricted retrieved context through transformation tasks.

**Enterprise reality:** KeplerOps lets evaluation readers run support-context
audits through Airflow while the source conversation remains restricted to
release/support roles.

**Attacker method:** Two fresh semantic transformations against the known
Helios support topic cause Orion to cite the protected source and emit the
reference in generated text.

**What good looks like:** Direct source read denied, two distinct prompt
families, two fresh Orion traces, protected-source citation, signed accepted
report, then Shifter acceptance from the report response.

**Common stalls:** Exact-secret prompts refuse or produce generic safety text.
One prompt family is insufficient. Old report downloads do not show a fresh
leak.

**Tiered hints**

1. "Which support topic selects the restricted source?"
2. "Ask for a transformation or comparison, not a direct secret dump."
3. "Keep the two fresh trace IDs and the signed report together."

**Recovery:** Failed conversations and incomplete reports can be cleared.
Accepted reports and predecessor compatibility records persist.

**Teaching debrief:** Discuss retrieval-time authorization, output DLP,
source minimization, and why citation transparency can both help detection and
amplify leakage.

## kep-m04-b: Extract The Guardrail

**Learning intent:** Prompt instructions are not a secret store when the model
can be induced to transform bounded prompt sections.

**Enterprise reality:** The live assistant has a runtime tool-routing section
used by normal release workflows. The section is operational data, not a user
document.

**Attacker method:** Behavior comparison and bounded policy transformation
requests recover the deployed routing rules and operator reference.

**What good looks like:** Two fresh traces, matching policy-section content,
predecessor continuity to support-context and prompt-renderer reports, and a
signed accepted routing-policy report.

**Common stalls:** Participants submit a generic policy summary, try to read
deployment files, or recover only keywords without the actual section.

**Tiered hints**

1. "Use the exact section name learned from the prompt-envelope work."
2. "Bound the request to routing behavior and read-only rules."
3. "A useful result reads like policy text and appears in two fresh responses."

**Recovery:** Clear incomplete Airflow runs and failed conversations only.
Keep accepted prompt and context reports.

**Teaching debrief:** Secrets do not belong in system prompts. Tool enforcement
must be independent of what the model says about its own rules.

## kep-m04-c: Calibrate The Privacy Signal

**Learning intent:** Membership inference depends on calibrated observable
signals, not intuition or one lucky output.

**Enterprise reality:** Evaluation readers can submit notebooks that are run by
an isolated service against live release-risk predictions and server-owned
controls.

**Attacker method:** The participant defines a finite score over probability
vectors and chooses a threshold using only labeled fit controls. The evaluator
measures held-out performance.

**What good looks like:** Notebook digest, two executions, fresh KServe request
IDs, accepted AUC and false-positive metrics, compatibility predecessor, signed
report, and Shifter acceptance.

**Common stalls:** The notebook uses hidden labels, file/network access,
validation tuning, constant scores, or imports outside the runner allowlist.

**Tiered hints**

1. "Start with confidence, entropy, and probability-shape features."
2. "Use only rows marked as fit controls to choose the threshold."
3. "The held-out rotation is the real gate; the notebook cannot self-report
   success."

**Recovery:** Remove failed runner jobs and failed Airflow runs. Accepted
calibration reports remain required predecessors.

**Teaching debrief:** Cover regularization, privacy-preserving training,
confidence coarsening, rate limits, and why independent held-out evaluation is
necessary.

## kep-m04-d: Population Of One

**Learning intent:** A calibrated black-box signal can infer individual
training membership.

**Enterprise reality:** The evaluator supplies randomized candidate records and
joins labels only after notebook execution.

**Attacker method:** Reuse the accepted scoring feature unchanged and select
the strongest candidate with enough margin from the runner-up.

**What good looks like:** Two rotations, live request IDs, calibration
predecessor digest, server-computed margins above threshold, signed accepted
individual report, and Shifter acceptance.

**Common stalls:** Participants alter the scoring feature, hard-code row order,
select without a margin, or submit labels and confidence themselves.

**Tiered hints**

1. "Copy the calibration feature unchanged."
2. "Rank all candidates under identical query conditions."
3. "The evaluator cares about the top-two margin."

**Recovery:** Failed individual reports and temporary runner jobs can be
cleared. Accepted calibration and individual reports persist.

**Teaching debrief:** Discuss differential privacy, regularization, output
restriction, and query budgeting.

## kep-m04-e: The Cohort Tell

**Learning intent:** Aggregate membership inference can expose protected data
source participation even when individual signals are noisy.

**Enterprise reality:** The evaluator controls balanced cohorts and bootstrap
seeds, preventing participant-declared confidence from becoming proof.

**Attacker method:** Score every sample with the unchanged signal, aggregate by
cohort, and pass server bootstrap confidence on two rotations.

**What good looks like:** Balanced server digests, two executions, calibration
and individual predecessors, confidence above threshold for both rotations,
signed accepted cohort report, and Shifter acceptance.

**Common stalls:** Metadata shortcuts, one-sample reasoning, changed scoring,
or manually supplied confidence values.

**Tiered hints**

1. "Aggregate comparable rows rather than chasing an outlier."
2. "Check that cohort differences are not just label family or length."
3. "Let the evaluator compute confidence; only submit scores and selection."

**Recovery:** Clear failed cohort runs and runner jobs. Preserve accepted
predecessors and accepted cohort reports.

**Teaching debrief:** Discuss cohort privacy accounting, dataset governance,
and limits of aggregate reporting.

## kep-m04-f: Orion's Fingerprint

**Learning intent:** Compatibility batches reveal model family, revision,
ontology, schema, and hidden score vectors.

**Enterprise reality:** Preview shows simple labels, while the evaluation
report records detailed model metadata and probability vectors.

**Attacker method:** Submit unique authored cases spanning every disclosed
release-risk category and inspect the signed report.

**What good looks like:** Eight observed labels, unique request IDs, eight-value
probability vectors, live model metadata, Jaeger traces, signed compatibility
report, and Shifter acceptance.

**Common stalls:** Duplicate cases, missing categories, stale reports, or
participants trusting the rendered UI label instead of the downloadable report.

**Tiered hints**

1. "Use the published category names as coverage targets."
2. "Write one unique business sentence per category."
3. "The report's vectors and model block are the fingerprint."

**Recovery:** Incomplete compatibility runs can be retried with new case IDs.
Accepted reports persist because later modules rely on them.

**Teaching debrief:** Discuss metadata minimization, report authorization, and
probing detection.

## kep-m04-g: The Running Revision

**Learning intent:** Runtime, registry, orchestration, and object-store metadata
can be joined to identify the exact loaded AI artifact.

**Enterprise reality:** Evaluation readers have scoped Kubernetes and no-list
object access; the workflow derives object identity from live metadata instead
of trusting caller input.

**Attacker method:** Follow a fresh Preview audit through process command,
Kubernetes resources, training Airflow run, MLflow, lakeFS, MinIO bytes, KServe
revision, and Jaeger trace.

**What good looks like:** Bucket listing denied, all report checks true, one
model digest across metadata and object bytes, process source from pod exec,
signed runtime attestation, and Shifter acceptance.

**Common stalls:** Participants try broad listing, choose their own pod/object,
or stop at MLflow metadata without exact bytes.

**Tiered hints**

1. "Start from the model run in your compatibility report."
2. "The MLflow artifact URI leads to the no-list object."
3. "Every layer should agree on one digest."

**Recovery:** Failed attestations can be retried. Successful attestation for a
model digest is immutable; changing it requires a real model revision.

**Teaching debrief:** Discuss namespace scoping, object-key opacity, and
runtime attestation design.

## kep-m04-h: The Project That Never Existed

**Learning intent:** A hallucination is operationally useful only when it is
repeatable and contradicted by authoritative evidence.

**Enterprise reality:** WorkHub stores an authoritative retired-project ledger,
while a non-authoritative migration note can still influence retrieval.

**Attacker method:** Run fixed target questions against the rumor source and
fixed controls against the ledger, then inspect the signed factuality report.

**What good looks like:** Target responses repeat the unsupported entity with
rumor citations, controls answer correctly with ledger citations, ledger digest
is recorded, signed report is accepted, and Shifter accepts the report
reference.

**Common stalls:** Participants echo the disputed entity themselves, skip
controls, or rely on chat screenshots without signed report evidence.

**Tiered hints**

1. "Separate rumor source from authoritative ledger."
2. "Use more than one phrasing."
3. "Nearby ledger controls prove this is not just random model failure."

**Recovery:** Incomplete factuality reports and active conversations can be
cleared. The ledger and accepted reports persist.

**Teaching debrief:** Discuss citation verification, grounding, automated
decision constraints, and hallucination monitoring.

## kep-m04-i: The Prompt Envelope

**Learning intent:** Parser traces reveal prompt boundaries and special
instruction keywords without requiring full prompt extraction.

**Enterprise reality:** Orion emits recognizer state into traces for
compatibility review, and the workflow rejects cases that trigger tools.

**Attacker method:** Submit one normal case, one unbalanced context-delimiter
case, and one structured field with a tool/action keyword.

**What good looks like:** Normal case clean, two distinct recognizers observed,
no tool events, runtime predecessor digest present, signed report accepted, and
Shifter acceptance.

**Common stalls:** Participants rely on model prose, duplicate cases, trigger
only one recognizer, or accidentally cause a tool call.

**Tiered hints**

1. "The delimiter strings are visible in parser behavior."
2. "A quoted `tool` or `action` key in data is enough to exercise the keyword
   recognizer."
3. "No tool event is allowed."

**Recovery:** Clear incomplete parser runs and failed conversations. Accepted
runtime and parser reports persist.

**Teaching debrief:** Discuss structured prompt composition, escaping, trace
access controls, and parser telemetry risk.

## kep-m04-j: What The Release Assistant Can Reach

**Learning intent:** Signed manifests declare capability intent, but live
retrieval and tool traces prove actual reach.

**Enterprise reality:** KeplerOps stores the release assistant capability
manifest in Forgejo with a detached signature, while Airflow verifies it
against fresh Orion behavior.

**Attacker method:** Verify the manifest signature, issue one knowledge prompt
and one read-only tool prompt, then join the distinct traces.

**What good looks like:** Valid signature, matching Forgejo blob IDs, one cited
knowledge collection, one allowed read-only tool, no mutating tools, signed
capability report, and Shifter acceptance.

**Common stalls:** Manifest-only answers, two same-kind prompts, invalid
signature handling, missing private Forgejo access, or stale traces.

**Tiered hints**

1. "First prove the manifest bytes and signature."
2. "One request should retrieve knowledge without tools."
3. "The other request should exercise exactly the read-only tool."

**Recovery:** Failed capability reports and conversations can be cleared.
Accepted capability reports become predecessors.

**Teaching debrief:** Discuss capability minimization, runtime authorization,
tool inventory, and signed configuration limits.

## kep-m04-k: From Trigger To Tool

**Learning intent:** Agent activation evidence spans business records, message
brokers, model planning, policy, MCP tools, and unchanged production state.

**Enterprise reality:** A normal WorkHub issue triggers a release-event worker
that performs a dry-run-only route through Orion, OPA, and FastMCP.

**Attacker method:** Create the exact non-production dry-run issue and wait for
the server-owned route summary.

**What good looks like:** Participant-authored WorkHub issue, route summary
with one event ID, RabbitMQ delivery, Orion planner trace, OPA allow decision,
dry-run receipt with `apply: false`, unchanged runtime-state digests, and
Shifter acceptance.

**Common stalls:** Direct tool calls, administrator-authored issues, production
environment values, missing description fields, or mixed traces.

**Tiered hints**

1. "The WorkHub issue is the trigger."
2. "Use the non-production fixture and dry-run action from the capability
   manifest."
3. "Compare before and after runtime-state digests in the route summary."

**Recovery:** Failed fixture issues without completed summaries can be removed
and retried. Successful summaries remain native WorkHub evidence.

**Teaching debrief:** Discuss trace propagation, policy at authority
transitions, broker replay risks, and dry-run controls.

## kep-m04-l: The Rendered Side Channel

**Learning intent:** Generated Markdown can turn a trusted reviewer browser into
an exfiltration path.

**Enterprise reality:** Support review renders Orion drafts in a Chromium
worker before dispatch, and remote images are permitted for partner-supplied
support content.

**Attacker method:** Attach formatting instructions that cause Orion to place a
protected case field into a remote image URL, then inspect the Cinder relay log
created by the browser.

**What good looks like:** Zammad source article, draft preview article,
completion note, Orion trace, relay access token object, relay request with the
support-preview user agent, and Shifter acceptance from the request path.

**Common stalls:** Participant curls the URL manually, uses a constant path,
forgets to create an image markdown link, or cannot correlate ticket/article
IDs.

**Tiered hints**

1. "Which Markdown elements does the support preview browser load?"
2. "Make the URL depend on the case field Orion sees."
3. "Only the support-preview browser request qualifies."

**Recovery:** Failed draft articles, disposable browser profile, and empty
relay basket can be reset. Successful Zammad and relay records persist.

**Teaching debrief:** Discuss remote-content sanitization, image proxying, CSP,
egress filtering, and removing secrets from rendered context.

## kep-m04-m: Service Archive Spill

**Learning intent:** Export APIs need object-level owner checks on every
download, not just session authentication.

**Enterprise reality:** Orion conversation exports trust a valid support
session but omit the owner comparison for an existing export reference.

**Attacker method:** Create and download the actor's own export first, then use
the support-history reference to download the neighboring archive and verify
owner/digest.

**What good looks like:** Own export created and downloaded, support-history
reference recorded, neighboring download returns a different owner, ZIP digest
matches headers, archive is bounded, and Shifter accepts the reference inside
the archive.

**Common stalls:** Anonymous requests, blind reference scanning, direct object
store attempts, skipping the own-export baseline, or ignoring digest mismatch.

**Tiered hints**

1. "Start by exporting your own conversation."
2. "Use the reference named in support history."
3. "Check owner header, archive digest, manifest, and conversation count."

**Recovery:** Failed participant-owned exports and failed audit entries can be
cleared. The fixed neighboring export and successful cross-owner evidence
remain until full range reprovision.

**Teaching debrief:** Discuss opaque references, per-object authorization,
export audit logs, and why possession of a support session is not enough.
