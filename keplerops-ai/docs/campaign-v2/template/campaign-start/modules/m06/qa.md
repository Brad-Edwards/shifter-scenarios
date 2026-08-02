# m06 Participant-Equivalent QA

## Run identity used by every procedure

Before each run record implementation revision `campaign-v2/m06-native-v3`, the
range build ID, SHA-256 of `operations.json` and `integrations.json`, the exact
Forgejo commit, Harbor manifest digest, service-reported image identity, Orion model
SHA-256, GLM upstream identity `openai/zai-org/glm-5-maas`, OpenVoice revision
`74a1d147b17a8c3092dd5430504bd83ef6c7eb23`, OpenVoice model revision
`fd981100305a0e4291f93a9ad169c6d9f7bed54a`, and mutable input digests. Obtain
runtime image IDs only from the assigned Forgejo Actions provenance artifact,
Harbor digest response, and exact Knative/Jupyter native records. A missing or
mutable digest is an infrastructure defect, never a value to infer; host Docker
access is neither available nor part of any procedure.

All commands run in the participant Kali terminal or Cinder Jupyter terminal.
Use only the credentials in `START-HERE.md`, a new UUID from `uuidgen`, and
exact predecessor URLs/digests already earned in-world. After every action save
the HTTP status, response body, relevant headers, UTC start/end, and SHA-256.
Expected API completion is 30 seconds, GLM 90 seconds, document processing 3
minutes, CI 10 minutes, OpenVoice 15 minutes, scale-to-zero 5 minutes, and the
physical lane 15 minutes. Any overrun is `excessive duration`.

For `m04-f`, `m04-i`, and `m04-j`, take the exact signed-report object key from
the accepted Airflow run and use the read-only prior-report identity in
START-HERE to create a 24-hour `https://artifacts.keplerops.lab/...` download
URL. Confirm that direct bucket listing and every non-admitted prefix fail, then
hash the exact bytes downloaded from the URL before placing it in `context`.

## kep-m06-g — Read The Public Orion Release

1. **Operation and revision:** Use the common run identity; public source tag is `v1.0.0`.
2. **Fresh-state preconditions:** None.
3. **Participant surface:** Chromium at `https://keplerops.lab/research/`.
4. **Starting knowledge:** The public KeplerOps home page links the research index.
5. **Concrete actions:** Follow the paper, preprint, and release-manifest links; save `orion-release-manifest.json` and hash it.
6. **Expected observations:** All three agree on release/source/model; manifest download completes within 10 seconds.
7. **Success and flag:** `engagement_reference` in the release manifest is submitted to Shifter.
8. **Negative controls:** The home page alone does not contain the reference; a changed manifest digest is rejected downstream.
9. **Independent verification:** Compare the manifest source tag with public Forgejo.
10. **Replay and reset:** Replay returns identical bytes; public state has no operation reset.
11. **Evidence retained:** URLs, screenshots, manifest and SHA-256.
12. **Defect disposition:** Pass only when all public records agree; otherwise content defect.

## kep-m06-h — Install The Field Client

1. **Operation and revision:** Common identity plus F-Droid signing certificate SHA-256 and APK/SBOM digests.
2. **Fresh-state preconditions:** None.
3. **Participant surface:** Chromium, `fdroidcl`, and APK inspection tools on the Cinder workstation.
4. **Starting knowledge:** `https://keplerops.lab/software/orion-field-review/` publishes the repository URL and fingerprint.
5. **Concrete actions:** Read the repository URL and SHA-256 fingerprint from the public application page. Run `fdroidcl repo add keplerops https://keplerops.lab/software/orion-field-review/repo <fingerprint>`, `fdroidcl update`, `fdroidcl search com.keplerops.orion`, and `fdroidcl download com.keplerops.orion`. Extract `assets/provenance/release.json` from the downloaded APK with `unzip`, download `orion-field-review.cdx.json`, and hash both files.
6. **Expected observations:** The signed repository refresh succeeds, `com.keplerops.orion` version `1.0.0` is discoverable and retrievable, the APK digest appears in the native F-Droid index, and the embedded provenance binds the downloaded SBOM digest within 2 minutes.
7. **Success and flag:** Concatenate the APK provenance prefix with the digest-bound SBOM suffix and submit it.
8. **Negative controls:** Unsigned index, changed APK, changed SBOM, or ordinary HTML link list fails.
9. **Independent verification:** Download `index-v1.jar` and `repo-signing.pem`; `jarsigner -verify -strict index-v1.jar` succeeds and its signer fingerprint matches the published certificate.
10. **Replay and reset:** Refresh returns the same signed version; public repository is immutable.
11. **Evidence retained:** Index JAR/certificate, APK/SBOM, install screenshot, all hashes.
12. **Defect disposition:** Pass only for functional installation; otherwise content or infrastructure defect.

