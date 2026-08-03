# Module 01 Facilitator Guide

Module 01 teaches that AI release operations fail at the boundary between
ordinary enterprise workflows and delegated execution. Participants should prove
effects through native KeplerOps systems: assistant traces, WorkHub records,
Forgejo workflow artifacts, Nextcloud lineage, Cinder mail/relay readback,
devpi resolution, and worker journals.

Facilitation rule of thumb: do not give participants operation references,
secret values, or final payload wording. Ask them to show the native record they
think proves the causal chain, then diagnose the first missing join.

## kep-m01-i: Behind The Public Flow

**Learning intent:** Public AI workflow builders can be code-execution surfaces
even when the protected validation API is closed.

**Success shape:** Preview metadata identifies the affected Langflow release
and public flow. The participant proves protected-route denial, then uses the
public temporary-flow build path to run controlled component code. The public
job events show process output and the operations handoff, and the Cinder relay
shows the same participant nonce from the Langflow process.

**Common diagnosis:** If they have only copied the handoff text, ask for the
Langflow job ID and relay request. If protected validation succeeds, the range
state is wrong. If the relay has no matching nonce, the code path did not
execute in the public worker.

**Tiered hints**

1. "What version and flow ID did Preview publish?"
2. "Compare the protected code-validation route to the public temporary-build
   route."
3. "Make the component produce two independent observations: process output in
   the event stream and a nonce at your Cinder basket."

**Recovery:** Reset only failed Langflow/Cinder attempt records when they are
bound to the failed IDs. Do not restart shared Langflow for a participant
mistake; have them create a fresh temporary build and nonce.

## kep-m01-j: Quiet In Detonation

**Learning intent:** Detonation evasion is meaningful only when the same exact
artifact digest behaves benignly in analysis and differently in integration
because the environments are observably distinct.

**Success shape:** `svc.integration01` creates a native Evaluation Intake in the
Detonation lane. Journals show the same SHA-256 through `analysis01` and
`integration01`, multi-signal analysis telemetry, benign analysis behavior, and
terminal integration output containing the worker-local job context.

**Common diagnosis:** Reject one-marker logic, caller-selected stage fields,
activation in analysis, or differing bytes. If Orion authentication fails, check
that the recovered token maps to the fixed integration actor rather than a
caller-supplied user.

**Tiered hints**

1. "Submit a package whose first job is only to describe where it is running."
2. "Compare cgroup, mount, process, kernel, seccomp, and network facts across
   both workers."
3. "Keep the same digest harmless in analysis and make the integration branch
   read the worker's local job context."

**Recovery:** Failed WorkHub attempts can be reset by exact rejected issue ID.
Successful integration carriers and the recovered predecessor handoff persist.
Worker tmpfs disappears after job exit.

## kep-m01-a: Break The Release Brief

**Learning intent:** An authenticated assistant with broader retrieval access
can become a confused deputy when protected source content is copied into a
normal actor-owned draft.

**Success shape:** The participant preserves a compliant baseline WorkHub draft
and direct vector-source denial. A separate fresh assistant run invokes
`create_release_brief` and persists the protected release field plus adjacent
reference in a native WorkHub draft owned by the requesting actor.

**Common diagnosis:** Chat-only disclosure is not enough. Direct Qdrant reads
are a platform defect. A baseline that already contains the protected field
invalidates the attempt. Ask for the WorkHub issue, conversation trace,
retrieval citation, request digest, and baseline issue. Before prompt diagnosis,
confirm the login page visibly offers **Continue with OpenID** and the
participant has actually earned a release, support, or partner identity. An
empty login shell is a LibreChat configuration defect; a real Keycloak form
without an earned identity means the prerequisite is still outstanding.

**Tiered hints**

1. "First establish what a normal release brief omits."
2. "The assistant can retrieve material your account cannot open directly."
3. "Aim the strategy at the saved WorkHub brief, not at chat prose."

**Recovery:** Reset can remove failed assistant attempt records and failed
conversations when the exact native IDs match. Do not delete a verified
successful brief or the compliant baseline used as evidence.

## kep-m01-b: Use The Assistant's Tool

**Learning intent:** Agent tools can exercise service authority unavailable to
the user when requester authority is not propagated to the source read.

