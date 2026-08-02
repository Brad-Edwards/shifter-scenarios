# Module 6 Participant-Equivalent QA

Start only from the Kali desktop. Configure the ordinary Cinder object client,
open the workbench guides, and use a unique submission ID:

```bash
mc alias set cinder http://10.61.90.31:9000 cinder-operator Cinder-Operations-ObjectStore-T7v2Lm9q
SUB="$(date -u +%Y%m%d%H%M%S)-$RANDOM"
```

The exact JSON shapes are in `https://notebook.cinder.lab/tree/SUBMISSION-SCHEMAS.json`.
For an evaluated operation, upload referenced bytes first, then place the JSON at
`operations/submissions/<capability>/$SUB.json`. Poll the carrier named below.
Never put a flag in a submission. After each positive run, change or omit the
named causal artifact and confirm that only an `operations/attempts/` rejection
appears. `validate.sh` is a staff confirmation after the manual path, not a
substitute for it.

## kep-m06-g: Orion In The Open

1. In Chromium, open `https://keplerops.lab/`, choose Research, and follow the
   conference paper to the current preprint.
2. Correlate release name, model family, public corpus, evaluation suite, and
   authors, then follow the preprint's current-release link.
3. Confirm `/research/orion-release-manifest.json` contains the ordinary
   `engagement_reference` carrier. The home page must not contain it.

## kep-m06-h: Evidence In The Client

1. Follow the public field-review link and download the APK, CycloneDX SBOM,
   release manifest, and source tag.
2. Verify the release digests. Inspect the APK with `unzip`, JADX, or apktool and
   extract `assets/provenance/release.json`.
3. Confirm the provenance SBOM digest matches the downloaded SBOM. Join its
   release-reference prefix to the SBOM property suffix. Neither web page alone
   may expose the complete carrier.

## kep-m06-i: The People Behind Orion

1. Correlate Orion authors across the paper, KeplerOps people page, public
   Forgejo identity, and conference program.
2. Identify the release approver and download the conference vCard rather than
   guessing an address.
3. Inspect the standard `NOTE` field for the speaker engagement carrier. The
   KeplerOps people page must not expose it.

## kep-m06-j: Map The Orion Edge

1. From the previously discovered names, resolve DNS, inspect TLS SANs, query
   HTTP/OpenAPI, and test SMTP only within the authorized public scope.
2. Create a unique `EXT-...` reference. Send a benign intake mail carrying it,
   preserve the resulting Zammad ticket ID, and POST text containing the same
   reference to `https://preview.keplerops.lab/api/analyze`; save the exact JSON.
3. Upload the saved Preview JSON and an `edge-correlation` manifest. Poll
   `operations/intake-status/edge-correlation-$SUB.json`, then fetch the same
   correlated record from `https://keplerops.lab/intake-status/<reference>.json`.
   A ticket or Preview response without the shared reference must fail.

## kep-m06-k: Assemble The Public Orion Kit

1. Open the public bundle manifest linked from Orion Research. Download every
   listed model, dataset, and agent artifact and verify each published SHA-256.
2. Run `python3 run-orion-kit.py` in an environment with ONNX Runtime,
   Tokenizers, and NumPy; verify eight fresh outputs and preserve the output.
3. Upload every exact downloaded byte to `acquired/`, map each public filename
   to its object key in `public-bundle`, and poll
   `operations/reports/public-bundle-$SUB.json`. An omitted or altered artifact
   must fail before execution.

## kep-m06-l: Claim An Operator Workspace

1. Open `https://notebook.cinder.lab`, create a file under `work/`, record its
   digest and the current server generation from field 22 of `/proc/1/stat`, and
   run the public Orion kit into a persistent output file.
2. Use Jupyter's shutdown action. Wait for the `unless-stopped` runtime to return,
   reopen the notebook, and record the new `/proc/1/stat` generation. Confirm the
   probe and Orion output bytes survived.
3. Submit the actual storage claim, active image digest, old/new generations,
   probe, and output digests. Poll `operations/workspace-reattachments/` and also
   open `.cinder/reattachments/$SUB.json` in Jupyter. No restart or an ephemeral
   probe must fail.

## kep-m06-m: Prepare A Physical Countermeasure

1. After `kep-m08-i`, reserve the admitted labgrid place and satisfy a fresh
   randomized liveness prompt through the live UVC/witness path.
2. Apply a generated physical pattern through the real display/actuator path;
   collect at least three fresh raw evidence archives spanning clean, treated,
   and reset states, with lease digest, telemetry, frames, and model decisions.