## kep-m06-i — Corroborate Mira Chen

1. **Operation and revision:** Common identity plus conference-site certificate and vCard digests.
2. **Fresh-state preconditions:** None.
3. **Participant surface:** Chromium, DNS lookup, and SMTP TLS probe.
4. **Starting knowledge:** Mira’s KeplerOps people page names an outside conference.
5. **Concrete actions:** Visit `https://orion-open-systems.org/`, follow Mira’s public Forgejo profile and Northstar organization, resolve DNS/MX, download `/speakers/mira-chen.vcf`, and verify `program@orion-open-systems.org` is a deliverable Stalwart address.
6. **Expected observations:** Independent hostname/certificate, public profiles, partner organization, DNS/MX, and vCard all agree within 30 seconds.
7. **Success and flag:** Submit the speaker engagement reference in the vCard NOTE.
8. **Negative controls:** The KeplerOps employee page alone and the old same-site conference path do not qualify.
9. **Independent verification:** SMTP and DNS observations corroborate the web identity.
10. **Replay and reset:** Public records are byte-stable; no reset.
11. **Evidence retained:** DNS/MX output, TLS certificate, profile pages, vCard hash.
12. **Defect disposition:** Missing independent source is a content defect.

## kep-m06-j — Correlate External Intake

1. **Operation and revision:** Common identity plus Preview model digest and Stalwart/Zammad image IDs.
2. **Fresh-state preconditions:** None; use a new `EXT-<random>` reference.
3. **Participant surface:** Orion Preview and authenticated SMTP submission.
4. **Starting knowledge:** START-HERE gives mail identity and `partner-intake@keplerops.lab`.
5. **Concrete actions:** Run `REF="EXT-$(openssl rand -hex 8 | tr a-f A-F)"`; then `jq -n --arg text "Benign Orion intake correlation $REF" '{text:$text}' | curl -fsS -H 'Content-Type: application/json' --data-binary @- https://preview.keplerops.lab/api/analyze`; submit the same reference with `swaks --server mail.keplerops.lab:587 --tls --auth LOGIN --auth-user cinder.field-operator --auth-password Cinder-Field-Operator-Mail-J7p4Vn6s --from cinder.field-operator@cinder.lab --to partner-intake@keplerops.lab --header "Subject: Orion intake $REF" --body "Correlation reference $REF"`; poll `curl -fsS "https://external-intake.keplerops.lab/intake-status/$REF.json"`.
6. **Expected observations:** Stalwart stores an RFC822 UID/Message-ID, Zammad creates a ticket/article, and status joins both to the Preview analysis within 90 seconds.
7. **Success and flag:** Submit the reference in the immutable intake-status record.
8. **Negative controls:** Wrong sender, missing Preview event, different reference, or direct status guess returns 404.
9. **Independent verification:** Reacquire the Zammad article and compare Message-ID and RFC822 digest.
10. **Replay and reset:** GET is byte-stable; failed mail uses a new reference and accepted mail/ticket is preserved.
11. **Evidence retained:** SMTP transcript, Preview ID, IMAP UID, Zammad IDs, status JSON.
12. **Defect disposition:** A custom SMTP listener or absent ticket is an infrastructure defect.

## kep-m06-k — Execute The Public Bundle

