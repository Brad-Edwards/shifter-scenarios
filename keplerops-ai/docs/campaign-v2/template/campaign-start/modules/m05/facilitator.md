# Module 05 Facilitator Guide

## `kep-m05-a`: Plant A Durable Preference

- **Lesson and enterprise reality:** User memory is a separate trusted context source; KeplerOps exposes it to make repeated release work useful.
- **Attacker method and why it succeeds:** The participant stores a normal-looking but security-relevant source preference. Orion accepts semantic release preferences without approval or source-risk classification.
- **Milestones and timing:** Earned identity, new thread, explicit preference, saved memory record, then byte-identical later requests under affected and clean identities with divergent source selection.
- **Common stalls and hints:** If Orion only replies conversationally, direct the player to documented memory behavior, then measurable source priority, then the explicit preference form. Do not provide an identity they have not earned.
- **Defense and diagnostics:** Require approval for security-relevant memory, display provenance, constrain retention, and alert on source-priority changes. Staff inspect Orion Redis memory and the two later request audits read-only; persistence alone does not prove impact.
- **Reset boundary:** Remove only rejected user memory and its thread; preserve accepted memory and identities.

## `kep-m05-b`: Fresh Session, Old Orders

- **Lesson and enterprise reality:** Persistence is proven only when stored state changes a genuinely fresh run relative to a clean control.
- **Attacker method and why it succeeds:** The participant submits identical neutral requests under poisoned and clean identities; Orion assembles user memory before retrieval.
- **Milestones and timing:** Two fresh conversation IDs, identical request text, different cited source/tool path, influenced source flag. Normal completion is under 90 seconds.
- **Common stalls and hints:** Repeating the malicious instruction invalidates the test. Guide toward a new thread, neutral task, and side-by-side tool/citation comparison.
- **Defense and diagnostics:** Bind memory to policy, expose memory use in traces, and test control identities. Staff compare actor, memory key, source ID, and workflow trace.
- **Reset boundary:** Delete failed fresh sessions, not the accepted memory ancestor.

## `kep-m05-c`: Shared Thread, Shared Influence

- **Lesson and enterprise reality:** Shared agent threads cross identity boundaries even when authentication remains correct.
- **Attacker method and why it succeeds:** One earned identity plants context; a distinct earned identity later triggers the action in the same room.
- **Milestones and timing:** Two clean profiles, distinct actors, ordered messages, second-actor workflow, shared-room source. Under 90 seconds.
- **Common stalls and hints:** Players often reuse one browser session or perform the final action as the planter. Point to shared history, planting without execution, then actor audit.
- **Defense and diagnostics:** Partition agent context by task/actor, mark inherited instructions, and require revalidation at ownership transfer. Staff inspect room and workflow IDs.
- **Reset boundary:** Recreate only a rejected thread and downstream attempt; preserve earned identities and accepted memory.

## `kep-m05-d`: Erase The Thread, Keep The Memory

- **Lesson and enterprise reality:** Conversation retention and semantic memory are independent stores with different audit and deletion behavior.
- **Attacker method and why it succeeds:** The attacker removes visible planting evidence through normal controls while the unlinked memory record remains active.
- **Milestones and timing:** Message visible, edit/delete succeeds, message absent after reload, memory remains, fresh run still influenced.
- **Common stalls and hints:** Deleting the whole account or memory defeats the objective. Point to separate stores, normal history controls, then a fresh neutral request.
- **Defense and diagnostics:** Couple deletion lineage, preserve tamper-evident audit, and notify users of retained derived memory. Staff compare history audit and memory timestamps.
- **Reset boundary:** Clear rejected edit audit/fresh thread only; preserve accepted ancestors.

## `kep-m05-e`: Corrupt A Trusted Tool

- **Lesson and enterprise reality:** Tool schemas and passing tests do not prove behavior when source, build, and deployment trust one compromised contributor path.
- **Attacker method and why it succeeds:** The participant extends the existing allow-list while preserving schema and benign behavior, then uses normal CI and GitOps.
- **Milestones and timing:** Commit, green contract tests, signed image, Argo sync, benign control, hidden action. CI/reconciliation should finish within five minutes.
- **Common stalls and hints:** Schema changes should fail. Guide toward an existing updateable tool, contract preservation, then commit-to-runtime digest continuity.
- **Defense and diagnostics:** Review behavioral diffs, restrict protected source expansion, sign policy as well as images, and monitor novel tool targets. Staff inspect Forgejo, Harbor, Argo, and MCP traces.
- **Reset boundary:** Revert by clean commit and reconciliation; never repair a live pod.

## `kep-m05-f`: Blueprint Drift

- **Lesson and enterprise reality:** Public reference architecture is not evidence of deployed configuration; immutable artifact correspondence matters.
- **Attacker method and why it succeeds:** The participant verifies public bytes and dispatches the normal Forgejo drift audit, whose server-side runner compares the deployed render and commits an exact signed diff.
- **Milestones and timing:** Cosign success, two immutable digests, changed MLflow auth path, generated report. Under three minutes once artifacts are found.
- **Common stalls and hints:** Tag comparison and unverified downloads are invalid. Point to publishing registry, digest matching, and both attestation/source bytes.
- **Defense and diagnostics:** Continuously compare signed source to rendered state and alert on secret materialization. Staff inspect workflow inputs and report digests.
- **Reset boundary:** Remove incomplete reports only; accepted report is immutable.

