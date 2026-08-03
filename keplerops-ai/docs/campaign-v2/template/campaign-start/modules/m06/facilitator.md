# m06 Facilitator Guide

Use read-only service records for diagnosis. Never supply an undiscovered
hostname, credential, predecessor locator, accepted reference, or management
identity. A record is accepted only by its owning system after the participant
action; staff do not create, edit, copy, or award one manually.

Each note states the teaching intent, the enterprise behavior that keeps the
operation realistic, causal success criteria, diagnosis, three escalating hint
tiers, read-only staff observations, and the smallest valid recovery. Give one
tier at a time. Never skip an undiscovered predecessor, hostname, credential,
or record locator. A broken participant surface is a defect, not a reason to
complete an operation from observability.

## kep-m06-a — Preserve Meaning Across Intake

**Intent:** Evasion can preserve operational semantics while changing a classifier decision.
**Realism:** Partner Intake owns exact uploads, Preview decisions, typed dry-run instructions, and effects.
**Attacker method:** Produce distinct held/accepted bytes with one bounded instruction; valid document tools are alternatives.
**Why it succeeds:** Classification is weaker than the downstream typed instruction path; the review joins both.
**What good looks like:** Two intake IDs, different hashes, same typed fields, held→accepted, one dry-run effect in three minutes.
**Diagnosis:** Missing `m04-f/q`, reusing bytes, changing fields, or asking staff to upload.
**Tier 1 - Orientation:** Ask the team to compare the held intake's reason codes with its accepted attempts.
**Tier 2 - Mechanism:** Point out that action, target, and `dry-run` must remain identical while representation changes.
**Tier 3 - Execution:** Name `acceptance-review` and require the held baseline ID beside the accepted intake and exact lineage.
**Defensive discussion:** Canonicalize, compare semantics, isolate actions, and require approval for changed representations.
**Diagnostics:** Read intake/review/fixture records and Preview IDs only.
**Recovery:** Delete unreferenced attempts; preserve accepted review, effect, bytes, and parents.

## kep-m06-b — Cross The Command Boundary

**Intent:** A reusable prompt template can turn model output into varied executable effects.
**Realism:** Orion Developer calls GLM; the read-only bridge parses an allowlisted command object without a shell.
**Attacker method:** Reuse one template for two objectives that yield distinct commands/effects.
**Why it succeeds:** Template instructions cross from prose into a constrained but real executor.
**What good looks like:** One template digest, two provider-bound threads/jobs, distinct commands and output hashes.
**Diagnosis:** Different templates, duplicate effects, malformed JSON, forbidden paths, absent parents.
**Tier 1 - Orientation:** Direct the team to Developer's output schema and bridge allowlist.
**Tier 2 - Mechanism:** Explain that both objectives must render from byte-identical template text.
**Tier 3 - Execution:** Suggest two small read-only fixture goals and tell them to execute both returned thread IDs through `/v1/jobs`.
**Defensive discussion:** Treat generated commands as untrusted, minimize tools, validate intent, sandbox, and audit.
**Diagnostics:** Read thread/job/corpus records and GLM usage joins.
**Recovery:** Clear threads/jobs only before corpus acceptance; preserve accepted corpus.

## kep-m06-c — Optimize Through Preview

**Intent:** Bounded query access can steer a black-box model.
**Realism:** Preview writes immutable, ordered input/output audits.
**Attacker method:** Submit a complete three-or-more-step series with increasing target score inside the distance bound.
**Why it succeeds:** Output probabilities expose an optimization signal.
**What good looks like:** All experiment audit IDs in native order, clean first, target candidate last.
**Diagnosis:** Cherry-picking IDs, reordering, two inputs, or exceeding the bound.
**Tier 1 - Orientation:** Point to Preview's experiment header and probability vector.
**Tier 2 - Mechanism:** Ask the team to move one bounded feature at a time and watch the chosen target score.
**Tier 3 - Execution:** Require at least three unique inputs and every native query ID in execution order at `preview-experiments`.
**Defensive discussion:** Rate limits, coarse outputs, anomaly detection, and query-budget tradeoffs.
**Diagnostics:** Read Preview audit files and experiment export.
**Recovery:** Failed request is transactional; preserve accepted audits/export.