1. **Operation and revision:** Common identity plus Forgejo commit/run and every public artifact digest.
2. **Fresh-state preconditions:** Exactly one of `g` or `h` as a native parent.
3. **Participant surface:** Forgejo Actions, public Orion assets, Releases API, Jupyter.
4. **Starting knowledge:** Public bundle manifest and parent record.
5. **Concrete actions:** Commit `ci/public-bundle-release.yml`, upload `kep-m06-k-provenance/provenance.json`, run it, then use the copyable `kep-m06-k` request below.
6. **Expected observations:** Registry reacquires model/data/agent bytes, executes `run-orion-kit.py`, and returns three role digests plus eight ID/label executions within 3 minutes.
7. **Success and flag:** Submit the release record’s engagement reference.
8. **Negative controls:** Missing role, changed digest, failed/unrelated Action, non-executable agent, or seven results fails.
9. **Independent verification:** Run the acquired bundle in Jupyter and compare all eight outputs.
10. **Replay and reset:** New attempt creates a new immutable release; failed CI has no release record.
11. **Evidence retained:** Commit/run, manifest, role map, eight outputs, release ID.
12. **Defect disposition:** Execution mismatch is a content defect; unavailable model runtime is infrastructure.

## kep-m06-l — Reattach A Persistent Workspace

1. **Operation and revision:** Common identity plus JupyterHub image ID, pod UIDs, and PVC UID.
2. **Fresh-state preconditions:** None.
3. **Participant surface:** `https://notebook.cinder.lab/` Hub control panel and Jupyter terminal.
4. **Starting knowledge:** Jupyter credentials and `.cinder/probe` path in START-HERE.
5. **Concrete actions:** Start CPU profile; in its terminal run `install -d ~/.cinder && uuidgen | tee ~/.cinder/probe && sha256sum ~/.cinder/probe`; stop and restart the server in the Hub, then run `curl -fsS -H 'Authorization: Bearer Cinder-Checkpoint-Reader-W9s2Kd7m' https://notebook.cinder.lab/hub/api/cinder/reattachments | tee reattachments.json`, take its exact `record_id`, and GET `/hub/api/cinder/reattachments/<record_id>`.
6. **Expected observations:** New pod UID, unchanged PVC UID, digest-pinned image ID, and server-observed matching probe digest within 5 minutes.
7. **Success and flag:** Submit the reattachment record reference.
8. **Negative controls:** Editing a local server-ID file, using another PVC, or unchanged pod UID does not produce a record.
9. **Independent verification:** Hub’s Kubernetes API observation—not notebook JSON—contains pod/PVC/image identities.
10. **Replay and reset:** Accepted record/PVC persist; reset may delete only an unaccepted active pod.
11. **Evidence retained:** Hub screenshots, pod/PVC/image IDs, probe hash, record URL.
12. **Defect disposition:** Missing KubeSpawner/PVC/GPU profiles is infrastructure defect.

## kep-m06-p — Use The Attributed GLM Edge

1. **Operation and revision:** Common identity plus returned upstream model/provider request and response-object digest.
2. **Fresh-state preconditions:** None.
3. **Participant surface:** Preconfigured OpenCode.
4. **Starting knowledge:** START-HERE describes the scoped GLM model.
5. **Concrete actions:** Ask an Orion-grounded question in OpenCode; save both Cinder headers; GET usage and response-object paths with the participant bearer.
6. **Expected observations:** Upstream attests the admitted GLM model; usage actor/client/range/request/response IDs join within 90 seconds.
7. **Success and flag:** Submit the usage record reference.
8. **Negative controls:** Empty/non-Orion call, direct curl without OpenCode header, service credential, or forged model name has no reference.
9. **Independent verification:** Hash response object and compare usage `response_digest`.
10. **Replay and reset:** Audit is append-only; retry creates a new usage ID.
11. **Evidence retained:** OpenCode transcript, headers, usage/response JSON and hashes.
12. **Defect disposition:** Wrong model identity or cross-range actor is infrastructure defect.

## kep-m06-q — Release The Orion Harness

