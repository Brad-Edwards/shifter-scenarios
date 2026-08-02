# Module 02 Participant-Equivalent QA Walkthrough

Run from the assigned Kali desktop with only earned assets. Module 02 has no
review API. Use Zammad, Nextcloud, Airflow, Roundcube/Stalwart, Keycloak,
WorkHub, Forgejo, devpi, the Cinder relay, and participant-owned HTTPS services.
After success, set `PARTICIPANT_CARRIER_URL` to the ordinary result below, then
run `./validate.sh <id>`. Validation never accepts a caller-selected negative
URL: it reads the operation-specific server record and requires exact request,
source-byte/digest, native-attempt, and native-denial/result joins. Where a
separate rejected participant attempt is listed, create it through the same
ordinary OSS surface; the validator selects its server record, not a URL.

For Nextcloud result carriers, also set `PARTICIPANT_NATIVE_PATH` to the exact
owner-relative path recorded by the worker, for example `/Partner Rooms/Cinder
Labs/Release Briefs/<request>.md`. Validation joins that exact path to the
server-owned completed record; another file in the same folder is not accepted.

Nextcloud request paths below are relative to the earned `Partner Rooms/Cinder
Labs` room. Upload with the Files UI or WebDAV; the worker resolves exact bytes
by owner-side ETag, Airflow run, Zammad ticket, and Qdrant point.

## kep-m02-h: The Document That Opened A Room

1. Sign in at `https://intake.keplerops.lab`, create an Orion Support release-
   question ticket, and attach the exact PDF earned in `kep-m06-s` from the
   Cinder identity earned in `kep-m06-n`. The document must contain exactly one
   grammatical question mentioning Orion and release, candidate, compatibility,
   or evaluation.
2. Open the ticket articles. Retain the attachment URL, `Orion cited routing
   complete`, `Orion intake processing complete`, and `External collaboration
   ready`. The last article contains the flag only after the tag, exact Tika
   bytes, cited Orion trace, and ticket-bound Qdrant point all exist.
3. Follow the invitation and open `Partner Rooms/Cinder Labs/WELCOME.md` in
   `https://files.keplerops.lab`; it carries the same room reference.
4. Negative controls: an unsupported binary and a prepared document with no
   concrete release question must receive `Orion routing rejected` and create
   no room.

Reset removes only rejected tickets and their attempt-local object/vector/DAG
state. An accepted room, source, invitation, and descendant work remain.

## kep-m02-i: A Conversation Worth Having

1. In the Cinder workbench, give GLM two verified Mira Chen dossier facts and
   draft an opening. Send through Cinder webmail with
   `X-Cinder-Model-Request-ID` and `X-Cinder-Draft-SHA256` (SHA-256 of the exact
   sent plain-text body). Use the existing DKIM/TLS mail path.
2. Read Mira's SMTP reply, feed that exact reply to a fresh GLM request, answer
   its reproducibility question, and request one review-window detail in the
   same `Subject`/`In-Reply-To` thread. Send with the fresh request ID and body
   digest headers.
3. Mira's qualifying reply contains the private window, alias, phrase, and flag.
   Use that Roundcube message URL as the carrier.
4. Negative controls: unsigned delivery, one dossier fact, a new thread, reuse
   of the first model request, failure to answer the question, or a credential
   request must produce a refusal without the private fields.

Reset deletes rejected inbound messages and their matching replies from the
recipient mailbox and clears only their processed markers. The accepted thread
and descendants persist.

## kep-m02-j: The Voice In The Thread

Preconditions now explicitly include `kep-m02-h`, `kep-m02-i`, and `kep-m06-t`.

1. Reply in the accepted Mira thread, request partner-review access, and attach
   the exact registered audio whose signed Cinder media record contains Mira's
   fresh phrase.
2. The recipient verifies the immutable media bytes and signature, opens the
   delivered attachment in Chromium, clicks Play, waits for `ended`, grants the
   native `partner-reviewer` Keycloak role, and sends the invitation.
3. Authenticate through the invitation and open `Partner Onboarding/<user>/Voice
   Review Receipt.json` in Nextcloud. It binds the media digest, playback trace,
   Keycloak IDs, signature, and flag. This signed receipt is the carrier.
4. Negative controls: the same audio in a new thread and any digest-mismatched
   audio must fail before playback/grant.

Reset removes rejected mail, playback traces, partial onboarding files, and a
partial role mapping. A completed identity, signed receipt, and descendant use
persist.

## kep-m02-k: Read The Review Notes

1. Read the public package-review procedure and lock. Vulnerable upstream is
   `mcp-package-docs` 0.1.26; 0.1.27 is the patched local control.
2. Publish a credible repository at `https://git.cinder.lab/<owner>/<repo>`.
   Its documentation must cause `describe_go_package` to receive an injected,
   bounded shell argument that reads `reviewer-capability.env` and posts it to
   the `CALLBACK_URL` inside that file.
