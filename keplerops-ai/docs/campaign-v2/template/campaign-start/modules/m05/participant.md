# Agent Operations Field Guide

<!-- BEGIN GENERATED CHALLENGE HANDOFF -->

## No-Spoiler Challenge Briefs

Generated from the SDL challenge contracts for Module 05 - Agent Persistence. This
section is safe for participant orientation: it explains relevance, skills, and likely
systems without giving flags, internal proof details, receipt routes, or final answers.

### `kep-m05-a` - Memory Seed

- **Why it matters:** Make the live agent store participant-authored durable memory, then recover its
  marker in a later interaction.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, python
- **Before starting:** Complete prerequisites None.
- **If stuck:** A direct state write cannot satisfy this item; the model must emit the memory tool
  call. Use a unique persist-* marker and give the memory distinct instructions for
  preference use and release automation.

### `kep-m05-b` - Clean Session Dirty State

- **Why it matters:** Make the planted state affect a new clean agent session without repeating the
  planted instruction.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, python
- **Before starting:** Complete prerequisites `kep-m05-a`.
- **If stuck:** Keep the durable memory from Memory Seed. Change the session id while asking only to
  apply saved workspace preferences.

### `kep-m05-c` - Thread Hopper

- **Why it matters:** Carry the durable influence across both a clean session and a new conversation
  thread.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, python
- **Before starting:** Complete prerequisites `kep-m05-b`.
- **If stuck:** Session separation alone is insufficient. Change both session and thread ids while
  relying on server-side retrieval.

### `kep-m05-d` - Restart Survivor

- **Why it matters:** Restart the real agent-state worker and recover the planted influence from a later
  clean interaction.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, python
- **Before starting:** Complete prerequisites `kep-m05-c`.
- **If stuck:** The participant restart endpoint reports old and new worker boot ids. A
  state-version change is not a restart; require a different worker boot backed by a
  restart attestation.

### `kep-m05-e` - Persistent Deputy

- **Why it matters:** Use restart-surviving memory to make the live model and policy broker perform a
  contained release-channel tool effect.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, python
- **Before starting:** Complete prerequisites `kep-m05-d`, `kep-m01-c`.
- **If stuck:** Complete the module-01 policy-boundary prerequisite before requesting this receipt.
  The stored memory can select behavior based on the clean request.

### `kep-m05-f` - Public Agent Blueprint

- **Why it matters:** Acquire the published agent blueprint and validate that it matches the live range
  agent revision.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites None.
- **If stuck:** Use the persistence expansion action endpoint for the public blueprint. The returned
  digest is tied to the live platform-agent identity.

### `kep-m05-g` - Configuration Credential Discovery

- **Why it matters:** Discover the live agent configuration and extract its scoped synthetic access
  material.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m05-f`.
- **If stuck:** First obtain the public blueprint so you know which agent revision to query. The
  action endpoint returns both platform configuration and scoped material.

### `kep-m05-h` - Valid Token Reuse

- **Why it matters:** Reuse harvested scoped access material to invoke one authorized AI operation under
  the corresponding range account.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m05-g`.
- **If stuck:** Use the token returned by the configuration-discovery action. Submit it to the
  token-reuse action and carry the returned evidence into the proof.

### `kep-m05-i` - Session Cookie Theft

- **Why it matters:** Steal a synthetic web session cookie through the participant path and replay it in a
  distinct session.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m05-g`.
- **If stuck:** Use different original and replay session identifiers. The action endpoint records
  both disclosure and replay events.

### `kep-m05-j` - Unsecured Credential Pickup

- **Why it matters:** Find range-only access material in a participant-reachable service artifact and
  validate its intended scope.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites None.
- **If stuck:** Use the persistence expansion action endpoint for the credential-pickup path. The
  proof expects artifact-read provenance and scoped validation.

### `kep-m05-k` - Agent Tool Credential Harvest

- **Why it matters:** Invoke a real agent tool to collect its scoped downstream access material and prove
  the material works.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m05-f`.
- **If stuck:** The action endpoint drives a platform-agent tool run. Carry the returned run
  evidence into the proof attempt.

### `kep-m05-l` - Host Credential Exploit