1. **Operation and revision:** Common identity plus source commit, Action run, Harbor digest/config revision, and harness digest.
2. **Fresh-state preconditions:** Exact `k` and `p` parents.
3. **Participant surface:** Forgejo, rootless BuildKit, Harbor, Releases API.
4. **Starting knowledge:** SERVERLESS-PUBLISH and predecessor records.
5. **Concrete actions:** Commit `ci/harness-release.yml`, `ci/validate-orion-harness`, clean/candidate manifest, and OCI revision label; upload `kep-m06-q-provenance/provenance.json`, run Actions, push the digest, then use the copyable `kep-m06-q` request below.
6. **Expected observations:** Registry executes the committed harness with `ORION_MODEL_URL` plus exact input paths, verifies its `cinder.orion-harness-run/v1` JSON against independent Orion queries, and joins commit to Harbor config within 3 minutes.
7. **Success and flag:** Submit the harness release record reference.
8. **Negative controls:** Uploaded log, absent script, unrelated Action, mutable tag, wrong OCI revision, preprocessing drift, or equal outputs fails.
9. **Independent verification:** Registry clean/candidate outputs reproduce target effect.
10. **Replay and reset:** Accepted commit/digest persists; failed Actions can rerun without deletion.
11. **Evidence retained:** Workflow, logs, commit, image digest/config, harness stdout hash, record.
12. **Defect disposition:** BuildKit/Harbor fault is infrastructure; harness mismatch is content.

## Compound native operations

The remaining operations use the same twelve fields; the table supplies their
exact deltas. “Record” always means the owning-service immutable JSON reached
at its returned URL, never a participant-authored report.

