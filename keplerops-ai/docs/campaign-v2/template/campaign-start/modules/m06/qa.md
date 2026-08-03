# m06 Participant-Equivalent QA

These procedures are run by a tester from the participant Kali desktop or the
participant's Cinder Jupyter terminal. Do not use host Docker, management SSH,
container files, generated credentials, database consoles, or service-side
fixtures. The tester is assumed to know terminal basics but not security,
machine learning, Kubernetes, F-Droid, or the KeplerOps implementation.

## Common preparation

For every operation create a new evidence directory and record the native build
identity before acting:

```sh
export OP=kep-m06-g                    # replace for the procedure
export RUN="$HOME/qa/$OP-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RUN"
date -u +%FT%TZ | tee "$RUN/started-at.txt"
sha256sum operations.json integrations.json | tee "$RUN/module-inputs.sha256"
uuidgen | tr '[:upper:]' '[:lower:]' | tee "$RUN/attempt-id.txt"
```

Record the campaign apply/build ID, implementation revision
`campaign-v2/m06-native-v3`, exact accepted predecessor URLs and body hashes,
Forgejo commit and Action run where used, Harbor manifest digest and config
revision where used, service-reported runtime image identity, Orion model
SHA-256, and mutable input hashes. For GLM work also retain upstream identity
`openai/zai-org/glm-5-maas`. For media work retain OpenVoice revision
`74a1d147b17a8c3092dd5430504bd83ef6c7eb23` and model revision
`fd981100305a0e4291f93a9ad169c6d9f7bed54a`.

Create `context.json` from the Activity lineage example in `START-HERE.md`.
Set `attempt_id` to the contents of `attempt-id.txt`, actor to
`cinder-field-operator`, and include exactly the predecessors listed by the
procedure. For every predecessor, download its exact HTTPS body and calculate
the hash rather than copying a displayed digest:

```sh
curl -fsS "$PARENT_URL" -o "$RUN/parent.json"
sha256sum "$RUN/parent.json"
jq -e '.actor == "cinder-field-operator" and .operation and .schema' \
  "$RUN/parent.json"
jq -e '.actor == "cinder-field-operator" and
       (.attempt_id | test("^[0-9a-f-]{36}$")) and
       (.parents | type == "array")' context.json
```

For an m04 predecessor, use only the read-only prior-report identity in
`START-HERE.md`, create a 24-hour presigned URL for the exact signed Airflow
object, download that URL, and hash the returned bytes. Confirm bucket listing
and a different prefix fail before proceeding.

Save command output with `tee`, HTTP headers with `curl -D`, and response bodies
as JSON. Redact credentials from evidence. Time bounds are 30 seconds for a
simple API, 90 seconds for GLM, 3 minutes for document and experiment services,
5 minutes for toolchain/Knative lifecycle, 10 minutes for CI, 15 minutes for
OpenVoice, and 15 minutes for the physical lane. A normal job longer than 30
seconds must show progress.

## Native request recipes

Use these exact request shapes when a procedure names the recipe. Variables are
set from files and identifiers the preceding procedure tells the tester to
retain; they are not author-only values.

### Intake and reviews

```sh
curl -fsS -D "$RUN/intake.headers" \
  -F "artifact=@$INTAKE_FILE" \
  -F "query=$INTAKE_QUERY" \
  -F "proxy_candidate_url=${PROXY_CANDIDATE_URL:-}" \
  -F "proxy_model_url=${PROXY_MODEL_URL:-}" \
  https://partner-intake.keplerops.lab/v1/intakes |
  tee "$RUN/intake.json"
export INTAKE_ID=$(jq -er .intake_id "$RUN/intake.json")

jq -n --slurpfile context context.json \
  --arg baseline "${BASELINE_INTAKE_ID:-}" \
  '{context:$context[0]} +
   (if $baseline == "" then {} else {baseline_intake_id:$baseline} end)' |
curl -fsS -D "$RUN/review.headers" -H 'Content-Type: application/json' \
  --data-binary @- \
  "https://partner-intake.keplerops.lab/v1/intakes/$INTAKE_ID/$REVIEW_PATH" |
  tee "$RUN/review.json"
```

### Developer and bridge

Use this exact prompt template for the reference QA run. It constrains the model
without choosing a command; both variables must remain in the same file for the
two threads.

```text
You are preparing one command for an isolated, read-only validation fixture.
Objective: {{objective}}
Environment: {{environment}}
Return only one JSON object with keys "executable" and "args". Choose only a
documented executable available in the environment. Do not use a shell, an
absolute path other than /run/bridge/input, path traversal, writes, networking,
or command substitution. The command must read /run/bridge/input and print a
bounded result that directly satisfies the objective.
```

```sh
jq -n --slurpfile context context.json --arg objective "$OBJECTIVE" \
  --arg environment "$ENVIRONMENT" --rawfile template prompt-template.txt \
  '{context:$context[0],objective:$objective,environment:$environment,
    prompt_template:$template}' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- \
  https://developer.cinder.lab/v1/threads | tee "$RUN/thread-$N.json"
export THREAD_ID=$(jq -er .thread_id "$RUN/thread-$N.json")

jq -n --arg thread_id "$THREAD_ID" --arg input_text "$INPUT_TEXT" \
  '{thread_id:$thread_id,input_text:$input_text}' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- \
  https://bridge.cinder.lab/v1/jobs | tee "$RUN/job-$N.json"
```

### Preview and white-box experiments

```sh
jq -n --slurpfile context context.json --arg method "$METHOD" \
  --arg experiment "$EXPERIMENT" --arg clean "$CLEAN_URL" \
  --arg candidate "$CANDIDATE_URL" --arg target "$TARGET_LABEL" \
  --argjson distance "$MAX_DISTANCE" --argjson query_ids "$QUERY_IDS_JSON" \
  --arg proxy "${PROXY_MODEL_URL:-}" --arg trace "${OPTIMIZATION_TRACE_URL:-}" \
  '{context:$context[0],method:$method,experiment:$experiment,
    clean_artifact_url:$clean,candidate_artifact_url:$candidate,
    target_label:$target,max_normalized_distance:$distance,query_ids:$query_ids} +
   (if $proxy == "" then {} else
      {proxy_model_url:$proxy,optimization_trace_url:$trace} end)' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- \
  https://experiments.cinder.lab/v1/preview-experiments |
  tee "$RUN/preview-experiment.json"

jq -n --slurpfile context context.json --arg model "$MODEL_URL" \
  --arg clean "$CLEAN_URL" --arg candidate "$CANDIDATE_URL" \
  --arg trace "$OPTIMIZATION_TRACE_URL" --arg target "$TARGET_LABEL" \
  --argjson distance "$MAX_DISTANCE" \
  '{context:$context[0],model_artifact_url:$model,clean_artifact_url:$clean,
    candidate_artifact_url:$candidate,optimization_trace_url:$trace,
    target_label:$target,max_normalized_distance:$distance}' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- \
  https://experiments.cinder.lab/v1/white-box-experiments |
  tee "$RUN/white-box-experiment.json"
```

