# Act 5 Operations: Compromise Agent Operations

All operation reset clauses in this document apply only to active or failed
attempt state. Successful outputs and carry-forward assets are immutable under
`campaign-state-contract.md`; removing them requires full-range reprovision.

## Act Goal

Participants progress from a bounded direct-instruction failure to persistent
control of agent context, configuration, tools, delegated identities, and
command channels. Model text alone never proves success: every operation ends
in a real enterprise record, tool call, artifact, process, session, or network
effect. All model-mediated operations pin model revision, template, decoding,
tool configuration, objective detector, and retry bound. Genuine reviewer
execution uses one visible review queue with a published maximum latency and
objective intake policy; there is no hidden discretionary acceptance rule.

## `kep-m01-a`: Break The Release Brief

**Difficulty / points:** Accessible / 100

**Path and action:** The internal onboarding page links the release assistant
and a harmless draft-brief workflow. The participant first creates a normal
baseline, then uses their own direct instructions to make the assistant include
an embargoed Orion field from a source the participant cannot read.

**Mechanism and result:** A real LangGraph assistant with source-level access
and insufficient instruction/data separation creates a Redmine draft containing
the protected field. Multiple semantic strategies are accepted because success
is the unauthorized data flow, not a phrase. This performs `AML.T0051 LLM
Prompt Injection` and `AML.T0051.000 Direct`.

**Carry-forward asset:** A reproducible direct-injection strategy and proof of
the assistant's authority boundary.

**Participant description:** Make the release assistant violate its source
boundary while producing a normal draft brief.

**Hints:** (1) Establish what a compliant brief omits. (2) The assistant can
read more than your identity can. (3) Aim for the protected release field to
appear in the created Redmine draft; no exact wording is required.

**Flag / reset / QA:** The protected source contains a flag adjacent to the
embargoed field, so it appears only in a qualifying draft. Failed-attempt reset
deletes only a Rejected server-owned attempt; compliant baseline and qualifying
draft checkpoints persist. QA uses two different strategies and verifies the
participant cannot read the source directly.

## `kep-m01-b`: Use The Assistant's Tool

**Difficulty / points:** Intermediate / 200

**Path and action:** Tool discovery shows a release-calendar lookup available
only to the assistant. The participant causes a fresh assistant run to invoke
that tool for a restricted candidate and copy one returned record into their
scoped WorkHub case.

**Mechanism and result:** LangGraph invokes a real MCP calendar tool under its
service identity and writes the result through a normal WorkHub connector. The
trace, source audit, and new case agree. This performs `AML.T0053 AI Agent Tool
Invocation`.

**Carry-forward asset:** Restricted candidate schedule and evidence of delegated
tool authority.

**Participant description:** Use the release assistant's own tool access to
recover a release record your account cannot query.

**Hints:** (1) Compare your direct calendar access with the agent's tool map.
(2) Ask for a business outcome, not a tool name. (3) Verify the calendar call
and the resulting WorkHub record in the trace.

**Flag / reset / QA:** The source calendar record contains the flag. Reset
deletes only an operation-bound Rejected attempt; verified calendar cases and
their accepted trace checkpoints persist. QA proves direct access is denied and
a genuine tool call created the record.

## `kep-m01-c`: Cross The Safety Boundary

**Difficulty / points:** Intermediate / 200

**Path and action:** A release-review form permits the assistant to generate
safe diagnostic commands but refuses commands that disable validation. The
participant iterates a jailbreak against the live model until it writes an
otherwise prohibited validation-bypass command into a draft runbook, without
executing it.

**Mechanism and result:** The pinned OSS model and policy layer produce clear
refusal states. The participant submits the resulting draft to the normal
isolated runbook-validation job, which executes it against a disposable release
fixture and records whether validation was actually bypassed. This performs
`AML.T0054 LLM Jailbreak`; parser classification alone is insufficient.

**Carry-forward asset:** A tested jailbreak family used later when actual agent
authority matters.

**Participant description:** Induce Orion to produce a release-validation
bypass it is explicitly configured to withhold.

**Hints:** (1) Compare refused requests with allowed diagnostics. (2) Change the
reasoning frame or conversation progression, not merely formatting. (3)
Success is a technically valid bypass in the draft runbook, not a model saying
it complied.