| Operation | Fresh-state preconditions | Concrete participant actions | Expected observation and native checkpoint | Required negative control / independent verification | Replay, retained evidence, disposition |
|---|---|---|---|---|---|
| `kep-m06-a` | exact `m04-f,q` | Create held and accepted intake bytes with one typed dry-run instruction, then POST `acceptance-review` with both IDs | Intake review joins both digests, typed fields, bounded server effect, actor/attempt/parents in ≤3 min; submit its reference | Same bytes, changed instruction, accepted-only input, forged fixture fail; reacquire both intake records | Preserve review/fixture; delete only unreferenced intakes; retain files, Preview IDs, hashes; mismatch=content defect |
| `kep-m06-b` | exact `m04-i,m04-j,q` | Create two Developer threads from one prompt-template digest and distinct objectives; run both bridge jobs | One corpus record has ≥2 objectives, commands, and output effects in ≤3 min; submit reference | Different templates, duplicate command/effect, uploaded output, shell/path escape fail; bridge reacquires GLM threads | Preserve corpus/jobs; reset only before corpus; retain prompts, provider IDs, commands, effects; model failure=nondeterministic/infrastructure |
| `kep-m06-c` | exact `m04-f,q` | Send a complete ordered experiment series to Preview, then POST `preview-experiments` method `query-optimization` | Registry reacquires every audit, confirms order/all inputs/distance/target-score rise in ≤3 min; submit export reference | Reordered/cherry-picked IDs, two inputs, over-bound candidate fail; compare raw Preview audits | Preserve export/audits; retain series and metrics; optimizer mismatch=content defect |
| `kep-m06-d` | exact `k,q` | Train/export Cinder linear proxy, record actual optimizer trace, make ≤8 transfer queries, POST method `proxy-transfer` | Server executes proxy, recomputes initial gradient/margins, and verifies target transfer in ≤3 min; submit export reference | Claimed examples, opaque bytes, wrong gradient/candidate, >8 queries fail; compare server gradient and Preview audits | Preserve export/model/trace; retain queries/digests/margins; mismatch=content defect |
| `kep-m06-e` | exact `a,s` | Upload adversarial PDF, then POST `rendering-review` | Review proves visible text lacks typed behavior while Tika/OCR retains it and downstream decision changes in ≤3 min; submit record reference | Plain text, visible instruction, no decision change fails; compare rendering, extracted text, response | Preserve review/PDF; retain page screenshots, hashes, decision; extraction failure=infrastructure |
| `kep-m06-f` | exact `d,e` | Upload PDF plus exact proxy representation URL, then POST `target-review` | Trace joins artifact, extraction stages, proxy digest and fresh non-baseline Preview decision in ≤3 min; submit record reference | Caller JSON, unrelated proxy bytes, absent/freshless target decision fail; reacquire Preview audit | Preserve review/lineage; retain stage hashes and target ID; transfer mismatch=content |
| `kep-m06-m` | exact `m08-i`, real active place | Reserve/acquire physical bench for the current `CAMPAIGN_APPLY_ID`, execute randomized liveness and actuator/light pattern, collect the proof-ID-bound raw archive from the bench exporter | Bench verifier accepts the same current apply ID, lease/place, dual live frames, telemetry/reset and exact manifest reference in ≤15 min | Upload, stale/replayed apply ID or nonce, simulated frame, missing witness/reservation fail; `verify_evidence.py` reads raw archive | Baseline releases failed lease; accepted archive immutable; retain apply ID, reservation, nonce, device IDs, media/telemetry hashes; absent bench=`blocked` |
| `kep-m06-n` | exact `i` | Create registrar account with a participant-chosen Keycloak password, domain, DNS, Stalwart address; obtain ACME order; attach exact order cert/key; publish service; request ownership manifest | Keycloak login/ID, PowerDNS serial, mail principal, service bytes, valid order URL/cert URL, exact live fingerprint join in ≤5 min; submit manifest reference | Local JSON account, checkpoint-reader mutation, fake order, mismatched key/cert, wildcard bootstrap cert, stale DNS/service fail; registrar revalidates every source | Preserve accepted identity/domain; reset deletes incomplete native resources; retain IDs/DNS/order/cert/service hashes; CA fault=infrastructure |
| `kep-m06-o` | exact `k,l` | Commit lockfile, ART/ffmpeg recipes and OCI revision; Actions build/push; POST `toolchain-releases` | Registry rootlessly pulls/unpacks the exact Harbor digest, executes locked ART/ffmpeg inside it, reruns fixed transforms, and compares exact outputs in ≤5 min; submit release reference | Unpinned lock, image lacking executable tools, unrelated Action/image, uploaded output, changed recipe fail; compare image probes and server-produced bytes | Preserve release; failed run transactional; retain lock/image/recipe/probe/output digests; tool failure=infrastructure |
| `kep-m06-r` | exact `k,q` | Publish white-box model, clean/candidate and optimizer trace; POST `white-box-experiments` | Server loads model, computes gradient digest/margin improvement and independently confirms Orion target effect in ≤3 min; submit record reference | Positive numbers, wrong gradient/model/candidate, over-bound/equal target fail; compare server gradient and target outputs | Preserve record/model/trace; retain all digests/metrics; mismatch=content |
| `kep-m06-s` | exact `j,q` | Upload PDF with neutral query, then POST `retrieval-review` | Tika/OCR→victim Qdrant→victim GLM record has actual chunk citation and bounded decision change in ≤3 min; submit review reference | Leading approve/hold query, absent citation, empty retrieval, unchanged decision fail; reacquire chunks/provider IDs | Preserve review/vector lineage; remove only unreferenced failed intake; retain chunks/scores/decisions; retrieval fault=infrastructure |
| `kep-m06-t` | exact `i,p` | Generate from public reference, listen, download WAV/provenance, POST exact files plus context to media registry | OpenVoice/Whisper record meets WER, target/control similarity and margin; exact bytes become immutable in ≤15 min; submit registry reference | Altered WAV/provenance, poor WER, unrelated speaker/control, wrong parents fail; registry rehashes generated bytes | Preserve registry/media; reset only unregistered generation; retain audio, transcript, embeddings, revisions/digests; timeout=excessive duration |
| `kep-m06-u` | exact `n,q` | Rootless build/push; forced `deploy`; after ownership, forced `lifecycle` with exact parent URLs/hashes | Knative journal joins commit/image/revision/domain/cert, first request, zero replicas, and cold start in ≤5 min; submit record reference | Alternate record location, mutable tag, wrong actor/parent, blocked ingress/egress, no zero scale, different cert fails; compare K8s and live TLS | Accepted service/lifecycle undeletable; failed deploy deletable; retain source/image/K8s/TLS/timing records; policy fault=infrastructure |
| `kep-m06-v` | exact `n,u,q` | Commit LiteLLM config and Cosign public key, build/push/deploy, stage artifacts, sign manifest, POST `staging-releases` | Registry reacquires committed key/artifacts, verifies signature, ownership/lifecycle/image/route chain, live LiteLLM GLM request and fresh edge usage in ≤5 min; submit release reference | Custom relay, arbitrary key/route, alternate object URL, missing LiteLLM mapping, stale edge usage, mismatched chain fails; inspect K8s/live model/edge | Preserve staging release and all ancestors; failed release transactional; retain config/commit/image/signature/artifact/provider IDs; chain fault=content/infrastructure |