## `kep-m05-g`: Secret In The Agent Manifest

- **Lesson and enterprise reality:** A trusted drift report can disclose rendered application credentials even when participants cannot read the deployment view directly.
- **Attacker method and why it succeeds:** The player follows the exact private-render diff in the signed report and decodes standard JWT claims before using the token.
- **Milestones and timing:** Exact manifest path, token bytes, decoded issuer/subject/audience/scope/reference. Under five minutes.
- **Common stalls and hints:** Searching for plaintext flags is a near miss. Guide toward the drift, tool authentication, and audience-aware JWT decoding.
- **Defense and diagnostics:** Redact secrets from drift output, keep references opaque, issue short-lived audience-bound tokens, and audit report reads. Staff inspect Forgejo Actions and repository access logs.
- **Reset boundary:** Read-only; rotate failed-attempt sessions without changing the earned drift baseline.

## `kep-m05-h`: A Token Travels Further Than Its Owner

- **Lesson and enterprise reality:** Alternate application material can bypass interactive SSO while retaining a bounded service identity.
- **Attacker method and why it succeeds:** Use the recovered JWT as the MLflow application credential and enumerate its actual boundary.
- **Milestones and timing:** Successful service login, one experiment, correct audit actor, artifact read, adjacent denial. Under two minutes.
- **Common stalls and hints:** The SSO form is wrong. Point to service/audience, application-token client use, then resource enumeration.
- **Defense and diagnostics:** Prefer workload identity, rotate exposed tokens, enforce audience and resource ACLs, and alert on unusual clients. Staff inspect MLflow auth/access logs.
- **Reset boundary:** Preserve the shared token fixture and append-only MLflow audit; failed reads retry under a fresh client request.

## `kep-m05-i`: The Session In The Trace

- **Lesson and enterprise reality:** Support artifacts can preserve state-bearing web authentication that remains replayable.
- **Attacker method and why it succeeds:** Extract the synthetic cookie from a HAR and import it into an isolated browser profile for the correct domain.
- **Milestones and timing:** HAR acquired, cookie identified, clean profile, bounded support identity, protected note, admin denial.
- **Common stalls and hints:** Query parameters are not authentication. Point to attachment, state-bearing cookie, then clean-profile domain import.
- **Defense and diagnostics:** Redact HARs, revoke captured sessions, bind high-risk sessions, and shorten support-session lifetime. Staff inspect Zammad session/ticket access.
- **Reset boundary:** Preserve the shared HAR/session fixture and append-only Zammad audit; discard only the caller's failed local browser profile.

## `kep-m05-j`: Notebook Residue

- **Lesson and enterprise reality:** Persistent notebook homes retain output and client configuration after projects migrate.
- **Attacker method and why it succeeds:** Follow the migration record, inspect ordinary residue, and use the named viewer credential in Airflow.
- **Milestones and timing:** Notebook path, output clue, client config, viewer login, DAG description, trigger denial.
- **Common stalls and hints:** Searching every filesystem is unnecessary. Point to migration issue, notebook output/config, then Airflow role verification.
- **Defense and diagnostics:** Scrub retired workspaces, use short-lived SSO, scan notebook output, and inventory client files. Staff inspect Jupyter volume and Airflow audit.
- **Reset boundary:** Preserve immutable notebook residue, viewer state, and Airflow audit; retry under a fresh browser session.

## `kep-m05-k`: The Tool Sees More

- **Lesson and enterprise reality:** Agent tools can return verbose upstream logs containing credentials beyond the user's direct application access.
- **Attacker method and why it succeeds:** Trigger a fresh bounded status tool, follow its real Forgejo job, and use leaked Harbor robot material.
- **Milestones and timing:** Tool call, failed job/log, robot login, one Harbor project, protected object, mutation denial.
- **Common stalls and hints:** A seeded log found directly is insufficient. Point to call-chain tool, normal status request, then the referenced failed job.
- **Defense and diagnostics:** Redact tool output, use ephemeral scoped robot tokens, classify logs, and enforce project ACLs. Staff correlate Orion, MCP, Forgejo, and Harbor audit IDs.
- **Reset boundary:** Preserve the immutable log, robot scope, registry object, and Harbor audit; retry with a fresh tool and registry session.

## `kep-m05-l`: Credentials In The Worker

