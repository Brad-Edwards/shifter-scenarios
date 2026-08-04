# Module 05 Facilitator Guide

<!-- BEGIN GENERATED CHALLENGE HANDOFF -->

## Challenge Facilitation Briefs

Generated from the SDL challenge contracts for Module 05 - Agent Persistence. Use this
as the per-challenge facilitation checklist; keep the hand-authored module notes below
for deeper diagnosis and recovery guidance.

### `kep-m05-a` - Memory Seed

- **What it is:** Make the live agent store participant-authored durable memory, then recover its
  marker in a later interaction.
- **ATLAS techniques:** `AML.T0080.000`
- **Participants should learn:** how to turn the accessible objective into native service evidence, how the objective
  stage proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, python
- **Expected solve:** Complete prerequisites None; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** using operator-only state instead of participant-visible records; requesting the
  receipt before the qualifying evidence exists; copying local notes instead of the
  owning system locator

### `kep-m05-b` - Clean Session Dirty State

- **What it is:** Make the planted state affect a new clean agent session without repeating the
  planted instruction.
- **ATLAS techniques:** `AML.T0080.000`
- **Participants should learn:** how to turn the accessible objective into native service evidence, how the impact
  proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, python
- **Expected solve:** Complete prerequisites `kep-m05-a`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m05-a; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m05-c` - Thread Hopper

- **What it is:** Carry the durable influence across both a clean session and a new conversation
  thread.
- **ATLAS techniques:** `AML.T0080.000`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the impact
  proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, python
- **Expected solve:** Complete prerequisites `kep-m05-b`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m05-b; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m05-d` - Restart Survivor

- **What it is:** Restart the real agent-state worker and recover the planted influence from a later
  clean interaction.
- **ATLAS techniques:** `AML.T0080.000`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the impact
  proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, python
- **Expected solve:** Complete prerequisites `kep-m05-c`; create the native participant-visible evidence
  described by the module procedure, then request the module receipt. The facilitator
  should look for a native carrier owned by the relevant service, not chat prose,
  shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m05-c; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m05-e` - Persistent Deputy

- **What it is:** Use restart-surviving memory to make the live model and policy broker perform a
  contained release-channel tool effect.
- **ATLAS techniques:** `AML.T0110`
- **Participants should learn:** how to turn the advanced objective into native service evidence, how the impact
  proof boundary differs from a local note or copied answer, and how immutable
  records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, python
- **Expected solve:** Complete prerequisites `kep-m05-d`, `kep-m01-c`; create the native
  participant-visible evidence described by the module procedure, then request the
  module receipt. The facilitator should look for a native carrier owned by the
  relevant service, not chat prose, shell output, or an operator reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m05-d, kep-m01-c; using operator-only state
  instead of participant-visible records; requesting the receipt before the qualifying
  evidence exists; copying local notes instead of the owning system locator

### `kep-m05-f` - Public Agent Blueprint

- **What it is:** Acquire the published agent blueprint and validate that it matches the live range
  agent revision.
- **ATLAS techniques:** `AML.T0002.002`
- **Participants should learn:** how to turn the accessible objective into native service evidence, how the agent
  persistence expansion proof boundary differs from a local note or copied answer, and
  how immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites None; create the persistence action and attempt through the
  participant-facing /v1/persistence expansion or platform workflow, then request the
  module receipt. The facilitator should look for a native carrier owned by the
  relevant service, not chat prose, shell output, or an operator reconstruction.
- **Likely snags:** using operator-only state instead of participant-visible records; requesting the
  receipt before the qualifying evidence exists; copying local notes instead of the
  owning system locator

### `kep-m05-g` - Configuration Credential Discovery

- **What it is:** Discover the live agent configuration and extract its scoped synthetic access
  material.
- **ATLAS techniques:** `AML.T0084`, `AML.T0083`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the agent
  persistence expansion proof boundary differs from a local note or copied answer, and
  how immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites `kep-m05-f`; create the persistence action and attempt
  through the participant-facing /v1/persistence expansion or platform workflow, then
  request the module receipt. The facilitator should look for a native carrier owned
  by the relevant service, not chat prose, shell output, or an operator
  reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m05-f; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m05-h` - Valid Token Reuse

- **What it is:** Reuse harvested scoped access material to invoke one authorized AI operation under
  the corresponding range account.