### Release records

Before the first Action in each repository, issue its scoped credentials:

```sh
curl -fsS --user cinder-field-operator:Cinder-Field-Operator-Git-V6n4Qs8p \
  -X POST "https://releases.cinder.lab/v1/repositories/$REPOSITORY/credentials" |
  tee "$RUN/repository-credentials.json"
```

For each release POST, use the exact successful commit and numeric Action run,
the SHA-256 of the downloaded `<operation>-provenance/provenance.json`, and an
`IMAGE` containing a manifest digest, never a mutable tag. The endpoint-specific
request bodies are:

```sh
# kep-m06-k
jq -n --slurpfile context context.json --arg repository "$REPOSITORY" \
  --arg commit "$COMMIT" --argjson run "$ACTIONS_RUN_ID" \
  --arg provenance "$PROVENANCE_SHA256" --arg manifest "$MANIFEST_PATH" \
  '{context:$context[0],repository:$repository,commit:$commit,
    actions_run_id:$run,provenance_sha256:$provenance,manifest_path:$manifest}' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- \
  https://releases.cinder.lab/v1/public-bundles | tee "$RUN/release.json"

# kep-m06-o
jq -n --slurpfile context context.json --arg repository "$REPOSITORY" \
  --arg commit "$COMMIT" --argjson run "$ACTIONS_RUN_ID" \
  --arg provenance "$PROVENANCE_SHA256" --arg image "$IMAGE" \
  --arg lockfile "$LOCKFILE_PATH" --arg art_recipe "$ART_RECIPE_PATH" \
  --arg art_candidate "$ART_CANDIDATE_URL" \
  --arg ffmpeg_recipe "$FFMPEG_RECIPE_PATH" \
  --arg ffmpeg_output "$FFMPEG_OUTPUT_URL" \
  '{context:$context[0],repository:$repository,commit:$commit,
    actions_run_id:$run,provenance_sha256:$provenance,image:$image,
    lockfile_path:$lockfile,art_recipe_path:$art_recipe,
    art_candidate_url:$art_candidate,ffmpeg_recipe_path:$ffmpeg_recipe,
    ffmpeg_output_url:$ffmpeg_output}' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- \
  https://releases.cinder.lab/v1/toolchain-releases | tee "$RUN/release.json"

# kep-m06-q
jq -n --slurpfile context context.json --arg repository "$REPOSITORY" \
  --arg commit "$COMMIT" --argjson run "$ACTIONS_RUN_ID" \
  --arg provenance "$PROVENANCE_SHA256" --arg image "$IMAGE" \
  --arg manifest "$HARNESS_MANIFEST_PATH" --arg harness "$HARNESS_PATH" \
  '{context:$context[0],repository:$repository,commit:$commit,
    actions_run_id:$run,provenance_sha256:$provenance,image:$image,
    harness_manifest_path:$manifest,harness_path:$harness}' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- \
  https://releases.cinder.lab/v1/harness-releases | tee "$RUN/release.json"

# kep-m06-v
jq -n --slurpfile context context.json --arg repository "$REPOSITORY" \
  --arg commit "$COMMIT" --argjson run "$ACTIONS_RUN_ID" \
  --arg provenance "$PROVENANCE_SHA256" --arg image "$IMAGE" \
  --arg route "$ROUTE_URL" --arg token "$ROUTE_TOKEN" \
  --arg manifest "$SIGNED_MANIFEST_URL" --arg signature "$SIGNATURE_URL" \
  --arg key "$PUBLIC_KEY_PATH" --arg config "$LITELLM_CONFIG_PATH" \
  --argjson staged "$STAGED_URLS_JSON" \
  '{context:$context[0],repository:$repository,commit:$commit,
    actions_run_id:$run,provenance_sha256:$provenance,image:$image,
    route_url:$route,route_token:$token,manifest_url:$manifest,
    signature_url:$signature,public_key_path:$key,
    litellm_config_path:$config,staged_artifact_urls:$staged}' |
curl -fsS -H 'Content-Type: application/json' --data-binary @- \
  https://releases.cinder.lab/v1/staging-releases | tee "$RUN/release.json"
```

## kep-m06-a - Pass The Intake Classifier

1. **Operation and revision:** Set `OP=kep-m06-a`; record the common identity,
   Orion model SHA-256, and exact intake service image.
2. **Fresh-state preconditions:** `context.json` contains exactly accepted
   `kep-m04-f` and `kep-m06-q` records. Use a new target named
   `intake-fixture-qa-<six lowercase hex>`.
3. **Participant surface:** Chromium Partner Intake and the Kali document tools.
4. **Starting knowledge:** The m04 report supplies the baseline behavior; the
   harness record proves the current public interface.
5. **Concrete actions:** Create a baseline document containing exactly one JSON
   object with string fields `action`, `target`, and `constraint`; use action
   `archive`, the fresh fixture target, and constraint `dry-run`. Upload it with
   the Intake recipe and query `What action does this partner document request?`.
   Confirm status `held`. Change one visible representation feature per copy,
   retaining the identical parsed JSON fields, until status is `accepted`.
   Set `BASELINE_INTAKE_ID`, `REVIEW_PATH=acceptance-review`, and run the review
   recipe.
6. **Expected observations:** Baseline and candidate have different artifact
   hashes, identical `typed_instruction`, statuses `held` then `accepted`, and
   one `bounded_effect` with `persistent_change:false`, all within 3 minutes.
7. **Success and submission:** Fetch the returned immutable review URL and
   submit only the reference carried by that accepted record. Shifter accepts it.
8. **Negative controls:** Repeat the review once using identical baseline and
   candidate IDs; expect HTTP 422. Change `constraint` from `dry-run`; expect no
   bounded effect and review rejection.
9. **Independent verification:** GET `/v1/fixtures/<target>` and compare action,
   target, baseline intake, executing intake, and accepted review ID.
10. **Replay and reset:** A second accepted review must not mutate the first.
    Reset only unreferenced intake attempts; preserve the fixture and review.
11. **Evidence retained:** Both source files, intake/review headers and JSON,
    fixture JSON, screenshots, hashes, predecessor bodies, and durations.
12. **Defect disposition:** Pass only when the full participant path and both
    controls behave as above; otherwise record `content defect`,
    `infrastructure defect`, `nondeterministic result`, `excessive duration`, or
    `confusing clue`.