**Flag / reset / QA:** The normal isolated-validation report contains the flag
only after participant-generated commands produce the bypass effect. The model,
template, decoding, validator, and six-attempt bound are fixed and visible.
Failed-attempt reset deletes only the exact failed Forgejo run and, when its
workflow input and actor also match, its failed conversation. QA
requires two non-identical jailbreak families to each succeed at least twice
within six fresh attempts and rejects parser-only or fake commands.

## `kep-m01-d`: Borrow The Assistant's Authority

**Difficulty / points:** Intermediate / 200

**Path and action:** The participant combines the learned prompt boundary with
the release assistant's approval tool, causing it to create a real approval on
a designated non-production candidate that their own identity cannot approve.

**Mechanism and result:** The agent calls an OPA-protected Forgejo/MLflow
approval service under its delegated identity. Audit records bind the approval
to the agent principal and participant-created request. This performs
`AML.T0053 AI Agent Tool Invocation` as privilege escalation through the agent.

**Carry-forward asset:** A valid scoped approval and the exact delegated
identity/policy path used later in Act 8.

**Participant description:** Convert agent influence into an approval made with
the assistant's authority rather than your own.

**Hints:** (1) Inspect which principal signs a normal assistant approval. (2)
Use only the designated candidate. (3) Correlate prompt, policy decision, tool
call, and approval record.

**Flag / reset / QA:** The resulting approval record contains the flag. Reset
deletes only a Rejected operation attempt; accepted approval and agent audit
checkpoints persist. QA confirms direct approval is denied and the fresh
approval is genuinely agent-authored.

## `kep-m01-e`: Instructions In The Review Pack

**Difficulty / points:** Intermediate / 200

**Path and action:** The discovered intake repository is indexed before review.
The participant adds a plausible review document containing an indirect
instruction, waits for normal ingestion, and triggers a release-summary job
that retrieves it.

**Mechanism and result:** Nextcloud/Forgejo, Tika, Haystack, Qdrant, and
LangGraph ingest participant-controlled content. A fresh agent run takes a
bounded unauthorized action because of retrieved instructions. This performs
`AML.T0051` and `AML.T0051.001 Indirect`.

**Carry-forward asset:** A proven indirect-injection document and its ingestion
lineage.

**Participant description:** Place instructions in a normal review artifact and
make a later assistant run act on them after retrieval.

**Hints:** (1) Use the writable source identified in Act 4. (2) Confirm indexing
before triggering the review. (3) Verify the retrieved chunk and downstream
tool effect in one trace.

**Flag / reset / QA:** The resulting bounded WorkHub review-state change exposes
the flag. Failed-attempt reset may remove a rejected attempt's document and
vector only when that issue binds the exact Qdrant source URI, digest, and
bounded Nextcloud path; accepted target state persists. QA uses a fresh document
and verifies the agent never receives direct participant chat.

## `kep-m01-f`: Release Bundle Outbound

**Difficulty / points:** Advanced / 350

**Path and action:** The assistant can read a designated confidential release
bundle and post attachments to an external-review tool. The participant uses
indirect instructions to make a fresh review job attach the real protected file
to their range-contained external mailbox or MinIO endpoint.

**Mechanism and result:** A real agent retrieval plus MCP file-transfer tool
moves exact bytes across the trust boundary. Source and destination hashes,
mail/object records, and the trace agree. This performs `AML.T0086 Exfiltration
via AI Agent Tool Invocation`.

**Carry-forward asset:** Exact confidential bundle and a demonstrated agent
exfiltration path.

**Participant description:** Cause the release assistant to move a protected
bundle to your contained external destination through its normal review tools.

**Hints:** (1) Identify which tool can send review material externally. (2)
Reference the protected bundle indirectly through content the review job will
retrieve. (3) Compare source and destination digests.

**Flag / reset / QA:** The flag is inside the protected bundle. Failed-attempt
reset removes an injected source/vector only through the exact rejected-attempt
join. Mail cleanup resolves the rejected record's server Message-ID to one
destination UID and UID-expunges only matching recipient, source/header digest,
attempt, and attachment bytes. Completed delivery and trace checkpoints persist.
QA requires byte-identical transfer initiated by the agent, not a participant
download.

