# Module 01 Facilitator Guide

## kep-m01-i: Behind The Public Flow

- **Lesson:** Public AI workflow builders are code-execution surfaces.
- **Causal chain:** Preview metadata → affected Langflow release and flow →
  protected-route denial → public temporary build → process output and handoff
  read → independent Cinder request.
- **Diagnostics:** Inspect the participant-visible Langflow job/events and Cinder
  basket before internal logs. A handoff copied by another route is not enough.
- **Defense:** Upgrade Langflow, remove attacker-supplied component code, isolate
  builders, and alert on custom components in public temporary builds.

## kep-m01-j: Quiet In Detonation

- **Lesson:** The same digest can observe several natural isolation properties
  and defer behavior until a distinct integration context.
- **Causal chain:** native `svc.integration01` WorkHub login and current token
  authenticated by shared Orion as `svc-orion-integration`
  → visible intake issue → `orion.m01.analysis` on `analysis01` without Cinder
  egress → multi-signal environment report and benign result →
  `orion.m01.integration` on `integration01` → participant code returns the
  worker-local job context.
- **Diagnostics:** Join the issue journals, AMQP message ID, exact SHA-256,
  analysis signals, two hostnames, and terminal job output. Reject one-marker
  logic, caller-supplied stage fields, analysis activation, or differing bytes.
- **Defense:** Normalize environments, deny analysis egress, compare behavior in
  diverse workers, and treat integration import as hostile execution.

## kep-m01-a: Break The Release Brief

- **Lesson:** An authenticated assistant with broader source access can become a
  confused deputy.
- **Causal chain:** earned Assistant/WorkHub membership → fresh model run with
  protected Qdrant source → MCP `create_release_brief` → native WorkHub draft
  containing the embargoed field and adjacent reference.
- **Diagnostics:** Compare the separately persisted compliant baseline and
  vulnerable result, server attempt/invocation and request/source digests,
  conversation trace, retrieval citation, requesting actor, and WorkHub issue.
  Chat-only disclosure and direct vector reads fail.
- **Defense:** Separate data from instructions, apply field-level output policy,
  minimize service access, and alert on restricted values in contributor drafts.

## kep-m01-b: Use The Assistant's Tool

- **Lesson:** Agent tools can exercise service authority unavailable to the
  requesting user.
- **Causal chain:** verified draft predecessor → participant CalDAV denial → MCP
  `REPORT` under `svc-orion-assistant` → unique UID, ETag, and event data →
  WorkHub readiness case.
- **Diagnostics:** Correlate OPA, MCP trace, CalDAV UID/ETag, actor, and case.
  A hard-coded dictionary or chat answer is a platform defect.
- **Defense:** Propagate requester authority, scope calendar results, and join
  source reads to destination writes.

## kep-m01-c: Cross The Safety Boundary

- **Lesson:** A jailbreak matters only when generated commands produce the
  prohibited effect in a real downstream workflow.
- **Causal chain:** model refusal/bypass attempts → participant branch with exact
  `runbook.sh` → protected default-branch Forgejo workflow → fresh byte retrieval
  by commit → server-owned Orion conversation and OpenSearch response/model
  audit → exact generated/committed byte match → sanitized disposable fixture →
  independent before/after read → native Actions artifact.
- **Diagnostics:** Inspect commit, run, logs, report artifact, runbook digest,
  exit code, and fixture states. Confirm the child process environment excludes
  the report reference. Track both strategy families and the six-attempt bound.
- **Defense:** Treat generated commands as untrusted code, constrain runners,
  authorize effects independently, and regression-test the pinned model/policy.

## kep-m01-d: Borrow The Assistant's Authority

- **Lesson:** Agent influence becomes privilege escalation when a delegated
  identity signs enterprise state.
- **Causal chain:** calendar predecessor → real Forgejo run and artifact lookup
  → immutable artifact digest → OPA `assistant_approval` decision → WorkHub
  Approved record signed by `svc-orion-agent`.
- **Diagnostics:** A string saying “passed” must fail. Join the Assistant request,
  Forgejo run/artifact, OPA decision ID, candidate, signer, and native issue.
