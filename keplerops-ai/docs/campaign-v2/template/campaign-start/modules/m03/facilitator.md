# Module 03 Facilitator Guide

Module 03 is the agent and supply-chain block of the campaign. Participants are
acting as Cinder Typhoon operators against a realistic KeplerOps enterprise:
they should make normal systems do normal work, then observe where trust,
retrieval, and automation carry attacker-controlled state farther than intended.

Facilitation should stay participant-equivalent. Staff may inspect read-only
service health, logs, and seeded state to diagnose defects, but should not hand
out generated carrier values, undiscovered credentials, backend object contents,
source-only secrets, or validator commands. When a participant is close, point
them back to the participant-visible service that proves the same fact.

## kep-m03-a: The Helpful Evaluation Update

**Learning intent:** Show that a private Python utility becomes executable code
inside a clean evaluation worker even when the utility's public scoring contract
still looks harmless.

**Realism:** KeplerOps pins an exact internal package from devpi, runs a normal
dependency review, and mounts worker-only context during evaluation. The attack
is plausible because enterprise package review often verifies outputs but not
import-time behavior, filesystem access, or egress.

**Preconditions:** The Cinder package publisher path works, devpi accepts the
participant's stable upload, the Airflow evaluation dependency review is
triggerable, Cinder object storage exposes the relay token, and the relay
basket records worker-origin callbacks.

**Likely failure modes:** Participants change `score_batch` behavior, publish
the wrong package version, test only by importing locally, forget to trigger the
worker review, or read the relay without the Cinder object token. Service
failures usually show as devpi upload errors, Airflow dependency install
failures, missing mounted worker reference, or absent relay requests.

**Participant-visible diagnosis:** Have them compare the worker run package
version and artifact digest with the devpi upload, then compare the score digest
with their local public fixture. If the relay is empty, ask whether the callback
was emitted by the worker run rather than their own shell.

**Tiered hints:**

1. Read the lockfile and update runbook before editing code.
2. Preserve the public scoring fixture exactly, then add behavior that only
   activates when the worker-only callback and reference are present.
3. The qualifying native record is joined to the Airflow worker run and relay
   request, not to a local import.

**Recovery:** For incomplete attempts, let them publish a later exact version
and re-trigger the worker. Do not delete successful devpi versions or worker
audit history. Staff reset should remove only incomplete relay state if it
blocks replay.

**Debrief:** Discuss hash pinning, isolated build/install stages, import
sandboxing, egress denial, and review of package side effects in addition to
functional tests.

## kep-m03-b: Earn The Maintainer's Trust

**Learning intent:** Teach that legitimate contribution and package reputation
can be an attack stage, not a distraction from the attack.

**Realism:** The Cinder project has a real SPDX normalization defect, normal CI,
maintainer review, a signed npm release, and a KeplerOps consumer that adopts
the approved package through routine dependency automation.

**Preconditions:** Cinder Forgejo accepts the participant identity, the issue and
repository are visible, Actions runners can run `npm test`, the maintainer merge
automation is active, the release workflow publishes to Verdaccio, and the
KeplerOps consumer can verify and record adoption.

**Likely failure modes:** Participants remove or weaken the failing check, add
malicious callback behavior too early, skip the source pull request reference,
tag an unmerged commit, assume comments/stars establish trust, or stop before
the KeplerOps consumer installs the release.

**Participant-visible diagnosis:** Ask for the Cinder PR, green CI run, merged
commit, release tag, signature asset, consumer lock integrity, and adoption
manifest. If a valid field-operator PR is rejected, treat it as a content
defect rather than a participant mistake.

**Tiered hints:**

1. The trust artifact is a merged useful fix with passing CI, not social proof.
2. Keep this release benign; the future value is the package identity and
   adoption path.
3. The downstream manifest must name the installed digest of the signed release.

**Recovery:** Participants can open a corrected PR or publish a later benign
version. Preserve failed branches, rejected PRs, release attempts, and adoption
history for audit.

**Debrief:** Cover maintainer trust boundaries, source provenance, reproducible
builds, signed releases, and dependency-review policies that remain strict after
a contributor becomes familiar.

## kep-m03-c: Change After Adoption

**Learning intent:** Show that a previously trusted package identity can ship a
malicious successor while preserving the same public behavior that made the
earlier release acceptable.

**Realism:** The successor uses the same package coordinate, publisher, signing
workflow, tests, and dependency-update mechanism. The consumer sees a normal
version bump and a preserved model-card compatibility result.

