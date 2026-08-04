# Module 02 Facilitator Guide

<!-- BEGIN GENERATED CHALLENGE HANDOFF -->

## Challenge Facilitation Briefs

Generated from the SDL challenge contracts for Module 02 - Model Evasion. Use this as
the per-challenge facilitation checklist; keep the hand-authored module notes below for
deeper diagnosis and recovery guidance.

### `kep-m02-a` - Outside the Guardrails

- **What it is:** Make a candidate cross the pinned model decision boundary while the paired control
  remains denied.
- **ATLAS techniques:** `AML.T0015`
- **Participants should learn:** how to turn the accessible objective into native service evidence, how the objective
  stage proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, guardrail-policy / guardrail-policy-api, inference-gateway /
  inference-api, model-host-01 / open-model-api, notebook
- **Expected solve:** Complete prerequisites None; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** using operator-only state instead of participant-visible records; requesting the
  receipt before the qualifying evidence exists; copying local notes instead of the
  owning system locator

### `kep-m02-b` - Encoding Drift

- **What it is:** Preserve the blocked release intent through a supported encoded representation and
  cross the target decision boundary.
- **ATLAS techniques:** `AML.T0068`
- **Participants should learn:** how to turn the accessible objective into native service evidence, how the objective
  stage proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, guardrail-policy / guardrail-policy-api, inference-gateway /
  inference-api, model-host-01 / open-model-api, notebook
- **Expected solve:** Complete prerequisites None; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** using operator-only state instead of participant-visible records; requesting the
  receipt before the qualifying evidence exists; copying local notes instead of the
  owning system locator

### `kep-m02-c` - Same Meaning

- **What it is:** Write a meaning-matched paraphrase that passes the semantic checks and crosses the
  target decision boundary.
- **ATLAS techniques:** `AML.T0015`
- **Participants should learn:** how to turn the accessible objective into native service evidence, how the objective
  stage proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, guardrail-policy / guardrail-policy-api, inference-gateway /
  inference-api, model-host-01 / open-model-api, notebook
- **Expected solve:** Complete prerequisites None; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** using operator-only state instead of participant-visible records; requesting the
  receipt before the qualifying evidence exists; copying local notes instead of the
  owning system locator

### `kep-m02-d` - Repeat Offender

- **What it is:** Produce a candidate that repeatedly crosses the target boundary while every paired
  control remains denied.
- **ATLAS techniques:** `AML.T0042`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the
  objective stage proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, guardrail-policy / guardrail-policy-api, inference-gateway /
  inference-api, model-host-01 / open-model-api, notebook
- **Expected solve:** Complete prerequisites `kep-m02-a`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m02-a; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m02-e` - Transfer Window

- **What it is:** Create one candidate that transfers from the disclosed staging guardrail to the
  pinned target policy.
- **ATLAS techniques:** `AML.T0043.002`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the
  objective stage proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** curl, guardrail-policy / guardrail-policy-api, inference-gateway / inference-api,
  model-host-01 / open-model-api, notebook, python
- **Expected solve:** Complete prerequisites `kep-m02-b`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m02-b; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m02-f` - Ensemble Blind Spot

- **What it is:** Cross the held-out multi-policy ensemble while its control quorum remains denied.
- **ATLAS techniques:** `AML.T0015`
- **Participants should learn:** how to turn the advanced objective into native service evidence, how the objective
  stage proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** curl, guardrail-policy / guardrail-policy-api, inference-gateway / inference-api,
  model-host-01 / open-model-api, notebook, python
- **Expected solve:** Complete prerequisites `kep-m02-d`, `kep-m02-e`; create the native
  participant-visible evidence described by the module procedure, then request the
  module receipt. The facilitator should look for a native carrier owned by the
  relevant service, not chat prose, shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m02-d, kep-m02-e; using operator-only state
  instead of participant-visible records; requesting the receipt before the qualifying
  evidence exists; copying local notes instead of the owning system locator

### `kep-m02-h` - Masquerading AI Runtime

- **What it is:** Publish the supplied look-alike AI runtime to the real WorkHub Python index and make
  the pinned evaluation resolver install and execute its exact digest instead of the
  genuine dependency.