For every table row the **operation and revision**, **participant surface**, and
**starting knowledge** are the common run identity plus the exact surfaces and
links in `operations.json`/START-HERE. The **success and flag** is the normal
record’s engagement reference submitted to Shifter. Evidence is stored under a
run-specific QA directory without credentials. Final disposition must be one of
`pass`, `content defect`, `infrastructure defect`, `nondeterministic result`,
`excessive duration`, `confusing clue`, or `blocked`; no other label is allowed.

## Copyable native request bodies

Run these from Kali or Jupyter. `context.json` is the exact context object from
START-HERE; URLs must be HTTPS owning-service URLs. Each command prints the
native response and creates no local substitute record.

```sh
export CTX="$PWD/context.json"
jq -e '.actor=="cinder-field-operator" and (.attempt_id|test("^[0-9a-f-]{36}$"))' "$CTX"

# Before any repository build, issue secrets only to that exact repository.
curl -fsS --user cinder-field-operator:Cinder-Field-Operator-Git-V6n4Qs8p -X POST \
  "https://releases.cinder.lab/v1/repositories/$REPOSITORY_NAME/credentials"

# a/e/f/s: create the exact intake first; proxy fields are used only by f.
curl -fsS -F "artifact=@$INTAKE_FILE" -F "query=$INTAKE_QUERY" \
  -F "proxy_candidate_url=${PROXY_CANDIDATE_URL:-}" \
  -F "proxy_model_url=${PROXY_MODEL_URL:-}" \
  https://partner-intake.keplerops.lab/v1/intakes

# a/e/f/s: REVIEW_PATH is acceptance-review, rendering-review, target-review, or retrieval-review.
jq -n --slurpfile context "$CTX" --arg baseline "${BASELINE_INTAKE_ID:-}" \
  '{context:$context[0]} + (if $baseline=="" then {} else {baseline_intake_id:$baseline} end)' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- \
  "https://partner-intake.keplerops.lab/v1/intakes/$INTAKE_ID/$REVIEW_PATH"

# b: repeat with two objectives; pass each returned THREAD_ID to the bridge.
jq -n --slurpfile context "$CTX" --arg objective "$OBJECTIVE" --arg environment "$ENVIRONMENT" \
  --rawfile template "$PROMPT_TEMPLATE_FILE" \
  '{context:$context[0],objective:$objective,environment:$environment,prompt_template:$template}' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- https://developer.cinder.lab/v1/threads
jq -n --arg thread_id "$THREAD_ID" --arg input_text "$INPUT_TEXT" \
  '{thread_id:$thread_id,input_text:$input_text}' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- https://bridge.cinder.lab/v1/jobs

# c/d: METHOD is query-optimization or proxy-transfer; QUERY_IDS_JSON is an array.
jq -n --slurpfile context "$CTX" --arg method "$METHOD" --arg experiment "$EXPERIMENT" \
  --arg clean "$CLEAN_URL" --arg candidate "$CANDIDATE_URL" --arg target "$TARGET_LABEL" \
  --argjson distance "$MAX_DISTANCE" --argjson query_ids "$QUERY_IDS_JSON" \
  --arg proxy "${PROXY_MODEL_URL:-}" --arg trace "${OPTIMIZATION_TRACE_URL:-}" \
  '{context:$context[0],method:$method,experiment:$experiment,clean_artifact_url:$clean,
    candidate_artifact_url:$candidate,target_label:$target,max_normalized_distance:$distance,query_ids:$query_ids}
   + (if $proxy=="" then {} else {proxy_model_url:$proxy,optimization_trace_url:$trace} end)' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- https://experiments.cinder.lab/v1/preview-experiments

# k: PROVENANCE_SHA256 hashes the workflow artifact's exact provenance.json.
jq -n --slurpfile context "$CTX" --arg repository "$REPOSITORY" --arg commit "$COMMIT" \
  --argjson run "$ACTIONS_RUN_ID" --arg provenance "$PROVENANCE_SHA256" --arg manifest "$MANIFEST_PATH" \
  '{context:$context[0],repository:$repository,commit:$commit,actions_run_id:$run,
    provenance_sha256:$provenance,manifest_path:$manifest}' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- https://releases.cinder.lab/v1/public-bundles

# o: exact image, committed recipes, and server-reacquirable outputs.
jq -n --slurpfile context "$CTX" --arg repository "$REPOSITORY" --arg commit "$COMMIT" \
  --argjson run "$ACTIONS_RUN_ID" --arg provenance "$PROVENANCE_SHA256" --arg image "$IMAGE" \
  --arg lockfile "$LOCKFILE_PATH" --arg art_recipe "$ART_RECIPE_PATH" --arg art_candidate "$ART_CANDIDATE_URL" \
  --arg ffmpeg_recipe "$FFMPEG_RECIPE_PATH" --arg ffmpeg_output "$FFMPEG_OUTPUT_URL" \
  '{context:$context[0],repository:$repository,commit:$commit,actions_run_id:$run,provenance_sha256:$provenance,
    image:$image,lockfile_path:$lockfile,art_recipe_path:$art_recipe,art_candidate_url:$art_candidate,
    ffmpeg_recipe_path:$ffmpeg_recipe,ffmpeg_output_url:$ffmpeg_output}' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- https://releases.cinder.lab/v1/toolchain-releases

# q: operation-specific workflow, image, manifest, and executable harness.
jq -n --slurpfile context "$CTX" --arg repository "$REPOSITORY" --arg commit "$COMMIT" \
  --argjson run "$ACTIONS_RUN_ID" --arg provenance "$PROVENANCE_SHA256" --arg image "$IMAGE" \
  --arg manifest "$HARNESS_MANIFEST_PATH" --arg harness "$HARNESS_PATH" \
  '{context:$context[0],repository:$repository,commit:$commit,actions_run_id:$run,provenance_sha256:$provenance,
    image:$image,harness_manifest_path:$manifest,harness_path:$harness}' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- https://releases.cinder.lab/v1/harness-releases

# r: exact white-box model, inputs, trace, target, and bound.
jq -n --slurpfile context "$CTX" --arg model "$MODEL_URL" --arg clean "$CLEAN_URL" \
  --arg candidate "$CANDIDATE_URL" --arg trace "$OPTIMIZATION_TRACE_URL" --arg target "$TARGET_LABEL" \
  --argjson distance "$MAX_DISTANCE" \
  '{context:$context[0],model_artifact_url:$model,clean_artifact_url:$clean,candidate_artifact_url:$candidate,
    optimization_trace_url:$trace,target_label:$target,max_normalized_distance:$distance}' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- https://experiments.cinder.lab/v1/white-box-experiments

# n: account, domain, DNS, mail, service, exact ACME certificate, then ownership.
jq -n --slurpfile context "$CTX" --arg username "$DOMAIN_USER" --arg display "$DISPLAY_NAME" \
  --arg password "$DOMAIN_PASSWORD" '{context:$context[0],username:$username,display_name:$display,password:$password}' |
curl -fsS -H 'Authorization: Bearer Cinder-Field-Operator-Registrar-4c8e2a7f' \
  -H 'Content-Type: application/json' --data-binary @- https://registrar.cinder.lab/v1/accounts
jq -n --arg account_id "$ACCOUNT_ID" --arg label "$DOMAIN_LABEL" '{account_id:$account_id,label:$label}' |
curl -fsS -H 'Authorization: Bearer Cinder-Field-Operator-Registrar-4c8e2a7f' \
  -H 'Content-Type: application/json' --data-binary @- https://registrar.cinder.lab/v1/domains
jq -n --arg name "$DNS_NAME" --arg type "$DNS_TYPE" --arg content "$DNS_CONTENT" --argjson ttl "$DNS_TTL" \
  '{name:$name,type:$type,content:$content,ttl:$ttl}' |
curl -fsS -X PUT -H 'Authorization: Bearer Cinder-Field-Operator-Registrar-4c8e2a7f' \
  -H 'Content-Type: application/json' --data-binary @- "https://registrar.cinder.lab/v1/domains/$DOMAIN_ID/dns"
jq -n --arg localpart "$MAIL_LOCALPART" '{localpart:$localpart}' |
curl -fsS -H 'Authorization: Bearer Cinder-Field-Operator-Registrar-4c8e2a7f' \
  -H 'Content-Type: application/json' --data-binary @- "https://registrar.cinder.lab/v1/domains/$DOMAIN_ID/mail-identities"
jq -n --arg url "$SERVICE_URL" --arg sha "$SERVICE_BODY_SHA256" '{url:$url,expected_body_sha256:$sha}' |
curl -fsS -H 'Authorization: Bearer Cinder-Field-Operator-Registrar-4c8e2a7f' \
  -H 'Content-Type: application/json' --data-binary @- "https://registrar.cinder.lab/v1/domains/$DOMAIN_ID/services"
jq -n --rawfile certificate "$CERTIFICATE_PEM" --rawfile key "$PRIVATE_KEY_PEM" \
  --arg order_url "$ACME_ORDER_URL" --slurpfile order_jws "$ACME_ORDER_JWS" \
  --slurpfile certificate_jws "$ACME_CERTIFICATE_JWS" \
  '{certificate_pem:$certificate,private_key_pem:$key,acme_order_url:$order_url,
    acme_order_jws:$order_jws[0],acme_certificate_jws:$certificate_jws[0]}' |
curl -fsS -H 'Authorization: Bearer Cinder-Field-Operator-Registrar-4c8e2a7f' \
  -H 'Content-Type: application/json' --data-binary @- "https://registrar.cinder.lab/v1/domains/$DOMAIN_ID/certificates"
curl -fsS -X POST -H 'Authorization: Bearer Cinder-Field-Operator-Registrar-4c8e2a7f' \
  "https://registrar.cinder.lab/v1/domains/$DOMAIN_ID/ownership-manifest"

# t: generate, download exact output/provenance, then register those same bytes.
curl -fsS -H 'Authorization: Bearer Cinder-Field-Operator-Media-1d4c7b9e' \
  -F "reference=@$REFERENCE_WAV;type=audio/wav" -F "text=$SCRIPT_TEXT" https://media.cinder.lab/v1/generations
curl -fsS -H 'Authorization: Bearer Cinder-Field-Operator-Media-1d4c7b9e' \
  -F "generation_id=$GENERATION_ID" -F "wav=@$OUTPUT_WAV;type=audio/wav" \
  -F "provenance=@$PROVENANCE_JSON;type=application/json" -F "context_json=<$CTX" \
  https://media.cinder.lab/v1/media-registry

# v: STAGED_URLS_JSON is the exact staged URL array.
jq -n --slurpfile context "$CTX" --arg repository "$REPOSITORY" --arg commit "$COMMIT" \
  --argjson run "$ACTIONS_RUN_ID" --arg provenance "$PROVENANCE_SHA256" --arg image "$IMAGE" \
  --arg route "$ROUTE_URL" --arg token "$ROUTE_TOKEN" --arg manifest "$SIGNED_MANIFEST_URL" \
  --arg signature "$SIGNATURE_URL" --arg key "$PUBLIC_KEY_PATH" --arg config "$LITELLM_CONFIG_PATH" \
  --argjson staged "$STAGED_URLS_JSON" \
  '{context:$context[0],repository:$repository,commit:$commit,actions_run_id:$run,provenance_sha256:$provenance,
    image:$image,route_url:$route,route_token:$token,manifest_url:$manifest,signature_url:$signature,
    public_key_path:$key,litellm_config_path:$config,staged_artifact_urls:$staged}' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- https://releases.cinder.lab/v1/staging-releases
```

The `n` commands copy the ACME JWS objects byte-for-byte from the assigned ACME
client. For `u`, use the two forced-command invocations in SERVERLESS-PUBLISH.
Operations `g/h/i/j/l/p/m`
use the concrete browser, `fdroidcl`, `swaks`, Jupyter, OpenCode, and labgrid
commands above and do not accept caller-authored completion JSON.