**Preconditions:** The benign adoption from `kep-m03-b` is complete, the Cinder
release workflow can sign a new version, KeplerOps dependency automation can
open a proposal, and Actions artifacts expose the proposal audit.

**Likely failure modes:** Participants rename the package, publish from the
wrong identity, break `inspectModelCard` public output, rely on local callback
tests, or manually edit the KeplerOps proposal instead of letting the updater
create it.

**Participant-visible diagnosis:** Compare the proposal lockfile to the Cinder
release integrity, confirm the release signature, check that the public result
is unchanged, and verify the proposal audit came from the KeplerOps consumer
workflow.

**Tiered hints:**

1. Keep the same package name, signer, and publisher.
2. Public model-card output should still look exactly boring.
3. Wait for the dependency proposal that names the successor integrity.

**Recovery:** Let participants publish a later successor version if they poison
the wrong one. Preserve prior benign adoption, rejected successors, and proposal
audit records.

**Debrief:** Discuss rug-pull risk, version-diff review, staged runtime
observation, behavior attestation, and why package identity is not a permanent
trust grant.

## kep-m03-d: Publish The Phantom Dependency

**Learning intent:** Demonstrate how repeatable hallucinated entities can become
real attacker-owned dependencies when automated review systems try to resolve
them.

**Realism:** The participant must reproduce a normal Orion factuality result,
register the exact entity through a Cinder registrar, publish DNS/TLS/service
state, and wait for the KeplerOps common review worker to visit the service.

**Preconditions:** The factuality prerequisite exposes fresh request IDs through
a participant-visible surface, the Cinder registrar can create the exact domain,
the operator service logs victim-origin visits, and the phantom-dependency
resolution DAG can be triggered or naturally scheduled.

**Likely failure modes:** Participants rely on a single model answer, change
spelling when converting the entity to a domain, visit their own service and
mistake that for proof, publish a service without TLS or ownership metadata, or
cannot find a participant-visible factuality report path.

**Participant-visible diagnosis:** Ask them to show two fresh request IDs for
the same unsupported entity, the registrar ownership manifest, live DNS/TLS/body
checks, the Airflow run ID, and the service log line with the review-worker user
agent and matching workflow run.

**Tiered hints:**

1. Get the model to repeat the unsupported entity before registering anything.
2. Register the exact normalized label, not an improved or guessed variant.
3. The qualifying event is a victim resolver visit, not an operator test curl.

**Recovery:** Rejected registrations and failed worker attempts can be reset.
Accepted ownership records and victim visits should remain intact. If no
participant-visible factuality report exists, mark the operation as needing live
verification.

**Debrief:** Emphasize dependency allowlists, authoritative resolution,
citation-backed factuality checks, and human review before automation resolves a
model-suggested external name.

## kep-m03-e: Poison The Tool's Truth

**Learning intent:** Show that tool-using agents can be policy-compliant and
still wrong when their trusted source of truth is attacker-editable.

**Realism:** Release Engineering can legitimately edit a WorkHub readiness
record. Orion then uses an allowed read-only MCP tool to fetch the current
record and write a release decision based on that source.

**Preconditions:** The Release Engineer role can edit `Preview rollback
readiness`, WorkHub journals source revisions, the current-status review can be
triggered, and the resulting decision journal exposes source revision, tool, and
trace details.

**Likely failure modes:** Participants paste instructions into chat instead of
editing WorkHub, edit the wrong issue, omit the readiness marker, trigger before
saving, or try to reuse an older assistant answer.

**Participant-visible diagnosis:** Have them compare the edit timestamp,
WorkHub source revision, Airflow run timestamp, tool response, and decision
journal. The decision should name the fresh source revision they changed.

**Tiered hints:**

1. The agent reads the saved WorkHub record, not your message to it.
2. Make the source say rollback is ready and preserve a plausible release note.
3. Join the edit, tool read, and decision journal from the same attempt.

**Recovery:** If no completion-bearing decision exists, compensate the source
back to its prior state and allow a fresh edit. Preserve WorkHub journals and
decision traces once written.

**Debrief:** Cover source integrity, approval workflow for high-impact fields,
freshness checks, corroboration, and distinguishing prompt injection from data
poisoning.

## kep-m03-f: The Tool That Calls Home

**Learning intent:** Distinguish publication from execution: the malicious
package matters only after the real consumer installs and invokes it as an MCP
tool in the model-card workflow.

**Realism:** KeplerOps merges a normal dependency proposal, runs the normal
model-card compatibility check, records the expected public result, and the
installed package copies a private field only through the hidden callback path.