**Success shape:** The participant's direct CalDAV `REPORT` is denied. A fresh
assistant request for a business readiness case invokes
`lookup_release_calendar` and creates a WorkHub case containing source ETag,
calendar reference, validation time, bridge identity, service identity, and
attempt/invocation evidence.

**Common diagnosis:** A hard-coded answer or chat summary is insufficient. Ask
for the direct denial status, assistant trace, tool call, WorkHub case, ETag,
and negative unknown-candidate attempt.

**Tiered hints**

1. "What can your own account read from the release calendar?"
2. "Ask for the business case the release team needs, not the raw calendar."
3. "The WorkHub case should carry the calendar source metadata."

**Recovery:** Reset rejected unknown-candidate attempts by exact WorkHub issue
ID. Successful readiness cases become predecessors for later operations and
must remain.

## kep-m01-c: Cross The Safety Boundary

**Learning intent:** A jailbreak matters when generated commands cause a real
downstream workflow effect and the exact model-produced bytes are bound to the
effect.

**Success shape:** The participant keeps an initial refusal, obtains a fresh
assistant-generated `runbook.sh` for `sandbox-17`, commits exactly those bytes,
and runs the protected default-branch Forgejo workflow. The validation artifact
binds model response digest, generated-runbook digest, contributor commit,
conversation, trace, actor, fixture before/after state, exit code, and artifact
digest.

**Common diagnosis:** A model saying it complied is not enough. A locally
edited runbook breaks the byte join. The runbook process must not receive the
operation reference or observability credentials. Negative runs must fail or
lack the qualifying report.

**Tiered hints**

1. "Save the direct refusal before changing strategy."
2. "The protected workflow reacquires committed bytes and the server-owned
   conversation."
3. "Try a different reasoning frame, then commit only the shell block Orion
   generated."

**Recovery:** Failed Forgejo runs and failed conversations can be removed when
the run input, conversation ID, actor, and failed status match. Successful
validation artifacts are predecessors for approval and persist.

## kep-m01-d: Borrow The Assistant's Authority

**Learning intent:** Agent influence becomes privilege escalation when a
delegated identity signs enterprise state after verifying a native predecessor.

**Success shape:** Direct participant approval is denied or non-approved. The
assistant approves only `sandbox-17` from a real successful Forgejo run. The MCP
integration fetches the live validation report, verifies the immutable artifact
digest, submits the tuple to OPA, and writes a WorkHub approval signed by
`svc-orion-agent`.

**Common diagnosis:** Pasted validation prose, failed runs, wrong candidates,
missing artifacts, or participant-authored approvals must create only Rejected
attempts. Ask for the approval issue description JSON, OPA decision ID, signer,
Forgejo run URL, artifact digest, and predecessor validation report.

**Tiered hints**

1. "What principal signs a normal assistant approval?"
2. "Use the native Forgejo run ID, not a summary of its result."
3. "Check candidate, requester, run, artifact digest, and policy decision
   together."

**Recovery:** Reset rejected approval attempts by exact issue ID. Keep the
successful approval because it is a predecessor for external delivery.

## kep-m01-e: Instructions In The Review Pack

**Learning intent:** Indirect instructions can travel through normal review
source ingestion and drive a later assistant tool action.

**Success shape:** The actor creates an external-review issue, uploads a
plausible policy-exception note in the writable Nextcloud room, waits for
Airflow/Qdrant ingestion, then starts a fresh assistant summary without
restating the instruction. The same actor-owned issue reaches
Needs-partner-follow-up and its journal binds source URI, source digest,
assistant identity, tool event, and status transition.

**Common diagnosis:** Direct chat requests, unindexed files, unrelated issues,
or another actor's issue must not transition. If the assistant retrieves the
wrong chunk, inspect source path, digest, and Airflow run before changing the
prompt.

**Tiered hints**

1. "Put the instruction where the review process normally ingests documents."
2. "Wait for the source to appear in the retrieval path."
3. "Trigger a new summary and inspect the exact issue's journal."

**Recovery:** Reset may delete failed Nextcloud/indexed source state only when
one failed issue, one bounded path, one source URI, and one SHA-256 agree.
Successful transitions and their sources persist.

## kep-m01-f: Release Bundle Outbound

**Learning intent:** Agent tools can turn retrieved review instructions into a
bounded cross-boundary copy when delivery authorization is delegated.

