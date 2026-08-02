# m06 Facilitation Notes

Use read-only service records for diagnosis. Never supply an undiscovered
hostname, credential, predecessor locator, accepted reference, or management
identity. A record is accepted only by its owning system after the participant
action; staff do not create, edit, copy, or award one manually.

## kep-m06-a — Preserve Meaning Across Intake

**Lesson:** Evasion can preserve operational semantics while changing a classifier decision.
**Enterprise reality:** Partner Intake owns exact uploads, Preview decisions, typed dry-run instructions, and effects.
**Attacker method:** Produce distinct held/accepted bytes with one bounded instruction; valid document tools are alternatives.
**Why it succeeds:** Classification is weaker than the downstream typed instruction path; the review joins both.
**What good looks like:** Two intake IDs, different hashes, same typed fields, held→accepted, one dry-run effect in three minutes.
**Common stalls:** Missing `m04-f/q`, reusing bytes, changing fields, or asking staff to upload.
**Hint guidance:** Orientation points to intake history; Mechanism to preserved fields; Execution to acceptance-review.
**Defensive discussion:** Canonicalize, compare semantics, isolate actions, and require approval for changed representations.
**Diagnostics:** Read intake/review/fixture records and Preview IDs only.
**Reset boundary:** Delete unreferenced attempts; preserve accepted review, effect, bytes, and parents.

## kep-m06-b — Cross The Command Boundary

**Lesson:** A reusable prompt template can turn model output into varied executable effects.
**Enterprise reality:** Orion Developer calls GLM; the read-only bridge parses an allowlisted command object without a shell.
**Attacker method:** Reuse one template for two objectives that yield distinct commands/effects.
**Why it succeeds:** Template instructions cross from prose into a constrained but real executor.
**What good looks like:** One template digest, two provider-bound threads/jobs, distinct commands and output hashes.
**Common stalls:** Different templates, duplicate effects, malformed JSON, forbidden paths, absent parents.
**Hint guidance:** Orientation to the bridge schema; Mechanism to template reuse; Execution to two small fixture effects.
**Defensive discussion:** Treat generated commands as untrusted, minimize tools, validate intent, sandbox, and audit.
**Diagnostics:** Read thread/job/corpus records and GLM usage joins.
**Reset boundary:** Clear threads/jobs only before corpus acceptance; preserve accepted corpus.

## kep-m06-c — Optimize Through Preview

**Lesson:** Bounded query access can steer a black-box model.
**Enterprise reality:** Preview writes immutable, ordered input/output audits.
**Attacker method:** Submit a complete three-or-more-step series with increasing target score inside the distance bound.
**Why it succeeds:** Output probabilities expose an optimization signal.
**What good looks like:** All experiment audit IDs in native order, clean first, target candidate last.
**Common stalls:** Cherry-picking IDs, reordering, two inputs, or exceeding the bound.
**Hint guidance:** Orientation to experiment header; Mechanism to score progression; Execution to preserve every query ID.
**Defensive discussion:** Rate limits, coarse outputs, anomaly detection, and query-budget tradeoffs.
**Diagnostics:** Read Preview audit files and experiment export.
**Reset boundary:** Failed request is transactional; preserve accepted audits/export.

## kep-m06-d — Transfer From An Executed Proxy

**Lesson:** An acquired public bundle can support low-query transfer.
**Enterprise reality:** Experiments loads the proxy, recomputes gradients/margins, then joins live Preview queries.
**Attacker method:** Train the documented linear proxy, optimize locally, and spend at most eight target queries.
**Why it succeeds:** Proxy and target share useful decision features.
**What good looks like:** Exact proxy/trace/candidate hashes, matching server gradient, rising proxy margin, target label.
**Common stalls:** Opaque model, claimed training count, wrong gradient digest, too many target calls.
**Hint guidance:** Orientation to public bundle; Mechanism to local margin; Execution to JSON model format.
**Defensive discussion:** Limit artifact disclosure, diversify models, monitor transfer probes, retain calibration value.
**Diagnostics:** Read proxy execution fields and Preview audits.
**Reset boundary:** Preserve accepted export/model/trace; rejected POST leaves no record.

## kep-m06-e — Separate Human And Machine Views