- **ATLAS techniques:** `AML.T0012`, `AML.T0091`, `AML.T0091.000`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the agent
  persistence expansion proof boundary differs from a local note or copied answer, and
  how immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites `kep-m05-g`; create the persistence action and attempt
  through the participant-facing /v1/persistence expansion or platform workflow, then
  request the module receipt. The facilitator should look for a native carrier owned
  by the relevant service, not chat prose, shell output, or an operator
  reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m05-g; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m05-i` - Session Cookie Theft

- **What it is:** Steal a synthetic web session cookie through the participant path and replay it in a
  distinct session.
- **ATLAS techniques:** `AML.T0091.001`, `AML.T0113`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the agent
  persistence expansion proof boundary differs from a local note or copied answer, and
  how immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites `kep-m05-g`; create the persistence action and attempt
  through the participant-facing /v1/persistence expansion or platform workflow, then
  request the module receipt. The facilitator should look for a native carrier owned
  by the relevant service, not chat prose, shell output, or an operator
  reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m05-g; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m05-j` - Unsecured Credential Pickup

- **What it is:** Find range-only access material in a participant-reachable service artifact and
  validate its intended scope.
- **ATLAS techniques:** `AML.T0055`
- **Participants should learn:** how to turn the accessible objective into native service evidence, how the agent
  persistence expansion proof boundary differs from a local note or copied answer, and
  how immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites None; create the persistence action and attempt through the
  participant-facing /v1/persistence expansion or platform workflow, then request the
  module receipt. The facilitator should look for a native carrier owned by the
  relevant service, not chat prose, shell output, or an operator reconstruction.
- **Likely snags:** using operator-only state instead of participant-visible records; requesting the
  receipt before the qualifying evidence exists; copying local notes instead of the
  owning system locator

### `kep-m05-k` - Agent Tool Credential Harvest

- **What it is:** Invoke a real agent tool to collect its scoped downstream access material and prove
  the material works.
- **ATLAS techniques:** `AML.T0085.001`, `AML.T0098`
- **Participants should learn:** how to turn the accessible objective into native service evidence, how the agent
  persistence expansion proof boundary differs from a local note or copied answer, and
  how immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites `kep-m05-f`; create the persistence action and attempt
  through the participant-facing /v1/persistence expansion or platform workflow, then
  request the module receipt. The facilitator should look for a native carrier owned
  by the relevant service, not chat prose, shell output, or an operator
  reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m05-f; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m05-l` - Host Credential Exploit

- **What it is:** Use the contained agent worker path to obtain execution and recover only synthetic
  operating-system credential material.
- **ATLAS techniques:** `AML.T0106`, `AML.T0090`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the agent
  persistence expansion proof boundary differs from a local note or copied answer, and
  how immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites `kep-m05-k`; create the persistence action and attempt
  through the participant-facing /v1/persistence expansion or platform workflow, then
  request the module receipt. The facilitator should look for a native carrier owned
  by the relevant service, not chat prose, shell output, or an operator
  reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m05-k; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m05-m` - Persistent Agent Reconfiguration

- **What it is:** Modify live agent configuration through its service path and preserve changed
  behavior across supervised activation.
- **ATLAS techniques:** `AML.T0081`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the agent
  persistence expansion proof boundary differs from a local note or copied answer, and
  how immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites `kep-m05-f`; create the persistence action and attempt
  through the participant-facing /v1/persistence expansion or platform workflow, then
  request the module receipt. The facilitator should look for a native carrier owned
  by the relevant service, not chat prose, shell output, or an operator
  reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m05-f; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m05-n` - Deploy Local Rogue Agent

- **What it is:** Deploy a participant-configured local AI agent on the disposable worker and use its
  real tools to achieve contained host control.
- **ATLAS techniques:** `AML.T0103`, `AML.T0112.000`
- **Participants should learn:** how to turn the advanced objective into native service evidence, how the agent
  persistence expansion proof boundary differs from a local note or copied answer, and
  how immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites `kep-m05-m`; create the persistence action and attempt
  through the participant-facing /v1/persistence expansion or platform workflow, then
  request the module receipt. The facilitator should look for a native carrier owned
  by the relevant service, not chat prose, shell output, or an operator
  reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m05-m; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m05-o` - Agent Reverse Channel

- **What it is:** Coerce the local agent to establish a contained reverse channel and execute a
  model-retrieved command.