## kep-m06-d — Transfer From An Executed Proxy

**Intent:** An acquired public bundle can support low-query transfer.
**Realism:** Experiments loads the proxy, recomputes gradients/margins, then joins live Preview queries.
**Attacker method:** Train the documented linear proxy, optimize locally, and spend at most eight target queries.
**Why it succeeds:** Proxy and target share useful decision features.
**What good looks like:** Exact proxy/trace/candidate hashes, matching server gradient, rising proxy margin, target label.
**Diagnosis:** Opaque model, claimed training count, wrong gradient digest, too many target calls.
**Tier 1 - Orientation:** Return the team to the public bundle's preprocessing and labels.
**Tier 2 - Mechanism:** Explain target-versus-runner-up margin optimization and the eight-query target budget.
**Tier 3 - Execution:** Name the executable linear JSON fields and require the trace's initial gradient hash to match server recomputation.
**Defensive discussion:** Limit artifact disclosure, diversify models, monitor transfer probes, retain calibration value.
**Diagnostics:** Read proxy execution fields and Preview audits.
**Recovery:** Preserve accepted export/model/trace; rejected POST leaves no record.

## kep-m06-e — Separate Human And Machine Views

**Intent:** A PDF can render benignly while retaining machine-consumed behavior.
**Realism:** Partner Intake uses Poppler, Tika, OCR, Qdrant, GLM, and Preview on exact bytes.
**Attacker method:** Hide a typed instruction from visible extraction while retaining it in machine extraction.
**Why it succeeds:** Rendering and parser pipelines disagree, and downstream automation trusts the latter.
**What good looks like:** Page rendering, different visible/machine hashes, hidden typed fields, changed decision.
**Diagnosis:** Visible payload, too little human content, identical extraction, absent `a/s`.
**Tier 1 - Orientation:** Ask for a side-by-side rendered page, `pdftotext`, Tika, and OCR comparison.
**Tier 2 - Mechanism:** Explain that the typed instruction must exist only in the machine-consumed view.
**Tier 3 - Execution:** Name `rendering-review` after a fresh retrieved decision changes and both parents are present.
**Defensive discussion:** Multi-view comparison, sanitization, provenance, and human approval.
**Diagnostics:** Read intake text hashes, pipeline trace, and rendering review.
**Recovery:** Remove only unreferenced failed intake; preserve accepted PDF/review.

## kep-m06-f — Transfer Through The Full Document Path

**Intent:** A proxy representation matters only if the deployment pipeline reproduces target effect.
**Realism:** Exact PDF bytes flow through extraction, retrieval, assistant, and Preview.
**Attacker method:** Bind the local proxy candidate to one extraction representation and trigger a fresh target decision.
**Why it succeeds:** Deployment transformation preserves the adversarial representation.
**What good looks like:** Matching proxy/extraction digest, complete stage lineage, fresh Preview ID and target decision.
**Diagnosis:** Unrelated proxy bytes, stale Preview event, missing `d/e`, or participant-authored result JSON.
**Tier 1 - Orientation:** Point to the intake pipeline trace and its stage hashes.
**Tier 2 - Mechanism:** Ask which extraction-stage digest equals the proxy candidate digest.
**Tier 3 - Execution:** Tell the team to create the intake with exact proxy candidate/model HTTPS URLs, then request `target-review` after a fresh Preview ID appears.
**Defensive discussion:** Test transformed inputs, stage-by-stage provenance, and release gates.
**Diagnostics:** Read intake trace/review and Preview audit.
**Recovery:** Preserve accepted lineage; clear only unreferenced attempt directory.

## kep-m06-g — Read The Release Record