- **Lesson and enterprise reality:** A real vulnerable MLflow loader turns path traversal into child-process execution and live process credential theft.
- **Attacker method and why it succeeds:** Host a payload with an absolute `Content-Disposition` filename, write `sitecustomize.py`, trigger a new child, and read only its own environment.
- **Milestones and timing:** Advisory/version match, arbitrary write, child import, actual token output, bounded service access, adjacent denials. Under ten minutes after payload hosting.
- **Common stalls and hints:** A supplied shell or planted token is invalid. Point to the public advisory, writable import path/new child, then `/proc/self/environ` or process environment.
- **Defense and diagnostics:** Upgrade to MLflow 2.9+, sanitize filenames, use read-only imports, remove long-lived environment secrets, and isolate egress. Staff inspect worker job and HTTP logs.
- **Reset boundary:** Discard failed worker and rotate attempt token; checkpoint successful equivalent identity for model/release descendants.

## `kep-m05-m`: Rewrite The Agent Rules

- **Lesson and enterprise reality:** Agent security properties are software supply-chain state and require source-to-runtime continuity.
- **Attacker method and why it succeeds:** Change one security property through Forgejo, signed CI, and Argo rather than editing runtime directly.
- **Milestones and timing:** Scoped diff, commit, signature, Argo sync, exact runtime revision, fresh changed behavior. Under five minutes after merge.
- **Common stalls and hints:** Cosmetic edits and pod-local changes fail. Point to drift/config repo, measurable boundary, then full revision continuity.
- **Defense and diagnostics:** Protect security fields, require policy review, enforce signed configuration, and alert on runtime-boundary changes. Staff inspect Git/CI/Cosign/Argo/runtime records.
- **Reset boundary:** Revert through the same chain; preserve descendants bound to accepted malicious bytes.

## `kep-m05-n`: Rogue Agent On The Worker

- **Lesson and enterprise reality:** Compromised execution can host a distinct persistent agent that reuses only earned schemas and credentials.
- **Attacker method and why it succeeds:** Launch the installed OSS harness detached, register a separate identity, heartbeat, and call a bounded company tool.
- **Milestones and timing:** Distinct PID/identity, successful registration, tool response, heartbeat after disconnect. Under two minutes.
- **Common stalls and hints:** A script printing expected output is not an agent. Point to existing runtime/schema, separate process identity, then persistence and real tool call.
- **Defense and diagnostics:** Enforce workload identity, process allow-listing, egress policy, and agent registration approval. Staff inspect worker process and telemetry records.
- **Reset boundary:** Kill rogue process, remove state/identity, and rotate scoped attempt token; preserve worker ancestor.

## `kep-m05-o`: Beyond The Agent Sandbox

- **Lesson and enterprise reality:** A sandboxed computer-use agent may delegate approved actions through a privileged host bridge that becomes the true boundary.
- **Attacker method and why it succeeds:** Poison confirmation policy, invoke the legitimate bridge, and establish a live Cinder callback on the disposable host.
- **Milestones and timing:** Sandbox/host identity difference, bridge action, callback, fresh nonce, host diagnostic. Callback should arrive within 90 seconds.
- **Common stalls and hints:** Sandbox shell and prerecorded output do not pass. Point to delegated tools, confirmation boundary, then unpredictable host command through Cinder.
- **Defense and diagnostics:** Minimize bridge verbs, require out-of-band confirmation, isolate host identity, and detect callbacks. Staff inspect agent, bridge, host, and network telemetry.
- **Reset boundary:** Remove callback/task and reimage only failed disposable workstation attempt; never touch hypervisor state.

## `kep-m05-p`: Commands In The AI API

- **Lesson and enterprise reality:** Allowed OpenAI-compatible traffic can become bidirectional C2 when provider configuration and an internal agent are compromised.
- **Attacker method and why it succeeds:** Repoint the scoped provider to Cinder, embed a valid task in inference content, execute it, and return output later over the same API.
- **Milestones and timing:** Config revision, first request, parsed task, execution, later result request, no secondary flow. Two polling intervals maximum.
- **Common stalls and hints:** A second callback invalidates the operation. Point to an already allowed API, valid inference envelope, then request/execution/result correlation.
- **Defense and diagnostics:** Pin providers, authenticate destinations, inspect structured output, restrict agent execution, and correlate egress to process events. Staff inspect GitOps, API, worker, and network telemetry.
- **Reset boundary:** Clear endpoint conversation/tasks and restore provider through GitOps; preserve rogue-agent checkpoint.

## `kep-m05-q`: Relay Through The Web Assistant

- **Lesson and enterprise reality:** A normal browser chat workflow can carry C2 when a compromised agent can poll and post as an ordinary user.
- **Attacker method and why it succeeds:** Use a dedicated LibreChat thread as inbox/outbox and execute fresh tasks on the worker without direct participant access.
- **Milestones and timing:** Operator message, agent poll, execution, agent reply, second unpredictable round. Two polling intervals per round.
- **Common stalls and hints:** Direct API or worker access fails the objective. Point to worker-permitted web service, task/result framing, then fresh two-way proof.
- **Defense and diagnostics:** Detect machine polling, bind sessions to user behavior, scan encoded task formats, and constrain worker web egress. Staff inspect LibreChat identity/message and worker process telemetry.
- **Reset boundary:** Delete attempt thread/cursor and stop relay process; preserve the accepted rogue-agent ancestor.