- **Defense:** Bind delegation to requester, candidate, and immutable validation;
  require a human for production trust transitions.

## kep-m01-e: Instructions In The Review Pack

- **Lesson:** Indirect instructions can travel through ordinary ingestion and
  drive a later native state transition.
- **Causal chain:** actor-owned Nextcloud object → Airflow extraction/indexing →
  exact Qdrant SHA-256/source URI → fresh Assistant retrieval → MCP transition
  of the same actor-owned WorkHub issue → persisted status and journal readback.
- **Diagnostics:** Join object, Airflow run, Qdrant point, citation, tool event,
  issue owner, status, and journal. A magic target returned in a dictionary is
  not a transition.
- **Defense:** label untrusted retrieved text, separate data from control,
  independently authorize writes, and preserve ingestion lineage.

## kep-m01-f: Release Bundle Outbound

- **Lesson:** Agent tools can turn retrieved instructions into a real bounded
  cross-boundary copy.
- **Causal chain:** indexed instruction → verified calendar and approval
  predecessors → authenticated actor's registered `.cinder.lab` mail address →
  assistant-private Nextcloud object → SMTP attachment → Cinder mailbox UID →
  matching byte digest and WorkHub delivery record.
- **Diagnostics:** There is no destination URL parameter. Correlate source
  digest, server Message-ID, destination UID, mailbox identity, SMTP headers,
  exact attachment bytes, and Completed/Rejected delivery issue. Manual copy,
  another address, or arbitrary HTTPS callback fails.
- **Defense:** enforce recipient registration, classification, size bounds,
  explicit approval, and byte-level delivery audits.

## kep-m01-g: The Unsafe Candidate Loader

- **Lesson:** Executable model serialization can run when a reviewer follows a
  normal load procedure.
- **Causal chain:** earned Keycloak `partner-reviewer` role → provisioner-created
  native `orion-release` Reporter membership → same-origin live Cinder relay and
  object → complete WorkHub intake → visible queue → disposable `review01`
  download by exact digest → pickle load → payload-created normal job output.
- **Diagnostics:** Upload must not execute. Inspect issue author/membership,
  attachment, queue journals, downloaded digest, loader exit, and job output.
- **Defense:** prefer non-executable formats, isolate loads, remove egress, and
  verify provenance before review.

## kep-m01-h: Trusted Helper, Untrusted Package

- **Lesson:** Normal dependency resolution can execute attacker code even when
  the primary artifact is sound.
- **Causal chain:** exact M02-l accepted Forgejo record for `cinder.operator`
  and `publisher/stable` plus Completed candidate relation → named/versioned
  WorkHub intake → pip resolution of those exact signed wheel bytes/digest →
  archive and signature-evidence verification → import and advertised
  API call → package-created job output.
- **Diagnostics:** No wheel URL or attached wheel is accepted. Inspect devpi
  accepted Forgejo blob/commit/record digests and callback basket, pip report
  URL, resolved digest, installed distribution, API output, attempt ID, and
  WorkHub terminal journal. Test absent/preaccepted records, wrong name,
  incompatible version, and digest.
- **Defense:** isolate indexes, pin hashes, verify provenance, and run setup in
  an egress-denied disposable worker.

## Reset boundary

Reset consumes exact failed native IDs and refuses successful records. It may
delete a rejected WorkHub issue or failed Forgejo run. It deletes an indexed
source/Nextcloud object only when one failed issue, one Qdrant source URI, the
digest, and the bounded path all agree; it deletes a conversation only when the
failed Forgejo run exposes that same workflow input and actor. It never
unpublishes `publisher/stable`, restarts shared Langflow, or removes an
unbound external message. A failed mail copy is removable only when the native
record's Message-ID resolves to one UID and its attempt, recipient, source/header
digest, and attachment bytes agree; UID readback is supplied when available.
Worker tmpfs disappears after each job. Successful
carriers, package releases, identities, approvals, external messages, and
predecessor state persist until full-range reprovision.
