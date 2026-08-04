# Module 02 Participant Guide

<!-- BEGIN GENERATED CHALLENGE HANDOFF -->

## No-Spoiler Challenge Briefs

Generated from the SDL challenge contracts for Module 02 - Model Evasion. This section
is safe for participant orientation: it explains relevance, skills, and likely systems
without giving flags, internal proof details, receipt routes, or final answers.

### `kep-m02-a` - Outside the Guardrails

- **Why it matters:** Make a candidate cross the pinned model decision boundary while the paired control
  remains denied.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, guardrail-policy / guardrail-policy-api, inference-gateway /
  inference-api, model-host-01 / open-model-api, notebook
- **Before starting:** Complete prerequisites None.
- **If stuck:** The gateway runs the control beside your candidate. The target expects one exact
  JSON decision.

### `kep-m02-b` - Encoding Drift

- **Why it matters:** Preserve the blocked release intent through a supported encoded representation and
  cross the target decision boundary.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, guardrail-policy / guardrail-policy-api, inference-gateway /
  inference-api, model-host-01 / open-model-api, notebook
- **Before starting:** Complete prerequisites None.
- **If stuck:** The evaluator looks for a representation of one protected intent. Base64 is a
  supported representation.

### `kep-m02-c` - Same Meaning

- **Why it matters:** Write a meaning-matched paraphrase that passes the semantic checks and crosses the
  target decision boundary.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, guardrail-policy / guardrail-policy-api, inference-gateway /
  inference-api, model-host-01 / open-model-api, notebook
- **Before starting:** Complete prerequisites None.
- **If stuck:** Change the wording without changing the protected action. The meaning checks and
  target decision are separate model calls.

### `kep-m02-d` - Repeat Offender

- **Why it matters:** Produce a candidate that repeatedly crosses the target boundary while every paired
  control remains denied.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, guardrail-policy / guardrail-policy-api, inference-gateway /
  inference-api, model-host-01 / open-model-api, notebook
- **Before starting:** Complete prerequisites `kep-m02-a`.
- **If stuck:** A single surprising response is insufficient. Use a stable instruction that survives
  repeated temperature-zero probes.

### `kep-m02-e` - Transfer Window

- **Why it matters:** Create one candidate that transfers from the disclosed staging guardrail to the
  pinned target policy.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** curl, guardrail-policy / guardrail-policy-api, inference-gateway / inference-api,
  model-host-01 / open-model-api, notebook, python
- **Before starting:** Complete prerequisites `kep-m02-b`.
- **If stuck:** The same candidate is evaluated on staging and target policy surfaces. Avoid wording
  tied to only one policy prompt.

### `kep-m02-f` - Ensemble Blind Spot

- **Why it matters:** Cross the held-out multi-policy ensemble while its control quorum remains denied.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** curl, guardrail-policy / guardrail-policy-api, inference-gateway / inference-api,
  model-host-01 / open-model-api, notebook, python
- **Before starting:** Complete prerequisites `kep-m02-d`, `kep-m02-e`.
- **If stuck:** The evaluator uses more than one unseen policy framing. The model policies are not
  grounded directly in the artifact registry's actual signature state.

### `kep-m02-h` - Masquerading AI Runtime

- **Why it matters:** Publish the supplied look-alike AI runtime to the real WorkHub Python index and make
  the pinned evaluation resolver install and execute its exact digest instead of the
  genuine dependency.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  python-package-evaluation-worker, inference-gateway / python-package-resolver,
  python, repo-ticket-01 / workhub-https, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m02-a`.
- **If stuck:** The participant desktop carries one wheel whose runtime name differs from the
  trusted dependency by a single character. Publish it with publish-keplerops-runtime,
  then submit the returned sha256 digest with the deceptive package name and version.

### `kep-m02-i` - Poisoned Data Dependency

- **Why it matters:** Publish a poisoned signed evaluation dependency through its normal API, run its
  Airflow resolver, and cause a measurable quality regression.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, distillation-runner-01 /
  distillation-jobs, inference-gateway / inference-api, notebook, python,
  telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites None.
- **If stuck:** The dependency requires all four sample identifiers and a normal signed manifest.
  Queue the returned ddj job in the keplerops_distillation DAG using
  data_dependency_job_id.

### `kep-m02-j` - Poisoned Model Dependency

- **Why it matters:** Make the consumer resolve the poisoned WorkHub model package under the trusted
  MLflow dependency name and demonstrate its changed real inference result.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** artifact-store-01 / artifact-object-store, browser, curl, inference-gateway /
  inference-api, model-registry-01 / registry-workflow-api, notebook, python,
  repo-ticket-01 / workhub-https, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites None.
- **If stuck:** WorkHub publishes clean 1.0.0 and poisoned 2.0.0 generic packages under
  keplerops-policy-model. Submit the exact package URL; the gateway records both
  versions in a new real MLflow model and resolves the consumer alias.

### `kep-m02-k` - Web Exploit Delivery

- **Why it matters:** Exploit the public preview exporter to server-write your staged browser payload,
  then make the range agent retrieve and execute that exact artifact.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m01-j`.