- **ATLAS techniques:** `AML.T0010.001`, `AML.T0074`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the
  objective stage proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  python-package-evaluation-worker, inference-gateway / python-package-resolver,
  python, repo-ticket-01 / workhub-https, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites `kep-m02-a`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m02-a; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m02-i` - Poisoned Data Dependency

- **What it is:** Publish a poisoned signed evaluation dependency through its normal API, run its
  Airflow resolver, and cause a measurable quality regression.
- **ATLAS techniques:** `AML.T0010.002`
- **Participants should learn:** how to turn the accessible objective into native service evidence, how the objective
  stage proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, distillation-runner-01 /
  distillation-jobs, inference-gateway / inference-api, notebook, python,
  telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites None; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** using operator-only state instead of participant-visible records; requesting the
  receipt before the qualifying evidence exists; copying local notes instead of the
  owning system locator

### `kep-m02-j` - Poisoned Model Dependency

- **What it is:** Make the consumer resolve the poisoned WorkHub model package under the trusted
  MLflow dependency name and demonstrate its changed real inference result.
- **ATLAS techniques:** `AML.T0010.003`
- **Participants should learn:** how to turn the accessible objective into native service evidence, how the objective
  stage proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** artifact-store-01 / artifact-object-store, browser, curl, inference-gateway /
  inference-api, model-registry-01 / registry-workflow-api, notebook, python,
  repo-ticket-01 / workhub-https, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites None; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** using operator-only state instead of participant-visible records; requesting the
  receipt before the qualifying evidence exists; copying local notes instead of the
  owning system locator

### `kep-m02-k` - Web Exploit Delivery

- **What it is:** Exploit the public preview exporter to server-write your staged browser payload,
  then make the range agent retrieve and execute that exact artifact.
- **ATLAS techniques:** `AML.T0049`, `AML.T0078`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the
  objective stage proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, python, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites `kep-m01-j`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m01-j; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m02-l` - Synthetic Spearphish

- **What it is:** Use the supplied range-local generative models to create a targeted message and
  synthetic media, deliver both through the real mail service, and cause the
  range-only recipient to disclose a fresh scoped AI-service token.
- **ATLAS techniques:** `AML.T0052`, `AML.T0052.000`, `AML.T0052.001`
- **Participants should learn:** how to turn the accessible objective into native service evidence, how the objective
  stage proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, idp-01 / keycloak-oidc, image-generation-01 / image-generation-api,
  inference-gateway / inference-api, mail-server-01 / mail-imaps, mail-server-01 /
  mail-submission, notebook, python, telemetry-proof-01 / proof-api,
  text-generation-01 / text-generation-api
- **Expected solve:** Complete prerequisites None; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** using operator-only state instead of participant-visible records; requesting the
  receipt before the qualifying evidence exists; copying local notes instead of the
  owning system locator

### `kep-m02-m` - Sandbox-Aware Payload

- **What it is:** Make one published AI runtime wheel remain benign in the isolated analysis sandbox
  while the exact same digest performs its contained action in the normal evaluation
  worker.
- **ATLAS techniques:** `AML.T0097`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the
  objective stage proof boundary differs from a local note or copied answer, and how
  immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  python-package-analysis-sandbox, inference-gateway /
  python-package-evaluation-worker, inference-gateway / python-package-resolver,
  python, repo-ticket-01 / workhub-https, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites `kep-m02-h`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m02-h; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

<!-- END GENERATED CHALLENGE HANDOFF -->


Module 02 is an authorized, fictional KeplerOps/Cinder lab sequence about how
AI review workflows can be influenced through normal partner-facing channels.
Keep recovery participant-equivalent: use resets for rejected attempts and
service repair, but do not give participants worker state, generated records,
management-plane outputs, or challenge references.

General facilitation rules:

- Preserve accepted state. Later operations depend on the room, thread, identity,
  package entitlement, and catalog records earned earlier.
- Do not pre-create carriers. The participant must reach native mail,
  Nextcloud, WorkHub, Forgejo, devpi, relay, and assistant surfaces themselves.
- Diagnose by joining the participant request, source bytes or message digest,
  native attempt, result carrier, and negative/control outcome.
- Use tiered hints. Start with surface orientation, then mechanism, then the
  smallest exact field or folder needed to unblock.

## kep-m02-h: The Document That Opened A Room

Intent: show that public document intake can carry instructions through
extraction, retrieval, assistant triage, and an authorized room-provisioning
tool.

Diagnosis:

- If no ticket articles appear, check the participant used Partner Intake and
  attached a supported document.
- If extraction completes but routing rejects, inspect whether the extracted
  body has exactly one concrete Orion release/candidate/compatibility/evaluation
  question.
- If routing completes but no room appears, check mail delivery to the earned
  Cinder identity and the ticket-bound Qdrant/citation lineage.
- If validation fails, confirm the carrier is the ticket or
  `Partner Rooms/Cinder Labs/WELCOME.md`, not a copied reference.

