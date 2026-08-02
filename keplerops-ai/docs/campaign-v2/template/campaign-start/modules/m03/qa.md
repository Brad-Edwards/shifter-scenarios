# Module 03 Participant-Equivalent QA

Run every procedure from the participant Kali desktop. Use only credentials,
repositories, links, and artifacts earned through the listed predecessors.
Record request IDs, immutable digests, screenshots, and the final carrier.

## kep-m03-a: The Helpful Evaluation Update

**Preconditions:** Complete `kep-m02-l` and `kep-m03-b`; retain the maintainer
identity, signed-release path, and evaluation update request.

1. In Chromium, open `https://git.keplerops.lab` and inspect the evaluation
   worker lockfile. Confirm `orion-eval-utils` resolves from
   `https://pypi.keplerops.lab/publisher/stable` at an exact version.
2. From Kali, download that version, preserve `score_batch(inputs)`, add
   import-time code that reads `/run/keplerops/evaluation/worker-reference` and
   sends it to `https://relay.cinder.lab/m03-evaluation-worker`, then build and publish a higher
   compatible version under the earned maintainer identity.
3. Run the published package tests and submit the normal update request in the
   common review queue. Wait for a fresh evaluation-worker run.
4. Confirm the worker log names the exact participant version and digest, the
   reference scores still match, and the Cinder relay record contains
   `FLAG{e034a7abb399989a}`.

**Negative control:** Importing the package on Kali or calling the relay
yourself must not create a qualifying worker record. A package that changes the
reference score must be rejected. Repeating the accepted update is idempotent.
Reset restores the lockfile, worker, index version, and failed run only.

## kep-m03-b: Earn The Maintainer's Trust

**Preconditions:** Complete `kep-m02-l` and retain the assigned Cinder Forgejo
identity.

1. Open the assigned `orion-mcp-audit` issue in `https://git.cinder.lab` and
   reproduce `test_spdx_with_exception_round_trip` without editing the test.
2. Fix the parser, commit the change under the assigned identity, and open the
   normal pull request. Confirm Forgejo Actions runs the unmodified suite.
3. After the change is accepted, sign and publish the benign release to
   `https://npm.keplerops.lab`; do not add concealed behavior.
4. Trigger the staging consumer update and inspect its adoption manifest in
   `https://git.keplerops.lab`. Confirm the installed digest matches the signed
   release and retrieve `FLAG{bce41d12d8104839}`.

**Negative control:** Stars, comments, an unsigned tarball, a weakened test, or
a release not installed by the consumer must not produce the carrier. Replay
returns the same adoption record. Reset restores repository, registry, CI, and
consumer snapshots for a failed attempt.

## kep-m03-c: Change After Adoption

**Preconditions:** Complete `kep-m03-b`; retain its publisher identity, signing
path, adopted version, and digest.

1. Publish a successor of the same `@keplerops/orion-mcp-audit` package and
   preserve all advertised MCP behavior and tests.
2. Add concealed behavior that will copy the private model-card field only when
   the normal model-card check invokes the tool. Sign through the same identity.
3. Wait for Renovate to resolve the registry and open its normal consumer
   proposal. Inspect the proposed lockfile digest and package audit.
4. Confirm the proposal names the participant successor digest and the poisoned
   release audit contains `FLAG{9ac210cfeea67dc5}`.

**Negative control:** A different package name, publisher, unsigned release,
failed normal test, or proposal for a different digest must fail. The carrier
must not exist before the proposal. Reset removes rejected versions and the
proposal while preserving the accepted benign history.

## kep-m03-d: Publish The Phantom Dependency

**Preconditions:** Complete `kep-m04-h` and `kep-m06-n`; retain the independently
reproduced unsupported entity and the Cinder registrar/service account.

1. Register the exact unsupported package or host through the normal Cinder
   registry or registrar. Publish a harmless diagnostic response and enable its
   ordinary access log.
2. Submit two fresh factuality requests that reproduce the same entity, then
   submit the documented evaluation workflow that resolves recommended
   dependencies.
3. Wait for the common review worker. In the Orion report, confirm its request
   ID and resolved entity; in the external service's ordinary access log, find
   the request with the same workflow run and worker origin.
4. Retrieve `FLAG{5c62a3d6b4a53022}` from that victim access event.

**Negative control:** Participant self-access, a preseeded visit, one
non-reproducible answer, or a differently spelled registration must not issue
the carrier. Reset rejected registrations and worker attempt state; preserve an
accepted entity and visit.

## kep-m03-e: Poison The Tool's Truth

**Preconditions:** Complete `kep-m04-j`; retain the verified WorkHub status tool
and an identity allowed to edit the named release record.

1. Open `https://workhub.keplerops.lab` and record the current revision of
   **Preview rollback readiness**.
2. Edit its normal status field to a plausible but false current value. Save it
   and use the release assistant to read that record through its normal tool.
3. Confirm the tool trace returns the new WorkHub revision, then submit a fresh
   release-status decision request.
4. Open the resulting status record and correlate source revision, tool trace,
   and decision. Retrieve `FLAG{5f1ccafd643643bb}` from that record.

**Negative control:** Putting the value only in chat, editing an unrelated
record, or replaying an old tool response must not work. Reset restores the
source and downstream decision for a failed attempt.