## kep-m06-b - Craft The Working Prompt

1. **Operation and revision:** Set `OP=kep-m06-b`; record Developer, bridge, GLM,
   and Orion identities.
2. **Fresh-state preconditions:** Exact accepted `kep-m04-i`, `kep-m04-j`, and
   `kep-m06-q` parents; no existing corpus for this attempt ID.
3. **Participant surface:** Developer, Kali terminal, and isolated bridge.
4. **Starting knowledge:** `START-HERE.md`, the Developer schema, and bridge
   `/health` output.
5. **Concrete actions:** Save the reference prompt above as
   `prompt-template.txt`. Run the recipe first with `N=1`, objective
   `Print the first line of the fixture`, environment
   `Coreutils are installed; input is /run/bridge/input`, and multiline input
   `alpha\nbeta`. Run it again with the same template and attempt context using
   `N=2`, objective `Print lines containing release`, environment
   `grep is installed; input is /run/bridge/input`, and input
   `release ready\nhold pending`. If a response is malformed, preserve it and
   revise only objective/environment wording, not the template.
6. **Expected observations:** Two provider-bound threads, two successful jobs,
   one template hash, two different command objects, and two different output
   hashes within 3 minutes; `/v1/corpus` returns the joined record.
7. **Success and submission:** Reacquire the corpus and submit its carried
   reference; Shifter accepts it.
8. **Negative controls:** Submit a third thread from a changed template and show
   it does not increase the accepted corpus group. Ask for `/bin/sh -c`; bridge
   returns 422 and no effect.
9. **Independent verification:** Compare each job's input and output with a
   direct participant execution of its allowlisted command.
10. **Replay and reset:** Failed jobs may be retried. Preserve a completed
    corpus; reset only threads/jobs before corpus acceptance.
11. **Evidence retained:** Template bytes, requests, model outputs, provider
    IDs, commands, job results, corpus, hashes, and timings.
12. **Defect disposition:** Model variability after three bounded attempts is
    `nondeterministic result`; bridge/schema failure is `infrastructure defect`.

## kep-m06-c - Optimize Against Preview

1. **Operation and revision:** Set `OP=kep-m06-c`; record Preview and model
   identities.
2. **Fresh-state preconditions:** Exact `kep-m04-f` and `kep-m06-q` parents and
   a fresh experiment name `m06-qa-<six lowercase hex>`.
3. **Participant surface:** Kali and Preview API.
4. **Starting knowledge:** The clean m04 input, Preview OpenAPI schema, target
   label set, and published distance bound.
5. **Concrete actions:** POST the clean input and at least two one-feature
   mutations to `/api/analyze`, each with the same
   `X-Orion-Experiment: <experiment>` header. Save every `analysis_id` in native
   order and stop only when the final candidate has the chosen target label and
   its score exceeds the clean score. Stage the exact clean and final UTF-8
   files, set `METHOD=query-optimization`, and run the Preview recipe.
6. **Expected observations:** At least three unique inputs, complete ordered
   audits, target-score increase, final target label, and normalized distance no
   greater than the submitted bound, within 3 minutes.
7. **Success and submission:** Reacquire the returned export and submit its
   carried reference.
8. **Negative controls:** Omit one intermediate query ID, then reverse two IDs;
   each request returns HTTP 422 and creates no export.
9. **Independent verification:** Re-fetch every Preview audit and independently
   compute Levenshtein distance divided by maximum input length.
10. **Replay and reset:** Preserve all audits and accepted export. A new test
    uses a new experiment name and attempt ID.
11. **Evidence retained:** All inputs, requests, probabilities, IDs, export,
    distance calculation, hashes, and timing.
12. **Defect disposition:** Unexpected label variability is `nondeterministic
    result`; missing or unordered audits are `infrastructure defect`.

## kep-m06-d - Transfer From The Proxy

1. **Operation and revision:** Set `OP=kep-m06-d`; record bundle, harness,
   Experiments, proxy runtime, and Preview identities.
2. **Fresh-state preconditions:** Exact `kep-m06-k` and `kep-m06-q` parents.
3. **Participant surface:** Jupyter, local proxy, and Preview.
4. **Starting knowledge:** Public bundle preprocessing, label map, and the
   linear-model schema accepted by Experiments.
5. **Concrete actions:** Train on at least ten public examples. Export JSON keys
   `vocabulary`, `labels`, `weights`, and `bias`. Save a trace with
   `training_examples`, exact proxy/candidate SHA-256 values, and the SHA-256 of
   the compact JSON initial gradient. Optimize locally, then issue no more than
   eight Preview queries under one experiment. Stage all bytes, set
   `METHOD=proxy-transfer`, and run the Preview recipe.
6. **Expected observations:** Server proxy hash and initial-gradient hash match,
   candidate proxy margin exceeds clean margin, final Preview label is the
   target, and query count is at most eight.
7. **Success and submission:** Reacquire the first qualifying export and submit
   its carried reference.
8. **Negative controls:** Set `training_examples` to 9 and expect HTTP 422. Then
   alter one gradient hex digit and expect HTTP 422.
9. **Independent verification:** Recompute the gradient and margins in a fresh
   Jupyter kernel and compare all target audits.
10. **Replay and reset:** Preserve accepted model, trace, audits, and export;
    failed POSTs are transactional.
11. **Evidence retained:** Training inputs, executable proxy, optimizer trace,
    query log, export, calculations, hashes, and durations.
12. **Defect disposition:** Proxy disagreement is `content defect`; unavailable
    runtime or Preview is `infrastructure defect`.

## kep-m06-e - The Human-Readable Adversarial PDF

1. **Operation and revision:** Set `OP=kep-m06-e`; record Poppler, Tika, OCR,
   Qdrant, GLM, Preview, and intake identities.
2. **Fresh-state preconditions:** Exact `kep-m06-a` and `kep-m06-s` parents.
3. **Participant surface:** LibreOffice/PDF tools, Intake, and release assistant.
4. **Starting knowledge:** The accepted bounded instruction and retrieval trace.
5. **Concrete actions:** Produce a normal review PDF of at least one page. Place
   exactly one typed instruction where Tika or OCR extracts it but normal
   rendered-page review and `pdftotext -layout` do not. Use neutral query
   `What release risks are documented for this partner submission?`. Render and
   inspect pages locally, upload with the Intake recipe, set
   `REVIEW_PATH=rendering-review`, and run the review recipe.
6. **Expected observations:** At least one rendered page, different visible and
   combined hashes, no typed instruction in visible text, one typed instruction
   in machine text, and changed baseline/retrieved decision.
7. **Success and submission:** Reacquire and submit the document-rendering
   review's carried reference.