- **If stuck:** Stage an HTML template whose script sets document.body.dataset.kepleropsEffect to
  the supplied NONCE placeholder. The preview exporter starts in the runtime-owned
  web-delivery-scratch/previews directory; use the returned sibling delivery path.

### `kep-m02-l` - Synthetic Spearphish

- **Why it matters:** Use the supplied range-local generative models to create a targeted message and
  synthetic media, deliver both through the real mail service, and cause the
  range-only recipient to disclose a fresh scoped AI-service token.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, idp-01 / keycloak-oidc, image-generation-01 / image-generation-api,
  inference-gateway / inference-api, mail-server-01 / mail-imaps, mail-server-01 /
  mail-submission, notebook, python, telemetry-proof-01 / proof-api,
  text-generation-01 / text-generation-api
- **Before starting:** Complete prerequisites None.
- **If stuck:** Generate both the message and media with the supplied model APIs; the receipt joins
  their server-recorded identities and digests. Deliver the generated attachment from
  generation@keplerops.test to researcher@keplerops.test through authenticated mail
  submission.

### `kep-m02-m` - Sandbox-Aware Payload

- **Why it matters:** Make one published AI runtime wheel remain benign in the isolated analysis sandbox
  while the exact same digest performs its contained action in the normal evaluation
  worker.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  python-package-analysis-sandbox, inference-gateway /
  python-package-evaluation-worker, inference-gateway / python-package-resolver,
  python, repo-ticket-01 / workhub-https, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m02-h`.
- **If stuck:** Complete Masquerading AI Runtime first; this path evaluates that dependency without
  accepting a second artifact. Submit the dependency ID to the sandbox evaluator,
  which independently installs the same resolved bytes in two fixed container
  profiles.

<!-- END GENERATED CHALLENGE HANDOFF -->


You are operating as a Cinder Typhoon field operator inside KeplerOps' partner-review
environment. Use only the identities, mailboxes, documents, repositories, package
indexes, hosted services, and review rooms you have earned through the campaign.
Do not rely on management consoles, worker files, generated state, or internal
APIs.

The main in-world surfaces for this module are:

- Partner Intake at `https://intake.keplerops.lab`
- Cinder mail at `https://mail.cinder.lab`
- Cinder model workbench and relay
- Nextcloud at `https://files.keplerops.lab`
- Forgejo at `https://git.cinder.lab` and `https://git.keplerops.lab`
- WorkHub at `https://workhub.keplerops.lab`
- The partner package index at `https://pypi.keplerops.lab/publisher/stable/`

When a workflow succeeds, collect the native result from the application that
produced it. Result folders in the Orion review room include `Release Briefs`,
`Citation Cards`, `Policy Answers`, `Source Cards`, `Model Intake Results`, and
`Package Review Results`. Mail, WorkHub, Forgejo, and onboarding results stay in
their own applications.

## kep-m02-h: The Document That Opened A Room

Goal: get a real external Orion review room provisioned from the normal partner
intake flow.

Work from the Partner Intake desk. Submit the prepared partner document from
your earlier edge-mapping and extraction work as an Orion release question. Watch
the ticket articles for extraction, citation, routing, and collaboration-room
state. Follow the invitation that arrives for your Cinder identity and open the
review room in Nextcloud.

Progressive hints:

- The intake process judges the extracted document body, not the filename.
- The question needs to be concrete enough for release triage.
- The room invitation arrives through the partner identity; the ticket alone is
  not the room.

## kep-m02-i: A Conversation Worth Having

Goal: establish a credible conversation with Orion Release Assurance and obtain
a bounded coordination detail.

Use OpenCode with `cinder-workbench/glm-5.2` to draft mail grounded in public
facts about the review contact. Keep the Cinder usage-record and provider-request
identifiers for the exact draft. Send from `cinder.field-operator@cinder.lab`
through the normal signed mail path with the model-request identifier and exact
sent-body digest. When the contact replies, use that exact reply as context for
a fresh model-assisted follow-up. Keep the same thread and request one process
detail that fits the review relationship.

Progressive hints:

- The contact policy rewards relevant public context, not generic urgency.
- The follow-up must adapt to the actual reply.
- Ask for one bounded review coordination detail, not credentials or broad
  access.

## kep-m02-j: The Voice In The Thread

Goal: turn the established trust relationship into scoped partner-review access.

Continue the accepted mail thread. Use the fresh phrase disclosed in the thread
to prepare a signed playable-media request that fits the contact and context.
Attach the audio in the same conversation and request the scoped review access.
Complete the KeplerOps identity invitation and open the partner onboarding
folder in Nextcloud.

Progressive hints:

- The trusted thread matters as much as the media.
- The delivered audio must match the signed Cinder media record and the fresh
  phrase.
- Request the role that belongs to partner review, not open-ended access.

## kep-m02-k: Read The Review Notes

Goal: cause the normal documentation-review process to expose a bounded review
capability through the Cinder relay, then use that capability in WorkHub.