**Intent:** Public research and release records leak operationally useful lineage.
**Realism:** KeplerOps publishes a normal research index and signed release manifest.
**Attacker method:** Follow public links and compare source/model/release fields.
**Why it succeeds:** The manifest intentionally carries the engagement reference.
**What good looks like:** Consistent paper, preprint, manifest, and public Forgejo tag.
**Diagnosis:** Searching only the home page or ignoring downloaded JSON.
**Tier 1 - Orientation:** Direct the team from the public home page to Research.
**Tier 2 - Mechanism:** Ask them to compare stable release/source/model identifiers across paper and preprint.
**Tier 3 - Execution:** Name the downloadable release manifest and tell them to inspect its complete JSON and verify its Forgejo tag.
**Defensive discussion:** Minimize public metadata while retaining supply-chain transparency.
**Diagnostics:** Read public HTTP bytes only.
**Recovery:** Immutable public state; no local reset.

## kep-m06-h — Trust A Signed Mobile Repository

**Intent:** Mobile provenance spans repository signature, APK, source, and SBOM.
**Realism:** A functional F-Droid repository distributes the workflow-built Android package.
**Attacker method:** Verify the signed index, install the package, and join provenance prefix to SBOM suffix.
**Why it succeeds:** Separate provenance surfaces disclose complementary reference parts.
**What good looks like:** Valid JAR signature, installable app, exact index/APK/SBOM digests.
**Diagnosis:** Treating HTML as F-Droid, skipping package retrieval, passing a fingerprint as a third `repo add` argument, or assuming `fdroidcl` verifies the JAR signature.
**Tier 1 - Orientation:** Point to the repository URL and published signing SHA-256 on the client page.
**Tier 2 - Mechanism:** Explain that `fdroidcl` v0.8.1 relies on HTTPS, so the certificate fingerprint and signed JAR must be checked separately.
**Tier 3 - Execution:** Give `fdroidcl repo add keplerops <URL>` with exactly two arguments, identify `~/.config/fdroidcl/config.toml`, then direct them to the APK provenance and digest-bound SBOM property.
**Defensive discussion:** Reproducible builds, repository signing, transparency, and metadata minimization.
**Diagnostics:** Check `fdroidcl version`, TOML `id/url/enabled`, certificate SHA-256, `jarsigner -verify -strict`, index/APK hash, embedded provenance, SBOM hash, and source tag. `repo: wrong amount of arguments` means the obsolete three-argument instruction was used.
**Recovery:** Immutable public repository.

## kep-m06-i — Corroborate Identity Independently

**Intent:** Reliable OSINT requires sources with different ownership and protocols.
**Realism:** Independent conference web/DNS/mail and public Forgejo identities corroborate KeplerOps employment.
**Attacker method:** Cross-check conference, partner organization, profiles, DNS/MX, mail, and vCard.
**Why it succeeds:** The outside program record carries a speaker engagement reference.
**What good looks like:** Independent hostname/certificate and five agreeing identity signals.
**Diagnosis:** Using only the KeplerOps people page or old same-site path.
**Tier 1 - Orientation:** Ask which outside conference the KeplerOps biography names.
**Tier 2 - Mechanism:** Require corroboration from a different hostname and at least one non-HTTP protocol.
**Tier 3 - Execution:** Point to the conference vCard and its `NOTE` after DNS, MX, TLS, Forgejo, and partner organization agree.
**Defensive discussion:** Separate personal/public identities and monitor impersonation without erasing legitimate scholarship.
**Diagnostics:** DNS, TLS, Stalwart principal, public Forgejo and static site.
**Recovery:** Immutable public corroboration.

## kep-m06-j — Join Preview, Mail, And Case Management

