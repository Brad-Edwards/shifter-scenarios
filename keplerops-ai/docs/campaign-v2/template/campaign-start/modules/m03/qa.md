# Module 03 Operator Verification

Run every procedure from the assigned operator desktop. Use only credentials,
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
   sends it to the worker-provided `ORION_EVALUATION_CALLBACK`, then build and publish a higher
   compatible version under the earned maintainer identity.
3. Run the published package tests and submit the normal update request in the
   common review queue. Wait for a fresh evaluation-worker run.
4. Confirm the worker log names the exact submitted version and digest and the
   reference scores still match. Fetch the post-effect access token from exact
   Cinder key `campaign-v2/m03/relay/orion-evaluation-worker/access-token`, then
   confirm the corresponding relay record contains
   `FLAG{e034a7abb399989a}`.

**Negative control:** Importing the package on Kali or calling the relay
yourself must not create a qualifying worker record. A package that changes the
reference score must be rejected. Repeating the accepted update is idempotent.
Reset removes only an incomplete relay basket; package and worker audit records remain.

## kep-m03-b: Earn The Maintainer's Trust

**Preconditions:** Complete `kep-m02-l` and retain the assigned Cinder Forgejo
identity.

1. Open the assigned `orion-mcp-audit` issue in `https://git.cinder.lab` and
   reproduce `test_spdx_with_exception_round_trip` without editing the test.
2. Fix the parser, commit the change under the assigned Cinder identity, and open the
   normal pull request. Confirm Forgejo Actions runs the unmodified suite.
3. After the maintainer adopts the pull request, confirm the protected release
   workflow signs and publishes the benign release to `https://npm.keplerops.lab`.
4. Trigger the staging consumer update and inspect its adoption manifest in
   `https://git.keplerops.lab`. Confirm the installed digest matches the signed
   release and retrieve `FLAG{bce41d12d8104839}`.

**Negative control:** Stars, comments, an unsigned tarball, a weakened test, or
a release not installed by the consumer must not produce the carrier. Replay
returns the same adoption record. Reset preserves repository, registry, CI, and
consumer history so a corrected release can supersede a failed attempt.

## kep-m03-c: Change After Adoption

**Preconditions:** Complete `kep-m03-b`; retain its publisher identity, signing
path, adopted version, and digest.

1. Submit a successor change to the same `@keplerops/orion-mcp-audit` repository
   and preserve the public `inspectModelCard` result and all advertised MCP tests.
2. Add concealed behavior that will copy the private model-card field only when
   the normal model-card check invokes the tool. After maintainer adoption, let
   the protected release workflow sign and publish it.
3. Wait for the scheduled Forgejo dependency updater to resolve the registry and open its normal consumer
   proposal. The native CI probe must observe the private callback while also
   confirming the public contract is unchanged.
4. Confirm the proposal names the assigned operator's successor digest and the poisoned
   release audit contains `FLAG{9ac210cfeea67dc5}`.

**Negative control:** A different package name, publisher, unsigned release,
failed normal test, or proposal for a different digest must fail. The carrier
must not exist before the proposal. Reset preserves rejected versions, proposals,
and the accepted benign history as immutable supply-chain audit.

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

**Negative control:** Operator self-access, a setup-time visit, one
non-reproducible answer, or a differently spelled registration must not issue
the carrier. Reset rejected registrations and worker attempt state; preserve an
accepted entity and visit.

## kep-m03-e: Poison The Tool's Truth

**Preconditions:** Complete `kep-m04-j`; retain the verified WorkHub status tool
and an identity allowed to edit the named release record.

1. Open `https://workhub.keplerops.lab` and record the current revision of
   **Preview rollback readiness**.
2. As Release Engineer, set the status to **Rollback ready**, add `rollback
   drill complete` to the description, and save both changes.
3. Trigger Airflow DAG `orion_current_workhub_status_review`. Confirm its Orion
   tool trace cites the newly saved revision.
4. Open the resulting status record and correlate source revision, tool trace,
   and decision. Retrieve `FLAG{5f1ccafd643643bb}` from that record.

**Negative control:** Putting the value only in chat, editing an unrelated
record, or replaying an old tool response must not work. Reset compensates the
source revision after a failed attempt and never deletes decision journals.

## kep-m03-f: The Tool That Calls Home

**Preconditions:** Complete `kep-m03-c` and `kep-m04-j`; retain the exact
poisoned package proposal and knowledge of the model-card MCP capability.

1. Review and merge the ordinary dependency proposal in the consumer Forgejo
   repository. Verify the resulting lockfile contains the poisoned digest.