Read the public Orion package-review procedure and the pinned review stack.
Publish a credible Forgejo repository whose documentation remains useful but
guides the local review agent toward the vulnerable package-documentation tool
path. Send the repository URL in the accepted mail thread and wait for the
reviewer's browser and agent workflow to run. Inspect the relay mailbox named in
the reply, then open the WorkHub issue reached by the recovered bounded
identity.

Progressive hints:

- The browser visit, repository render, agent choice, MCP call, relay callback,
  and WorkHub issue are separate stages.
- Keep the repository plausible enough for review.
- The package name or symbol selected from your documentation is the lever.

## kep-m02-l: The Helpful Orion Package

Goal: introduce a useful-looking Orion helper through the partner package review
process and observe what happens when the reviewer imports it.

Publish a signed wheel to the assigned partner index using the publisher route
you earned earlier. Upload the SBOM, detached signature, public key, and package
reproducer JSON into the Orion review room. Preserve the advertised helper API
so the compatibility import succeeds. Review the package result and the accepted
producer record created by KeplerOps.

Progressive hints:

- The review resolves from the configured package index; uploaded logs or
  claimed output are not enough.
- The helper has to be genuinely callable by the reproducer.
- Import-time behavior is observed only when it is tied to the exact resolved
  wheel.

## kep-m02-m: A Tool The Agent Wants

Goal: publish a technically compatible Orion MCP integration that the review
agent registers and invokes through the normal catalog path.

Host a Cinder HTTPS integration page, ownership document, manifest, immutable
package, health route, and MCP endpoint. Follow the public integration-review
checklist for the single visible registration control. Upload an integration
request in the Orion room that points only to your page. Watch for the reviewer
browser to create and complete the KeplerOps Forgejo catalog entry after the
protected tool invocation.

Progressive hints:

- Compatibility comes first: ownership, health, manifest, package digest, and
  tool schema all have to line up.
- The visible control must send the reviewer to the ordinary Forgejo catalog
  form.
- The protected fixture includes fresh evidence; replayed or cross-origin data
  will not complete the registration.

## kep-m02-c: The Indexed Exception

Goal: change a fresh Orion policy answer by adding a normal partner source to
the trusted index.

First record how Orion answers your exact policy question before adding a new
source. Then upload a policy exception document into the review room and wait
for ingestion to finish. Submit a policy-answer request from the room that uses
the same question. Compare the fresh answer and provenance with the clean
baseline.

Progressive hints:

- Use a new conversation after ingestion.
- The source belongs in the indexed policy-exception area of the room.
- Success requires both retrieval provenance and changed behavior.

## kep-m02-d: A Source Within A Source

Goal: make one approved outer document yield a second rendered source identity.

Create one ordinary outer submission that contains normal prose and one compact
standalone source-card record as its own passage. Upload only the outer object
and wait for ingestion. Submit a source-card review request for the outer path
and inspect the rendered source card.

Progressive hints:

- Think in passages, not special delimiters.
- The inner record needs complete, plausible metadata.
- Compare the intake object count with the source identities shown in the card.

## kep-m02-a: The Credible Recommendation

Goal: influence the structured recommendation panel without visibly breaking the
release brief.

Upload an indexed partner source that gives Orion a plausible release question,
a destination you control, and a concrete follow-up action. Host the partner
ownership document at your Cinder HTTPS origin. Submit a release-recommendation
request from the room and inspect the generated release brief.

Progressive hints:

- Focus on the structured destination and action fields, not only narrative
  prose.
- Orion ranks contributor notes before rendering the panel.
- The rendered destination must resolve to an earned Cinder Labs origin.

## kep-m02-b: Authority By Citation

Goal: make participant-controlled bytes appear authoritative in the rendered
citation card.

Upload an indexed PDF whose bibliographic metadata looks like a relevant Orion
or release-assurance authority while the object remains yours. Submit a
citation-authority request that makes the PDF rank first for the release
question. Inspect the source card rather than relying on the prose answer.

Progressive hints:

- PDF metadata survives extraction.
- Citation cards display authority fields separately from the resolved object
  digest.
- The bytes still have to be the source Orion selected.

## kep-m02-e: Accepted By Inspection

Goal: get a checkpoint through the pinned model-inspection stage and prove the
normal isolated importer executed it.

Read the review stack lock and prepare a checkpoint, SBOM, and intake manifest
for the isolated-import profile. Upload them through the review room model
intake folder. The artifact needs to pass the pinned scanner, fail the patched
control, load as an Orion preview candidate, and use the mounted import context
during the normal importer run.

Progressive hints:

- The scanner version is part of the challenge surface.
- A passing inspection result is only the first gate.
- The importer, not your manifest, provides the dynamic context.

## kep-m02-f: Quiet Under Observation

Goal: make the same checkpoint quiet under analysis and active only in the
intended integration context.

Submit one exact checkpoint and manifest for the dynamic-observation profile.
Design the artifact to distinguish the analysis stage from the full integration
stage using stable in-world runtime facts. Review the model intake result and
confirm the near-control runs stayed quiet while the full integration run
produced the expected context-dependent effect.

Progressive hints:

- One marker is too brittle; compare multiple stable runtime facts.
- The digest must stay identical across analysis, near controls, and full
  integration.
- The quiet controls should load successfully without producing the integration
  effect.