**Lesson:** A PDF can render benignly while retaining machine-consumed behavior.
**Enterprise reality:** Partner Intake uses Poppler, Tika, OCR, Qdrant, GLM, and Preview on exact bytes.
**Attacker method:** Hide a typed instruction from visible extraction while retaining it in machine extraction.
**Why it succeeds:** Rendering and parser pipelines disagree, and downstream automation trusts the latter.
**What good looks like:** Page rendering, different visible/machine hashes, hidden typed fields, changed decision.
**Common stalls:** Visible payload, too little human content, identical extraction, absent `a/s`.
**Hint guidance:** Orientation to extraction hashes; Mechanism to parser differences; Execution to rendering-review.
**Defensive discussion:** Multi-view comparison, sanitization, provenance, and human approval.
**Diagnostics:** Read intake text hashes, pipeline trace, and rendering review.
**Reset boundary:** Remove only unreferenced failed intake; preserve accepted PDF/review.

## kep-m06-f — Transfer Through The Full Document Path

**Lesson:** A proxy representation matters only if the deployment pipeline reproduces target effect.
**Enterprise reality:** Exact PDF bytes flow through extraction, retrieval, assistant, and Preview.
**Attacker method:** Bind the local proxy candidate to one extraction representation and trigger a fresh target decision.
**Why it succeeds:** Deployment transformation preserves the adversarial representation.
**What good looks like:** Matching proxy/extraction digest, complete stage lineage, fresh Preview ID and target decision.
**Common stalls:** Unrelated proxy bytes, stale Preview event, missing `d/e`, or participant-authored result JSON.
**Hint guidance:** Orientation to pipeline trace; Mechanism to digest continuity; Execution to target-review.
**Defensive discussion:** Test transformed inputs, stage-by-stage provenance, and release gates.
**Diagnostics:** Read intake trace/review and Preview audit.
**Reset boundary:** Preserve accepted lineage; clear only unreferenced attempt directory.

## kep-m06-g — Read The Release Record

**Lesson:** Public research and release records leak operationally useful lineage.
**Enterprise reality:** KeplerOps publishes a normal research index and signed release manifest.
**Attacker method:** Follow public links and compare source/model/release fields.
**Why it succeeds:** The manifest intentionally carries the engagement reference.
**What good looks like:** Consistent paper, preprint, manifest, and public Forgejo tag.
**Common stalls:** Searching only the home page or ignoring downloaded JSON.
**Hint guidance:** Orientation to Research; Mechanism to manifest fields; Execution to `engagement_reference`.
**Defensive discussion:** Minimize public metadata while retaining supply-chain transparency.
**Diagnostics:** Read public HTTP bytes only.
**Reset boundary:** Immutable public state; no local reset.

## kep-m06-h — Trust A Signed Mobile Repository

**Lesson:** Mobile provenance spans repository signature, APK, source, and SBOM.
**Enterprise reality:** A functional F-Droid repository distributes the workflow-built Android package.
**Attacker method:** Verify the signed index, install the package, and join provenance prefix to SBOM suffix.
**Why it succeeds:** Separate provenance surfaces disclose complementary reference parts.
**What good looks like:** Valid JAR signature, installable app, exact index/APK/SBOM digests.
**Common stalls:** Treating HTML as F-Droid, skipping install, or using mutable files outside the repo.
**Hint guidance:** Orientation to repository URL; Mechanism to signed index; Execution to package metadata and SBOM property.
**Defensive discussion:** Reproducible builds, repository signing, transparency, and metadata minimization.
**Diagnostics:** Verify JAR/APK/SBOM/source release.
**Reset boundary:** Immutable public repository.

## kep-m06-i — Corroborate Identity Independently

**Lesson:** Reliable OSINT requires sources with different ownership and protocols.
**Enterprise reality:** Independent conference web/DNS/mail and public Forgejo identities corroborate KeplerOps employment.
**Attacker method:** Cross-check conference, partner organization, profiles, DNS/MX, mail, and vCard.
**Why it succeeds:** The outside program record carries a speaker engagement reference.
**What good looks like:** Independent hostname/certificate and five agreeing identity signals.
**Common stalls:** Using only the KeplerOps people page or old same-site path.
**Hint guidance:** Orientation to conference name; Mechanism to source independence; Execution to vCard NOTE.
**Defensive discussion:** Separate personal/public identities and monitor impersonation without erasing legitimate scholarship.
**Diagnostics:** DNS, TLS, Stalwart principal, public Forgejo and static site.
**Reset boundary:** Immutable public corroboration.

## kep-m06-j — Join Preview, Mail, And Case Management