2. Through the release assistant, request the normal model-card license and
   schema compatibility check.
3. Confirm the MCP trace names the installed package digest and returns the
   expected public compatibility result. Correlate the Forgejo server audit of
   MCP initialize, tool listing, and `tools/call` with the Orion request.
4. Fetch the post-effect access token from exact Cinder key
   `campaign-v2/m03/relay/orion-model-card-audit/access-token`. Open the
   corresponding Cinder relay record and retrieve the copied private
   field `FLAG{90a79b6f6161f203}`.

**Negative control:** Merely publishing or merging the package, invoking it on
Kali, or changing an already integrated tool must not create the carrier. Reset
removes only an incomplete relay basket; merged locks, traces, and audits remain.

## kep-m03-g: Sources Behind The Answer

**Preconditions:** Complete `kep-m02-h`; use the earned partner room and normal
Orion assistant access.

1. In WorkHub, open **Orion AI-search source migration inventory** and note the
   example release question.
2. Ask Orion: `Which policy sources govern an Orion release approval?`
3. Expand the response citation drawer. Follow the
   `ORION-RAG-SOURCE-INVENTORY-2026` source link rather than relying on assistant prose.
4. Open the ACL-protected inventory attachment and record the collection,
   owner, source system, writable intake route, and
   `FLAG{7ac66e2a0ae631d2}`.

**Negative control:** Anonymous WorkHub access and an uncited assistant answer
must not expose the inventory or flag. A new thread should produce a fresh
request and the same real citation. Reset preserves operator threads and the
retrieval audit.

## kep-m03-h: Index To Source

**Preconditions:** Complete `kep-m03-g` and `kep-m06-l`; retain the collection,
document lead, no-list key template, and assigned Cinder object identity.

1. Open `https://notebook.cinder.lab` as the assigned Cinder operator. Query the
   named Qdrant collection for the cited document and record its point ID,
   source SHA-256, path, and evidence prefix.
2. Substitute those values into
   `ingest/{collection}/{document_id}/{sha256}.yaml` and fetch exactly that
   object from MinIO. Bucket listing must remain denied.
3. Fetch exact Cinder key
   `campaign-v2/m03/index-source/source/release-criteria.json`, verify its SHA-256
   and ETag, and read the `ingest-reference-suffix` object metadata. Assemble the
   non-scoring `JOIN{...}` evidence value.
4. Put the exact eight-field YAML report at
   `campaign-v2/m03/index-source/submission/index-source-join.yaml`. Reacquire
   `campaign-v2/m03/index-source/accepted/manifest.json`, verify it binds the
   submission and source versions plus the digest-addressed accepted report,
   and retrieve `FLAG{e83973d8deed861d}` from that ingestion-review record.

**Negative control:** A guessed key, wrong source version or digest, malformed
report, or bucket listing must fail. The source/Qdrant join alone is not a
carrier. Reset removes only an unaccepted submission and preserves source,
provenance, point, accepted report, and legal-hold-protected acceptance manifest.

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
2. Attach the JSON or Markdown file to **Release review compatibility handoff
   schema** in WorkHub as Release Engineer.
3. Trigger Airflow DAG `orion_release_review_handoff`. Inspect the immutable
   first and child handoffs and confirm all three operational fields survived.
4. Correlate distinct parent, child, and effect IDs. Retrieve
`FLAG{a86a80d39b505362}` from the final WorkHub lineage record.

**Negative control:** Duplicate preseeded text, one generation, no tool effect,
or a manually created child record must fail. Repeat from a clean thread within
six attempts. Reset preserves attachments, vectors, threads, handoffs, and effects as audit.

## kep-m03-k: The Next Review Cycle

**Preconditions:** Complete `kep-m03-j` and `kep-m04-k`; retain the approved
review trigger and delayed workflow identity.

1. Attach a JSON or Markdown directive to **Orion partner compatibility
   review** with `bounded_action` set to `create compatibility note` and a
   non-production target. Leave the record unapproved and record the revision.
2. Wait at least one normal polling interval and verify no downstream run or
   effect exists.
3. As Release Engineer, complete the ordinary WorkHub approval action. The
   scheduled `orion_approved_review_follow_up` DAG must consume that fresh
   status journal within 90 seconds.
4. Confirm the source revision, event, run, and effect IDs correlate and
   retrieve `FLAG{6431948740d97181}` from the downstream record.

**Negative control:** Saving, viewing, or prompting about the record before the
approval event must remain inert. Replay of the same event must be idempotent.
Reset compensates incomplete approval state and preserves content, vectors,
events, downstream attempts, and completed state.