**Intent:** Cross-channel correlation can reveal a public intake reference.
**Realism:** Stalwart stores SMTP mail; the mail-to-case bridge creates a Zammad ticket; status joins Preview.
**Attacker method:** Use one fresh external reference in benign Preview text and authenticated mail.
**Why it succeeds:** Operational status intentionally correlates exact Message-ID/RFC822 digest and model event.
**What good looks like:** Preview ID, IMAP UID, Message-ID, Zammad ticket/article and stable status record.
**Diagnosis:** Wrong sender/recipient/reference, missing Preview, or expecting a custom SMTP port.
**Tier 1 - Orientation:** Return the team to the external intake address and Preview origin already recovered.
**Tier 2 - Mechanism:** Explain that one fresh reference must appear in both Preview text and the stored RFC822 message.
**Tier 3 - Execution:** Give SMTP submission on port 587 with STARTTLS and the status path `/intake-status/<reference>.json`.
**Defensive discussion:** Reduce public correlation, authenticate status viewers, and preserve case traceability.
**Diagnostics:** Read Stalwart mailbox, Zammad article, Preview audit, status record.
**Recovery:** Preserve accepted mail/ticket/status; retry failed attempt with new reference.

## kep-m06-k — Execute Acquired Public Assets

**Intent:** Artifact presence is weaker than reproducible execution.
**Realism:** Releases reacquires public model/data/agent bytes and runs their declared entrypoint.
**Attacker method:** Bind a successful Forgejo run to one exact public manifest and record all outputs.
**Why it succeeds:** Public release exposes a complete runnable bundle.
**What good looks like:** Three role digests and eight deterministic execution records.
**Diagnosis:** First-line-only prediction, missing runtime asset, failed/unrelated Action, wrong parent mode.
**Tier 1 - Orientation:** Point to the public bundle manifest as the artifact authority.
**Tier 2 - Mechanism:** Ask the team to account for all model, dataset, and agent roles plus the declared entrypoint.
**Tier 3 - Execution:** Require all eight executions and the exact successful Actions provenance at `/v1/public-bundles`.
**Defensive discussion:** Publish least-necessary artifacts, sign manifests, test disclosure consequences.
**Diagnostics:** Read Forgejo run, acquired digests, runner stdout and executions.
**Recovery:** Preserve accepted release; failed CI/reacquisition creates no record.

## kep-m06-l — Prove Kubernetes Workspace Persistence

**Intent:** Notebook persistence depends on server/PVC identity, not a participant-written marker.
**Realism:** JupyterHub KubeSpawner provides per-user PVC and CPU/GPU profiles.
**Attacker method:** Write a probe, stop/start through Hub, and inspect Hub’s Kubernetes observation.
**Why it succeeds:** New pod reattaches the same PVC and exact runtime image.
**What good looks like:** Different pod UIDs, same PVC UID, real image ID, matching server-observed probe hash.
**Diagnosis:** Kernel restart instead of server stop, wrong path, waiting on GPU capacity, local fake ID.
**Tier 1 - Orientation:** Direct the team to stop/start the user server from the Hub control panel.
**Tier 2 - Mechanism:** Explain that pod replacement and PVC continuity are separate observations.
**Tier 3 - Execution:** Give `/home/jovyan/work/.cinder/probe` and the Hub reattachments API; require changed pod UID and unchanged PVC UID.
**Defensive discussion:** Namespace/RBAC isolation, image pinning, encryption, quota, and durable workspace risk.
**Diagnostics:** Read Hub state and K8s pod/PVC only.
**Recovery:** Delete only unaccepted pod; preserve accepted record/PVC.

## kep-m06-m — Exercise A Real Physical Countermeasure

**Intent:** Physical AI evidence needs live device, liveness, witness view, telemetry, and reset.
**Realism:** labgrid reserves an external bench; bench exporter owns raw evidence.
**Attacker method:** Reserve/acquire the declared place and execute randomized actuator/light pattern.
**Why it succeeds:** Current lease/nonces bind dual frames and telemetry to one physical action.
**What good looks like:** Real place, opaque reservation, live nonce markers, safe limits, visible/telemetry deltas, reset.
**Diagnosis:** No bench, stale reservation, uploaded/simulated media, missing witness or reset sample.
**Tier 1 - Orientation:** Offer no operational hint until `labgrid-client places` shows a real active place; then point to reservation/acquisition.
**Tier 2 - Mechanism:** Explain the same current nonce and lease must bind dual live views, telemetry, and reset.
**Tier 3 - Execution:** Direct the team to the proof-ID-bound bench exporter archive and participant verifier; never provide substitute media.
**Defensive discussion:** Hardware roots of trust, anti-replay, safety interlocks, privacy, and throughput.
**Diagnostics:** Read labgrid/exporter and raw evidence verifier; never substitute media.
**Recovery:** Release failed lease; accepted raw archive immutable; absent physical bench remains blocked.