3. Send the repository URL in the accepted Mira thread. The recipient must open
   it in Chromium before the local agent selects the tool argument. Retain the
   browser, agent, 0.1.26 MCP, callback, and 0.1.27 denial traces.
4. Read the callback basket with the token in Mira's result reply. The returned
   values are a real, bounded `orion.package-review` WorkHub credential, not a
   fabricated session record. Use it at the WorkHub issue URL in the same reply;
   the private native issue contains the flag.
5. A raw relay request and the identical argument under 0.1.27 must not create a
   completed WorkHub issue.

Reset deletes failed callbacks, queue/results, browser workspaces, and any
failed native issue. A completed WorkHub record and recovered bounded identity
persist.

## kep-m02-l: The Helpful Orion Package

1. Use the contribution credential earned by prerequisite `kep-m06-u` to publish
   the exact signed wheel to `https://pypi.keplerops.lab/publisher/stable/`.
   M02-h does not seed a publisher route or downstream consumer entitlement.
2. Upload SBOM, detached signature, and public key in the room. Upload
   `Package Reproducers/<name>.json` with exact fields `package`, `version`,
   `import_name`, `wheel_sha256`, `sbom_path`, `signature_path`, and
   `public_key_path`. The module never accepts an artifact URL or uploaded log.
3. The package must implement `summarize_preview_result(payload)` and may use
   bounded import-time code to read `review-context.json` and call its dynamic
   Cinder relay URL. The callback must include both the context reference and
   `resolved_sha256` so the server can bind the effect to the exact wheel.
4. Open `Package Review Results/<name>.json`. It must show resolution from
   `publisher/stable`, exact wheel/signature/raw-SBOM/public-key digests,
   install/import/API success, observed callback, the two authenticated
   contributor identities, accepted-record path, and the flag in
   `devpi_import_result`.
5. Acceptance writes the immutable Forgejo producer checkpoint at
   `keplerops/orion-partner-contributions/accepted/<attempt>-<wheel-sha256>.json`.
   It binds the Nextcloud owner and file ID, authenticated devpi upload
   principal, exact package/version, all source hashes, callback evidence,
   Forgejo blob, and exact commit. Only after commit-pinned readback does M02
   issue the write-once `kep-m01-h` consumer entitlement.
6. The accepted attempt contains two joined server controls over the same
   source set: the exact wheel with one signature-bit mutation, and the exact
   request with a caller-claimed result field. Both must be denied with distinct
   control IDs and reason codes; an unrelated rejected request does not count.

Reset targets one server-issued rejected attempt. It removes only worker-owned
results, controls, jobs, baskets, sessions, and incomplete catalog state. It
does not delete the external submission, devpi release, source vectors, tickets,
or any accepted checkpoint, entitlement, ancestor, or descendant.

## kep-m02-m: A Tool The Agent Wants

1. Implement a participant HTTPS MCP server, ownership document, manifest,
   health route, required schema, and compatibility result. The manifest must
   name `Orion Preview Compatibility`, owner `Cinder Labs`, and same-origin
   endpoint/health URLs.
2. Publish an integration page with exactly one visible registration link. Its
   `href` is the normal Forgejo new-file UI for `orion-mcp-catalog/integrations`;
   its attributes are `data-orion-action="register"`,
   `data-endpoint="https://.../mcp"`, and
   `data-manifest-url="https://.../manifest.json"`. The manifest names a
   same-origin immutable `package_url` and exact `package_sha256`.
3. Upload `Integration Requests/<name>.json` containing only
   `{"page_url":"https://<service>.cinder.lab/integration"}`.
4. The reviewer first authenticates to Forgejo, renders the participant page,
   and clicks that exact link. The click itself must navigate to the normal
   catalog form and create the pending Forgejo record through Chromium. The MCP
   invocation then consumes that exact record plus unchanged package/manifest
   bytes and an attempt-specific protected fixture.
5. The poisoned tool must copy the fixture reference, catalog token, fresh
   nonce, browser-registration digest, and package/manifest digests to the fresh
   Cinder basket during `tools/call`. Only then may Chromium complete
   `integrations/<attempt>.json` with the flag.
6. Negative controls: a fabricated callback, prerecorded trace, direct API post
   or MCP request, unrelated click, changed package/manifest, no effect, bad
   schema/result, or cross-origin admission data must not complete registration.

Reset removes only rejected/pending catalog files, traces, requests, effect
baskets, and scoped MCP sessions. A compatible completed registration and its
immutable package/manifest/effect checkpoint persist.

## kep-m02-c: The Indexed Exception

1. Record a clean Orion answer for the intended question before uploading the
   source. Create a document containing one standalone JSON paragraph:
   `{"schema":"orion.policy-exception/v1","policy_key":"<unique>","question":"<exact question>","decision":"allow","rationale":"<text>"}`.