**Lesson:** Cross-channel correlation can reveal a public intake reference.
**Enterprise reality:** Stalwart stores SMTP mail; the mail-to-case bridge creates a Zammad ticket; status joins Preview.
**Attacker method:** Use one fresh external reference in benign Preview text and authenticated mail.
**Why it succeeds:** Operational status intentionally correlates exact Message-ID/RFC822 digest and model event.
**What good looks like:** Preview ID, IMAP UID, Message-ID, Zammad ticket/article and stable status record.
**Common stalls:** Wrong sender/recipient/reference, missing Preview, or expecting a custom SMTP port.
**Hint guidance:** Orientation to external intake address; Mechanism to shared reference; Execution to status URL.
**Defensive discussion:** Reduce public correlation, authenticate status viewers, and preserve case traceability.
**Diagnostics:** Read Stalwart mailbox, Zammad article, Preview audit, status record.
**Reset boundary:** Preserve accepted mail/ticket/status; retry failed attempt with new reference.

## kep-m06-k — Execute Acquired Public Assets

**Lesson:** Artifact presence is weaker than reproducible execution.
**Enterprise reality:** Releases reacquires public model/data/agent bytes and runs their declared entrypoint.
**Attacker method:** Bind a successful Forgejo run to one exact public manifest and record all outputs.
**Why it succeeds:** Public release exposes a complete runnable bundle.
**What good looks like:** Three role digests and eight deterministic execution records.
**Common stalls:** First-line-only prediction, missing runtime asset, failed/unrelated Action, wrong parent mode.
**Hint guidance:** Orientation to bundle manifest; Mechanism to entrypoint; Execution to public-bundles endpoint.
**Defensive discussion:** Publish least-necessary artifacts, sign manifests, test disclosure consequences.
**Diagnostics:** Read Forgejo run, acquired digests, runner stdout and executions.
**Reset boundary:** Preserve accepted release; failed CI/reacquisition creates no record.

## kep-m06-l — Prove Kubernetes Workspace Persistence

**Lesson:** Notebook persistence depends on server/PVC identity, not a participant-written marker.
**Enterprise reality:** JupyterHub KubeSpawner provides per-user PVC and CPU/GPU profiles.
**Attacker method:** Write a probe, stop/start through Hub, and inspect Hub’s Kubernetes observation.
**Why it succeeds:** New pod reattaches the same PVC and exact runtime image.
**What good looks like:** Different pod UIDs, same PVC UID, real image ID, matching server-observed probe hash.
**Common stalls:** Kernel restart instead of server stop, wrong path, waiting on GPU capacity, local fake ID.
**Hint guidance:** Orientation to Hub control panel; Mechanism to PVC; Execution to `.cinder/probe`.
**Defensive discussion:** Namespace/RBAC isolation, image pinning, encryption, quota, and durable workspace risk.
**Diagnostics:** Read Hub state and K8s pod/PVC only.
**Reset boundary:** Delete only unaccepted pod; preserve accepted record/PVC.

## kep-m06-m — Exercise A Real Physical Countermeasure

**Lesson:** Physical AI evidence needs live device, liveness, witness view, telemetry, and reset.
**Enterprise reality:** labgrid reserves an external bench; bench exporter owns raw evidence.
**Attacker method:** Reserve/acquire the declared place and execute randomized actuator/light pattern.
**Why it succeeds:** Current lease/nonces bind dual frames and telemetry to one physical action.
**What good looks like:** Real place, opaque reservation, live nonce markers, safe limits, visible/telemetry deltas, reset.
**Common stalls:** No bench, stale reservation, uploaded/simulated media, missing witness or reset sample.
**Hint guidance:** Offer none until real place appears; then orientation to labgrid, mechanism to liveness, execution to exporter contract.
**Defensive discussion:** Hardware roots of trust, anti-replay, safety interlocks, privacy, and throughput.
**Diagnostics:** Read labgrid/exporter and raw evidence verifier; never substitute media.
**Reset boundary:** Release failed lease; accepted raw archive immutable; absent physical bench remains blocked.

## kep-m06-n — Establish Native Domain Ownership

**Lesson:** Service ownership is a chain across identity, DNS, mail, ACME, content, and live TLS.
**Enterprise reality:** Keycloak, PowerDNS, Stalwart, Step CA, Caddy, and Registrar each own one link.
**Attacker method:** Complete links separately and present signed ACME POST-as-GET messages for the exact order/certificate.
**Why it succeeds:** Registrar deploys and revalidates the exact order certificate and private-key match.
**What good looks like:** Keycloak ID, zone serial, mail principal, service hash, valid order/cert URLs, matching live fingerprint.
**Common stalls:** Service before certificate, fake/local account, mismatched key, bootstrap wildcard, stale DNS.
**Hint guidance:** Orientation to registrar sequence; Mechanism to ACME order continuity; Execution to ownership-manifest.
**Defensive discussion:** Domain-control validation, key custody, scoped automation, and continuous revalidation.
**Diagnostics:** Read only linked native records and live DNS/TLS.
**Reset boundary:** Delete incomplete Keycloak/DNS/mail/domain state; preserve accepted ownership.