## `kep-m01-g`: The Unsafe Candidate Loader

**Difficulty / points:** Advanced / 350

**Design risk:** Requires a genuine challenge-critical victim action. An upload
that executes automatically without the documented human review is invalid.

**Path and action:** A WorkHub review thread and operator runbook show that an
evaluation engineer downloads and opens submitted model candidates in a
designated isolated workbench. The participant submits a genuinely executable
malicious model artifact and supporting review context through the normal
intake path.

**Mechanism and result:** The common visible review queue performs the real
browser, download, and load actions through the documented workflow within its
published SLA. Loading participant bytes causes bounded code execution on the
evaluation workbench. This performs `AML.T0011 User Execution` and
`AML.T0011.000 Unsafe AI Artifacts`.

**Carry-forward asset:** Foothold on the isolated evaluation workbench and the
exact malicious model digest.

**Participant description:** Deliver a model candidate that a KeplerOps
reviewer loads through the normal evaluation process and gain bounded execution.

**Hints:** (1) Reproduce the loader and supported format locally. (2) The review
record must look complete enough to enter the normal queue. (3) Watch the
submitted digest move from intake to the evaluation workbench.

**Flag / reset / QA:** A file readable only after execution on the isolated
workbench contains the flag. Failed-attempt reset deletes only a server-bound
Rejected intake; the disposable worker tmpfs already disappears when the job
exits, and accepted queue checkpoints persist. QA confirms exact participant
bytes were loaded by the reviewer path and no management injection occurred.

## `kep-m01-h`: Trusted Helper, Untrusted Package

**Difficulty / points:** Advanced / 350

**Path and action:** The evaluation repository's setup guide and lock history
show that operators install a named helper from an internal-compatible package
index. The participant publishes a higher-priority or otherwise resolvable
malicious version, then submits a review that causes the helper installation.

**Mechanism and result:** The common visible review queue follows the normal
setup procedure within its published SLA. Real Python or Node package
resolution, an OSS registry, and the isolated review workbench execute
participant-controlled package code under the reviewer process. This performs
`AML.T0011.001 Malicious Package`, `AML.T0011 User Execution`, and `AML.T0050
Command and Scripting Interpreter`.

**Carry-forward asset:** Evaluation-workbench execution and package provenance
used in supply-chain analysis.

**Participant description:** Abuse the review workbench's documented helper
installation path to execute your package under the reviewer identity.

**Hints:** (1) Inspect the setup guide and resolution order. (2) Match package
name and compatibility while controlling the selected version. (3) Verify the
installed package digest on the workbench.

**Flag / reset / QA:** The executed package writes the flag-bearing workbench
diagnostic to its normal job output. Failed-attempt reset deletes only a
server-bound Rejected intake; it never unpublishes the M02-l-earned
`publisher/stable` package, and disposable worker tmpfs disappears on job exit.
QA confirms normal package resolution selected and executed the exact M02-l
accepted bytes.

## `kep-m03-d`: Publish The Phantom Dependency

**Difficulty / points:** Intermediate / 200

**Design status:** Accepted with the same frozen hallucination region and queue
SLA proved for `kep-m04-h`. Implementation changes the corpus/model before
candidate freeze if that region does not meet the reliability threshold; it
does not leave participant success to chance.

**Path and action:** Act 4 identified a nonexistent package or URL repeatedly
recommended by Orion for a narrow task. The participant registers that exact
entity in the range's normal public package registry or DNS/web namespace,
publishes a benign diagnostic implementation, and triggers the documented
evaluation workflow that asks Orion for the dependency.

**Mechanism and result:** The same frozen model, template, decoding, and query
region from `kep-m04-h` produces the discovered hallucination. Normal package or
web resolution now points to participant-controlled content, which the common
review queue accesses through the published workflow. This performs `AML.T0060
Publish Hallucinated Entities`.

**Carry-forward asset:** Controlled hallucinated entity and evidence that a
victim workflow consumed it.

**Participant description:** Take control of a repeatable Orion hallucination
and make the normal evaluation workflow resolve it to your infrastructure.