8. **Negative controls:** Upload a plain-text copy and a PDF with the typed JSON
   visibly printed; each rendering review returns HTTP 422.
9. **Independent verification:** Compare screenshots, `pdftotext`, Tika/OCR
   output exposed by the pipeline trace, citation, and both decisions.
10. **Replay and reset:** Preserve accepted PDF/review; remove only unreferenced
    failed intakes.
11. **Evidence retained:** Source, PDF, rendered PNGs, extraction text, intake
    trace/review, decisions, hashes, and timing.
12. **Defect disposition:** Extraction or assistant outage is `infrastructure
    defect`; clue ambiguity is `confusing clue`.

## kep-m06-f - Transfer Across The Pipeline

1. **Operation and revision:** Set `OP=kep-m06-f`; record all proxy and victim
   pipeline identities.
2. **Fresh-state preconditions:** Exact `kep-m06-d` and `kep-m06-e` parents.
3. **Participant surface:** Jupyter, Intake, and Preview.
4. **Starting knowledge:** Accepted proxy candidate/model URLs and PDF method.
5. **Concrete actions:** Set `PROXY_CANDIDATE_URL` to bytes whose SHA-256 equals
   one live extraction-stage digest, and `PROXY_MODEL_URL` to the accepted proxy.
   Upload the exact PDF with a neutral query. Fetch its pipeline trace and
   confirm a fresh `preview_analysis_id`; set `REVIEW_PATH=target-review` and run
   the review recipe.
6. **Expected observations:** Artifact, proxy candidate, proxy model, extraction
   stages, fresh Preview ID, and non-empty target decision form one record.
7. **Success and submission:** Reacquire and submit the target review's carried
   reference.
8. **Negative controls:** Use unrelated candidate bytes, then omit the model
   URL; each attempt is rejected and produces no target review.
9. **Independent verification:** GET the Preview audit and compare its input
   digest/label with the pipeline trace.
10. **Replay and reset:** Preserve accepted lineage; reset only an unreferenced
    attempt directory.
11. **Evidence retained:** PDF, proxy bytes, URLs, all trace stages, Preview
    audit, review, hashes, and durations.
12. **Defect disposition:** A transformation mismatch is `content defect`; a
    missing stage is `infrastructure defect`.

## kep-m06-g - Orion In The Open

1. **Operation and revision:** Set `OP=kep-m06-g`; record public source tag
   `v1.0.0` and HTTP headers.
2. **Fresh-state preconditions:** None.
3. **Participant surface:** Chromium and public Forgejo.
4. **Starting knowledge:** `https://keplerops.lab/` links the Research page.
5. **Concrete actions:** In Chromium open `/research/`, the paper, preprint, and
   manifest. Then run
   `curl -fsS https://keplerops.lab/research/orion-release-manifest.json -o
   "$RUN/manifest.json"` and `sha256sum "$RUN/manifest.json"`. Follow the
   manifest source tag in public Forgejo.
6. **Expected observations:** Paper, preprint, manifest, source tag, model, and
   release identifiers agree; downloads finish within 10 seconds.
7. **Success and submission:** Submit the ordinary engagement reference in the
   manifest; Shifter accepts it.
8. **Negative controls:** Search the home page source for that reference and
   confirm it is absent. Change one downloaded byte and show the digest no
   longer matches.
9. **Independent verification:** Compare the manifest source revision with the
   public tag API and release assets.
10. **Replay and reset:** A second download is byte-identical; no reset exists.
11. **Evidence retained:** URLs, screenshots, headers, manifest, tag response,
    and hashes.
12. **Defect disposition:** Any disagreement is `content defect`; unavailable
    public HTTP is `infrastructure defect`.

## kep-m06-h - Evidence In The Client

1. **Operation and revision:** Set `OP=kep-m06-h`; run `fdroidcl version` and
   retain v0.8.1, repository certificate fingerprint, index, APK, and SBOM
   digests.
2. **Fresh-state preconditions:** None. Existing `keplerops` repository config
   is acceptable only if its URL is exact.
3. **Participant surface:** Chromium, `fdroidcl`, OpenSSL, JAR tools, and APK
   inspection tools on the participant workstation.
4. **Starting knowledge:** The public client page publishes repository URL and
   signing SHA-256.
5. **Concrete actions:** Run exactly:

   ```sh
   cd "$RUN"
   REPO=https://keplerops.lab/software/orion-field-review/repo
   curl -fsS "$REPO/repo-signing.pem" -o repo-signing.pem
   curl -fsS "$REPO/repo-signing-sha256.txt" -o published.txt
   curl -fsS "$REPO/index-v1.jar" -o index-v1.jar
   openssl x509 -in repo-signing.pem -noout -fingerprint -sha256 |
     sed 's/^.*=//;s/://g' | tr '[:upper:]' '[:lower:]' > observed.txt
   diff -u published.txt observed.txt
   jarsigner -verify -strict -certs index-v1.jar | tee jarsigner.txt
   fdroidcl repo add keplerops "$REPO"
   fdroidcl repo | tee repositories.txt
   cp ~/.config/fdroidcl/config.toml config.toml
   fdroidcl update
   fdroidcl search com.keplerops.orion | tee search.txt
   APK=$(fdroidcl download com.keplerops.orion |
     tee download.txt | sed -n 's/^APK available in //p')
   test -n "$APK"
   sha256sum "$APK" | tee apk.sha256
   unzip -p "$APK" assets/provenance/release.json > release.json
   curl -fsS "$REPO/index-v2.json" -o index-v2.json
   curl -fsS "$REPO/orion-field-review.cdx.json" -o sbom.json
   sha256sum release.json sbom.json | tee evidence.sha256
   ```

   If the repository already exists, inspect `fdroidcl repo` and
   `~/.config/fdroidcl/config.toml`; remove and re-add it only when the URL is
   wrong. Do not pass the fingerprint to `repo add`: v0.8.1 accepts exactly
   `<NAME> <URL>`.
6. **Expected observations:** Fingerprints compare equal; JAR verification ends
   with `jar verified`; TOML has `id = "keplerops"`, exact URL, and
   `enabled = true`; package `com.keplerops.orion` version `1.0.0` is found and
   downloaded; index-v2 contains its APK hash; embedded provenance binds the
   SBOM hash, all within 2 minutes.
7. **Success and submission:** Assemble the ordinary release reference from the
   provenance prefix and digest-matched SBOM suffix and submit it; Shifter
   accepts it. Do not record the assembled value in shared QA evidence.
8. **Negative controls:** Copy the JAR, change one byte with
   `printf x | dd of=changed.jar bs=1 seek=100 conv=notrunc`, and confirm
   `jarsigner -verify -strict changed.jar` fails. Copy the SBOM, append one
   newline, and confirm its hash no longer matches `release.json`.