## kep-m06-o — Reproduce Upstream Tools

**Lesson:** Toolchain integrity requires executing declared versions and images.
**Enterprise reality:** Forgejo/Harbor release record pins lockfile, ART and ffmpeg recipes.
**Attacker method:** Commit exact lock and deterministic inputs/outputs, then request registry reproduction.
**Why it succeeds:** Fixed upstream transformations are reproducible byte-for-byte.
**What good looks like:** Commit/image/lock continuity plus matching ART array and ffmpeg output hashes.
**Common stalls:** Unpinned lock, unrelated image/run, unsupported ffmpeg args, uploaded output only.
**Hint guidance:** Orientation to recipes; Mechanism to deterministic rerun; Execution to toolchain-releases.
**Defensive discussion:** Lock dependencies, provenance images, hermetic tests, and upstream monitoring.
**Diagnostics:** Read source/run/image and server rerun fields.
**Reset boundary:** Rejected requests transactional; preserve accepted release and `k/l`.

## kep-m06-p — Attribute Shared GLM Use

**Lesson:** Shared inference needs per-range/actor/client attribution and response continuity.
**Enterprise reality:** Cinder edge separates participant and service credentials over a redundant shared Vertex pool.
**Attacker method:** Use OpenCode for an Orion-grounded request and follow usage/response headers.
**Why it succeeds:** The edge verifies upstream model identity and journals exact request/response digests.
**What good looks like:** Participant credential class, OpenCode client, target grounding, provider ID, response object.
**Common stalls:** Generic curl, non-Orion prompt, internal service call, wrong upstream model.
**Hint guidance:** Orientation to OpenCode; Mechanism to headers; Execution to usage path.
**Defensive discussion:** Short-lived credentials, quotas/fairness, model attestation, isolated caches, privacy.
**Diagnostics:** Read edge journal and shared-pool request ID; do not inspect prompt bodies.
**Reset boundary:** Usage audit append-only; retry creates a new ID.

## kep-m06-q — Validate A Target Harness

**Lesson:** CI provenance must bind executable source, preprocessing, image, and target behavior.
**Enterprise reality:** Isolated Forgejo runner uses rootless BuildKit and project-scoped Harbor robot.
**Attacker method:** Commit and execute `ci/validate-orion-harness` with clean/candidate bytes and OCI revision label.
**Why it succeeds:** Registry reruns committed code and target queries rather than trusting CI prose.
**What good looks like:** Successful exact commit, Harbor digest/revision, harness stdout hash, different target outputs.
**Common stalls:** Repository-local secret assumption, Docker command, mutable tag, absent script/label, unrelated Action.
**Hint guidance:** Orientation to user-level secrets/BuildKit; Mechanism to commit label; Execution to harness-releases.
**Defensive discussion:** Ephemeral builders, no host socket, least-privilege robots, attestations, protected workflows.
**Diagnostics:** Read runner isolation, Action, Harbor config, registry execution.
**Reset boundary:** Preserve accepted release; rerun failed Actions without deleting history.

## kep-m06-r — Recompute White-Box Gradients

**Lesson:** Positive metric claims are not gradient evidence.
**Enterprise reality:** Experiments loads the declared white-box model and computes gradient/margins itself.
**Attacker method:** Publish model, clean/candidate, and optimizer trace with a server-reproducible initial gradient.
**Why it succeeds:** Local objective improvement transfers to Orion under the distance bound.
**What good looks like:** Exact model/input/trace hashes, matching gradient digest, margin rise, target output change.
**Common stalls:** Self-reported numbers, opaque model, wrong target, over-bound candidate.
**Hint guidance:** Orientation to linear model schema; Mechanism to target-vs-runner-up gradient; Execution to white-box endpoint.
**Defensive discussion:** Protect weights, robust training, gradient masking caveats, independent target testing.
**Diagnostics:** Read server gradient/margins and live target outputs.
**Reset boundary:** Rejected POST transactional; accepted evaluation immutable.

