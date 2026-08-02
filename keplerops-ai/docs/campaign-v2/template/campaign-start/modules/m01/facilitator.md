# Module 01 Facilitator Guide

## kep-m01-i: Behind The Public Flow

- **Lesson / reality:** Public AI workflow builders are code-execution surfaces; KeplerOps exposes a real public Langflow flow for partner Preview compatibility.
- **Method / cause:** Participants adapt `GHSA-vwmf-pq79-vjvx` against the discovered version and UUID. The unauthenticated temporary-build endpoint accepts attacker flow data whose component code reaches `exec()`.
- **Milestones:** benign build, protected-route denial, job ID, `id` output, handoff file, relay observation. Normal completion is under two minutes.
- **Stalls / hints:** Give orientation when the tester misses Preview metadata, mechanism when they confuse the protected route with the public route, and execution when their JSON graph is malformed.
- **Defense:** Remove attacker-supplied flow data, upgrade beyond the affected release, isolate builders, and alert on custom component code from public requests.
- **Diagnostics / reset:** Inspect Langflow build logs and job state read-only. Restart Langflow and clear ephemeral jobs; preserve flow UUID and handoff source.

## kep-m01-j: Quiet In Detonation

- **Lesson / reality:** One artifact can identify analysis and defer behavior until integration; KeplerOps genuinely runs the same digest in separate workers.
- **Method / cause:** Compare multiple cgroup, mount, seccomp, process, kernel, and network properties; activate only in integration. One magic environment variable is invalid.
- **Milestones:** diagnostic callbacks from both workers, identical digest, benign analysis, integration callback containing scoped context.
- **Stalls / hints:** First orient to the two named queues, then explain stable environmental evidence, then help preserve identical bytes. Distinguish queue latency from code failure in worker logs.
- **Defense:** Normalize environments, deny artifact egress, use behavior comparison across diverse sandboxes, and treat integration load as another hostile execution.
- **Diagnostics / reset:** Read RabbitMQ job/result IDs and guest service logs. Purge failed jobs and recreate disposable workspaces without deleting the earned integration identity.

## kep-m01-a: Break The Release Brief

- **Lesson / reality:** An assistant with broader source access can become a confused deputy even when users cannot read the source directly.
- **Method / cause:** Participants use semantic instruction conflict to make a normal Redmine draft copy the embargo field. No exact prompt is scored.
- **Milestones:** compliant baseline omits the field, direct source read is denied, fresh draft contains the protected field and flag.
- **Stalls / hints:** Orient to draft creation rather than chat text, explain source/identity asymmetry, then suggest a schema or discrepancy framing. A refusal is normal feedback.
- **Defense:** Separate data from instructions, enforce field-level output policy after generation, minimize service access, and alert on restricted-source values in contributor records.
- **Diagnostics / reset:** Correlate assistant request, citations, and Redmine issue. Delete only failed draft/thread state; preserve predecessor access.

## kep-m01-b: Use The Assistant's Tool

- **Lesson / reality:** Tool-capable agents can exercise service authority unavailable to the requesting user.
- **Method / cause:** A business-outcome request causes a real calendar lookup and WorkHub case write under the assistant identity.
- **Milestones:** participant calendar denial, allowed tool event, source audit, created case, restricted schedule and flag.
- **Stalls / hints:** Orient to the agent tool map, explain delegated identity, then focus the request on candidate readiness. Chat-only disclosure is not success.
- **Defense:** Propagate requesting-user authority, scope tool outputs, require purpose-bound authorization, and correlate source reads with destination writes.
- **Diagnostics / reset:** Inspect OPA decision, tool trace, calendar read, and Redmine record. Delete the case/trace and restore the conversation.

## kep-m01-c: Cross The Safety Boundary

- **Lesson / reality:** A jailbreak matters only when generated content produces the prohibited technical effect in a real downstream workflow.
- **Method / cause:** Participants iteratively induce a valid validation-bypass command, then submit it to the disposable runbook job. Parser acceptance alone fails.
- **Milestones:** baseline refusal, syntactically valid assistant draft, isolated job progress, bounded validation-disabled effect, flag-bearing report.
- **Stalls / hints:** Orient to allowed diagnostics, explain conversational reframing, then point to the documented fixture semantics. Track the six-attempt bound.
- **Defense:** Treat generated commands as untrusted code, constrain runbook interpreters, authorize effects independently, and test model/policy updates against adversarial suites.
- **Diagnostics / reset:** Inspect model revision, conversation, command, runner output, and fixture state. Remove failed drafts/jobs/conversations only.