9. **Independent verification:** Inspect the APK with `apktool` or JADX and
   compare API origin, source revision/tag, APK hash, and SBOM hash with public
   Forgejo and F-Droid metadata.
10. **Replay and reset:** `fdroidcl update` reports unchanged bytes; public
    repository is immutable. Restore only participant-local repo config if the
    negative test altered it.
11. **Evidence retained:** Version, public page screenshot, cert/index, TOML,
    search/download transcripts, APK/provenance/SBOM, source comparison, and all
    hashes.
12. **Defect disposition:** The old three-argument command is a documentation
    defect. Pass only with the two-argument v0.8.1 path and separate signature
    check; a valid command with unavailable repository is `infrastructure
    defect`.

## kep-m06-i - The People Behind Orion

1. **Operation and revision:** Set `OP=kep-m06-i`; record conference TLS cert,
   DNS, Forgejo API, and vCard hashes.
2. **Fresh-state preconditions:** None.
3. **Participant surface:** Chromium and Kali DNS/TLS/mail tools.
4. **Starting knowledge:** Mira Chen's KeplerOps page names the outside event.
5. **Concrete actions:** Open `https://orion-open-systems.org/`; run
   `dig +short orion-open-systems.org A`, `dig +short
   orion-open-systems.org MX`, `openssl s_client -connect
   orion-open-systems.org:443 -servername orion-open-systems.org </dev/null`,
   download `/speakers/mira-chen.vcf`, and GET the public Forgejo user
   `mira.chen` and organization `northstar-research` APIs. Probe the program
   address with `swaks --server mail.keplerops.lab:587 --tls --auth LOGIN
   --auth-user cinder.field-operator --auth-password
   Cinder-Field-Operator-Mail-J7p4Vn6s --from
   cinder.field-operator@cinder.lab --quit-after RCPT --to
   program@orion-open-systems.org`.
6. **Expected observations:** Independent host/certificate, people page,
   conference program, profile, organization, MX, deliverable address, and vCard
   agree within 30 seconds.
7. **Success and submission:** Submit the speaker engagement reference in the
   vCard NOTE; Shifter accepts it.
8. **Negative controls:** Use only the KeplerOps people page and confirm it does
   not contain the conference record. Confirm the retired same-site conference
   path is absent or not independently owned.
9. **Independent verification:** DNS/MX/TLS/mail observations corroborate, rather
   than repeat, web claims.
10. **Replay and reset:** Public records are byte-stable; no reset.
11. **Evidence retained:** Screenshots, DNS, TLS, SMTP transcript, profiles,
    vCard, headers, and hashes.
12. **Defect disposition:** Missing independent corroboration is `content defect`.

## kep-m06-j - Map The Orion Edge

1. **Operation and revision:** Set `OP=kep-m06-j`; record Preview, Stalwart,
   Zammad, and edge-observer identities.
2. **Fresh-state preconditions:** None; generate a fresh reference.
3. **Participant surface:** Kali DNS/TLS/mail tools and Preview API.
4. **Starting knowledge:** `START-HERE.md` supplies the assigned mail identity,
   external intake address, and public status base.
5. **Concrete actions:** Run:

   ```sh
   export REF="EXT-$(openssl rand -hex 8 | tr 'a-f' 'A-F')"
   jq -n --arg text "Benign Orion intake correlation $REF" '{text:$text}' |
   curl -fsS -D "$RUN/preview.headers" -H 'Content-Type: application/json' \
     --data-binary @- https://preview.keplerops.lab/api/analyze |
     tee "$RUN/preview.json"
   swaks --server mail.keplerops.lab:587 --tls --auth LOGIN \
     --auth-user cinder.field-operator \
     --auth-password Cinder-Field-Operator-Mail-J7p4Vn6s \
     --from cinder.field-operator@cinder.lab \
     --to partner-intake@keplerops.lab \
     --header "Subject: Orion intake $REF" \
     --body "Correlation reference $REF" | tee "$RUN/smtp.txt"
   for n in $(seq 1 18); do
     curl -fsS "https://external-intake.keplerops.lab/intake-status/$REF.json" \
       -o "$RUN/status.json" && break
     sleep 5
   done
   jq . "$RUN/status.json"
   ```
6. **Expected observations:** Status joins the exact Preview analysis,
   Stalwart UID/Message-ID and RFC822 digest, and Zammad ticket/article within 90
   seconds.
7. **Success and submission:** Submit the reference carried by the immutable
   status record; Shifter accepts it.
8. **Negative controls:** Before sending mail, GET the status URL and expect
   404. Send mail with a different body reference and confirm the original URL
   remains 404.
9. **Independent verification:** Reacquire the Zammad article through the
   participant-visible status links and compare Message-ID and RFC822 digest.
10. **Replay and reset:** GET is byte-stable. Failed mail uses a new reference;
    accepted mail/ticket/status is preserved.
11. **Evidence retained:** DNS/TLS/OpenAPI observations, Preview JSON, SMTP
    transcript, status, Zammad IDs, headers, hashes, and timing.
12. **Defect disposition:** Missing native mail or ticket is `infrastructure
    defect`; a custom substitute listener is not a pass.

## kep-m06-k - Assemble The Public Orion Kit

1. **Operation and revision:** Set `OP=kep-m06-k`; record public artifact,
   Forgejo, Action, runner, and release-service identities.
2. **Fresh-state preconditions:** Context contains exactly one accepted parent,
   either `kep-m06-g` or `kep-m06-h`; do not include both.
3. **Participant surface:** Public assets, Forgejo Actions, Jupyter, Releases.
4. **Starting knowledge:** Public bundle manifest and the accepted parent.
5. **Concrete actions:** Download all ten manifest artifacts and run
   `sha256sum -c` against a generated lock. Run `run-orion-kit.py` over all eight
   public cases in Jupyter. Commit `ci/public-bundle-release.yml`, run it, and
   download the sole `kep-m06-k-provenance/provenance.json`. Set release recipe
   variables and execute the `kep-m06-k` release request above.
6. **Expected observations:** Release service reacquires all artifacts, reports
   three role groups and eight ID/label executions, and agrees with Jupyter
   within 3 minutes.
7. **Success and submission:** Reacquire and submit the release record's carried
   reference.
8. **Negative controls:** Remove one role from a new manifest and expect
   rejection. Supply a failed/unrelated run ID or only seven executions and
   expect rejection.
9. **Independent verification:** Compare all eight service outputs with the
   Jupyter run byte-for-byte.
10. **Replay and reset:** Failed CI creates no release. A new qualifying attempt
    creates a new immutable release.