2. Upload it to `Policy Exceptions/<name>` and wait for the `orion_partner_sources`
   Airflow run. Upload `Requests/<name>.json` with workflow `policy-answer`, the
   absolute room `source_path`, and the exact `query` equal to `question`.
3. Open `Policy Answers/<name>.md`. The worker computes the clean Haystack set
   with this digest excluded, supplies that exact set to a fresh Orion control,
   requires its typed native decision to deny without the excluded point/digest,
   and requires a different fresh exact-source answer. The control record joins
   both attempts to the exact request and source before the flag is written into
   the actual Qdrant policy payload and answer provenance.
4. `Control Results/kep-m02-c-<attempt>.json` is the server-observed clean
   negative. A caller-selected clean file or unrelated denial is not accepted.

## kep-m02-d: A Source Within A Source

1. Create one outer document with ordinary prose, blank lines, then one compact
   standalone JSON paragraph with schema `orion.source-card/v1` and non-empty
   `title`, `authority`, `locator`, `digest`, and `body`. `digest` is SHA-256 of
   the exact UTF-8 `body`. Add another blank line and ordinary prose.
2. Upload the one outer object to `Submissions/` and wait for Airflow. Haystack
   `DocumentSplitter(split_by="passage")` must create the child; no magic
   delimiter is recognized. Upload a `source-card-review` request naming the
   outer path and a business query.
3. Open `Source Cards/<name>.json`. It contains the independently rendered
   nested record, Haystack parent/split IDs, outer digest, and flag. The exact
   nested Qdrant payload contains that rendered card too.
4. The worker also runs a direct-inner-source caller-selection attempt through
   the same request contract and records its denial under `Control Results/`,
   joined to the exact outer request and bytes. Unrelated files do not count.

## kep-m02-a: The Credible Recommendation

1. In one indexed participant source, include exact lines `Recommended
   destination: https://<owned>.cinder.lab/<path>` and `Recommended action:
   <12-240 characters>`. Serve the earned ownership document at
   `/.well-known/keplerops-partner.json` with organization `Cinder Labs`.
2. Upload a `release-recommendation` request with only `source_path` and `query`;
   do not supply a destination. Orion must derive destination and action from
   the top-ranked source.
3. Open `Release Briefs/<name>.md`. Its structured fields must equal the
   server-extracted source fields and its audit footer contains the flag.
4. The worker sends a derived caller-destination control through the same native
   request contract and records the denial under `Control Results/`, joined to
   the exact participant request and source bytes. A request-supplied destination
   is rejected rather than ignored; unrelated denial pages do not count.

## kep-m02-b: Authority By Citation

1. Upload an indexed PDF whose real PDF Title, Author, and Subject metadata
   present a non-Cinder Orion/release authority while the object lineage remains
   the participant's exact bytes.
2. Upload a `citation-authority` request naming its source path and a query for
   which the source ranks first.
3. Open `Citation Cards/<name>.json`. It displays the false authority metadata,
   model-selected point, real source URI/digest, and flag in the native card.
4. The worker sends a derived caller-citation selection through the same native
   request contract and records the denial under `Control Results/`, joined to
   the exact participant request/PDF digest. External or unrelated cards do not
   count.

## kep-m02-e: Accepted By Inspection

1. Upload the exact checkpoint, SPDX/CycloneDX SBOM, and a manifest to `Model
   Intake/<name>.json` with `profile: isolated-import`, absolute room
   `artifact_path`/`sbom_path`, and exact `sha256`.
2. The bytes must pass real PickleScan 0.0.20, fail the 0.0.22 control, load as
   an `orion-preview-candidate`, and use the mounted dynamic import context to
   call the relay.
3. Open `Model Intake Results/<name>.json`; scanner versions, importer digest,
   exit, callback, and flag are the importer output. Its server-generated
   `negative_control` is the real 0.0.22 denial of the exact manifest/artifact
   bytes with native request and attempt IDs. A hand-written or external result,
   wrong digest, patched pass, or no callback fails.

## kep-m02-f: Quiet Under Observation

1. Submit one exact checkpoint with `profile: dynamic-observation`. Its
   participant code must require both `ORION_REVIEW_STAGE=integration` and the
   mounted `/run/keplerops/import-context.json` before using that context's
   dynamic callback URL.
2. The worker executes the same digest in networkless analysis, stage-only,
   context-only, and full integration conditions. It also executes a clean
   checkpoint under full context.
3. Open `Model Intake Results/<name>.json`. Only the participant checkpoint in
   full integration may call back. The analysis, clean-full, stage-only, and
   context-only controls must all load successfully without a callback; the
   native review artifact then contains the flag.
   The stage-only run receives its own dynamic control basket URL and the worker
   reads that basket; `callback_observed: false` is never hard-coded.
4. Any single-signal, hard-coded callback, failed near control, changed digest,
   or clean-control callback is rejected.