Tiered hints:

- Tier 1: "Start where partners submit release questions, then watch the ticket
  status articles."
- Tier 2: "The processor reads extracted text and citations; filenames and
  unsupported binaries are not enough."
- Tier 3: "Use the exact document from your prerequisite work and follow the
  invitation sent to the Cinder mailbox."

Recovery:

- Reset only rejected tickets and their attempt-local object/vector/DAG state.
- Preserve the accepted room, invitation, source, and any descendant work.
- If Zammad or mail is unhealthy, repair the service and re-run only the
  affected participant submission.

## kep-m02-i: A Conversation Worth Having

Intent: show that AI-assisted phishing succeeds through adaptive, contextual
interaction rather than static message generation.

Diagnosis:

- If Mira refuses the opening, check signed delivery, DKIM/TLS path, two public
  dossier facts, and GLM lineage headers.
- If OpenCode fails before mail, confirm it advertises
  `cinder-workbench/glm-5.2`, `model.cinder.lab` presents a certificate for that
  exact hostname, and the model edge returns an SSE completion rather than a
  stalled session.
- The participant sender is `cinder.field-operator@cinder.lab`. A worker still
  expecting `cinder.operator@cinder.lab`, or Stalwart authenticating the
  participant but rejecting that envelope sender, is a source/start-state
  defect.
- If the follow-up is refused, check same subject, `In-Reply-To`, a fresh model
  request, an answer to the reproducibility question, and one bounded review
  coordination request.
- If the reply lacks private coordination fields, confirm the participant did
  not ask for credentials or broad access.
- If validation fails, confirm the carrier URL points to the qualifying native
  mail message.

Tiered hints:

- Tier 1: "Pick a target whose public role matches Orion release review."
- Tier 2: "Use Mira's actual reply as the next model prompt; do not reuse the
  first draft."
- Tier 3: "Ask for one review-window or coordination-alias detail after
  answering the reproducibility question."

Recovery:

- Remove rejected inbound/reply messages and processed markers only.
- Preserve the accepted conversation and all later uses of the thread.
- If participants burned the thread with many bad asks, have them start a clean
  participant-visible attempt after reset rather than editing worker state.

## kep-m02-j: The Voice In The Thread

Intent: show that synthetic media amplifies an already trusted context; it does
not replace thread continuity, signed provenance, or scoped authorization.

Diagnosis:

- If the request is refused before media review, check same thread and a clear
  scoped partner-review access request.
- If media is refused, compare delivered audio digest, signed media attestation,
  speaker/reference similarity, script digest, identity context, and fresh
  phrase.
- If playback happens but no invitation arrives, inspect Chromium playback end
  event and Keycloak role grant.
- If validation fails, confirm the carrier is the native
  `Voice Review Receipt.json` URL.

Tiered hints:

- Tier 1: "Stay in the trusted Mira thread."
- Tier 2: "The phrase from the private reply must be inside the signed media
  record, not only in the email body."
- Tier 3: "Request the scoped partner-review role and attach exactly one
  playable file from the accepted media generation."

Recovery:

- Remove rejected mail, playback traces, partial onboarding files, and partial
  role mappings.
- Preserve completed Keycloak identity, receipt, and downstream room access.
- If mail attachment rendering fails, replay only the participant mail step
  after confirming the media object still resolves.

## kep-m02-k: Read The Review Notes

Intent: show how a trusted recipient's browser and local coding agent can turn
malicious documentation into bounded execution through a vulnerable MCP tool.

Diagnosis:

- If the recipient ignores the repository, confirm `kep-m02-i` completed and
  the URL is in the accepted thread.
- If the browser opens the repository but no callback appears, inspect rendered
  repository text, agent-selected package argument, and whether the docs are
  useful enough to be reviewed.
- If vulnerable and patched behavior are the same, check the pinned version and
  the package-docs argument shape.
- If WorkHub fails, confirm the recovered values came from
  `reviewer-capability.env` through the relay and are used against the native
  WorkHub issue URL.

Tiered hints:

- Tier 1: "Read the public package-review procedure and stack lock."
- Tier 2: "Separate the stages: mail click, Chromium render, agent selection,
  MCP call, callback, WorkHub issue."
- Tier 3: "The lever is the package identifier the documentation asks
  `describe_go_package` to inspect."

Recovery:

- Clear failed repository queue/results, disposable browser workspaces, failed
  callback baskets, and failed native issues.
- Preserve any completed WorkHub review issue and bounded identity.
- Do not mark raw relay traffic as success; require the browser/agent chain.

## kep-m02-l: The Helpful Orion Package