## kep-m01-d: Borrow The Assistant's Authority

- **Lesson / reality:** Agent influence becomes privilege escalation when a delegated identity can sign enterprise state.
- **Method / cause:** The participant drives the assistant to approve only `sandbox-17`; OPA authorizes the agent principal but denies the participant.
- **Milestones:** direct denial, agent OPA allow, approval-tool call, agent signer, candidate-bound flag record.
- **Stalls / hints:** Orient to signer identity, explain designated-candidate scope, then correlate request and decision IDs. Wrong candidates should fail clearly.
- **Defense:** Bind delegation to initiating user and candidate digest, require human approval for trust transitions, and make agent authorship prominent.
- **Diagnostics / reset:** Join prompt, OPA decision, tool event, and approval. Revoke only the scoped approval and clear agent attempt state.

## kep-m01-e: Instructions In The Review Pack

- **Lesson / reality:** Indirect prompt injection travels through ordinary document ingestion and can drive a later tool effect.
- **Method / cause:** The participant uploads a plausible review artifact; Tika/Haystack/Qdrant retrieve its instruction into a fresh LangGraph run.
- **Milestones:** source upload, extraction/index IDs, retrieved chunk, bounded WorkHub state change, flag in changed state.
- **Stalls / hints:** Orient to the writable indexed source, explain waiting for ingestion, then locate citation and tool event in one trace.
- **Defense:** Strip or label untrusted instructions, separate retrieval data from control text, require authorization for tool effects, and preserve ingestion lineage.
- **Diagnostics / reset:** Inspect Nextcloud/Forgejo object, Airflow run, Qdrant point, agent trace, and WorkHub transition. Remove only attempt descendants.

## kep-m01-f: Release Bundle Outbound

- **Lesson / reality:** Agent tools can convert indirect instructions into genuine cross-boundary data transfer.
- **Method / cause:** Retrieved content causes the assistant's approved transfer tool to attach the exact protected bundle to a Cinder destination.
- **Milestones:** direct-source denial, indexed instruction, transfer tool event, external object/mail record, matching hashes, embedded flag.
- **Stalls / hints:** Orient to the transfer-capable tool, explain indirect bundle reference, then compare source/destination digests. Manual participant transfer fails.
- **Defense:** Apply data-loss policy at tool invocation, bind recipients and classifications, require approval for external attachments, and audit byte digests.
- **Diagnostics / reset:** Join source classification, retrieval trace, transfer call, and Cinder receipt. Delete the external copy and attempt lineage only.

## kep-m01-g: The Unsafe Candidate Loader

- **Lesson / reality:** Serialized AI artifacts can execute code when a human reviewer follows a normal loading procedure.
- **Method / cause:** A complete submission reaches the visible review queue; the evaluation worker downloads and loads exact participant bytes.
- **Milestones:** accepted intake, digest continuity, reviewer download/load, compatible smoke result, bounded callback containing workbench flag.
- **Stalls / hints:** Orient to the supported loader, explain that review completeness triggers human action, then inspect digest movement. Upload-time auto-execution is a platform defect.
- **Defense:** Prefer non-executable formats, isolate all loads, inspect conversion paths, remove egress, and verify provenance before any human review.
- **Diagnostics / reset:** Inspect queue states, artifact hash, reviewer action, guest journal, and callback. Recreate the disposable workbench and failed queue items.

## kep-m01-h: Trusted Helper, Untrusted Package

- **Lesson / reality:** Documented dependency resolution can execute attacker code even when the primary model artifact is sound.
- **Method / cause:** A compatible higher-priority helper is published through the real index and imported during normal evaluation setup.
- **Milestones:** setup-guide discovery, package publication, pip-selected digest, advertised API success, import-time diagnostic and flag in job output.
- **Stalls / hints:** Orient to lock history and index order, explain name/version compatibility, then inspect pip's selected source. Different names do not qualify.
- **Defense:** Pin hashes, isolate indexes, use dependency confusion controls, verify signed provenance, and execute setup in an egress-denied worker.
- **Diagnostics / reset:** Inspect devpi metadata, resolver output, installed files, guest log, and callback. Remove malicious version and recreate workbench attempt state.
