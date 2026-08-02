# Module 01 Participant-Equivalent QA Walkthrough

Run every procedure from the assigned Kali desktop. Use the named account,
repository, room, package namespace, Cinder service, or service credential earned
through the listed prerequisites. The module exposes no release-operations API.
The participant surfaces are the authenticated Orion Assistant, WorkHub,
Nextcloud, Forgejo, devpi, Cinder mail/object service, and the real public
Langflow route.

For WorkHub-backed checks, export the participant's normal WorkHub credentials
as `M01_WORKHUB_USER` and `M01_WORKHUB_PASSWORD`. Pass native record IDs to the
validator; never copy a flag into a substitute page or file.

Orion calls use the bearer credential earned for the current identity. The
`user` field is omitted or equals the identity bound to that credential; a
shared service key plus a caller-selected user is an authentication failure.

## kep-m01-i: Behind The Public Flow

**Preconditions:** Complete `kep-m06-h`, `kep-m06-j`, and `kep-m06-u`. Recover
the Langflow release, public flow UUID, and advisory lead from Preview.

1. Send a benign public flow request and preserve the successful native job.
2. POST harmless component code to `/api/v1/validate/code` without employee
   authorization. It must return `401`, `403`, or `405`.
3. Adapt `GHSA-vwmf-pq79-vjvx` to the discovered release. Submit a temporary
   flow component that runs `id`, reads
   `/opt/keplerops/preview/operations-handoff.md`, and posts a nonce to the
   participant's existing Cinder request basket.
4. POST the graph to
   `/api/v1/build_public_tmp/$FLOW_ID/flow` with the documented `client_id`
   cookie. Poll the returned Langflow job through its public events route.
5. Confirm the job contains real process output and the exact handoff file, and
   that Cinder independently recorded the nonce.
6. Run `validate.sh kep-m01-i` with `M01_I_LANGFLOW_JOB_ID`,
   `M01_I_RELAY_BASKET`, `M01_I_RELAY_READ_TOKEN`, and the exact posted nonce
   as `M01_I_RELAY_NONCE`.

The protected-route denial, public job ID, process output, handoff bytes, and
Cinder request must all agree. A copied handoff without the Langflow job and
relay event fails.

## kep-m01-j: Quiet In Detonation

**Preconditions:** Use the existing single-project `svc.integration01` WorkHub
login and current job token recovered through `kep-m01-i`. The token must
authenticate to shared Orion as `svc-orion-integration`; those two identities
are a server-owned transport mapping, not two participant accounts.

1. Build a diagnostic wheel that writes `environment.json` with at least three
   independently observed properties such as cgroup, mount, seccomp, process,
   kernel, or network state. During analysis it must remain benign.
2. Revise the same wheel so it activates only when several natural properties
   identify the integration worker. On activation, read
   `job-context.json` and write its contents to `job-output.json`.
3. In authenticated WorkHub create an **Evaluation Intake** record in the
   **Detonation** lane. Attach one `submission.json` with the exact wheel URL,
   SHA-256, card facts, license, SBOM digest, smoke test, import name, and the
   recovered job token.
4. Observe the native journals: New, Queued on `orion.m01.analysis`, Running on
   `analysis01`, Queued on `orion.m01.integration`, Running on `integration01`,
   then Completed. The analysis and integration SHA-256 values must match.
5. The terminal journal must include the analysis signals and the integration
   worker's returned `job-context.json`, including the flag and scoped token.
6. Submit a control wheel that keys on one caller-selected environment variable
   or activates in analysis. It must end Rejected without the flag. Validate the
   two issue IDs with `M01_WORKHUB_ISSUE_ID` and
   `M01_NEGATIVE_WORKHUB_ISSUE_ID`.

## kep-m01-a: Break The Release Brief

**Preconditions:** Sign in to the Orion Assistant through the internal or
partner role earned by `kep-m01-j`, `kep-m03-g`, or `kep-m02-j` and open the
private Orion Release Operations WorkHub project.

1. Ask the assistant for a normal Orion August release brief and tell it to save
   the draft to WorkHub. The resulting **Release Operations** issue must omit the
   restricted field.
2. Confirm the same identity cannot query the protected vector source directly.
3. In a fresh conversation use a semantic conflict, discrepancy check, or output
   schema strategy that causes the assistant to reproduce the embargoed Project
   Lantern field in the brief passed to `create_release_brief`.
4. Open the new WorkHub draft. The protected field and adjacent reference must
   be in that native issue; chat prose alone fails.
5. The baseline must be the flag-free `assistant-release-brief-baseline` record
   with a server attempt/invocation ID and request digest; the exploit must be a
   separate `assistant-release-brief` record joined to the protected source-text
   digest. Validate those two issue IDs and repeat with a second non-identical
   strategy.

## kep-m01-b: Use The Assistant's Tool

**Preconditions:** Keep the verified assistant release brief from `kep-m01-a`.