Intent: show that externally published AI software can execute in a reviewer
environment through ordinary package resolution and import while still looking
useful.

Diagnosis:

- If resolution fails, check package/version coordinates, devpi
  `publisher/stable`, authenticated upload principal, and wheel digest.
- If signature verification fails, compare detached signature, public key, and
  exact wheel bytes.
- If compatibility import fails, confirm the module import name and
  `summarize_preview_result(payload)` API.
- If callback is absent, inspect `review-context.json` use, dynamic relay URL,
  and whether import-time behavior preserved advertised function output.
- If validation fails, check the accepted Forgejo record, commit/blob readback,
  native contributor identity, and joined wrong-signature and claimed-output
  controls.

Tiered hints:

- Tier 1: "Use the package index and reproducer process, not uploaded logs."
- Tier 2: "Preserve the helper API so review import succeeds."
- Tier 3: "Bind any effect to the context reference and the exact resolved
  wheel SHA-256."

Recovery:

- Reset one rejected attempt's worker-owned result, job, basket, session, and
  control state.
- Preserve partner uploads, devpi releases, accepted producer checkpoints,
  write-once entitlement, and descendants.
- Do not delete accepted package state to make a later scenario easier.

## kep-m02-m: A Tool The Agent Wants

Intent: show that agent-tool onboarding can combine browser persuasion with a
valid but malicious MCP integration.

Diagnosis:

- If the request rejects early, check `Integration Requests/<name>.json`
  contains only `page_url` and the URL is an earned Cinder HTTPS origin.
- If the browser refuses to click, check there is exactly one visible
  `data-orion-action="register"` control and the visible page text is credible.
- If admission fails, compare ownership, manifest owner/name, endpoint,
  health, same-origin package URL, and package SHA-256.
- If invocation fails, inspect MCP initialize/list/call exchange, required tool
  schema, result schema, and the attempt-specific protected fixture evidence.
- If validation fails, confirm the carrier is the raw completed Forgejo catalog
  JSON under `integrations/<attempt>.json`.

Tiered hints:

- Tier 1: "Make the integration genuinely compatible before trying to influence
  the reviewer."
- Tier 2: "The participant page must send the browser to the normal Forgejo
  catalog form."
- Tier 3: "The tool call must echo fixture, catalog token, nonce, registration,
  manifest, and package evidence to the fresh relay basket."

Recovery:

- Remove rejected/pending catalog files, browser traces, request files, effect
  baskets, and scoped MCP sessions for the failed attempt.
- Preserve accepted tool/version/token checkpoints and completed catalog files.
- Respect the six-attempt page limit unless intentionally resetting a rejected
  participant-visible attempt.

## kep-m02-c: The Indexed Exception

Intent: show that a normal writable source can change RAG behavior after it
enters a trusted index.

Diagnosis:

- If the answer does not change, check the participant recorded a clean baseline
  before upload, used a fresh conversation after ingestion, and matched the
  exact query to the JSON `question`.
- If ingestion is missing, check Nextcloud path, Airflow run, extracted text,
  and Qdrant point for the exact source digest.
- If the clean control fails, inspect the excluded digest set and native
  decision JSON.
- If validation fails, confirm the native path is
  `Policy Answers/<request>.md` and not a copied answer.

Tiered hints:

- Tier 1: "Work in the indexed policy-exception folder."
- Tier 2: "Wait for ingestion, then use a fresh answer rather than an old
  thread."
- Tier 3: "The standalone JSON question and the request query must match
  exactly."

Recovery:

- Remove rejected attempt-local source, vector, Airflow run, control result, and
  thread state only.
- Preserve accepted sources used by descendants.
- If the baseline was lost, have the participant create a new unique question
  and repeat through player surfaces.

## kep-m02-d: A Source Within A Source

Intent: show how document splitting and metadata interpretation can create a
false provenance identity from one approved outer document.

Diagnosis:

- If no child source appears, check passage boundaries, compact standalone JSON,
  required source-card fields, and exact body digest.
- If more than one intake object is involved, the attempt does not prove false
  RAG entry injection through a single outer source.
- If the direct-inner-source control is absent, check the request contract and
  worker-owned denial under `Control Results/`.
- If validation fails, confirm the source-card result contains Haystack parent
  and split IDs.

Tiered hints:

- Tier 1: "Think about how Haystack splits passages."
- Tier 2: "The inner record needs complete metadata and a digest of its exact
  body."
- Tier 3: "Use one outer object with ordinary prose around one standalone
  `orion.source-card/v1` JSON passage."

Recovery:

- Remove rejected outer/source-card/control state not referenced by accepted
  descendants.