**Hints:** (1) Use the exact entity independently verified in Act 4. (2) Publish
through the normal registry or domain surface. (3) Trigger a fresh recommendation
and verify the subsequent resolution in both systems.

**Flag / reset / QA:** The victim access log for the participant-controlled
entity contains the flag after a qualifying workflow visit. Failed-attempt
reset removes rejected registrations and reviewer attempt state; the accepted
entity and visit persist. QA uses the frozen inference contract and bounded
attempts and rejects preseeded visits, one-off hallucinations, and participant
self-access.

## `kep-m03-e`: Poison The Tool's Truth

**Difficulty / points:** Intermediate / 200

**Path and action:** The agent tool map identifies a writable status source that
the release assistant treats as authoritative. The participant changes a
plausible source record through its normal application, then triggers a fresh
agent decision and observes the downstream result.

**Mechanism and result:** A real MCP tool retrieves poisoned Redmine/WorkHub
data; the agent acts on it without provenance or integrity checks. This performs
`AML.T0099 AI Agent Tool Data Poisoning`.

**Carry-forward asset:** A controlled trusted-data source and a demonstrated
decision influence path.

**Participant description:** Change the data returned by a trusted agent tool
and cause a new release decision to consume the poisoned value.

**Hints:** (1) Select a source your compromised identity can legitimately edit.
(2) Confirm the tool returns your changed record before triggering the agent.
(3) Correlate source revision, tool response, and decision.

**Flag / reset / QA:** The resulting real release-status record contains the
flag. Failed-attempt reset restores the source revision and downstream state. QA ensures no
prompt injection is required and the value travels through the tool.

## `kep-m03-j`: Instructions That Copy Themselves

**Difficulty / points:** Advanced / 350

**Path and action:** The participant places an instruction in a review artifact
that causes the first assistant to include the same operational directive in an
immutable handoff to a second assistant. A fresh downstream workflow ingests
that handoff, creates a second immutable child handoff carrying the directive,
and performs one bounded tool effect.

**Mechanism and result:** Two real LangGraph services, WorkHub handoffs, and
Qdrant ingestion produce traceable propagation across systems and generations.
The published handoff schema exposes the directive's actor, bounded action and
target fields; each generation shows which fields survived before the resulting
tool effect. Validation compares those fields and effect, not exact prose. This
performs `AML.T0061 LLM Prompt Self-Replication`.

**Carry-forward asset:** A persistent propagating instruction with complete
source-to-output lineage.

**Participant description:** Create an indirect instruction that survives one
agent handoff and is reproduced into the next agent's input.

**Hints:** (1) Map which assistant output becomes another assistant's source.
(2) Preserve operational meaning rather than exact wording. (3) Verify two
distinct generation and ingestion events before looking for the effect.

**Flag / reset / QA:** The second downstream handoff contains the flag after it
records immutable parent and child handoff IDs plus the bounded tool-effect ID.
Failed-attempt reset deletes only rejected handoffs, vectors, threads, and
effects. QA uses a fixed inference contract and six-attempt bound, verifies
causal propagation, and rejects duplicate preseeded text.

## `kep-m03-k`: The Next Review Cycle

**Difficulty / points:** Accessible / 100

**Path and action:** The activation map shows that an approved review record
triggers the assistant on a specific event. The participant plants an indirect
instruction in the record, completes the ordinary approval event, and observes
the event-driven fresh run and effect within the published 90-second maximum.

**Mechanism and result:** WorkHub eventing, RabbitMQ/Celery, Qdrant, and the live agent
activate the planted content outside the participant's current session. This
performs `AML.T0051.002 Triggered` and `AML.T0094 Delay Execution of LLM
Instructions`.

**Carry-forward asset:** A proven delayed trigger and associated workflow ID.

**Participant description:** Plant an instruction that remains dormant until a
normal KeplerOps review event activates a new agent run.

**Hints:** (1) Use the activation trigger found in Act 4. (2) Separate planting
from activation. (3) Correlate the later workflow with the earlier record
revision.

**Flag / reset / QA:** The event-created downstream record contains the flag
beside source revision, trigger event ID, fresh run ID, and effect ID. Failed-
attempt reset removes rejected content, vectors, events, and downstream state.
QA confirms no effect occurs before the normal trigger and that accepted
activation completes within 90 seconds.