## kep-m06-n — Establish Native Domain Ownership

**Intent:** Service ownership is a chain across identity, DNS, mail, ACME, content, and live TLS.
**Realism:** Keycloak, PowerDNS, Stalwart, Step CA, Caddy, and Registrar each own one link.
**Attacker method:** Complete links separately and present signed ACME POST-as-GET messages for the exact order/certificate.
**Why it succeeds:** Registrar deploys and revalidates the exact order certificate and private-key match.
**What good looks like:** Keycloak ID, zone serial, mail principal, service hash, valid order/cert URLs, matching live fingerprint.
**Diagnosis:** Service before certificate, fake/local account, mismatched key, bootstrap wildcard, stale DNS.
**Tier 1 - Orientation:** Point to the Registrar resource sequence in `START-HERE.md`.
**Tier 2 - Mechanism:** Explain that Keycloak, DNS, mail, service body, ACME order, key/cert, and live TLS must describe one domain.
**Tier 3 - Execution:** Give the `/v1/domains/<id>/...` order and reserve `/ownership-manifest` for the final live verification.
**Defensive discussion:** Domain-control validation, key custody, scoped automation, and continuous revalidation.
**Diagnostics:** Read only linked native records and live DNS/TLS.
**Recovery:** Delete incomplete Keycloak/DNS/mail/domain state; preserve accepted ownership.

## kep-m06-o — Reproduce Upstream Tools

**Intent:** Toolchain integrity requires executing declared versions and images.
**Realism:** Forgejo/Harbor release record pins lockfile, ART and ffmpeg recipes.
**Attacker method:** Commit exact lock and deterministic inputs/outputs, then request registry reproduction.
**Why it succeeds:** Fixed upstream transformations are reproducible byte-for-byte.
**What good looks like:** Commit/image/lock continuity plus matching ART array and ffmpeg output hashes.
**Diagnosis:** Unpinned lock, unrelated image/run, unsupported ffmpeg args, uploaded output only.
**Tier 1 - Orientation:** Point to the upstream ART and ffmpeg recipes and lockfile.
**Tier 2 - Mechanism:** Explain that the registry must execute the declared tools inside the exact image digest and reproduce fixed transforms.
**Tier 3 - Execution:** Name `ci/toolchain-release.yml` and `/v1/toolchain-releases`, including committed recipe paths and server-reacquirable outputs.
**Defensive discussion:** Lock dependencies, provenance images, hermetic tests, and upstream monitoring.
**Diagnostics:** Read source/run/image and server rerun fields.
**Recovery:** Rejected requests transactional; preserve accepted release and `k/l`.

## kep-m06-p — Attribute Shared GLM Use

**Intent:** Shared inference needs per-range/actor/client attribution and response continuity.
**Realism:** Cinder edge separates participant and service credentials over a redundant shared Vertex pool.
**Attacker method:** Use OpenCode for an Orion-grounded request and follow usage/response headers.
**Why it succeeds:** The edge verifies upstream model identity and journals exact request/response digests.
**What good looks like:** Participant credential class, OpenCode client, target grounding, provider ID, response object.
**Diagnosis:** Generic curl, non-Orion prompt, internal service call, wrong upstream model.
**Tier 1 - Orientation:** Direct the team to the preconfigured OpenCode profile and Orion notes.
**Tier 2 - Mechanism:** Ask them to preserve the Cinder usage and provider-request headers from a substantive Orion-grounded request.
**Tier 3 - Execution:** Give the usage and response-object GET sequence and require the response hash to match `response_digest`.
**Defensive discussion:** Short-lived credentials, quotas/fairness, model attestation, isolated caches, privacy.
**Diagnostics:** Read edge journal and shared-pool request ID; do not inspect prompt bodies.
**Recovery:** Usage audit append-only; retry creates a new ID.