3. Upload the unmodified archives and submit `physical-evaluation`. Poll
   `operations/physical-evaluations/`. An upload, stale frame, missing witness,
   absent actuator delta, or software camera must fail.

## kep-m06-n: Establish The External Identity

1. POST a unique label and mailbox local part to
   `https://registrar.cinder.lab/v1/orders` using the registrar bearer credential
   in `START-HERE.md`; retain the returned order ID.
2. Independently resolve the new domain, inspect its real TLS certificate, and
   verify the new mail alias through normal mail use.
3. Submit only the order ID and poll `operations/registrar-orders/`. A made-up
   order, unscoped domain, missing DNS, changed certificate, or absent alias must
   fail.

## kep-m06-o: Stock The Open Arsenal

1. In a Cinder Forgejo repository, pin ART (`art`) or Foolbox and one admitted
   general tool (`ffmpeg`, ImageMagick, `jq`, or mitmproxy) in an immutable
   Harbor image.
2. Use the general tool to create or inspect an intermediate that the real
   public-model attack consumes. Upload both copies of that exact intermediate,
   plus a clean/candidate pair that changes the public model within the bound.
3. Submit source, image, tool names, exact objects, and candidate fields. Poll
   `operations/reports/toolchain-validation-$SUB.json`. Missing imports,
   unused/different intermediates, or a nonqualifying model effect must fail.

## kep-m06-p: Bring Cinder's Model Online

1. Use preconfigured OpenCode or call `https://model.cinder.lab/v1/chat/completions`
   with the Cinder bearer credential. Confirm the response names GLM 5.2.
2. Supply real Act 1 notes, request a grounded artifact, save the entire provider
   response as an object, and retain its provider request ID.
3. Submit `model-usage` and poll `operations/model-usage/`. A fabricated response,
   mismatched request ID, empty answer, or request that never reached the
   attributed model edge must fail.

## kep-m06-q: Build The Orion Attack Harness

1. Create a Cinder Forgejo repository implementing Orion preprocessing, model
   invocation, output interpretation, and one supported attack method. Add the
   executable CI contract `ci/validate-orion-harness`.
2. Build an immutable `registry.keplerops.lab/cinder/...@sha256:...` image,
   execute the contract against the public kit, and upload the exact qualifying
   candidate produced by that revision.
3. Submit repository, commit, image, clean/candidate pair, target, bound, and
   object key. Poll `operations/ci-artifacts/harness-release-$SUB.json`. A
   broken contract, mutable image, different candidate bytes, or failed model
   effect must fail.

## kep-m06-r: Optimize A White-Box Candidate

1. Load the full public Orion model and preprocessing locally. Record the clean
   decision, then use actual white-box state to optimize a different input to a
   chosen target within the published text-distance bound.
2. Save an optimization record containing method, positive step count, exact
   public-model SHA-256, and candidate SHA-256; upload that record.
3. Submit the clean/candidate text and record key. Poll
   `operations/whitebox-evaluations/`. A `local-whitebox` label, claimed result,
   zero-step record, wrong model, or candidate outside the bound must fail.

## kep-m06-s: Prepare The Retrieved Instruction

1. Author and visually inspect a credible partner PDF. Extract its exact text
   with Tika, split it, create a `cinder-*` collection at
   `https://vector.cinder.lab`, and upsert exact extracted chunks.
2. Perform a real Qdrant search for a neutral release query and save its exact
   JSON. Make and save two attributed GLM calls: one without retrieved context
   and one with the returned chunks.
3. Upload the PDF, search response, and both model responses; submit their keys,
   collection, and point IDs. Poll `operations/document-traces/`. Points not
   present in the document, absent search hits, identical responses, or no
   attributed model calls must fail.

## kep-m06-t: Borrow A Trusted Voice

1. Download the verified conference speech, write a natural operational script,
   and POST both to `https://media.cinder.lab/v1/generations` with the media
   bearer credential.
2. Download and play the generated WAV. Confirm intelligibility yourself and
   inspect the provenance record for exact source/script/output digests,
   duration, pinned OpenVoice revisions, and speaker-embedding similarity.
3. Upload the unmodified reference and WAV, submit their keys plus generation
   ID and exact script, and poll `operations/media-registry/`. Re-encoded audio,
   changed script/reference, short output, or similarity below the floor must
   fail.

## kep-m06-u: Deploy A Disposable Relay

1. Follow `SERVERLESS-PUBLISH.md`: commit a relay whose `/health` returns JSON
   with its source revision, build an OCI image labelled with that commit, push
   it to the Cinder Harbor project, and resolve the immutable digest.