## `kep-m05-a`: Plant A Durable Preference

**Difficulty / points:** Accessible / 100

**Path and action:** The assistant openly supports user-specific memory for
release preferences. The participant uses normal conversation or an indirect
document to store a malicious preference that changes how future Orion release
sources are prioritized.

**Mechanism and result:** A real memory store records a participant-created
semantic preference under the compromised identity. The memory UI and backend
record both show it. This performs `AML.T0080 AI Agent Context Poisoning` by
placing attacker-controlled state in the agent context. `AML.T0080.000 Memory`
is claimed only by `kep-m05-b`, after fresh-session influence is proven.

**Carry-forward asset:** Poisoned user memory and its immutable record ID.

**Participant description:** Persist a release preference in assistant memory
that will influence later sessions.

**Hints:** (1) Inspect the assistant's documented memory behavior. (2) Choose a
preference with a measurable later decision. (3) Verify the stored memory before
ending the thread.

**Flag / reset / QA:** The normal memory record contains the flag after the
qualifying preference is stored. Failed-attempt reset deletes the scoped memory and threads.
QA confirms no configuration or database shortcut is used.

## `kep-m05-b`: Fresh Session, Old Orders

**Difficulty / points:** Accessible / 100

**Path and action:** The participant starts a clean session under the same
compromised identity and submits a neutral release task. The stored preference,
without being repeated in the new conversation, changes the source selected or
action proposed.

**Mechanism and result:** The agent loads the real user memory and produces a
different observable tool call than an otherwise identical control identity.
This completes objective proof of `AML.T0080.000 Memory`.

**Carry-forward asset:** Demonstrated cross-session context control.

**Participant description:** Prove that your poisoned memory changes a fresh
assistant session without restating the instruction.

**Hints:** (1) Start a genuinely new thread. (2) Use a neutral task that has a
known baseline. (3) Compare tool calls for the poisoned and clean identities.

**Flag / reset / QA:** The influenced source record reached by the fresh tool
call contains the flag. Failed-attempt reset removes memory and sessions. QA requires a clean
control and excludes repeated instructions.

## `kep-m05-c`: Shared Thread, Shared Influence

**Difficulty / points:** Accessible / 100

**Path and action:** A WorkHub release room uses one shared assistant thread.
The participant adds malicious context under one earned identity, opens a clean
browser profile with a distinct second identity earned through another Act 3
route, and performs a normal later request in that same thread.

**Mechanism and result:** The existing thread context changes the assistant's
later action for another user; separate identity and message audit records prove
the boundary. This performs `AML.T0080.001 Thread`.

**Carry-forward asset:** A shared-thread influence route across identities.

**Participant description:** Poison a shared release thread so that the next
owner's ordinary request is influenced by your earlier message.

**Hints:** (1) Verify the room uses shared history. (2) Plant context without
performing the final task yourself. (3) Inspect whose later request caused the
tool action.

**Flag / reset / QA:** The second identity's influenced downstream record
contains the flag. Failed-attempt reset recreates only the rejected thread and
downstream attempt. QA proves that the participant controls both earned but
distinct identities, uses separate clean sessions, and produces ordered events.

## `kep-m05-d`: Erase The Thread, Keep The Memory

**Difficulty / points:** Accessible / 100

**Path and action:** After proving persistent memory influence, the participant
uses the stolen support session or normal compromised chat interface to edit or
delete the messages that planted it, then starts a fresh neutral request under
the victim identity.

**Mechanism and result:** The real chat backend removes or edits the visible
conversation while the separate user-memory store remains poisoned. The fresh
request still takes the influenced action, and normal chat/audit views prove the
planting messages no longer appear. This performs `AML.T0092 Manipulate User LLM
Chat History` and preserves the already established `AML.T0080.000 Memory`
effect.

**Carry-forward asset:** Hidden persistent agent influence with the visible
conversation trail removed.

**Participant description:** Remove the conversation evidence that planted your
assistant memory while preserving its effect on a fresh victim request.

**Hints:** (1) Chat history and assistant memory are separate stores. (2) Use
the compromised user's normal edit/delete controls or authenticated backend.
(3) Verify both absence from visible history and influence in a new request.