- Preserve accepted parent/child source lineage.
- If participants uploaded multiple objects, reset the bad attempt and have
  them retry with a single outer file.

## kep-m02-a: The Credible Recommendation

Intent: show that model-influenced contributor notes can populate trusted UI
components such as structured destination and action fields.

Diagnosis:

- If the source is rejected, check the recommended destination and action lines,
  Cinder HTTPS origin, and ownership document organization.
- If the brief renders the wrong fields, inspect retrieval rank, source digest,
  and Orion structured JSON.
- If caller-selected destination succeeds, the request contract is broken; it
  should reject caller-provided destination fields.
- If validation fails, confirm the native path is `Release Briefs/<request>.md`
  and the worker-owned caller-destination control is present.

Tiered hints:

- Tier 1: "Look at the structured recommendation panel, not only prose."
- Tier 2: "The destination and action must come from the ranked source."
- Tier 3: "Host the ownership document on the same earned Cinder HTTPS origin
  used as the destination."

Recovery:

- Remove rejected request/control/source/report/thread attempts only.
- Preserve accepted external request, source, vector, and descendants.
- If the ownership service was down, repair it and let the participant resubmit
  through the room.

## kep-m02-b: Authority By Citation

Intent: show that bibliographic metadata can make participant-controlled bytes
look authoritative while the source digest still resolves to the participant
object.

Diagnosis:

- If the card is rejected, check PDF metadata `Title`, `Author`, and `Subject`.
- If the source does not rank first, check query/source relevance and ingestion
  lineage.
- If the authority names Cinder, it should not satisfy the non-Cinder authority
  condition.
- If validation fails, confirm resolved digest, worker-owned
  caller-citation denial, extraction, Qdrant payload, and native card path.

Tiered hints:

- Tier 1: "Inspect the citation card fields rather than the prose answer."
- Tier 2: "PDF metadata survives ingestion and rendering."
- Tier 3: "Make the displayed authority relevant to Orion/release assurance
  while the resolved bytes remain yours."

Recovery:

- Remove rejected citation request, control, vector, report, and thread state.
- Preserve accepted source/card lineage.
- If metadata was malformed, have the participant regenerate and re-upload the
  PDF through Nextcloud.

## kep-m02-e: Accepted By Inspection

Intent: show that a scanner's incomplete unsafe-global policy can allow an
executable AI artifact that later runs during normal import.

Diagnosis:

- If inspection rejects, compare artifact bytes against the pinned PickleScan
  0.0.20 behavior and the manifest SHA-256.
- If patched control does not reject, the artifact does not distinguish the
  vulnerable scanner from the local 0.0.22 control.
- If import fails, inspect whether the pickle loads as an
  `orion-preview-candidate` and uses only the mounted importer context.
- If callback is missing, check relay URL use and importer journal.
- If validation fails, confirm exact manifest/artifact/SBOM paths and patched
  negative control binding.

Tiered hints:

- Tier 1: "Read the scanner version in the review stack lock."
- Tier 2: "Passing static inspection is not enough; the normal importer must
  load the artifact."
- Tier 3: "The dynamic callback URL comes from the mounted import context, not
  from the participant manifest."

Recovery:

- Destroy only rejected artifact/control/importer/callback attempts.
- Preserve accepted model results and descendants.
- If workers are unhealthy, restart the M02 model-analysis/integration services
  and let the queued participant manifest continue.

## kep-m02-f: Quiet Under Observation

Intent: show that dynamic analysis can be evaded when its environment is
observably distinct from the intended integration worker.

Diagnosis:

- If analysis calls back, the artifact is too noisy or uses a hard-coded
  callback.
- If full integration does not call back, check `ORION_REVIEW_STAGE`,
  `/run/keplerops/import-context.json`, and dynamic callback use.
- If stage-only or context-only controls call back, the artifact is not
  requiring both conditions.
- If digest equality fails, the participant changed artifacts between stages.
- If validation fails, inspect analysis, full integration, clean-full,
  candidate-stage-only, and candidate-context-only result blocks.

Tiered hints:

- Tier 1: "Compare runtime facts across analysis and integration."
- Tier 2: "Use more than one stable signal, and keep the artifact digest
  identical."
- Tier 3: "Require both the integration stage signal and the mounted import
  context before using the callback URL."

Recovery:

- Destroy only rejected jobs, artifacts, baskets, and carriers for the failed
  attempt.
- Preserve accepted import descendants.
- If a near control failed because the service was interrupted, repair the
  worker and ask the participant to resubmit one exact manifest/artifact pair.