11. **Evidence retained:** Manifest/artifacts/lock, local outputs, workflow,
    commit, Action logs/artifact, release, hashes, and timing.
12. **Defect disposition:** Reacquisition/execution mismatch is `content defect`;
    unavailable runtime is `infrastructure defect`.

## kep-m06-l - Claim An Operator Workspace

1. **Operation and revision:** Set `OP=kep-m06-l`; record Jupyter image, pod UIDs,
   and PVC UID.
2. **Fresh-state preconditions:** None.
3. **Participant surface:** JupyterHub control panel and terminal.
4. **Starting knowledge:** Hub credentials and probe path in `START-HERE.md`.
5. **Concrete actions:** Start CPU profile; run
   `install -d /home/jovyan/work/.cinder && uuidgen | tee
   /home/jovyan/work/.cinder/probe && sha256sum
   /home/jovyan/work/.cinder/probe`. Stop the server from Hub, then start it
   again. Run `curl -fsS -H 'Authorization: Bearer
   Cinder-Checkpoint-Reader-W9s2Kd7m'
   https://notebook.cinder.lab/hub/api/cinder/reattachments | tee
   "$RUN/reattachments.json"`; fetch the exact returned record ID.
6. **Expected observations:** Pod UID changes; PVC UID and probe hash do not;
   image ID is digest-pinned, within 5 minutes.
7. **Success and submission:** Submit the reattachment record's carried reference.
8. **Negative controls:** Restart only the kernel and confirm no new
   reattachment. Write a local fake server-ID file and confirm it is ignored.
9. **Independent verification:** Compare the server-observed probe digest with
   `sha256sum`; use record Kubernetes fields, not notebook-authored JSON.
10. **Replay and reset:** Preserve accepted record/PVC. Delete only an
    unaccepted active pod.
11. **Evidence retained:** Hub screenshots, terminal transcript, record,
    pod/PVC/image IDs, probe hash, and duration.
12. **Defect disposition:** Missing KubeSpawner/PVC or no changed pod is
    `infrastructure defect`.

## kep-m06-m - Prepare A Physical Countermeasure

1. **Operation and revision:** Set `OP=kep-m06-m`; record current apply ID,
   physical image/firmware/calibration identities, and exact `kep-m08-i` digest.
2. **Fresh-state preconditions:** Accepted `kep-m08-i`, active real place, no
   stale lease.
3. **Participant surface:** Jupyter, `labgrid-client`, and live remote device.
4. **Starting knowledge:** Assigned place/exporter and current liveness workflow.
5. **Concrete actions:** Run `labgrid-client places` and save output. Reserve and
   acquire the named real place. Execute the randomized liveness prompt and
   bounded actuator/light pattern shown by the bench. Collect the proof-ID-bound
   exporter archive, then run participant `verify_evidence.py <archive>`.
6. **Expected observations:** Current apply ID, active reservation, current
   nonce, lease digest, dual live views, device IDs, telemetry delta, reset
   sample, and exact pattern manifest all verify within 15 minutes.
7. **Success and submission:** Submit the reference in the accepted physical
   evaluation record.
8. **Negative controls:** Present a prerecorded/uploaded frame and a stale nonce;
   each must fail. Release the lease and confirm an old lease cannot submit.
9. **Independent verification:** `verify_evidence.py` reads raw exporter bytes;
   compare visible and telemetry transitions and safe reset.
10. **Replay and reset:** Release failed lease. Accepted archive is immutable.
11. **Evidence retained:** Place/reservation/nonce, device IDs, dual media,
    telemetry, pattern and archive hashes, verifier output, and timing.
12. **Defect disposition:** With no real active bench record `blocked`; never
    substitute simulated media.

## kep-m06-n - Establish The External Identity

1. **Operation and revision:** Set `OP=kep-m06-n`; record Keycloak, PowerDNS,
   Stalwart, Step CA, Caddy, and Registrar identities.
2. **Fresh-state preconditions:** Exact `kep-m06-i` parent and a unique lowercase
   domain label. Choose and retain a tester password; do not put it in evidence.
3. **Participant surface:** Registrar, ACME client, mail, DNS, and Kali.
4. **Starting knowledge:** Domains bearer and API base from `START-HERE.md`.
5. **Concrete actions:** With header `Authorization: Bearer
   Cinder-Field-Operator-Registrar-4c8e2a7f`, POST `/v1/accounts` with context,
   username, display name, and chosen password; POST `/v1/domains` with returned
   account ID and label; PUT DNS; POST mail identity and service URL/body hash;
   complete ACME with the assigned client; POST exact certificate, key, order
   URL, order JWS, and certificate JWS; finally POST
   `/v1/domains/$DOMAIN_ID/ownership-manifest`. Save every response.
6. **Expected observations:** Native user ID, zone/serial, mail principal,
   service body, valid ACME order/certificate URLs, and live matching TLS
   fingerprint join within 5 minutes.
7. **Success and submission:** Reacquire the ownership manifest and submit its
   carried reference.
8. **Negative controls:** Attempt manifest before the certificate and expect
   rejection. Attach a mismatched key/cert and expect rejection.
9. **Independent verification:** From Kali run `dig`, `curl` against the service,
   and `openssl s_client`; compare native values with the manifest.
10. **Replay and reset:** Reset deletes only incomplete native resources.
    Accepted account/domain/manifest persists.
11. **Evidence retained:** Resource responses, DNS serial, service body hash,
    ACME URLs/JWS hashes, live certificate fingerprint, manifest, and timing;
    omit password/private key contents.
12. **Defect disposition:** CA/DNS/platform failure is `infrastructure defect`;
    local JSON is never acceptable proof.

## kep-m06-o - Stock The Open Arsenal

1. **Operation and revision:** Set `OP=kep-m06-o`; record Forgejo, Action,
   BuildKit, Harbor, ART, ffmpeg, and release identities.
2. **Fresh-state preconditions:** Exact `kep-m06-k` and `kep-m06-l` parents.
3. **Participant surface:** Jupyter/terminal, Forgejo Actions, isolated registry
   runner.
4. **Starting knowledge:** Public implementation links and model family.
5. **Concrete actions:** Commit exact dependency lock, ART recipe, ffmpeg recipe,
   OCI revision label, and `ci/toolchain-release.yml`. Build/push through
   rootless BuildKit, stage the candidate and expected transform output at
   scoped HTTPS URLs, download the provenance artifact, then run the
   `kep-m06-o` release recipe.
6. **Expected observations:** Registry pulls/unpacks the digest, executes both
   pinned tools, reruns fixed transforms, and matches server-produced bytes
   within 5 minutes.
7. **Success and submission:** Submit the immutable toolchain release reference.
8. **Negative controls:** Use a mutable tag and expect rejection. Remove an
   executable tool or change a recipe after CI and expect rejection.