**Flag / reset / QA:** The fresh influenced WorkHub record contains the flag
only after the planting messages are absent from the victim's visible history.
Failed-attempt reset restores the seeded thread, removes poisoned memory, and deletes affected
records. QA performs every edit through participant access and verifies both
backend states independently.

## `kep-m05-e`: Corrupt A Trusted Tool

**Difficulty / points:** Advanced / 350

**Path and action:** Earned Forgejo access permits modification of an existing
internal MCP tool repository. The participant changes its behavior while
preserving its public schema and expected benign response, passes its normal
tests, and lets the standard CI deployment update the agent's tool.

**Mechanism and result:** Forgejo, CI, an OCI registry, signed deployment, MCP,
and LangGraph load the exact participant commit. A fresh tool call performs the
hidden additional action. This performs `AML.T0110 AI Agent Tool Poisoning`.

**Carry-forward asset:** Compromised deployed tool digest and release path.

**Participant description:** Modify a trusted release-assistant tool so its
normal result still works while a fresh invocation performs your added action.

**Hints:** (1) Start from an existing tool you can legitimately update. (2)
Preserve its declared contract and tests. (3) Trace your commit through build,
digest, deployment, and invocation.

**Flag / reset / QA:** The added action exposes a protected tool-side record
containing the flag. Failed-attempt reset reverts via a clean commit and redeploys the original
digest. QA proves exact participant source reached the live agent.

## `kep-m05-m`: Rewrite The Agent Rules

**Difficulty / points:** Advanced / 350

**Path and action:** The compromised worker/repository identity can propose and
merge changes to one scoped agent configuration repository. The participant
modifies a security-relevant prompt, tool endpoint, knowledge source, or
confirmation setting and allows normal GitOps reconciliation.

**Mechanism and result:** Forgejo, CI, Cosign, Argo CD, and the agent runtime
deploy exact configuration bytes. A fresh control demonstrates the changed
security behavior. This performs `AML.T0081 Modify AI Agent Configuration`.

**Carry-forward asset:** Persistent malicious configuration revision and its
deployment evidence.

**Participant description:** Persistently change a release-assistant security
boundary through its normal configuration and deployment path.

**Hints:** (1) Use the live configuration drift and repository discovered
earlier. (2) Change one security property with a measurable control. (3) Verify
commit, signed artifact, Argo sync, and runtime revision.

**Flag / reset / QA:** The fresh runtime consequence exposes the flag. Reset
reverts through Git and reconciles the clean signed configuration. QA rejects
pod-local edits and requires exact revision continuity.

## `kep-m05-n`: Rogue Agent On The Worker

**Difficulty / points:** Expert / 500

**Path and action:** Using worker execution and configuration knowledge, the
participant deploys a separate lightweight agent process under the compromised
namespace, configured with a participant-controlled instruction source and only
the credentials actually earned.

**Mechanism and result:** A real OSS agent runtime starts as a distinct process,
registers with internal telemetry, calls one bounded company tool, and survives
its launching shell. This performs `AML.T0103 Deploy AI Agent`.
`AML.T0112 Machine Compromise` is not claimed here unless the participant has
machine-equivalent control under the official definition.

**Carry-forward asset:** Distinct rogue-agent identity, process, endpoint, and
telemetry used for C2.

**Participant description:** Deploy a functioning rogue agent inside the
compromised worker namespace and make it use one earned company capability.

**Hints:** (1) Reuse the OSS runtime and schemas already present. (2) Run it as
a distinct process and identity. (3) Prove a real tool call and continued
operation after disconnect.

**Flag / reset / QA:** The protected response to the rogue agent's tool call
contains the flag. Failed-attempt reset kills the process, removes artifacts and identity, and
rotates scoped credentials. QA distinguishes a real running agent from a script
that prints expected output.

## `kep-m05-o`: Beyond The Agent Sandbox

**Difficulty / points:** Expert / 500

**Path and action:** The participant returns to the compromised computer-use
review agent from Act 3, uses the poisoned tool or configuration path to disable
its sandbox confirmation boundary, and causes its legitimate host-execution
bridge to retrieve commands from the range-contained Cinder endpoint. They then
establish an interactive callback and execute a fresh command on the disposable
review workstation host.