**Preconditions:** The successor proposal from `kep-m03-c` exists, the
participant can merge or request normal merge of the consumer proposal, the
model-card workflow can run, Cinder object storage exposes the relay token, and
the relay records the workflow-origin callback.

**Likely failure modes:** Participants stop at publication or proposal, do not
merge the consumer lock, invoke the package locally, expose the private field in
the public artifact, or compare against the wrong installed integrity.

**Participant-visible diagnosis:** Ask for the merged proposal, current `main`
lockfile integrity, Airflow or Actions run ID, public model-card artifact, relay
request, and timestamp ordering. The relay and public artifact should describe
the same workflow run but expose different fields.

**Tiered hints:**

1. The consumer must merge and install the successor.
2. Public output should remain only license and schema.
3. The relay request should join to the Forgejo run and installed lock
   integrity.

**Recovery:** Re-run the model-card check after fixing merge/install state.
Reset should remove only incomplete relay baskets. Repository and registry
history must remain.

**Debrief:** Discuss MCP sandboxing, least-privilege model-card inputs, egress
controls, signed behavior attestations, and why `npm ci --ignore-scripts` does
not remove all runtime risk.

## kep-m03-g: Sources Behind The Answer

**Learning intent:** Teach participants to use citations and source metadata to
map a RAG system rather than treating assistant prose as the evidence.

**Realism:** Orion's release assistant cites a protected WorkHub inventory
record that describes the collection, owner, source system, and writable intake
route behind release-policy answers.

**Preconditions:** The participant has assistant access, the WorkHub migration
issue is visible, the citation drawer works, and the earned role can open the
protected inventory attachment.

**Likely failure modes:** Participants stop at the assistant answer, ask a vague
question that produces no citation, use an anonymous WorkHub session, or try to
guess source locations from names.

**Participant-visible diagnosis:** Ask for the assistant request ID, citation
drawer source ID, WorkHub attachment URL, access role, and inventory fields.
Anonymous or underprivileged access should fail.

**Tiered hints:**

1. Use the migration issue to shape a release-policy question.
2. Expand the citation drawer; the answer text is not enough.
3. Follow the source ID into WorkHub with the earned role.

**Recovery:** Fresh assistant threads can be created safely. Preserve original
threads and retrieval audit. If the drawer is missing or links to the wrong
system, record a content defect.

**Debrief:** Discuss citation ACLs, source minimization, retrieval metadata
leakage, and separating writable intake routes from sensitive inventory.

## kep-m03-h: Index To Source

**Learning intent:** Show how vector metadata, provenance objects, and source
object metadata can be joined into a stronger source-of-truth proof than any
single system exposes alone.

**Realism:** Participants must use a Qdrant read path, exact-key provenance
read, Cinder object stat, source digest comparison, and fixed-key Cinder
submission. Listing is intentionally denied, so successful work depends on
deriving exact keys and matching immutable metadata.

**Preconditions:** The deployed range exposes participant-visible Qdrant read
access and provenance read credentials or equivalent read-only routes, Cinder
object credentials work, the ingestion-review service watches the fixed
submission key, and accepted manifests are visible through Cinder objects.

**Likely failure modes:** Participants guess bucket paths, depend on listing,
submit extra YAML fields, use only Qdrant metadata without source bytes, upload
to the wrong key, or encounter a source SHA mismatch between Qdrant and Cinder.

**Participant-visible diagnosis:** Ask for the Qdrant point payload, derived
provenance key, listing denial, Cinder source stat, local source SHA, submitted
eight-field report, and accepted manifest. If Qdrant/provenance access is not
discoverable in-world, do not provide backend credentials; record live
verification needed.

**Tiered hints:**

1. The inventory gives collection and source identity; Qdrant gives point and
   digest.
2. Listing should fail. Exact keys are assembled from metadata.
3. The accepted manifest appears only when source bytes, provenance, Qdrant
   point, and fixed report fields agree.

**Recovery:** Remove only an unaccepted fixed-key submission to allow replay.
Accepted manifests and digest-addressed reports should be preserved. If Cinder
source bytes and Qdrant `source_sha256` disagree, mark a content defect.

**Debrief:** Cover metadata minimization, no-list object design, exact-key
access, provenance gaps, object versioning, and write-once acceptance records.

## kep-m03-i: The Runbook That Should Not Be Indexed

**Learning intent:** Demonstrate that deleting a source document does not
automatically delete its indexed chunks or rotate credentials exposed in those
chunks.