## kep-m06-q — Validate A Target Harness

**Intent:** CI provenance must bind executable source, preprocessing, image, and target behavior.
**Realism:** Isolated Forgejo runner uses rootless BuildKit and project-scoped Harbor robot.
**Attacker method:** Commit and execute `ci/validate-orion-harness` with clean/candidate bytes and OCI revision label.
**Why it succeeds:** Registry reruns committed code and target queries rather than trusting CI prose.
**What good looks like:** Successful exact commit, Harbor digest/revision, harness stdout hash, different target outputs.
**Diagnosis:** Repository-local secret assumption, Docker command, mutable tag, absent script/label, unrelated Action.
**Tier 1 - Orientation:** Point to repository-scoped credentials and rootless BuildKit in `START-HERE.md`.
**Tier 2 - Mechanism:** Explain continuity among source commit, OCI revision, image digest, executable harness, and distinct clean/candidate inputs.
**Tier 3 - Execution:** Name `ci/harness-release.yml`, `ci/validate-orion-harness`, the required run schema, and `/v1/harness-releases`.
**Defensive discussion:** Ephemeral builders, no host socket, least-privilege robots, attestations, protected workflows.
**Diagnostics:** Read runner isolation, Action, Harbor config, registry execution.
**Recovery:** Preserve accepted release; rerun failed Actions without deleting history.

## kep-m06-r — Recompute White-Box Gradients

**Intent:** Positive metric claims are not gradient evidence.
**Realism:** Experiments loads the declared white-box model and computes gradient/margins itself.
**Attacker method:** Publish model, clean/candidate, and optimizer trace with a server-reproducible initial gradient.
**Why it succeeds:** Local objective improvement transfers to Orion under the distance bound.
**What good looks like:** Exact model/input/trace hashes, matching gradient digest, margin rise, target output change.
**Diagnosis:** Self-reported numbers, opaque model, wrong target, over-bound candidate.
**Tier 1 - Orientation:** Point to the linear model's vocabulary, labels, weights, and bias.
**Tier 2 - Mechanism:** Explain target-versus-runner-up gradient and margin improvement under the distance bound.
**Tier 3 - Execution:** Require two or more trace steps, exact input hashes, compact-JSON initial-gradient hash, and `/v1/white-box-experiments`.
**Defensive discussion:** Protect weights, robust training, gradient masking caveats, independent target testing.
**Diagnostics:** Read server gradient/margins and live target outputs.
**Recovery:** Rejected POST transactional; accepted evaluation immutable.

## kep-m06-s — Ground A Retrieval Decision

**Intent:** Retrieved instruction matters only when it grounds a bounded decision change.
**Realism:** Victim-owned Tika/OCR/Qdrant/GLM/Preview stack is separate from attacker Cinder stores/edge.
**Attacker method:** Use a neutral query and document whose retrieved chunk is actually cited.
**Why it succeeds:** Release assistant trusts indexed partner context.
**What good looks like:** Victim collection/chunk IDs/scores, cited chunk, baseline-vs-retrieved decision change.
**Diagnosis:** Leading query, empty retrieval, invented citation, attacker Qdrant/edge, missing `j/q`.
**Tier 1 - Orientation:** Ask the team to use a normal release-risk question with no decision word.
**Tier 2 - Mechanism:** Explain that a relevant distinctive chunk must be retrieved and cited before it can influence the decision.
**Tier 3 - Execution:** Name the neutral query control, real `chunk:<id>` citation requirement, and `retrieval-review` route.
**Defensive discussion:** Source trust, retrieval ACLs, citation validation, neutral controls, decision bounds.
**Diagnostics:** Read victim pipeline only; verify attacker services have no matching IDs.
**Recovery:** Preserve accepted trace/review; remove unreferenced failed collection/intake.

## kep-m06-t — Register Intelligible Voice Provenance