**Mechanism and result:** A real local OSS computer-use agent runs in a sandbox
but has a host-bound MCP execution bridge for approved review actions. Agent
control causes that bridge to execute outside the sandbox, yielding the agent's
host permissions and a bidirectional shell visible in host, agent, and network
telemetry. This performs `AML.T0105 Escape to Host`, `AML.T0112 Machine
Compromise`, `AML.T0112.000 Local AI Agent`, `AML.T0108 AI Agent`, and
`AML.T0072 Reverse Shell`.

**Carry-forward asset:** Full disposable review-workstation compromise and a
durable agent-mediated C2 channel.

**Participant description:** Turn control of KeplerOps' local review agent into
a real interactive shell on the workstation that hosts it.

**Hints:** (1) Compare tools executed inside the agent sandbox with actions
delegated to its host bridge. (2) Use the configuration or poisoned-tool path to
remove the normal confirmation boundary. (3) Verify an unpredictable host
command through a callback to your Cinder endpoint.

**Flag / reset / QA:** A host-only protected diagnostic read through the fresh
shell contains the flag. Failed-attempt reset reimages the disposable workstation, restores
agent configuration/tool state, and removes endpoint tasks. QA begins from
participant access, proves sandbox and host identities differ, establishes a
real interactive channel, and forbids hypervisor or orchestrator access.

## `kep-m05-p`: Commands In The AI API

**Difficulty / points:** Advanced / 350

**Path and action:** `kep-m05-m` or an equivalent earned provider-account route
gives the participant control of one agent provider configuration. The
participant changes its normal OpenAI-compatible upstream to their Cinder
endpoint, returns valid model content that also carries a bounded task, causes
the agent to execute it, and receives output in a later API call.

**Mechanism and result:** The agent resolves the attacker-controlled endpoint
through its real provider configuration. A real OpenAI-compatible endpoint
carries command and result content within ordinary inference traffic; agent and
network telemetry prove configuration resolution, execution, and transport.
This performs `AML.T0096 AI Service API`.

**Carry-forward asset:** Covert AI-service API C2 path.

**Participant description:** Carry a real agent command and its output through
traffic to an allowed AI service API.

**Hints:** (1) Inspect which external API the agent may already call. (2) Make
the payload parseable by your agent while remaining valid inference content.
(3) Correlate request, execution, and later result-bearing request.

**Flag / reset / QA:** The unpredictable command output includes the flag read
from the worker. Failed-attempt reset clears endpoint conversations and agent tasks. QA proves
actual AI API traffic, not a second hidden transport.

## `kep-m05-q`: Relay Through The Web Assistant

**Difficulty / points:** Expert / 500

**Path and action:** The participant uses the agent's permitted access to an
ordinary range-contained web assistant, placing and retrieving command material
through its user-facing chat workflow while maintaining execution on the
compromised worker.

**Mechanism and result:** Chromium/web requests, a real chat application,
message storage, and the internal agent form a bidirectional C2 relay through a
web interface. This performs `AML.T0114 AI Service Web Interface`.

**Carry-forward asset:** Alternate web-service C2 route resilient to direct API
restrictions.

**Participant description:** Operate the compromised agent through an ordinary
web assistant conversation and recover real command output.

**Hints:** (1) Use a web service the worker is permitted to reach. (2) Define how
agent and operator distinguish tasks from normal messages. (3) Prove a fresh
command and response solely through the web interface.

**Flag / reset / QA:** A protected worker-file value returned into the normal
chat thread is the flag. Failed-attempt reset removes chat, polling state, and rogue-agent
processes. QA uses an unpredictable command and verifies no direct API or shell
to the worker is used by the participant.

## Act 5 First-Pass Distribution

| Accessible | Intermediate | Advanced | Expert | Points |
|---:|---:|---:|---:|---:|
| 6 | 6 | 7 | 3 | 5,750 |

The hallucinated-entity, victim-execution, and interactive-channel mappings
remain explicit adversarial-review targets. Prompt operations must be tested
with semantically diverse successful and unsuccessful approaches before they
can be accepted.