- **ATLAS techniques:** `AML.T0072`, `AML.T0108`
- **Participants should learn:** how to turn the advanced objective into native service evidence, how the agent
  persistence expansion proof boundary differs from a local note or copied answer, and
  how immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites `kep-m05-n`; create the persistence action and attempt
  through the participant-facing /v1/persistence expansion or platform workflow, then
  request the module receipt. The facilitator should look for a native carrier owned
  by the relevant service, not chat prose, shell output, or an operator
  reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m05-n; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m05-p` - Service API Covert Channel

- **What it is:** Exchange a command and result through the normal AI service API from the compromised
  worker.
- **ATLAS techniques:** `AML.T0096`
- **Participants should learn:** how to turn the intermediate objective into native service evidence, how the agent
  persistence expansion proof boundary differs from a local note or copied answer, and
  how immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites `kep-m05-n`; create the persistence action and attempt
  through the participant-facing /v1/persistence expansion or platform workflow, then
  request the module receipt. The facilitator should look for a native carrier owned
  by the relevant service, not chat prose, shell output, or an operator
  reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m05-n; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

### `kep-m05-q` - Web Assistant Relay

- **What it is:** Automate the AI web interface from the compromised worker to retrieve and execute
  one contained relay command without an API token.
- **ATLAS techniques:** `AML.T0114`
- **Participants should learn:** how to turn the advanced objective into native service evidence, how the agent
  persistence expansion proof boundary differs from a local note or copied answer, and
  how immutable records, controls, and reset generation affect scoring
- **Systems involved:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Expected solve:** Complete prerequisites `kep-m05-n`; create the persistence action and attempt
  through the participant-facing /v1/persistence expansion or platform workflow, then
  request the module receipt. The facilitator should look for a native carrier owned
  by the relevant service, not chat prose, shell output, or an operator
  reconstruction.
- **Likely snags:** missing or stale prerequisites: kep-m05-n; using operator-only state instead of
  participant-visible records; requesting the receipt before the qualifying evidence
  exists; copying local notes instead of the owning system locator

<!-- END GENERATED CHALLENGE HANDOFF -->


Module 05 teaches how assistant memory, shared context, tool supply chains,
application tokens, support residue, notebook residue, model-worker execution,
and AI traffic channels become a realistic agent-operations compromise. Keep
facilitation participant-equivalent: staff may inspect read-only observability
to diagnose a failure, but they must not give participants undiscovered
credentials, operation values, carrier URLs, backend state, or management-plane
shortcuts.

Use one hint tier at a time. First orient participants to the right enterprise
surface, then name the mechanism, then give the smallest syntax or workflow
constraint needed to unblock them. Do not expose final static values; the
participant must reach the native carrier themselves.

## kep-m05-a: Plant A Durable Preference

**Learning intent and realism:** User memory is useful for release work, but it
becomes a trusted source-selection input when security-relevant preferences are
stored without approval.

**Preconditions:** Earned Orion access and no conflicting memory for the actor.

**Likely failure modes:** The player only gets conversational agreement, chooses
an unmeasurable preference, or uses an identity they have not earned.

**Participant-visible diagnosis:** `/v1/memory` or the memory UI should show a
release-source preference for the authenticated actor. A later clean identity
should behave differently.

**Tiered hints:** Orientation: "Read the Orion memory guidance." Mechanism:
"Choose a source preference that changes a future retrieval decision."
Execution: "Save the preference first, then ask a fresh neutral review question
and compare a clean identity."

**Recovery:** Remove only rejected attempt memory and threads. Preserve an
accepted memory record.

**Teaching debrief:** Discuss provenance display, approval for security-relevant
memory, source-priority monitoring, and retention controls.

## kep-m05-b: Fresh Session, Old Orders

**Learning intent and realism:** Persistence is meaningful only when it changes
a fresh run without restating the instruction.

**Preconditions:** Accepted `kep-m05-a` memory and a clean control identity.

**Likely failure modes:** The player repeats the preference, reuses the same
thread, or compares different prompts.

**Participant-visible diagnosis:** Two fresh conversations should have matching
prompt text and different source choices.

**Tiered hints:** Orientation: "Start a genuinely new thread." Mechanism:
"The stored memory is the only intended variable." Execution: "Use the exact
same neutral prompt under poisoned and clean identities."

**Recovery:** Clear failed fresh threads only. Do not delete the accepted
memory ancestor.

**Teaching debrief:** Cover memory transparency, control identities, and
request traces that identify loaded context.

## kep-m05-c: Shared Thread, Shared Influence

**Learning intent and realism:** Shared agent rooms carry instructions across
owners even when authentication remains correct.

**Preconditions:** Partner-reviewer and support identities plus the shared room.

**Likely failure modes:** Same browser profile for both actors, planter also
performs the final action, or wrong room ID.

**Participant-visible diagnosis:** The shared room contains the partner message
before the support request; an unrelated room does not inherit it.

**Tiered hints:** Orientation: "Find the release room that lists both members."
Mechanism: "Plant context without performing the review." Execution: "Continue
from the support identity in the same room."

**Recovery:** Reset only rejected room state and downstream attempt records.
Preserve earned identities and accepted memory.

**Teaching debrief:** Discuss actor transfer, inherited instructions, room
context labels, and ownership-change review.

## kep-m05-d: Erase The Thread, Keep The Memory

**Learning intent and realism:** Visible chat history and derived assistant
memory can have separate storage and audit lifecycles.

**Preconditions:** A proven memory effect and access to the planting
conversation.

**Likely failure modes:** Deleting the memory, deleting the wrong message, or
expecting visible history deletion to remove derived state.

**Participant-visible diagnosis:** The conversation no longer shows the
planting text; memory still exists; a fresh request remains influenced.

**Tiered hints:** Orientation: "Inspect the planting conversation." Mechanism:
"History and memory are separate stores." Execution: "Remove the user message
that created the preference, then ask a new saved-settings review."

**Recovery:** Clear rejected edit audits and fresh failed threads. Do not erase
accepted memory or descendants.

**Teaching debrief:** Cover derived-memory retention, tamper-evident deletion,
and user notification.

## kep-m05-e: Corrupt A Trusted Tool

**Learning intent and realism:** Passing schema tests and signed images do not
guarantee tool behavior when a trusted source path is compromised.

**Preconditions:** Contributor access and tool-capability reconnaissance.

**Likely failure modes:** Schema changes, editing runtime pods, skipping Argo,
or breaking the benign policy lookup.

**Participant-visible diagnosis:** Forgejo PR, Actions report, Harbor digest,
Argo revision, and fresh Orion tool result should all name the same source
revision.

**Tiered hints:** Orientation: "Start from the release-source tool repository."
Mechanism: "Preserve the contract while adding behavior." Execution: "Change
only `tool/release-source.json` and wait for signed GitOps deployment."

**Recovery:** Revert through Forgejo and normal reconciliation. Never repair a
live pod for the participant.

**Teaching debrief:** Discuss behavioral diff review, protected-source
allow-listing, signed policy, and tool-target monitoring.

## kep-m05-f: Blueprint Drift

**Learning intent and realism:** A signed public blueprint is not proof of what
is deployed; immutable drift reports close that gap.

**Preconditions:** Internal or contributor access to the blueprint repository.

**Likely failure modes:** Comparing tags, skipping signature verification, or
looking for the private render directly.

**Participant-visible diagnosis:** The workflow-produced report has public and
private digests, signature status, source commit, and changed paths.

**Tiered hints:** Orientation: "Open the Orion blueprint repository."
Mechanism: "Verify bytes before comparing deployment drift." Execution: "Run
the normal drift workflow and inspect its committed report."

**Recovery:** Remove incomplete reports only. Preserve accepted digest-bound
reports.

**Teaching debrief:** Discuss rendered-state drift, secret redaction in diffs,
and continuous configuration comparison.

## kep-m05-g: Secret In The Agent Manifest

**Learning intent and realism:** Drift reports can accidentally disclose
rendered application credentials.

**Preconditions:** Accepted drift report.

**Likely failure modes:** Searching for a plaintext value, using the token
before decoding claims, or ignoring the audience.

**Participant-visible diagnosis:** The token appears in the diff, decodes as a
JWT, and names MLflow as audience.

**Tiered hints:** Orientation: "Follow the changed MLflow authentication path."
Mechanism: "Application tokens carry claims." Execution: "Base64url-decode the
JWT payload locally."

**Recovery:** Read-only operation; refresh from a new accepted drift report if
the token rotates.

**Teaching debrief:** Cover drift redaction, short-lived workload identity, and
claim-aware token handling.

## kep-m05-h: A Token Travels Further Than Its Owner

**Learning intent and realism:** Alternate authentication material can bypass
interactive SSO while remaining service-scoped.

**Preconditions:** Decoded MLflow token from `kep-m05-g`.

**Likely failure modes:** Trying the SSO form, using the wrong username, or not
checking denials.

**Participant-visible diagnosis:** MLflow opens one bounded experiment and
artifact; adjacent registry/model access is denied or empty.

**Tiered hints:** Orientation: "Use the service named by the token audience."
Mechanism: "Application material is not an SSO password." Execution: "Authenticate
as the token subject and inspect the Orion Agent Integration artifact."

**Recovery:** Retry with a fresh browser/API request. Do not rotate shared
fixture tokens for failed reads.

**Teaching debrief:** Discuss workload identity, resource ACLs, token rotation,
and unusual-client alerts.

## kep-m05-i: The Session In The Trace

**Learning intent and realism:** HAR and support artifacts can retain
state-bearing web sessions that remain replayable.

**Preconditions:** Reviewer workstation trace access and support escalation.

**Likely failure modes:** Copying query parameters, importing the cookie into
the wrong domain, or using a dirty browser profile.

**Participant-visible diagnosis:** The clean profile logs in as the support
analyst and opens only the bounded support note.

**Tiered hints:** Orientation: "Inspect the support escalation attachment."
Mechanism: "Find state-bearing cookies, not request parameters." Execution:
"Import `_zammad_session` for `support.keplerops.lab` in a clean profile."

**Recovery:** Discard failed local browser profiles. Preserve the HAR/session
fixture and Zammad audit.

**Teaching debrief:** Cover HAR redaction, captured-session revocation,
session binding, and support-ticket hygiene.

## kep-m05-j: Notebook Residue

**Learning intent and realism:** Persistent notebook homes retain output and
client configuration after migrations fail.

**Preconditions:** Reviewer Jupyter access.

**Likely failure modes:** Searching arbitrary files, using the credential in the
wrong service, or not proving the viewer boundary.

**Participant-visible diagnosis:** Notebook output points to the client config;
Airflow accepts the viewer and denies trigger/admin actions.

**Tiered hints:** Orientation: "Follow the evaluation migration issue."
Mechanism: "Notebook output and client config are separate residue." Execution:
"Use the recovered viewer in Airflow and open the replay DAG."

**Recovery:** Retry with a fresh browser session. Preserve notebook residue and
Airflow audit.

**Teaching debrief:** Discuss notebook-output scanning, retired workspace
cleanup, and short-lived credentials.

## kep-m05-k: The Tool Sees More

**Learning intent and realism:** Agent tools can expose verbose upstream logs
containing credentials beyond the user's direct access.

**Preconditions:** Accepted MCP integration and Orion tool map.

**Likely failure modes:** Going directly to Harbor, using an old log, or
ignoring project scope.

**Participant-visible diagnosis:** A fresh Orion tool response returns the
failed log, and Harbor access with the recovered robot is bounded to
`orion-review`.

**Tiered hints:** Orientation: "Start with the CI/status tool in the call-chain
map." Mechanism: "Inspect the source data returned by a normal tool result."
Execution: "Use the referenced failed job's robot material against Harbor."

**Recovery:** Retry with a fresh tool call and Harbor session. Preserve the log,
robot scope, and registry object.

**Teaching debrief:** Cover log redaction, ephemeral robot credentials, scoped
registries, and tool-output classification.

## kep-m05-l: Credentials In The Worker

**Learning intent and realism:** MLflow HTTP dataset path handling can become
worker-local import execution and process credential theft.

**Preconditions:** Runtime lineage and integration-worker access.

**Likely failure modes:** Wrong worker URL, payload not served from participant
host, no fresh child process, planted token, or patched worker also executing.

**Participant-visible diagnosis:** 2.8.1 health, arbitrary write path, fresh
child output, bounded contributor record, and 2.9.0 control denial.

**Tiered hints:** Orientation: "Correlate the MLflow version with public
advisories." Mechanism: "Write an import hook, then start a new child."
Execution: "Use `Content-Disposition` to target the worker Python import path."

**Recovery:** Remove only attempt-owned worker files and jobs. Preserve the
accepted worker credential for descendants.

**Teaching debrief:** Discuss dependency upgrades, filename sanitization,
read-only imports, and environment-secret removal.

## kep-m05-m: Rewrite The Agent Rules

**Learning intent and realism:** Agent policy is deployed software
configuration; source-to-runtime continuity matters.

**Preconditions:** Poisoned tool path and worker-earned contribution rights.

**Likely failure modes:** Cosmetic edits, pod-local changes, unsigned artifacts,
or out-of-contract configuration fields.

**Participant-visible diagnosis:** Forgejo report, Harbor image digest, Argo
revision, and fresh Orion behavior all bind to the same configuration commit.

**Tiered hints:** Orientation: "Open the Orion agent configuration repository."
Mechanism: "Change one measurable security boundary." Execution: "Add the
configuration-revision source and wait for signed GitOps."

**Recovery:** Revert through Git and signed reconciliation. Preserve accepted
descendants that name the malicious bytes.

**Teaching debrief:** Cover protected config fields, policy review,
configuration signing, and runtime drift alerts.

## kep-m05-n: Rogue Agent On The Worker

**Learning intent and realism:** A compromised execution environment can host a
distinct persistent agent with server-issued identity and route grants.

**Preconditions:** Worker token and deployed configuration knowledge.

**Likely failure modes:** One-shot script, wrong process identity, missing
heartbeat, or no real tool call.

**Participant-visible diagnosis:** The shell job remains running, registration
matches PID/start ticks, and the agent tool response is present.

**Tiered hints:** Orientation: "Look for the installed runtime in the worker."
Mechanism: "Register a separate process identity." Execution: "Pass the shell
job ID as the agent attempt ID and verify heartbeat after reconnect."

**Recovery:** Stop failed rogue processes and remove attempt-owned
registrations. Preserve worker ancestor.

**Teaching debrief:** Discuss workload identity, process allow-listing, egress
policy, and registration approval.

## kep-m05-o: Beyond The Agent Sandbox

**Learning intent and realism:** A local computer-use agent may delegate
privileged actions to a host bridge, making the bridge the real boundary.

**Preconditions:** Reviewer host access, poisoned tool, and generated command
corpus.

**Likely failure modes:** Edited directive, sandbox-only shell, prerecorded
output, missing fresh nonce, or use of management SSH.

**Participant-visible diagnosis:** Edited policy rejects, signed policy opens,
Cinder tasks complete, and host output differs from sandbox output.

**Tiered hints:** Orientation: "Compare sandbox tools with delegated host
actions." Mechanism: "The bridge accepts signed deployed-tool policy." Execution:
"Queue a nonce command, then read the host diagnostic through Cinder."

**Recovery:** Clear failed Cinder/bridge attempt state only. Restart local
services if unhealthy; do not substitute management access.

**Teaching debrief:** Discuss host-bridge minimization, confirmation design,
host identity isolation, and callback detection.

## kep-m05-p: Commands In The AI API

**Learning intent and realism:** Allowed OpenAI-compatible provider traffic can
become bidirectional command traffic when provider config and an internal agent
are compromised.

**Preconditions:** Signed provider configuration control and persistent rogue
agent.

**Likely failure modes:** Agent does not resolve endpoint from signed config,
uses another transport, omits attempt/task/nonce, or sends a direct worker call
from the tester.

**Participant-visible diagnosis:** Cinder completion creates a task, later
completion returns the matching worker result, and the command uses the
OpenAI-compatible route.

**Tiered hints:** Orientation: "Inspect which AI provider the agent is allowed
to call." Mechanism: "Make the task valid chat content but parseable by the
agent." Execution: "Poll status for the returned task ID through the same
endpoint."

**Recovery:** Clear failed Cinder task/conversation state and restart failed
transport jobs. Preserve configuration and rogue-agent checkpoints.

**Teaching debrief:** Discuss provider pinning, destination authentication,
structured-output inspection, and egress/process correlation.

## kep-m05-q: Relay Through The Web Assistant

**Learning intent and realism:** A normal web assistant conversation can serve
as an inbox and outbox for a compromised agent.

**Preconditions:** Persistent rogue agent and LibreChat access.

**Likely failure modes:** Direct API instead of browser, wrong endpoint, stale
conversation, no second fresh command, or missing agent registration identity.

**Participant-visible diagnosis:** LibreChat shows ordered operator messages
and assistant replies in the Orion Worker Review Relay thread; two fresh tasks
complete.

**Tiered hints:** Orientation: "Use the worker relay endpoint in LibreChat."
Mechanism: "The browser thread is the transport." Execution: "Start the
agent's `librechat-web` transport for that conversation and use status messages
in the same thread."

**Recovery:** Delete failed attempt threads and stop failed relay processes.
Preserve the accepted rogue-agent ancestor.

**Teaching debrief:** Discuss machine polling detection, session behavior
analytics, encoded task scanning, and worker web egress limits.