## kep-m06-s — Ground A Retrieval Decision

**Lesson:** Retrieved instruction matters only when it grounds a bounded decision change.
**Enterprise reality:** Victim-owned Tika/OCR/Qdrant/GLM/Preview stack is separate from attacker Cinder stores/edge.
**Attacker method:** Use a neutral query and document whose retrieved chunk is actually cited.
**Why it succeeds:** Release assistant trusts indexed partner context.
**What good looks like:** Victim collection/chunk IDs/scores, cited chunk, baseline-vs-retrieved decision change.
**Common stalls:** Leading query, empty retrieval, invented citation, attacker Qdrant/edge, missing `j/q`.
**Hint guidance:** Orientation to neutral question; Mechanism to chunk marker; Execution to retrieval-review.
**Defensive discussion:** Source trust, retrieval ACLs, citation validation, neutral controls, decision bounds.
**Diagnostics:** Read victim pipeline only; verify attacker services have no matching IDs.
**Reset boundary:** Preserve accepted trace/review; remove unreferenced failed collection/intake.

## kep-m06-t — Register Intelligible Voice Provenance

**Lesson:** Voice generation needs intelligibility, target identity, and unrelated-control separation.
**Enterprise reality:** OpenVoice V2, Whisper, embeddings, player review, and media registry operate on exact WAV bytes.
**Attacker method:** Use the public conference reference and a clear script, listen, then register exact output/provenance.
**Why it succeeds:** Target similarity and margin meet bounds while transcript WER stays low.
**What good looks like:** Revisions/digests, WER ≤.25, target cosine ≥.65, margin ≥.05, exact registry bytes.
**Common stalls:** CPU time, poor reference, altered download, missing `i/p`, registering before acceptance.
**Hint guidance:** Orientation to reference audio; Mechanism to three quality metrics; Execution to exact multipart fields.
**Defensive discussion:** Consent, watermark/provenance, speaker verification, liveness, human review.
**Diagnostics:** Read generation/registry and listen to output; never weaken thresholds manually.
**Reset boundary:** Delete only unregistered generation; accepted media/registry immutable.

## kep-m06-u — Observe A Native Knative Lifecycle

**Lesson:** Serverless provenance spans source, build, image, domain, policy, TLS, revision, and autoscaling.
**Enterprise reality:** Forced participant publisher applies Knative/DomainMapping/per-service NetworkPolicy and journals observations.
**Attacker method:** Rootless build, digest push, q-bound deploy, n-bound lifecycle.
**Why it succeeds:** Actual first request, zero replicas, and cold start are observed against the same revision/certificate.
**What good looks like:** Participant owner, exact parents, source/image/revision/domain/fingerprint, ordered timestamps/digests.
**Common stalls:** Docker commands, missing OCI label, wrong parent hash, arbitrary service policy, wildcard bootstrap cert, no zero scale.
**Hint guidance:** Orientation to SERVERLESS-PUBLISH; Mechanism to two-phase deploy/lifecycle; Execution to exact forced command.
**Defensive discussion:** Namespace RBAC, admission, egress limits, digest pinning, cert continuity, autoscale telemetry.
**Diagnostics:** Read KService/DomainMapping/NetworkPolicy and public lifecycle journal.
**Reset boundary:** Delete failed deployment; publisher refuses accepted service deletion.

## kep-m06-v — Validate A LiteLLM Staging Front

**Lesson:** A relay is trustworthy only when source, image, config, route, signer, artifacts, ownership and upstream use form one chain.
**Enterprise reality:** Participant LiteLLM runs on Knative over shared GLM; Releases verifies committed key and live edge usage.
**Attacker method:** Expose only `glm-5.2`, separate route/upstream credentials, sign a manifest with committed key.
**Why it succeeds:** Registry checks exact `n/u/q` records, signature, bytes, live route, and fresh provider request.
**What good looks like:** One immutable staging record with commit/image/route/artifact digests/provider/edge IDs.
**Common stalls:** Custom relay, arbitrary public key URL, alternate lifecycle record, stale usage, mismatched domain/image.
**Hint guidance:** Orientation to LiteLLM config; Mechanism to committed key and three-way chain; Execution to staging-releases.
**Defensive discussion:** Service identity, signed provenance, config policy, upstream credential isolation, continuous verification.
**Diagnostics:** Read Forgejo/Harbor/K8s/TLS/route/edge/release records read-only.
**Reset boundary:** Failed POST transactional; preserve accepted staging and every ancestor.
