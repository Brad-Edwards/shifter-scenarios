# Agent Operations Field Guide

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