**Realism:** A WorkHub incident documents a removed evaluation-reader runbook,
but Orion semantic search can still retrieve stale chunks. The recovered account
must authenticate through normal Keycloak and remains limited to evaluation
reader scope: onboarding, the evaluation workspace, and scoped Orion Airflow
DAGs.

**Preconditions:** The incident is visible, Orion semantic search or assistant
search returns citations, the seeded `eval.reader` account remains valid, the
Airflow Orion View/Run grants are present, and the evaluation onboarding page
exposes a bounded proof.

**Likely failure modes:** Participants search for exact credential-looking
strings instead of purpose, use only one query, ignore citations, attempt admin
login paths, or overclaim access beyond the evaluation-reader role.

**Participant-visible diagnosis:** Ask for two fresh search request IDs, both
citation drawers, the deleted source ID, normal Keycloak login success, visible
role labels, onboarding page, and denied attempts to higher-privilege pages.

**Tiered hints:**

1. Search by the deleted runbook's purpose and onboarding workflow.
2. Two different phrasings should cite the same deleted source.
3. Use the recovered material through normal login and prove the role boundary.

**Recovery:** Revoke participant sessions and restore seeded vector/account
state if a replay is needed. Preserve incident and retrieval audit. If search no
longer cites the deleted source, record a content defect.

**Debrief:** Discuss coordinated source/vector deletion, secret scanning of
indexed content, credential rotation, and least-privilege blast-radius control.

## kep-m03-j: Instructions That Copy Themselves

**Learning intent:** Show that an indirect instruction can preserve operational
meaning across assistant handoffs even when exact text is transformed.

**Realism:** The participant plants a small structured directive in a WorkHub
artifact. The release-review assistant records a parent handoff, the
compatibility assistant consumes it, and only a bounded non-production WorkHub
journal is created.

**Preconditions:** Release Engineer can attach a directive to the schema issue,
the handoff DAG can run, WorkHub records attachment digests and journals, and
the final compatibility handoff record exposes parent/child/effect lineage.

**Likely failure modes:** Participants add extra fields, omit required fields,
reuse preseeded text, produce only one handoff, expect byte-for-byte copying, or
target a production mutation that the bounded tool refuses.

**Participant-visible diagnosis:** Ask for the attachment digest, schema
fields, parent handoff ID, child handoff ID, two trace IDs, bounded effect
journal, and final lineage record. Parent and child IDs must differ.

**Tiered hints:**

1. The directive is just actor, bounded action, and target.
2. The evidence is lineage through two handoffs, not duplicated wording.
3. The effect should be a bounded compatibility note, not a production change.

**Recovery:** Participants can attach a fresh valid directive and rerun the
handoff. Preserve malformed attempts, handoffs, traces, and bounded effects as
audit evidence.

**Debrief:** Cover taint tracking, schema-level instruction stripping, origin
policy, tool bounding, and reviewing generated handoff artifacts before they
become inputs to another agent.

## kep-m03-k: The Next Review Cycle

**Learning intent:** Demonstrate delayed activation: an indirect instruction can
sit inert in a legitimate record until a later approval event gives it execution
context.

**Realism:** The participant attaches a directive before approval, proves no
effect occurs while the record is unapproved, then uses the normal Release
Engineer approval path. The scheduled follow-up workflow processes the approved
event and creates one bounded downstream note.

**Preconditions:** The review issue is editable by Release Engineer, attachment
journals expose timestamps and digests, the scheduled follow-up DAG runs, and
the downstream record names the approval event, source revision, trace, and
bounded effect.

**Likely failure modes:** Participants expect immediate activation, approve
before attaching, attach malformed or production-targeted content, miss the
scheduler window, or treat page refreshes as trigger events.

**Participant-visible diagnosis:** Ask for the attachment timestamp, no-effect
wait evidence, approval journal, event ID beginning with the review-approved
prefix, scheduled run, downstream record, and proof that the effect is bounded
and non-production.

**Tiered hints:**

1. Planting the content should be inert.
2. The normal approval event is the trigger; preserve its journal timestamp.
3. The downstream record must tie attachment, approval event, agent run, trace,
   and bounded effect together.

**Recovery:** If no completion-bearing downstream record exists, staff may
restore incomplete approval state for replay. Once a downstream record exists,
preserve the event chain and use idempotent replay only.

**Debrief:** Discuss delayed-job reauthorization, event-payload sanitization,
content provenance, approval-time validation, idempotency, and separating
stored content from executable instructions.