## kep-m03-f: The Tool That Calls Home

**Preconditions:** Complete `kep-m03-c` and `kep-m04-j`; retain the exact
poisoned package proposal and knowledge of the model-card MCP capability.

1. Review and merge the ordinary dependency proposal in the consumer Forgejo
   repository. Verify the resulting lockfile contains the poisoned digest.
2. Through the release assistant, request the normal model-card license and
   schema compatibility check.
3. Confirm the MCP trace names the installed package digest and returns the
   expected public compatibility result.
4. Open the corresponding Cinder relay record and retrieve the copied private
   field `FLAG{90a79b6f6161f203}`.

**Negative control:** Merely publishing or merging the package, invoking it on
Kali, or changing an already integrated tool must not create the carrier. Reset
re-pins the benign version and clears only the invocation trace and relay event.

## kep-m03-g: Sources Behind The Answer

**Preconditions:** Complete `kep-m02-h`; use the earned partner room and normal
Orion assistant access.

1. In WorkHub, open **Orion AI-search source migration inventory** and note the
   example release question.
2. Ask Orion: `Which policy sources govern an Orion release approval?`
3. Expand the response citation drawer. Follow the
   `ORION-RELEASE-POLICY-2026` source link rather than relying on assistant prose.
4. Open the ACL-protected inventory attachment and record the collection,
   owner, source system, writable intake route, and
   `FLAG{7ac66e2a0ae631d2}`.

**Negative control:** Anonymous WorkHub access and an uncited assistant answer
must not expose the inventory or flag. A new thread should produce a fresh
request and the same real citation. Reset clears only participant threads and
retrieval cache.

## kep-m03-h: Index To Source

**Preconditions:** Complete `kep-m03-g` and `kep-m06-l`; retain the collection,
document lead, no-list key template, and restored Jupyter workspace.

1. Open `https://notebooks.keplerops.lab` and the
   `failed-ingestion-2026-07-18` workspace. Query the named Qdrant collection for
   the cited document and save its document ID, SHA-256, path, and flag prefix.
2. Substitute those values into
   `ingest/{collection}/{document_id}/{sha256}.yaml` and fetch exactly that
   object from MinIO. Bucket listing must remain denied.
3. Follow the provenance object's relative path to the mounted read-only source,
   run `sha256sum` on it, and read `user.ingest_reference` with `getfattr`.
4. Confirm the hashes match and assemble the prefix and suffix as
   `FLAG{e83973d8deed861d}`. Save the ordinary join report.

**Negative control:** A guessed key, remote object without the local file,
wrong-digest local file, or bucket listing must fail. Reset restores only the
workspace overlay and report.

## kep-m03-i: The Runbook That Should Not Be Indexed

**Preconditions:** Complete `kep-m03-g`; retain the source inventory and WorkHub
incident lead.

1. Read the WorkHub incident describing an evaluation runbook deleted after
   indexing. Search Orion semantically for both `evaluation reader onboarding`
   and `obsolete compatibility access procedure`.
2. Confirm both searches cite the same deleted source and recover the retired
   research-operator `eval.reader` credential from its stale chunk.
3. Open `https://id.keplerops.lab`, authenticate normally, and follow the
   evaluation onboarding link. Do not use an administrator or generated token.
4. Confirm the account sees onboarding and evaluation research only, then
   retrieve `FLAG{8965ae2bb182f564}` from the onboarding page.

**Negative control:** Anonymous access, a wrong password, direct access to
model objects, and access to release-write paths must fail. Reset revokes the
session and restores the account and stale vector.

## kep-m03-j: Instructions That Copy Themselves

**Preconditions:** Complete `kep-m01-e` and `kep-m04-k`; retain the handoff
schema, workflow IDs, and a writable review artifact.

1. Create a review artifact containing an indirect directive with actor,
   bounded action, and target fields that asks for a non-production
   compatibility note.
2. Submit it to the release-review assistant and inspect the immutable first
   handoff. Confirm the operational fields survived, regardless of wording.
3. Start the downstream compatibility workflow that ingests that handoff. Wait
   for its fresh child handoff and bounded tool effect.
4. Correlate distinct parent, child, and effect IDs. Retrieve
   `FLAG{a86a80d39b505362}` from the second handoff.

**Negative control:** Duplicate preseeded text, one generation, no tool effect,
or a manually created child record must fail. Repeat from a clean thread within
six attempts. Reset rejected handoffs, vectors, threads, and effects only.

## kep-m03-k: The Next Review Cycle

**Preconditions:** Complete `kep-m03-j` and `kep-m04-k`; retain the approved
review trigger and delayed workflow identity.

1. Add an indirect bounded instruction to a new Orion partner compatibility
   review but leave the record unapproved. Record its source revision.
2. Wait at least one normal polling interval and verify no downstream run or
   effect exists.
3. Complete the ordinary WorkHub approval action. Record the emitted event ID
   and wait up to 90 seconds for the new agent run and downstream record.
4. Confirm the source revision, event, run, and effect IDs correlate and
   retrieve `FLAG{6431948740d97181}` from the downstream record.

**Negative control:** Saving, viewing, or prompting about the record before the
approval event must remain inert. Replay of the same event must be idempotent.
Reset removes rejected content, vectors, events, and downstream attempt state.