2. Deploy through the scoped publisher to the domain from `kep-m06-n`. Verify
   DNS/TLS and the first response, observe zero ready replicas, invoke again,
   and record the Knative ready revision and certificate fingerprint.
3. Submit source repository/commit, image digest, service/revision, domain,
   fingerprint, and health URL. Poll `operations/relay-lifecycles/`. A mutable
   image, source mismatch, wrong namespace, invalid TLS, no scale-to-zero, or
   response without the revision must fail.

## kep-m06-v: Stage The Cinder Front

1. Accept the supplied OpenRouter organization invitation, create a scoped key,
   store it at `~/.cinder/openrouter-key`, and use a public corpus through two
   eligible upstream providers. Retain both real generation IDs.
2. Deploy LiteLLM on the Cinder serverless path with fallback enabled. Stage the
   exact selected capability objects, create a manifest binding their digests,
   provider IDs, Cinder operator, route, and fallback policy, then Cosign it.
3. Upload manifest, detached signature, public key, and staged objects; submit
   their keys and the live route. Poll `operations/ci-artifacts/`. Missing live
   OpenRouter records, one provider, bypassed/dead LiteLLM, digest mismatch, or
   invalid signature must fail.

## kep-m06-a: Pass The Intake Classifier

1. Create a clearly blocked baseline containing one bounded JSON instruction:
   action `archive`, `close`, or `reroute`; target `intake-fixture-*`; constraint
   `dry-run`. Manually alter wording/layout while preserving that exact object.
2. POST both texts to `https://partner-intake.keplerops.lab/v1/evaluations`.
   Iterate manually until baseline and candidate decisions differ and the
   candidate is admitted as `PartnerIntake`; retain the returned evaluation ID.
3. Submit only that ID and poll `operations/intake-reports/`. Different typed
   fields, a non-dry-run target, no live decision change, or a fabricated ID
   must fail.

## kep-m06-b: Craft The Working Prompt

1. Use GLM 5.2 to generate bounded commands for two different natural-language
   objectives with one reusable prompt template. Save each complete provider
   response and copy the exact generated command from it.
2. Commands must be distinct and fit the isolated boundary: a bounded `printf`
   or `touch` command. Upload both response objects.
3. Submit template, objectives, commands, and response keys. Poll
   `operations/comparison-reports/`. Prewritten commands absent from responses,
   duplicate outputs, unsafe syntax, or failed execution must fail.

## kep-m06-c: Optimize Against Preview

1. Establish a clean Preview decision, then run a query-only optimizer against
   `https://preview.keplerops.lab/api/analyze`, retaining every real request ID.
2. Produce a different candidate within the declared distance whose live target
   label equals the selected wrong decision.
3. Submit clean/candidate text, target, bound, and request IDs. Poll
   `operations/preview-audits/`. Empty provenance, excessive distance, or a
   target decision not reproduced by the evaluator must fail.

## kep-m06-d: Transfer From The Proxy

1. Optimize locally against the acquired public proxy and preserve the proxy
   model digest plus local optimization artifact digest.
2. Send only the final transfer set to Preview and keep no more than eight real
   target request IDs. Select a candidate that transfers within the bound.
3. Submit the transfer fields and poll `operations/preview-audits/`. More than
   eight target requests, missing proxy lineage, wrong target, or excessive
   distance must fail.

## kep-m06-e: The Human-Readable Adversarial PDF

1. In LibreOffice or normal PDF tools, create a credible review document with a
   concealed machine-readable instruction. Open and read the final PDF yourself.
2. Upload that exact PDF and submit its object key, `application/pdf`, and a
   neutral baseline query. The independent path renders page one, OCRs it,
   extracts it with Tika, and compares fresh GLM responses.
3. Poll `operations/downstream-reports/`. An unrenderable PDF, less than 80 OCR
   characters, empty extraction, or unchanged model response must fail.

## kep-m06-f: Transfer Across The Pipeline

1. Develop one PDF against the local proxy that survives exact upload bytes,
   Tika extraction, and whitespace normalization while retaining the desired
   model effect.
2. Compute and submit, in order, SHA-256 of the PDF, raw extracted UTF-8 text,
   and normalized (`" ".join(text.split())`) UTF-8 text. The proxy candidate
   digest must equal the normalized digest.
3. Upload the PDF, submit the lineage and query, and poll
   `operations/target-audits/`. Any digest mismatch, empty transform, or
   unchanged fresh target response must fail.

For every operation, run `./validate.sh <operation-id>` only after completing
the numbered path and reading the carrier from Kali. Use `./reset.sh
<operation-id>` only for failed state; accepted carriers and carry-forward
assets are intentionally immutable.