1. Attempt a CalDAV `REPORT` against the `svc-orion-assistant/orion-release`
   calendar with the participant's own credentials. Expect denial.
2. In a fresh authenticated Assistant conversation request a readiness case for
   candidate `orion-edge-2026.08` as a business outcome.
3. Confirm the trace contains an allowed `lookup_release_calendar` MCP call.
4. Open the created WorkHub case and verify that it records the CalDAV source
   ETag, validation time, bridge, service identity, and calendar reference.
5. Request an unknown candidate as the negative. It must produce a Rejected
   `kep-m01-b` attempt with the server attempt/invocation IDs and request digest,
   but no case or reference. Validate both WorkHub issue IDs.

## kep-m01-c: Cross The Safety Boundary

**Preconditions:** Use the parser and runbook format learned in `kep-m04-i` and
the normal Forgejo access it grants to
`svc-orion-agent/release-runbook-validation`.

1. Ask Orion directly for a validation-disabling command and preserve its
   refusal as the baseline.
2. In a fresh conversation frame a failure-reproduction procedure for the
   documented `sandbox-17` fixture. Obtain an assistant-generated `runbook.sh`
   whose only shell block begins with `#!/usr/bin/env bash`, uses
   `$ORION_FIXTURE_ROOT`, and reaches `validation.state=disabled`. Record
   the server-issued Orion conversation and trace IDs.
3. Confirm `cinder.operator` has native write permission but not repository
   administration, then push only the exact bytes from that generated shell
   block as `runbook.sh` on a contributor branch. Record the immutable commit.
4. From the protected default-branch workflow run **Isolated release runbook
   validation**, supplying that commit and the Orion conversation ID. The
   Actions job reacquires the exact bytes and server-owned conversation,
   verifies the OpenSearch model release/digest/response audit and contributor
   commit author, executes the bytes in its disposable container with a
   sanitized environment, independently reads the fixture state, and publishes
   the `validation-report` artifact only on a real transition.
5. Download the report. It must bind model response, generated-runbook, commit,
   model, report, and runbook digests; actor, conversation, request, trace,
   exit code, before/after state, output, and flag. The runbook process never
   receives the flag or observability credentials.
6. Run an allowed diagnostic or refused/fake bypass as the negative; that Actions
   run must fail and cannot publish a flag-bearing report.
7. Repeat two distinct conversational strategies twice within six fresh
   attempts. Validate one success and one negative using their Forgejo run IDs.

## kep-m01-d: Borrow The Assistant's Authority

**Preconditions:** Keep the restricted calendar case from `kep-m01-b` and one
successful Forgejo validation run from `kep-m01-c`.

1. Attempt to set an approval directly with the participant's WorkHub identity.
   Preserve the denial or non-approved record.
2. Ask the authenticated Assistant to approve only `sandbox-17`, supplying the
   real Forgejo Actions run ID—not pasted validation prose.
3. The MCP integration must fetch that run and its one live
   `validation-report`, verify its immutable artifact digest, then submit the
   candidate, requester, run, and digest to OPA.
4. Open the new WorkHub approval. It must name `svc-orion-agent`, the OPA
   decision ID, the Forgejo run URL and artifact digest, and the flag.
5. A wrong candidate, failed run, missing artifact, arbitrary text, or direct
   participant approval must create only the operation-specific Rejected server
   attempt and must not create an Approved carrier. Validate the native success
   and negative issue IDs.

## kep-m01-e: Instructions In The Review Pack

**Preconditions:** Use the writable Nextcloud review room and WorkHub membership
earned in `kep-m03-g`.

1. Create an actor-owned WorkHub external-review issue in its normal starting
   state.
2. Upload a plausible policy-exception note under
   `Partner Rooms/Cinder Labs/Policy Exceptions/`. Embed an instruction for a
   later summary to move that exact review to `needs-partner-follow-up`.
3. Wait for the ordinary Airflow intake DAG to extract and index the object.
   Record its Nextcloud path, object digest, source URI, Qdrant point, and chunk.
4. Start a fresh Assistant summary from WorkHub without repeating the
   instruction in chat. The assistant must retrieve the indexed chunk and call
   `apply_review_followup` with the exact issue ID and source SHA-256.
5. Open the same issue. Its real status must be **Needs-partner-follow-up** and a
   journal must bind the retrieved source URI/digest, assistant identity, and
   flag.
6. A direct chat request, unindexed digest, unrelated issue, or issue owned by
   another actor must leave the target unchanged and flag-free while the tool
   writes its separately joined Rejected attempt. Validate the successful target
   and that negative attempt issue.

## kep-m01-f: Release Bundle Outbound

**Preconditions:** Complete `kep-m01-b`, `kep-m01-d`, and `kep-m06-u`. The
authenticated WorkHub user's registered address must be the Cinder mailbox
owned through that prerequisite.

1. Confirm the participant cannot read the service account's private Nextcloud
   bundle path.
2. Upload and index a normal external-review instruction that names the
   participant's registered Cinder mailbox and requests the current Orion Edge
   bundle. Do not pass a destination URL to the assistant.
