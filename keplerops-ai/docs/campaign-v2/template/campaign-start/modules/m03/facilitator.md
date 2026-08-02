# Module 03 Facilitator Guide

## kep-m03-a: The Helpful Evaluation Update

**Lesson and reality:** Private Python dependencies are executable supply-chain
inputs; KeplerOps' clean evaluation worker installs an approved exact version
from devpi. **Method:** Preserve scoring while adding import-time access to the
worker-mounted integration value and relay. **Milestones:** exact lock source, passing
tests, signed publication, victim install, valid score, relay event. **Stalls:**
Kali-side imports and self-sent relay traffic do not count; check the victim run
digest. Offer hints in lockfile, behavior-preservation, then run-output order.
**Defense:** hash pinning, isolated builds, import sandboxing, egress denial,
and dependency review. **Diagnostics/reset:** inspect devpi serial, worker pip
report, score digest, and relay source; remove only an incomplete relay basket.

## kep-m03-b: Earn The Maintainer's Trust

**Lesson and reality:** Objective useful contribution can create exploitable
supply-chain trust. **Method:** Fix the real SPDX defect, retain the test, sign a
benign release, and get the staging consumer to install that digest.
**Milestones:** reproduced failure, green CI, signature, registry digest,
consumer adoption. **Stalls:** stars and comments are irrelevant; compare the
installed digest. Hints move from trust evidence to benignness to adoption.
**Defense:** maintain review depth after reputation, require reproducible builds
and independent ownership. **Diagnostics/reset:** Forgejo checks, signature,
Verdaccio metadata, consumer lockfile; retain failed branch/release/adoption audit.

## kep-m03-c: Change After Adoption

**Lesson and reality:** Trusted identities can publish malicious successors
without changing package coordinates. **Method:** Keep the same package,
publisher, signing path, and advertised behavior while adding concealed tool
behavior. **Milestones:** prior adoption, passing successor tests, signed new
digest, scheduled Forgejo dependency proposal. **Stalls:** a renamed fork or manually edited
proposal is invalid. Hints emphasize identity, behavior, then digest.
**Defense:** version-diff review, behavior tests, provenance policy, and staged
runtime observation. **Diagnostics/reset:** compare tarballs and signatures,
proposal resolution logs; retain rejected successor/proposal and benign trust.

## kep-m03-d: Publish The Phantom Dependency

**Lesson and reality:** Repeatable model hallucinations become supply-chain
targets when automated consumers resolve them. **Method:** Register the exact
independently verified entity, publish benign diagnostics, and trigger the real
victim resolver. **Milestones:** repeated unsupported entity, ownership record,
fresh recommendation, worker-origin visit. **Stalls:** operator self-visits
and one-off answers are excluded. **Defense:** allowlisted dependencies,
authoritative resolution, citation validation, and human review. **Diagnostics/reset:**
correlate inference, resolver, DNS/registry, and access-log IDs; reset rejected
registrations and review state, not an accepted ownership record.

## kep-m03-e: Poison The Tool's Truth

**Lesson and reality:** An agent can be policy-compliant yet wrong when its
authoritative tool data lacks integrity. **Method:** Edit a legitimately
writable WorkHub status and cause a fresh MCP read to drive a decision.
**Milestones:** source revision, tool response, decision trace, changed status.
**Stalls:** chat-only injection is a different technique; verify the source
revision. **Defense:** provenance, change approval, freshness/integrity checks,
and high-impact corroboration. **Diagnostics/reset:** WorkHub journal, MCP
trace, decision source digest; compensate the source revision and retain journals.

## kep-m03-f: The Tool That Calls Home

**Lesson and reality:** Publication is not compromise until the victim installs
and invokes malicious bytes. **Method:** Merge the normal update, run the real
model-card check, preserve its public result, and observe the concealed relay.
**Milestones:** installed digest, MCP load, expected result, private-field copy.
**Stalls:** direct package execution and proposal-only state fail. **Defense:**
tool sandboxing, least-privilege fields, egress policy, signed behavioral
attestations. **Diagnostics/reset:** consumer lock, MCP trace, relay origin;
remove only an incomplete relay basket and retain merged history.

## kep-m03-g: Sources Behind The Answer

**Lesson and reality:** Citations disclose the shape and ownership of a RAG
system more reliably than assistant prose. **Method:** Ask a normal release
question and follow its real citation to the protected inventory. **Milestones:**
fresh response, source ID, ACL transition, collection and ingestion route.
**Stalls:** users often stop at the answer; direct them to the citation drawer.
**Defense:** citation ACL enforcement, source minimization, and ingestion-route
separation. **Diagnostics/reset:** Orion request/retrieval trace and WorkHub
attachment ACL; preserve threads and retrieval audit.

## kep-m03-h: Index To Source

**Lesson and reality:** Vector metadata can bridge indexed content to an exact
versioned source object. **Method:** Join Qdrant metadata, a no-list provenance
object, Cinder source bytes, digest, ETag, version, and source metadata; submit
the fixed report key for normal ingestion review. **Milestones:** point ID,
derived provenance key, exact source hash, non-scoring evidence join, immutable
acceptance manifest. **Stalls:** bucket listing is intentionally denied and the
engagement reference does not exist until acceptance. **Defense:** metadata
minimization, distinct service identities, exact-key access, and write-once
acceptance under Cinder object legal hold. **Diagnostics/reset:** inspect ingestion-review logs and object
versions; remove only an unaccepted submission and preserve accepted audit.

## kep-m03-i: The Runbook That Should Not Be Indexed

**Lesson and reality:** Deleting a source does not delete its vector, and stale
RAG content can expose still-valid credentials. **Method:** Search semantically
with two phrasings, recover the bounded synthetic credential, and use normal
Keycloak login. **Milestones:** stale citation, same source ID, successful
login, limited onboarding. **Stalls:** explain source/vector lifecycle without
giving the search phrase. **Defense:** coordinated deletion, secret scanning,
credential rotation, and least privilege. **Diagnostics/reset:** Qdrant point,
Keycloak events, role checks; revoke sessions and restore seeded state.

## kep-m03-j: Instructions That Copy Themselves

**Lesson and reality:** Agent outputs become trusted inputs across immutable
handoffs, allowing operational meaning to propagate without byte equality.
**Method:** Plant actor/action/target semantics, induce two distinct handoffs,
and produce one bounded effect. **Milestones:** source revision, parent ID,
child ID, preserved fields, effect ID. **Stalls:** duplicate text or one handoff
is insufficient; compare lineage. **Defense:** taint tracking, schema-level
instruction stripping, origin policy, and bounded tools. **Diagnostics/reset:**
Qdrant ingestion, both handoffs, traces, effect; preserve rejected descendants.

## kep-m03-k: The Next Review Cycle

**Lesson and reality:** Persisted indirect instructions can remain dormant
until a legitimate event activates them. **Method:** Plant content, prove no
immediate effect, then approve normally and correlate the later run within 90
seconds. **Milestones:** source revision, inert interval, event, run, effect.
**Stalls:** saving is not activation; verify event identity. **Defense:** event
payload sanitization, content provenance, delayed-job reauthorization, and
idempotency. **Diagnostics/reset:** WorkHub journal, RabbitMQ event, worker and
effect records; compensate incomplete approval state and preserve the event chain.