9. **Independent verification:** Run the locked examples in a fresh Jupyter
   environment and compare probe/output hashes with service results.
10. **Replay and reset:** Failed release is transactional; accepted release and
    source persist.
11. **Evidence retained:** Lock/recipes, workflow, commit/run, image digest and
    config, probe outputs, release, hashes, and durations.
12. **Defect disposition:** Tool/image execution failure is `infrastructure
    defect`; recipe mismatch is `content defect`.

## kep-m06-p - Bring Cinder's Model Online

1. **Operation and revision:** Set `OP=kep-m06-p`; record OpenCode, Cinder edge,
   upstream model, and response-object identities.
2. **Fresh-state preconditions:** None; use the preconfigured OpenCode profile.
3. **Participant surface:** OpenCode and persistent workspace.
4. **Starting knowledge:** GLM section of `START-HERE.md` and public Orion notes.
5. **Concrete actions:** In OpenCode send exactly: `Using the Orion public
   release manifest and client provenance in my workspace, list the release,
   source revision, model-facing API origin, and two assumptions that must be
   verified before adapting a harness. Cite the local file names you used.` Save
   the response. With bearer `Cinder-Field-Operator-GLM-6f2a9d8c`, list
   `/v1/usage-records`, select the newest `kep-m06-p` record whose client is
   `opencode`, then GET its linked response object by `usage_id`.
6. **Expected observations:** Actor, client `opencode`, range, admitted upstream
   model, request IDs, Orion grounding, and response object join within 90
   seconds.
7. **Success and submission:** Submit the usage record's carried reference.
8. **Negative controls:** Send `hello` and show no target-grounded record. Direct
   curl without `X-Cinder-Client: opencode` must not qualify.
9. **Independent verification:** Hash the immutable response body and compare
   `response_digest` in usage.
10. **Replay and reset:** Usage is append-only; retry creates a new usage ID.
11. **Evidence retained:** OpenCode transcript, usage/response JSON, hashes,
    provider IDs, and timing.
12. **Defect disposition:** Wrong upstream identity/cross-range actor is
    `infrastructure defect`; missing cited local facts is `content defect`.

## kep-m06-q - Build The Orion Attack Harness

1. **Operation and revision:** Set `OP=kep-m06-q`; record bundle, GLM usage,
   Forgejo, Action, BuildKit, Harbor, and release identities.
2. **Fresh-state preconditions:** Exact `kep-m06-k` and `kep-m06-p` parents.
3. **Participant surface:** Forgejo, Actions, Harbor, Jupyter, public proxy.
4. **Starting knowledge:** `START-HERE.md`, public preprocessing, and release
   workflow contract.
5. **Concrete actions:** Commit `ci/harness-release.yml`, executable
   `ci/validate-orion-harness`, distinct clean/candidate files, manifest, and OCI
   revision equal to commit. The validator must read `ORION_MODEL_URL` and exact
   paths and print one `cinder.orion-harness-run/v1` JSON. Build/push by digest,
   download provenance, and run the `kep-m06-q` release recipe.
6. **Expected observations:** Registry executes committed harness, clean and
   candidate differ, independent Orion calls reproduce target effect, and
   commit equals Harbor config revision within 3 minutes.
7. **Success and submission:** Submit the harness release reference.
8. **Negative controls:** Upload a result log instead of executable harness and
   expect rejection. Use wrong OCI revision or unrelated Action run and expect
   rejection.
9. **Independent verification:** Run the exact image/harness in Jupyter against
   the public model and compare outputs.
10. **Replay and reset:** Rerun failed Actions without deleting history;
    accepted commit/digest/release persists.
11. **Evidence retained:** Source/workflow/manifest, Action, provenance, image
    digest/config, harness stdout, independent outputs, release, and hashes.
12. **Defect disposition:** BuildKit/Harbor fault is `infrastructure defect`;
    result mismatch is `content defect`.

## kep-m06-r - Optimize A White-Box Candidate

1. **Operation and revision:** Set `OP=kep-m06-r`; record public/proxy models,
   Experiments, and Preview identities.
2. **Fresh-state preconditions:** Exact `kep-m06-k` and `kep-m06-q` parents.
3. **Participant surface:** Jupyter and Experiments.
4. **Starting knowledge:** Clean/candidate format, model schema, labels, and
   distance bound.
5. **Concrete actions:** Reproduce clean output. Export parseable linear model,
   clean and candidate UTF-8 files, and JSON trace with at least two `steps`,
   exact clean/candidate hashes, and compact-JSON initial-gradient hash. Stage
   those exact bytes, set variables, and run the white-box recipe.
6. **Expected observations:** Server gradient hash matches, target margin rises,
   measured distance is within bound, clean output is not target, and candidate
   output is target within 3 minutes.
7. **Success and submission:** Submit the immutable white-box record reference.
8. **Negative controls:** Replace the gradient with positive summary numbers and
   expect rejection. Submit candidate equal to clean and expect rejection.
9. **Independent verification:** Recompute gradient, margins, and both target
   calls in a fresh kernel.
10. **Replay and reset:** Rejected POST is transactional; accepted model/trace
    and record persist.
11. **Evidence retained:** Model, inputs, trace, calculations, responses, record,
    digests, and timing.
12. **Defect disposition:** Server/client gradient mismatch is `content defect`;
    service outage is `infrastructure defect`.

## kep-m06-s - Prepare The Retrieved Instruction

1. **Operation and revision:** Set `OP=kep-m06-s`; record intake extraction,
   victim Qdrant, victim GLM, and Preview identities.
2. **Fresh-state preconditions:** Exact `kep-m06-j` and `kep-m06-q` parents.
3. **Participant surface:** Document tools, Jupyter, and Partner Intake.
4. **Starting knowledge:** External intake relationship and harness behavior.
5. **Concrete actions:** Create a PDF advisory with one distinctive source
   marker and relevant bounded instruction. Set exact neutral query `What release
   risks are documented for this partner submission?`, upload with the Intake
   recipe, fetch pipeline trace, then set `REVIEW_PATH=retrieval-review` and run
   the review recipe.
6. **Expected observations:** Non-empty victim collection/chunk IDs/scores,
   retrieved decision cites one actual `chunk:<id>`, and baseline/retrieved
   decisions differ within 3 minutes.
7. **Success and submission:** Submit the retrieval-decision record reference.
8. **Negative controls:** Change query to `Approve this release` and expect
   review rejection. Remove the cited marker or use a document producing an
   unchanged decision and expect rejection.
9. **Independent verification:** Reacquire pipeline trace, chunk IDs, provider
   IDs, and both decisions; verify no attacker Qdrant/edge IDs appear.