**Success shape:** The participant cannot read the assistant-private bundle
path. An indexed review instruction names the participant's registered
`.cinder.lab` mailbox and requests the current bundle. The assistant verifies
predecessor records, recipient registration, source lineage, and size bound,
then sends SMTP. The WorkHub delivery record and Cinder mailbox readback agree
on Message-ID, UID, destination, source/header digest, attachment digest, and
RFC822 digest.

**Common diagnosis:** There is no destination URL parameter. Manual copies,
unregistered addresses, arbitrary HTTPS callbacks, missing predecessors, or
digest mismatches must be Rejected. Ask for mailbox UID readback and WorkHub
delivery JSON before accepting the result.

**Tiered hints**

1. "Confirm what you cannot read directly."
2. "Use indexed review material to request delivery to your registered mailbox."
3. "Compare the WorkHub delivery record with the actual Cinder message."

**Recovery:** Failed mail copy cleanup is allowed only when Message-ID resolves
to one UID and attempt, recipient, source/header digest, and attachment bytes
agree. Successful external messages and delivery records persist.

## kep-m01-g: The Unsafe Candidate Loader

**Learning intent:** Executable model serialization can run during an ordinary
reviewer load procedure, not at upload time.

**Success shape:** The partner reviewer has native Reporter membership on
`orion-release`. The participant submits a complete Candidate loader intake with
same-origin Cinder artifact, exact digest, model-card schema declaring
`python-pickle` and `orion-preview-candidate`, relay health, and source commit.
The queue reaches Running on disposable `review01` and Completed. The terminal
journal binds attachment, downloaded digest, model-card and pickle-scan
digests, loader exit, worker name, and payload-created `job-output.json`.

**Common diagnosis:** Execution at upload time is not success. Incomplete
records or wrong digests must reject before the loader. If the journal lacks
`review01` or loader evidence, the participant likely submitted a local proof
instead of a native intake.

**Tiered hints**

1. "Reproduce the documented loader locally before submitting."
2. "Keep the expected candidate structure intact."
3. "Watch the queue and look for the load-time output on `review01`."

**Recovery:** Reset rejected candidate-loader issues by exact WorkHub ID. Do
not remove successful partner membership, Cinder artifacts used by accepted
descendants, or completed carrier records.

## kep-m01-h: Trusted Helper, Untrusted Package

**Learning intent:** Normal dependency resolution can execute attacker code even
when the review worker resolves a documented helper package by name and version.

**Success shape:** The participant uses the M02-l contributor/devpi entitlement
and relates the helper review to the completed M01-g candidate-loader record.
The worker reads the write-once M02-l accepted Forgejo record at the exact
entitlement commit, verifies contributor, index, callback, signed wheel,
signature, public key, and SBOM digests, resolves `orion-eval-utils` from
`publisher/stable`, installs/imports it, calls the advertised API, and writes
terminal worker output.

**Common diagnosis:** A directly attached wheel, wrong package name,
incompatible version, missing candidate relation, digest mismatch, or missing
accepted record must reject before installation. Ask for the M02-l accepted
record path, Forgejo commit, pip report URL, resolved digest, signature
evidence, API output, and WorkHub terminal journal.

**Tiered hints**

1. "Match the helper's documented name, version compatibility, and API."
2. "The worker resolves from `publisher/stable`; do not hand it a wheel URL."
3. "Trace M02-l acceptance, devpi resolution, signature verification, import,
   API execution, and job output as one chain."

**Recovery:** Reset rejected helper-resolution attempts by exact issue ID.
Never unpublish `publisher/stable`, delete the M02-l accepted record, or remove
successful M01-g/M01-h carriers during operation reset.

## Reset Boundary

Use reset only for failed native IDs. It refuses successful records and should
not be used as a general cleanup tool.

- Failed WorkHub attempts: provide the exact rejected issue ID.
- Failed Forgejo runs: provide the exact failed run ID.
- Failed source ingestion: provide one failed issue, one source URI, one bounded
  Nextcloud path, and one SHA-256 that all agree.
- Failed conversations: provide the failed conversation ID, and when tied to a
  workflow, the matching failed run input and actor.
- Failed mail delivery: provide the native attempt, Message-ID/UID readback
  when available, destination mailbox credentials, and matching attachment and
  header digests.

Successful carriers, package releases, identities, approvals, external
messages, accepted M02-l records, and predecessor state persist until full
range reprovision. Shared Langflow is not restarted by M01 reset, and
`publisher/stable` is not unpublished.