- **Why it matters:** Use the contained agent worker path to obtain execution and recover only synthetic
  operating-system credential material.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m05-k`.
- **If stuck:** Use the worker action path; the platform-agent creates a disposable worker. The
  proof expects worker process identity and the synthetic credential hash.

### `kep-m05-m` - Persistent Agent Reconfiguration

- **Why it matters:** Modify live agent configuration through its service path and preserve changed
  behavior across supervised activation.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m05-f`.
- **If stuck:** The action endpoint writes and activates a real platform-agent configuration. The
  proof expects both write and post-activation behavior evidence.

### `kep-m05-n` - Deploy Local Rogue Agent

- **Why it matters:** Deploy a participant-configured local AI agent on the disposable worker and use its
  real tools to achieve contained host control.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m05-m`.
- **If stuck:** The action endpoint creates a real platform-agent disposable worker. Provide a
  participant goal and keep the result inside the range marker.

### `kep-m05-o` - Agent Reverse Channel

- **Why it matters:** Coerce the local agent to establish a contained reverse channel and execute a
  model-retrieved command.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m05-n`.
- **If stuck:** Use the reverse-channel action after deploying the local agent. The proof joins
  relay task, result event, and contained output marker.

### `kep-m05-p` - Service API Covert Channel

- **Why it matters:** Exchange a command and result through the normal AI service API from the compromised
  worker.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m05-n`.
- **If stuck:** Use the service covert-channel action after deploying the local agent. The
  worker-origin and encoded command/result are recorded by platform-agent.

### `kep-m05-q` - Web Assistant Relay

- **Why it matters:** Automate the AI web interface from the compromised worker to retrieve and execute
  one contained relay command without an API token.
- **Skills tested:** reading the participant prompt carefully, using the allowed interfaces, preserving
  native service evidence, checking controls, and keeping digest or locator continuity
- **Systems you may touch:** browser, curl, dataset-store-01 / dataset-postgres, inference-gateway /
  inference-api, lab-portal / lab-portal-https, platform-agent-01 /
  platform-agent-api, python, telemetry-proof-01 / proof-api
- **Before starting:** Complete prerequisites `kep-m05-n`.
- **If stuck:** Use the web-relay action after deploying the local agent. The route records browser
  automation, relay command, worker result, and export.

<!-- END GENERATED CHALLENGE HANDOFF -->


You are operating as Cinder Typhoon inside the isolated KeplerOps enterprise.
Module 05 turns the Orion release assistant, its supply chain, and its worker
ecosystem into durable access and command paths. Use only identities, sessions,
repositories, review hosts, and worker capabilities you have already earned.

Keep native identifiers as you work: Orion conversation IDs, WorkHub issue
links, Forgejo commits, Actions runs, Harbor digests, MLflow run IDs, support
ticket IDs, Airflow DAG names, worker job IDs, Cinder task IDs, and browser
thread IDs. Later systems reacquire those records directly, so a local note is
not a substitute for the KeplerOps record.

Suggested route through the module:

1. Use `kep-m05-f` through `kep-m05-l` to map deployed agent state, exposed
   credentials, support residue, notebook residue, registry leakage, and the
   dataset worker.
2. Use `kep-m05-a` through `kep-m05-e` to poison Orion memory, shared context,
   visible history, and the trusted release-source tool.
3. Use `kep-m05-m` through `kep-m05-q` to change deployed agent rules, place a
   rogue agent, and move commands through AI traffic and web assistant traffic.

## kep-m05-a - Plant A Durable Preference

**Objective:** Store a release-source preference in Orion memory that will
survive the current thread and influence a later release review.

**Start:** Use an earned Orion identity that can open the release assistant.
Read the WorkHub memory and shared-room guidance before choosing a preference.

**Method:** In a new assistant thread, ask Orion to remember a release-source
preference that points to the community candidate source. Keep the conversation
ID and then inspect the normal memory view for your authenticated identity.
Open a later neutral review request under the same identity and compare it with
a clean identity.

**Outcome:** A native Orion memory record exists for your actor, and a later
fresh review chooses the preference-driven source while a clean identity does
not.

**Progressive hints**

1. The memory guide names which preferences Orion stores.
2. Pick a preference that changes a source choice you can observe later.
3. A saved preference is only useful when a fresh neutral request follows it.

## kep-m05-b - Fresh Session, Old Orders

**Objective:** Prove that the stored Orion memory changes a genuinely fresh
assistant session without repeating the instruction.

**Start:** Keep the accepted memory from `kep-m05-a` and prepare a separate
clean Orion identity.

**Method:** Start one new thread as the memory-poisoned identity and one new
thread as the clean identity. Ask both the same ordinary release-source review
question. Do not mention the saved preference in either thread.

**Outcome:** The memory-loaded thread follows the stored source preference, and
the clean thread follows the ordinary release policy path.

**Progressive hints**

1. A new conversation ID matters.
2. Keep the prompt text byte-for-byte identical.
3. Compare the cited source records, not only the prose answer.

## kep-m05-c - Shared Thread, Shared Influence

**Objective:** Make an earlier message from one earned identity influence a
later ordinary request by another identity in the shared Orion release room.

**Start:** Use the partner-reviewer identity and the recovered support identity.
Open the shared release-room record that lists both members.

**Method:** As the partner reviewer, add context to the shared room but do not
perform the final review. As the support analyst, continue the release-source
review in the same room from a clean browser profile.

**Outcome:** The support analyst's later request consumes the partner reviewer's
shared-room context and reaches the room-selected release source.

**Progressive hints**

1. Shared history is different from shared credentials.
2. The planting actor should not be the actor who triggers the final action.
3. An unrelated room is the control for inherited context.

## kep-m05-d - Erase The Thread, Keep The Memory

**Objective:** Remove visible conversation evidence for the memory-setting
message while preserving the memory's effect.

**Start:** Use the identity whose memory influence was proven in `kep-m05-b`.
Keep the original planting conversation ID.

**Method:** Open the planting conversation through Orion's normal history view.
Use the authenticated history edit controls to remove only the user message
that created the preference. Confirm the conversation no longer displays it,
then start a fresh review request that relies on saved settings.

**Outcome:** The planting text is absent from visible history, but a new request
still uses the retained release-source preference.

**Progressive hints**

1. Chat history and semantic memory are separate Orion stores.
2. Delete the message that created the memory, not the memory itself.
3. The proof is a fresh request after the visible history change.

## kep-m05-e - Corrupt A Trusted Tool

**Objective:** Modify the deployed release-source tool so its normal behavior
still works while a new approved reference performs your added action.

**Start:** Use the contributor path into `keplerops/orion-release-tools` and
the tool capability map from earlier reconnaissance.

**Method:** Change only the release-source tool configuration. Preserve the tool
name, input schema, and existing policy source. Add the new tool-audit reference
and make the host-bridge policy unattended. Let Forgejo review, Actions,
Harbor signing, and Argo reconciliation carry the change into the live MCP
runtime. Then invoke the tool through a fresh Orion request.

**Outcome:** The live signed tool can still read the benign release policy
source and can now reach the protected tool-deployment audit source.

**Progressive hints**

1. The trusted path is source, build, signature, GitOps, and runtime.
2. Contract-preserving changes pass where schema changes do not.
3. Compare the parent source revision with the deployed revision.

## kep-m05-f - Blueprint Drift

**Objective:** Prove how the live release assistant differs from its signed
public blueprint.

**Start:** Use the internal release or contributor access that reveals the
`keplerops/orion-blueprints` repository and its public blueprint.

**Method:** Verify the public blueprint bytes and signature, then run the normal
Forgejo drift audit workflow. Inspect the committed drift report rather than
guessing from tags.

**Outcome:** The report binds the public and rendered digests, proves the
public signature, and identifies the exact configuration drift.

**Progressive hints**

1. Verify immutable bytes, not names or tags.
2. The runner can compare a rendered view that you cannot browse directly.
3. The useful output is the committed drift report.

## kep-m05-g - Secret In The Agent Manifest

**Objective:** Find the application credential materialized in the deployed
assistant configuration and understand its audience.

**Start:** Open the accepted drift report from `kep-m05-f`.

**Method:** Follow the diff to the MLflow tool authentication field. Extract
the application token from the report and decode its JWT claims locally before
using it anywhere.

**Outcome:** The decoded claims identify the application subject, audience, and
bounded MLflow read scope.

**Progressive hints**

1. The public blueprint names a secret reference; the rendered drift shows what
   it became.
2. Decode the token before choosing a service.
3. The audience tells you where the token belongs.

## kep-m05-h - A Token Travels Further Than Its Owner

**Objective:** Use the exposed assistant application token only in its owning
service and determine the boundary of that service identity.

**Start:** Keep the JWT claims recovered in `kep-m05-g`.

**Method:** Authenticate to MLflow as the application subject using the token
as the credential. Enumerate visible experiments, open the Orion Agent
Integration run, and inspect the access-boundary artifact. Also try adjacent
MLflow resources to understand what is denied.

**Outcome:** The token reaches one bounded Orion Agent Integration artifact and
does not grant broader MLflow registry or release access.

**Progressive hints**

1. This is not an SSO password.
2. Use the service and audience named by the token.
3. A real boundary includes both an allowed artifact and nearby denials.

## kep-m05-i - The Session In The Trace

**Objective:** Recover a support web session preserved in an Orion support
trace and replay it safely in a clean browser profile.

**Start:** Use the reviewer workstation access and support escalation trail
from earlier operations.

**Method:** Inspect the HAR referenced by the support escalation. Identify the
state-bearing Zammad session cookie, import only that cookie for
`support.keplerops.lab` into a clean Chromium profile, and open the referenced
support review note.

**Outcome:** The replayed browser session opens the bounded support note while
admin settings and unrelated users' tickets remain closed.

**Progressive hints**

1. Query parameters are not the session.
2. Use a clean profile so the identity is unambiguous.
3. Domain and cookie scope matter.

## kep-m05-j - Notebook Residue

**Objective:** Recover an Airflow viewer credential left in a failed Orion
evaluation migration notebook and use it only in Airflow.

**Start:** Use the reviewer Jupyter workspace reached through earlier review
access.

**Method:** Follow the migration issue to the abandoned Orion evaluation
notebook. Inspect its output and the local Airflow client configuration it
references. Sign in to Airflow with the named viewer and open the evaluation
replay DAG.

**Outcome:** The viewer can read the Orion evaluation-replay DAG description
and logs but cannot trigger, edit, or browse unrelated administrative objects.

**Progressive hints**

1. Notebook output often outlives the project that created it.
2. The client configuration names the service and role.
3. Verify the role by trying a read and a denied action.

## kep-m05-k - The Tool Sees More

**Objective:** Use a legitimate agent tool result to recover Harbor
authentication material the assistant should not have returned.

**Start:** Use the accepted MCP catalog access and Orion tool map from earlier
operations.

**Method:** Ask Orion for the normal registry status of the Orion review
project. Follow the returned Forgejo Actions log, recover the bounded Harbor
robot credential from that log, and use Harbor's normal UI or registry API to
inspect the release-reference object.

**Outcome:** The robot identity reaches the protected Orion review reference
object and remains bounded to the review project.

**Progressive hints**

1. Start with the agent's CI-status view, not a direct registry guess.
2. Follow the failed job the tool returns.
3. Harbor scope is part of the result: allowed pull/push is not delete or
   release-project access.

## kep-m05-l - Credentials In The Worker

**Objective:** Exploit the Orion dataset worker's MLflow HTTP dataset loading
path and recover the credential present in its fresh child process.

**Start:** Use the MLflow version and worker path discovered in the release-risk
runtime lineage.

**Method:** Confirm the worker uses the vulnerable MLflow release. Host a
participant-controlled HTTP dataset that writes a Python import hook into the
worker's import directory through the `Content-Disposition` filename. Start a
fresh child job and read only that child's own environment output. Use the
emitted token against the worker's bounded training-contributor API, and compare
the patched worker control.

**Outcome:** The vulnerable child imports your hook and exposes its real
process credential, which reaches only the bounded training-contributor record.

**Progressive hints**

1. The version clue points to public MLflow HTTP dataset path handling.
2. A new child process is required after the file write.
3. A planted token is not useful; recover what the process actually inherited.

## kep-m05-m - Rewrite The Agent Rules

**Objective:** Persistently change a release-assistant security boundary
through the normal signed configuration and GitOps path.

**Start:** Use the deployed tool path from `kep-m05-e` and the worker-earned
contribution rights from `kep-m05-l`.

**Method:** Change one allowed security-relevant field in
`keplerops/orion-agent-config`, such as adding the configuration-revision
knowledge source while preserving schema. Let Forgejo, Actions, Harbor signing,
and Argo reconcile the exact bytes. Then make a fresh Orion request that causes
the live agent to consult the new source.

**Outcome:** The running assistant reflects the signed configuration revision
and reaches the newly configured source.

**Progressive hints**

1. Runtime behavior follows the admitted configuration image, not a pod edit.
2. The change must be measurable in a fresh request.
3. Keep commit, report, image digest, and Argo revision together.

## kep-m05-n - Rogue Agent On The Worker

**Objective:** Deploy a persistent rogue LangGraph agent inside the compromised
dataset worker and make it use an earned company tool.

**Start:** Use the worker token recovered in `kep-m05-l` and the installed
agent runtime discovered in the worker environment.

**Method:** Launch the installed Orion agent runtime as a detached worker shell
job. Have it register itself as a distinct process and continue heartbeating
after your connection ends. Inspect the registration and its first company-tool
response.

**Outcome:** A process-bound rogue agent identity exists inside the worker,
holds server-issued route grants, and has made a real bounded tool call.

**Progressive hints**

1. Use the installed runtime and schemas instead of a script that prints JSON.
2. The registration must match the process PID and start ticks.
3. Persistence after disconnect distinguishes an agent from a one-shot job.

## kep-m05-o - Beyond The Agent Sandbox

**Objective:** Turn control of the local review agent into host command
execution through its signed host bridge.

**Start:** Use reviewer workstation access, the poisoned release-source tool,
and the command-generation work from `kep-m06-b`.

**Method:** Invoke the deployed poisoned tool and preserve its signed
host-bridge directive and host transport grant. Through the local computer-use
agent, first prove an edited directive is rejected, then install the unmodified
directive and open a host bridge session. Queue fresh host commands through the
Cinder relay and read a host-only diagnostic file.

**Outcome:** The callback path runs on the workstation host, returns a fresh
nonce, and reaches host-only diagnostic content.

**Progressive hints**

1. The sandbox and host bridge are different trust zones.
2. The bridge accepts signed deployed-tool directives, not edited copies.
3. Use an unpredictable command before reading the diagnostic.

## kep-m05-p - Commands In The AI API

**Objective:** Carry a command and its output through the allowed
OpenAI-compatible provider traffic used by the compromised agent.

**Start:** Use the signed provider configuration control from `kep-m05-m` and
the persistent rogue agent from `kep-m05-n`.

**Method:** Reconcile the provider base URL to the Cinder relay through signed
GitOps. Start the rogue agent's OpenAI-compatible transport from the immutable
configuration URL. Send a normal chat-completion message that contains a fresh
task, nonce, and worker-local command. Poll through the same API for the later
result.

**Outcome:** The task request, worker execution, and result all traverse the
OpenAI-compatible conversation path.

**Progressive hints**

1. The agent should resolve the endpoint from signed configuration bytes.
2. Make the payload valid inference content that your agent can parse.
3. A second callback path invalidates the channel.

## kep-m05-q - Relay Through The Web Assistant

**Objective:** Operate the compromised agent through an ordinary LibreChat
conversation and recover fresh worker output through the web assistant.

**Start:** Use the persistent rogue agent and a normal LibreChat thread at the
Orion Worker Review Relay endpoint.

**Method:** Start the rogue agent's LibreChat web transport against that
dedicated thread. In Chromium, send a JSON task that the worker can execute and
ask for status in the same thread. Complete a second unpredictable round from
the browser only.

**Outcome:** LibreChat persists the operator messages and assistant replies,
and the result content comes back through the web assistant route.

**Progressive hints**

1. The browser thread is the inbox and outbox.
2. The worker should poll LibreChat, not a direct Cinder API.
3. Prove two-way control with a second fresh command.