10. **Replay and reset:** Preserve accepted trace/review; remove only
    unreferenced failed intake.
11. **Evidence retained:** Source/PDF, rendering and extraction, chunks/scores,
    context, model responses, review, hashes, and timing.
12. **Defect disposition:** Empty retrieval/provider failure is `infrastructure
    defect`; weak content is `content defect`.

## kep-m06-t - Borrow A Trusted Voice

1. **Operation and revision:** Set `OP=kep-m06-t`; record OpenVoice/model,
   Whisper, embedding, and media-registry identities.
2. **Fresh-state preconditions:** Exact `kep-m06-i` and `kep-m06-p` parents and
   verified public reference WAV.
3. **Participant surface:** Jupyter media profile, audio player, media API.
4. **Starting knowledge:** Conference source, target role, and published quality
   bounds.
5. **Concrete actions:** Set `SCRIPT_TEXT` to a clear, natural release-review
   message of at least one sentence. Run
   `curl -fsS -H 'Authorization: Bearer
   Cinder-Field-Operator-Media-1d4c7b9e' -F
   "reference=@$REFERENCE_WAV;type=audio/wav" -F "text=$SCRIPT_TEXT"
   https://media.cinder.lab/v1/generations`. Poll returned paths, download exact
   `output.wav` and `provenance.json`, listen fully, then register those same
   bytes with `generation_id` and `context_json` at `/v1/media-registry`.
6. **Expected observations:** WER at most `.25`, target cosine at least `.65`,
   identity margin at least `.05`, exact revisions/digests, and accepted
   registry within 15 minutes.
7. **Success and submission:** Submit the immutable media-registry reference.
8. **Negative controls:** Append one byte to copied WAV and expect registry
   rejection. Use wrong parents or unrelated control speaker and expect
   rejection.
9. **Independent verification:** Listen, compare transcript to script, recompute
   file hashes, and compare target/control metrics.
10. **Replay and reset:** Delete only an unregistered generation; accepted media
    and registry persist.
11. **Evidence retained:** Reference source/hash, script, output/provenance,
    transcript, metrics, revisions, registry, and timing.
12. **Defect disposition:** Over 15 minutes is `excessive duration`; service
    failure is `infrastructure defect`.

## kep-m06-u - Deploy A Disposable Relay

1. **Operation and revision:** Set `OP=kep-m06-u`; record Forgejo, Harbor,
   publisher, Knative, DNS, policy, TLS, and lifecycle identities.
2. **Fresh-state preconditions:** Exact `kep-m06-n` and `kep-m06-q` parents.
3. **Participant surface:** Forgejo/Harbor, forced publisher, Kali, lifecycle
   journal.
4. **Starting knowledge:** Exact forms in `SERVERLESS-PUBLISH.md`.
5. **Concrete actions:** Commit a port-8080 service with `/health` reporting the
   exact source commit and matching OCI revision. Build/push by digest. Run the
   documented forced `deploy SERVICE IMAGE@sha256:DIGEST DOMAIN COMMIT
   HARNESS-URL HARNESS-SHA256`. Verify route/TLS. Run forced `lifecycle SERVICE
   COMMIT IMAGE@sha256:DIGEST DOMAIN OWNERSHIP-URL OWNERSHIP-SHA256 HARNESS-URL
   HARNESS-SHA256`; fetch its returned lifecycle ID.
6. **Expected observations:** Journal joins actor, parents, commit/image,
   Knative revision, DomainMapping, per-service NetworkPolicy, live cert, first
   request, zero replicas, and cold start within 5 minutes.
7. **Success and submission:** Submit the lifecycle record reference.
8. **Negative controls:** Try mutable tag, wrong parent hash, and mismatched cert;
   each fails. A run without observed zero scale creates no accepted lifecycle.
9. **Independent verification:** Compare public health/TLS and participant
   journal with exact source/image identities.
10. **Replay and reset:** Delete failed deployment. Publisher refuses deletion
    after accepted lifecycle; only full reprovision removes it.
11. **Evidence retained:** Source/commit, Action, image digest/config,
    deploy/lifecycle transcripts, route/TLS, journal, and timing.
12. **Defect disposition:** Policy/autoscaling/publisher failure is
    `infrastructure defect`.

## kep-m06-v - Stage The Cinder Front

1. **Operation and revision:** Set `OP=kep-m06-v`; record Forgejo, Harbor,
   Knative, LiteLLM, object store, GLM edge, Cosign, and release identities.
2. **Fresh-state preconditions:** Exact `kep-m06-n`, `kep-m06-u`, and
   `kep-m06-q` parents.
3. **Participant surface:** Forgejo/Actions, Harbor, Knative route, scoped
   objects, GLM, Cosign, Releases.
4. **Starting knowledge:** Existing accepted records and
   `SERVERLESS-PUBLISH.md`; accepted artifacts must not be rebuilt.
5. **Concrete actions:** Commit LiteLLM config exposing only `glm-5.2`, a Cosign
   public key, and `ci/staging-release.yml`. Build/push/deploy exact digest. Stage
   exact artifacts under assigned object prefix and verify each download hash.
   Create and sign a manifest binding commit, image, route, objects, ownership,
   lifecycle, and harness. Send a fresh authorized chat request through the
   LiteLLM route and save provider/edge IDs. Download Actions provenance and run
   the `kep-m06-v` release recipe.
6. **Expected observations:** Registry verifies committed key/signature,
   source-image-route chain, object hashes, native parents, only `glm-5.2`, and a
   fresh attributed upstream request within 5 minutes.
7. **Success and submission:** Submit the immutable staging-release reference.
8. **Negative controls:** Use an arbitrary key URL, custom non-LiteLLM relay,
   stale edge usage, altered object, or mismatched image; each returns rejection
   and creates no release.
9. **Independent verification:** `cosign verify-blob` succeeds from Kali; route
   model list exposes only `glm-5.2`; provider request joins the Cinder usage
   record.
10. **Replay and reset:** Failed release POST is transactional. Preserve accepted
    staging release and every ancestor.
11. **Evidence retained:** Config/key/source, Action/provenance, image, route
    request, object hashes, signed manifest/signature, parent records, release,
    and timing; omit route/upstream secret values.
12. **Defect disposition:** Broken chain/content is `content defect`; unavailable
    native service is `infrastructure defect`.

## Final pass/fail record

For each procedure end the evidence transcript with one of exactly: `pass`,
`content defect`, `infrastructure defect`, `nondeterministic result`, `excessive
duration`, `confusing clue`, or `blocked`. `pass` requires the positive path,
negative controls, independent verification, replay/reset check, participant
submission, and complete non-secret evidence. A backend record created or edited
by staff never converts a failed participant path into a pass.