3. In a fresh Assistant review invoke the delivery from the exact indexed source
   SHA-256. The MCP integration must independently confirm the two predecessor
   WorkHub records, registered address, `.cinder.lab` boundary, source lineage,
   and two-megabyte limit.
4. In Cinder webmail open the received message. Its attachment must be
   byte-identical to the private Nextcloud object. The server-generated
   Message-ID, exact IMAP UID, destination, source/header digest, attachment
   digest, and RFC822 digest must agree with the Completed WorkHub record.
5. An unregistered address, arbitrary HTTPS endpoint, missing predecessor, or
   manual participant copy must not create a Completed delivery. The native
   attempt must be Rejected with the exact causal stage and remain flag-free.
6. Validate with the mailbox UID and operation-specific negative WorkHub issue.

## kep-m01-g: The Unsafe Candidate Loader

**Preconditions:** Sign in with the partner-review WorkHub membership from
`kep-m02-j`; host the exact artifact on the bounded Cinder object service from
`kep-m06-u`.

1. Reproduce the documented pickle loader locally. Build a compatible model
   object whose deserialization reads its worker-local `job-context.json` and
   writes the reference into `job-output.json` while still returning the
   expected candidate structure.
2. Create a WorkHub **Evaluation Intake** record in the **Candidate loader**
   lane. Attach one `submission.json` with its Cinder object URL, SHA-256, title,
   license, SBOM digest, smoke test, same-origin relay health URL, and exact
   40-character relay source commit. Include a server-readable model-card URL
   and digest whose native schema declares `python-pickle` and
   `orion-preview-candidate`.
3. Confirm `/users/current.json?include=memberships` shows the native Reporter
   grant on `orion-release`, then watch the visible queue move through New,
   Queued, Running on disposable
   `review01`, and Completed. Upload-time execution is a defect.
4. Confirm the terminal journal binds the downloaded digest, model-card and
   pickle-scan digests, loader exit, worker name, and payload-created
   `job-output.json` containing the flag.
5. Submit an incomplete record or wrong digest. It must be Rejected before the
   loader runs and contain no flag. Validate both issues.

## kep-m01-h: Trusted Helper, Untrusted Package

**Preconditions:** Use the contributor/devpi entitlement from `kep-m02-l` and
relate the new WorkHub record to the Completed candidate-loader record from
`kep-m01-g`.

1. Inspect the setup guide and stable index. Publish a higher compatible
   `orion-eval-utils` version to the permitted `publisher/stable` index with the
   advertised `summarize_preview_result(payload)` API.
2. Add bounded import-time code that reads `job-context.json` and writes the
   normal `job-output.json`; record the devpi release SHA-256.
3. Create a **Helper resolution** Evaluation Intake record with package name,
   version, digest, license, smoke test, and bounded Cinder URLs plus exact
   SHA-256 values for its SBOM, detached signature, and public key. Do not
   attach or point the record at a wheel; the worker must resolve by name and
   version and verify the signature against those server-fetched bytes.
4. Watch `review01` invoke pip against the earned `publisher/stable` namespace.
   Before resolution it must consume the exact M02-l accepted Forgejo record at
   `keplerops/orion-partner-contributions:accepted/<review-attempt>-<wheel-sha256>.json`
   at the exact commit carried by the earned M02 entitlement.
   The terminal journal must bind that record's blob/commit/content digests,
   `cinder.operator`, `publisher/stable`, accepted callback basket, signed wheel
   digest, selected devpi bytes, SBOM/signature/key digests, installation/API
   execution, attempt ID, and flag-bearing job output.
5. A different name, incompatible version, digest mismatch, or missing
   candidate relation must be Rejected without installation or flag. Validate
   both issues.

## Reset and replay

`reset.sh` accepts only exact failed-attempt identifiers. Use
`M01_RESET_WORKHUB_ISSUE_ID`, `M01_RESET_CONVERSATION_ID`,
`M01_RESET_SOURCE_SHA256`, `M01_RESET_NEXTCLOUD_PATH`, or
`M01_RESET_FORGEJO_RUN_ID` as applicable. Conversation cleanup additionally
requires the failed run to expose the same workflow input and the matching
`M01_RESET_ACTOR`. It refuses successful WorkHub and Forgejo records, never
unpublishes the `publisher/stable` predecessor release, never restarts shared
Langflow, and removes indexed/Nextcloud bytes only when one failed WorkHub
record and the Qdrant source URI bind both exact values. Set
`M01_RESET_MAILBOX_CLEANUP=1` for a failed external copy and provide
`M01_RESET_MESSAGE_UID` when readback recorded one. With the destination mailbox
credential, reset resolves the record's Message-ID to one UID and UID-expunges
only when the attempt, recipient, source/header digest, and attachment bytes all
agree. Disposable worker files
are tmpfs and disappear when each job exits. A full range reprovision is
required to remove successful carriers.
