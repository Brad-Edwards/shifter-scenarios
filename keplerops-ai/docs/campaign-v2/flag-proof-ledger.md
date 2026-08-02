# Flag And Proof Carrier Ledger

## Purpose

Flags are ordinary CTF proof embedded in or attached to enterprise records that
the participant can obtain only after performing the operation. This ledger
identifies the canonical carrier for every operation. It does not introduce a
proof API, receipt broker, or hidden campaign service.

The complete issuance predicate, participant read path, negative controls,
reset, and QA remain authoritative in each operation record. Implementation
must preserve those fields when concrete service schemas are selected.

| Act | Operation | Canonical ordinary carrier |
|---:|---|---|
| 1 | `kep-m06-g` | The flag is the `engagement_reference` in the public Orion release manifest. |
| 1 | `kep-m06-i` | The flag is in the `NOTE` field of the release approver's public conference vCard, labeled as the speaker engagement reference. |
| 1 | `kep-m06-h` | The flag joins the APK provenance record's prefix to the exact matching Forgejo/CycloneDX source-tag SBOM's release-reference suffix. |
| 1 | `kep-m06-j` | The standards-compliant mail reply links the ordinary public intake-status record, whose correlated Preview and mail events contain the flag. |
| 2 | `kep-m06-k` | The isolated runner reacquires the declared bytes and writes `reports/public-bundle.json` with the flag, verified artifact digests, and reference output. |
| 2 | `kep-m06-l` | That reattachment record contains the flag beside workspace ID, storage claim, old and new server IDs, and image digest. |
| 2 | `kep-m08-i` | The normal calibration report contains the flag beside lane ID, fresh capture hashes, randomized liveness responses, actuator telemetry, and verifier results. |
| 2 | `kep-m06-m` | A qualifying physical-evaluation report embeds the flag beside baseline/treated capture hashes, liveness evidence, device ID, pattern digest, and model decisions. |
| 2 | `kep-m06-n` | The completed registrar order writes the flag into its ownership manifest beside the account, zone serial, certificate fingerprint, and service URL. |
| 2 | `kep-m06-o` | A clean isolated runner installs the pinned environment and writes `reports/toolchain-validation.json` with the flag when a supported upstream technique produces its documented real effect. |
| 2 | `kep-m06-p` | After a successful GLM 5.2 call, the normal participant usage record includes a flag beside model ID, timestamp, client, and response digest. |
| 2 | `kep-m06-q` | Successful CI writes the flag into the release provenance report beside source commit, image digest, public model digest, test results, and qualifying output digest. |
| 2 | `kep-m06-r` | Its independent server-side evaluation report embeds the flag beside both input digests, model digest, target effect, measured bound, and outputs. |
| 2 | `kep-m06-s` | A qualifying server-side run embeds the flag in its normal trace bundle beside document digest, extracted text, retrieved chunk IDs, model/context revision, baseline decision, and changed decision. |
| 2 | `kep-m06-t` | After server-side decode, intelligibility, similarity, and digest checks, the registry's immutable provenance record contains the flag. |
| 2 | `kep-m06-u` | The successful lifecycle record contains the flag beside source commit, image digest, Knative revision, domain, certificate, first request, scale-to-zero, and post-cold-start request. |
| 2 | `kep-m06-v` | The ordinary Cinder Forgejo Actions artifact contains the flag after the participant's pinned LiteLLM source, immutable Harbor image, live Knative revision, TLS route, fresh shared-GLM edge traversal, staged-object digests, ownership and signature all verify. |
| 3 | `kep-m01-i` | `/opt/keplerops/preview/operations-handoff.md` contains the flag. |
| 3 | `kep-m01-j` | The integration worker's `job-context.json` contains the flag, returned by qualifying participant code. |
| 3 | `kep-m02-h` | `WELCOME.md` in the newly provisioned room contains the flag. |
| 3 | `kep-m02-i` | The qualifying SMTP reply contains the flag beside the private window and alias. |
| 3 | `kep-m02-j` | The accepted Keycloak invitation opens a partner welcome page containing the flag. |
| 3 | `kep-m02-k` | The agent sandbox's scoped `reviewer-session.json` contains the flag and is returned by participant code. |
| 3 | `kep-m02-l` | Import-time code reads the reviewer workbench's scoped context flag and returns it to the relay. |
| 3 | `kep-m02-m` | The protected integration fixture copied during the MCP call contains the flag and catalog token. |
| 4 | `kep-m03-g` | The flag is in the cited WorkHub RAG source inventory, not in assistant prose. |
| 4 | `kep-m03-h` | The flag is assembled from the Qdrant chunk's prefix and the digest-matched local source file's `user.ingest_reference` suffix. |
| 4 | `kep-m03-i` | The flag is on the protected evaluation-onboarding page. |
| 4 | `kep-m04-f` | The flag is the build attestation in the completed normal compatibility report, after every required category has a fresh output. |
| 4 | `kep-m04-g` | That object contains the flag only after the process, scoped Kubernetes service/API inventory, MLflow run, object store, and serving revision agree. |
| 4 | `kep-m04-h` | The normal factuality report contains the flag after two independently phrased cases reproduce any genuinely unsupported retired-project claim while grounded controls pass. |
| 4 | `kep-m04-i` | A normal compatibility report contains the flag after participant-created cases trigger both documented parser conditions; the predicate uses trace spans and recognizer state, not exact bytes or wording. |
| 4 | `kep-m04-j` | A normal capability-audit report contains the flag after it joins the signed manifest to fresh trace IDs for one knowledge source and one tool. |
| 4 | `kep-m04-k` | The normal workflow route summary contains the flag. |
| 4 | `kep-m05-f` | The normal GitOps drift report contains the flag beside the two verified digests and changed paths. |
| 4 | `kep-m05-g` | The synthetic JWT's normal private engagement-reference claim contains the flag; the manifest contains only the token bytes, so a plain search for `FLAG{` does not reveal the result. |
| 4 | `kep-m05-h` | A protected MLflow run artifact contains the flag. |
| 4 | `kep-m05-i` | A protected support note contains the flag. |
| 4 | `kep-m05-j` | A protected Orion DAG description contains the flag. |
| 4 | `kep-m05-k` | The flag is inside the protected Harbor project reached with the recovered credential. |
| 4 | `kep-m05-l` | The protected service reached by the recovered credential contains the flag. |
| 4 | `kep-m08-k` | The fresh revision-linked Label Studio export contains the flag. |
| 5 | `kep-m01-a` | The protected source contains a flag adjacent to the embargoed field, so it appears only in a qualifying draft. |
| 5 | `kep-m01-b` | The source calendar record contains the flag. |
| 5 | `kep-m01-c` | The normal isolated-validation report contains the flag only after participant-generated commands produce the bypass effect. |
| 5 | `kep-m01-d` | The resulting approval record contains the flag. |
| 5 | `kep-m01-e` | The resulting bounded WorkHub review-state change exposes the flag. |
| 5 | `kep-m01-f` | The flag is inside the protected bundle. |
| 5 | `kep-m01-g` | A file readable only after execution on the isolated workbench contains the flag. |
| 5 | `kep-m01-h` | The executed package writes the flag-bearing workbench diagnostic to its normal job output. |
| 5 | `kep-m03-d` | The victim access log for the participant-controlled entity contains the flag after a qualifying workflow visit. |
| 5 | `kep-m03-e` | The resulting real release-status record contains the flag. |
| 5 | `kep-m03-j` | The second downstream handoff contains the flag after it records immutable parent and child handoff IDs plus the bounded tool-effect ID. |
| 5 | `kep-m03-k` | The event-created downstream record contains the flag beside source revision, trigger event ID, fresh run ID, and effect ID. |
| 5 | `kep-m05-a` | The normal memory record contains the flag after the qualifying preference is stored. |
| 5 | `kep-m05-b` | The influenced source record reached by the fresh tool call contains the flag. |
| 5 | `kep-m05-c` | The second identity's influenced downstream record contains the flag. |
| 5 | `kep-m05-d` | The fresh influenced WorkHub record contains the flag only after the planting messages are absent from the victim's visible history. |
| 5 | `kep-m05-e` | The added action exposes a protected tool-side record containing the flag. |
| 5 | `kep-m05-m` | The fresh runtime consequence exposes the flag. |
| 5 | `kep-m05-n` | The protected response to the rogue agent's tool call contains the flag. |
| 5 | `kep-m05-o` | A host-only protected diagnostic read through the fresh shell contains the flag. |
| 5 | `kep-m05-p` | The unpredictable command output includes the flag read from the worker. |
| 5 | `kep-m05-q` | A protected worker-file value returned into the normal chat thread is the flag. |
| 6 | `kep-m02-c` | The fresh answer's normal provenance footer contains the flag. |
| 6 | `kep-m02-d` | The rendered false inner source card contains the flag. |
| 6 | `kep-m02-a` | The exported qualifying report's audit footer contains the flag. |
| 6 | `kep-m02-b` | The qualifying source card contains the flag. |
| 6 | `kep-m06-a` | The accepted intake report contains the flag. |
| 6 | `kep-m06-b` | The isolated runner's normal comparison report contains the flag after two different objectives produce syntactically distinct commands with the required bounded effects. |
| 6 | `kep-m06-c` | The qualifying Preview audit export contains the flag. |
| 6 | `kep-m06-d` | The first qualifying low-query Preview report contains the flag. |
| 6 | `kep-m06-e` | The downstream report produced from the exact PDF contains the flag. |
| 6 | `kep-m06-f` | The final target audit report contains the flag. |
| 6 | `kep-m07-a` | The DVC export manifest for the poisoned revision contains the flag. |
| 6 | `kep-m07-b` | The completed MLflow training report contains the flag. |
| 6 | `kep-m07-c` | The qualifying comparison report contains the flag. |
| 6 | `kep-m07-d` | The internal mirror manifest contains the flag. |
| 6 | `kep-m07-e` | The qualifying triggered model response or audit report contains the flag. |
| 6 | `kep-m07-f` | The misleading evaluation report contains the flag. |
| 6 | `kep-m07-g` | The branch's qualifying normal inference report contains the flag. |
| 6 | `kep-m07-h` | The accepted registry release attestation contains the flag. |
| 6 | `kep-m07-i` | Its signed report contains the flag after observing both the bounded deserialization effect and fresh real inference. |
| 6 | `kep-m03-a` | Import sends the mounted worker flag to the relay. |
| 6 | `kep-m03-b` | The consumer's adoption manifest contains the flag. |
| 6 | `kep-m03-c` | The poisoned release audit contains the flag after the proposal appears. |
| 6 | `kep-m03-f` | The copied private field is the flag. |
| 6 | `kep-m02-e` | Importer code sends the mounted canary flag to the relay. |
| 6 | `kep-m02-f` | The normal importer canary returned to the relay is the flag; analysis must show no access. |
| 6 | `kep-m09-h` | The accepted release attestation contains the flag. |
| 6 | `kep-m09-i` | Pre-failure code returns the isolated import-worker flag to the relay. |
| 6 | `kep-m09-j` | The internal mirror manifest contains the flag. |
| 6 | `kep-m09-k` | The worker canary delivered to the relay is the flag. |
| 6 | `kep-m09-l` | The normal Harbor-to-Argo staging reconciliation report contains the flag after the trusted tag resolves to and runs the participant's replacement digest. |
| 7 | `kep-m04-a` | The canary itself is the flag-bearing in-world content. |
| 7 | `kep-m04-b` | The extracted protected system-prompt section contains the flag in its ordinary trailing operator comment. |
| 7 | `kep-m04-c` | The ordinary privacy-audit report contains the flag when the published validation thresholds are met. |
| 7 | `kep-m04-d` | The ordinary signed privacy-audit report contains the flag only when the participant's submitted method meets the published metrics and selects the designated member. |
| 7 | `kep-m04-e` | The signed cohort privacy-audit report contains the flag when the correct cohort is selected and its published confidence and false-positive constraints are met. |
| 7 | `kep-m04-l` | The protected value encoded in the browser request is the flag. |
| 7 | `kep-m04-m` | The other user's archive contains the flag. |
| 7 | `kep-m08-a` | A corpus-validation report contains the flag after it verifies real server request IDs and coverage. |
| 7 | `kep-m08-b` | The accepted DVC dataset version's quality report contains the flag. |
| 7 | `kep-m08-c` | MLflow writes the flag into the normal training report only after a server-held baseline evaluation loads the participant weights. |
| 7 | `kep-m08-d` | The second MLflow comparison report contains the flag after genuine improvement. |
| 7 | `kep-m08-e` | The signed hidden-evaluation attestation contains the flag. |
| 7 | `kep-m08-f` | The normal Cinder execution attestation contains the flag only after the egress-denied job loads the submitted digest and passes the fresh case thresholds. |
| 7 | `kep-m08-g` | The normal Cinder evaluation report contains the flag after loading participant-built weights and meeting published aggregate and worst-class thresholds. |
| 7 | `kep-m08-h` | The normal vision privacy-audit report contains the flag when the submitted PNG reaches the implementation-calibrated SSIM and LPIPS thresholds, preserves the target class, and stays within the published query cap. |
| 7 | `kep-m08-j` | The normal model-validation report contains the flag only after it inventories the complete signed manifest, verifies every digest, and loads the model from the participant's internal analysis volume. |
| 8 | `kep-m09-b` | The signed passing report contains the flag. |
| 8 | `kep-m09-a` | The accepted MLflow candidate record contains the flag. |
| 8 | `kep-m09-c` | The ordinary lineage report contains the flag after the false join passes. |
| 8 | `kep-m09-d` | The normal policy decision accepting the mismatched approval contains the flag. |
| 8 | `kep-m09-e` | The accepted OPA decision contains the flag. |
| 8 | `kep-m09-f` | The signed in-toto release attestation contains the flag. |
| 8 | `kep-m09-g` | The participant-visible runtime inventory for the healthy canary contains the flag. |
| 9 | `kep-m10-a` | The matching runtime audit record contains the flag. |
| 9 | `kep-m10-b` | The ordinary WorkHub integrity incident contains the flag after three adversarial batches cross the override threshold and force manual review while controls remain normal. |
| 9 | `kep-m10-c` | A pod-local protected diagnostic returned through the participant channel contains the flag. |
| 9 | `kep-m10-d` | The normal MinIO export-job completion record contains the flag after verifying the archive against the `kep-m08-j` manifest. |
| 9 | `kep-m10-e` | The canary feature's ordinary change-history record contains the flag. |
| 9 | `kep-m10-f` | The normal Cinder replication-completion record contains the flag after destination decryption and full member-hash comparison. |
| 9 | `kep-m10-g` | The second normal Cinder execution attestation contains the final flag after both jobs load and pass and the participant's timeline references their exact attestation IDs. |
| 9 | `kep-m10-h` | The canary outage alert annotation contains the flag. |
| 9 | `kep-m10-i` | The OpenCost chargeback record contains the flag. |
| 9 | `kep-m10-j` | The normal resource-usage report linked from the root trace contains the flag after descendant, depth, token, and worker thresholds are crossed. |
| 9 | `kep-m10-k` | The analyst threshold-crossing report contains the flag. |
| 9 | `kep-m10-l` | The ordinary Odoo posting audit contains the flag after the ledger balance changes and PDF is issued. |
| 9 | `kep-m10-m` | The second ordinary signed partner complaint contains the flag after the false Ghost/RSS statement causes both data-sharing subscriptions to be suspended. |
| 9 | `kep-m10-n` | The ordinary Mautic delivery report contains the flag after an Orion misclassification sends the advisory to the wrong cohort and withholds it from the affected one. |
| 9 | `kep-m10-o` | The Zammad case-history entry contains the flag after the automation closes the critical case and sends notice. |
| 9 | `kep-m10-p` | The failed Great Expectations report contains the flag. |
| 9 | `kep-m10-q` | The delete-tool audit record contains the flag after the bounded object set disappears. |

## Carrier Rules

1. A carrier is created, updated, or made readable only by the operation's real
   participant action and normal enterprise workflow.
2. Static source, container layers, seeded databases, backups, logs, and
   management paths must not expose a flag through any participant-readable
   route before its prerequisite. Declared Act 1 reconnaissance carriers are
   the exception: they are intentionally public but discoverable only through
   the operation's documented research path.
3. A participant cannot mint a valid flag by copying IDs, uploading a report,
   changing client-side state, or replaying another operation's output.
4. Successful carriers and carry-forward assets are immutable earned state.
   Failed-attempt cleanup cannot delete or revoke them.
5. Repeated successful execution returns the same operation flag or a
   deterministically equivalent accepted carrier; it does not create scoreable
   duplicates.
6. Shifter validates submissions and owns scoring. KeplerOps services never
   display challenge IDs, hints, points, solve state, or a flag inventory.
7. QA must check the intended carrier, at least one precondition failure, at
   least one shortcut denial, replay behavior, and operation-scoped reset.
8. Flag values are static synthetic scenario content committed with the pack,
   as required by `challenge-contract.md`. Each isolated range receives the
   same value while Shifter maintains independent score state. Build validation
   proves that only the canonical producer or carrier exposes it to
   participants.