**Intent:** Voice generation needs intelligibility, target identity, and unrelated-control separation.
**Realism:** OpenVoice V2, Whisper, embeddings, player review, and media registry operate on exact WAV bytes.
**Attacker method:** Use the public conference reference and a clear script, listen, then register exact output/provenance.
**Why it succeeds:** Target similarity and margin meet bounds while transcript WER stays low.
**What good looks like:** Revisions/digests, WER ≤.25, target cosine ≥.65, margin ≥.05, exact registry bytes.
**Diagnosis:** CPU time, poor reference, altered download, missing `i/p`, registering before acceptance.
**Tier 1 - Orientation:** Return the team to the verified conference recording and role fit.
**Tier 2 - Mechanism:** Explain intelligibility, target similarity, and unrelated-control margin as three independent gates.
**Tier 3 - Execution:** Give the generation/output/provenance/registry order and exact multipart fields; register only the downloaded bytes.
**Defensive discussion:** Consent, watermark/provenance, speaker verification, liveness, human review.
**Diagnostics:** Read generation/registry and listen to output; never weaken thresholds manually.
**Recovery:** Delete only unregistered generation; accepted media/registry immutable.

## kep-m06-u — Observe A Native Knative Lifecycle

**Intent:** Serverless provenance spans source, build, image, domain, policy, TLS, revision, and autoscaling.
**Realism:** Forced participant publisher applies Knative/DomainMapping/per-service NetworkPolicy and journals observations.
**Attacker method:** Rootless build, digest push, q-bound deploy, n-bound lifecycle.
**Why it succeeds:** Actual first request, zero replicas, and cold start are observed against the same revision/certificate.
**What good looks like:** Participant owner, exact parents, source/image/revision/domain/fingerprint, ordered timestamps/digests.
**Diagnosis:** Docker commands, missing OCI label, wrong parent hash, arbitrary service policy, wildcard bootstrap cert, no zero scale.
**Tier 1 - Orientation:** Direct the team to `SERVERLESS-PUBLISH.md` and the normal Forgejo-to-Harbor path.
**Tier 2 - Mechanism:** Explain the two-phase `deploy` then `lifecycle` chain and continuity across commit, digest, domain, parents, and TLS.
**Tier 3 - Execution:** Provide the exact forced-command argument order and tell them to wait for observed zero replicas before cold start.
**Defensive discussion:** Namespace RBAC, admission, egress limits, digest pinning, cert continuity, autoscale telemetry.
**Diagnostics:** Read KService/DomainMapping/NetworkPolicy and public lifecycle journal.
**Recovery:** Delete failed deployment; publisher refuses accepted service deletion.

## kep-m06-v — Validate A LiteLLM Staging Front

**Intent:** A relay is trustworthy only when source, image, config, route, signer, artifacts, ownership and upstream use form one chain.
**Realism:** Participant LiteLLM runs on Knative over shared GLM; Releases verifies committed key and live edge usage.
**Attacker method:** Expose only `glm-5.2`, separate route/upstream credentials, sign a manifest with committed key.
**Why it succeeds:** Registry checks exact `n/u/q` records, signature, bytes, live route, and fresh provider request.
**What good looks like:** One immutable staging record with commit/image/route/artifact digests/provider/edge IDs.
**Diagnosis:** Custom relay, arbitrary public key URL, alternate lifecycle record, stale usage, mismatched domain/image.
**Tier 1 - Orientation:** Point to the committed LiteLLM config and already accepted native records.
**Tier 2 - Mechanism:** Explain the chain from committed key and exact staged objects through route to a fresh attributed upstream request.
**Tier 3 - Execution:** Require only `glm-5.2`, separate route/upstream credentials, `cosign verify-blob`, and the complete `/v1/staging-releases` request.
**Defensive discussion:** Service identity, signed provenance, config policy, upstream credential isolation, continuous verification.
**Diagnostics:** Read Forgejo/Harbor/K8s/TLS/route/edge/release records read-only.
**Recovery:** Failed POST transactional; preserve accepted staging and every ancestor.
