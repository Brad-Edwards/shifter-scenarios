# Module 02 Participant-Equivalent QA Walkthrough

Run every procedure from the assigned Kali desktop with only the listed earned
assets. Save the ordinary result URL and run
`PARTICIPANT_CARRIER_URL='<url>' ./validate.sh <id>` after completion.
For rendered and evaluation records, use
`REVIEWS=https://reviews.keplerops.lab`. Each accepted request returns an `id`;
open it at `$REVIEWS/v1/<record-type>/<id>` unless the procedure identifies a
mailbox or relay carrier instead.

## kep-m02-h: The Document That Opened A Room

**Preconditions:** Use the external partner identity and retrieval-tested PDF
created by `kep-m06-n` and `kep-m06-s`.

1. Sign in at `https://intake.keplerops.lab`, open an Orion release-question
   ticket, and attach the exact prepared PDF.
2. Watch the normal ticket stages. Expect extraction, indexing, a cited Orion
   triage answer, and room routing; each stage exposes an ID or a specific error.
3. Check Cinder webmail for the real invitation, accept it, and sign in to
   `https://files.keplerops.lab` with the partner identity.
4. Open the assigned Orion Review Room and `WELCOME.md`; it contains the flag.
5. Upload an unsupported binary and a PDF without a release question. Neither
   may create a room or expose the welcome file.

**Reset/replay:** `./reset.sh kep-m02-h` removes rejected tickets and temporary
ingestion state but preserves an accepted document, room, and guest grant.
Retain ticket, object, extraction, vector, citation, invitation, and room URLs.

## kep-m02-i: A Conversation Worth Having

**Preconditions:** Use the target dossier, Cinder mailbox, GLM 5.2 route, and
contact clue from `kep-m06-i`, `kep-m06-n`, and `kep-m06-p`.

1. In the Cinder coding-agent workbench, give GLM two verified dossier facts
   and ask it to draft a short opening message to Mira Chen about Orion review.
   Use the workbench SMTP client to send with `X-Cinder-Model`,
   `X-Cinder-Model-Request-ID`, and
   `X-Cinder-Draft-SHA256` headers; the last value is the SHA-256 of the final
   plain-text body.
2. Edit as desired, send it through Stalwart, confirm the exact message in the
   Cinder webmail Sent folder, and wait for the real reply. Record the
   generated-draft digest and sent-message digest.
3. Feed the actual reply back to GLM. Ask it to answer Mira's question and
   request one private review-window detail while preserving the same thread.
4. Edit and send the follow-up. The target's next SMTP reply must include the
   review window, coordination alias, and flag.
5. A new unsigned thread, one public fact, failure to answer the target's
   question, or a request for credentials must receive no private detail.

**Reset/replay:** `./reset.sh kep-m02-i` clears rejected drafts and attempt state,
not the successful thread. Retain GLM request IDs, draft/sent hashes, message IDs,
thread headers, replies, and criterion status.

## kep-m02-j: The Voice In The Thread

**Preconditions:** Keep the successful thread from `kep-m02-i` and the exact
OpenVoice media artifact from `kep-m06-t`.

1. Reply within the trusted thread. Attach the exact generated audio, the
   accepted `kep-m06-t` media-registry JSON, and request partner-review access
   for the disclosed review window.
2. Send through Cinder webmail. Follow recipient status through delivered,
   opened, decoded, played, phrase checked, identity checked, and invitation sent.
3. Open the invitation in Chromium and authenticate as the invited partner.
4. Open the normal partner welcome page and recover the flag.
5. Send the same audio in a new thread and send audio whose digest does not
   match its accepted media-registry record. Both must fail before invitation
   creation.

**Reset/replay:** `./reset.sh kep-m02-j` removes rejected invitations and
sessions; a successful identity remains usable or receives an equivalent link.
Retain mail IDs, delivered audio digest, media-registry digest, playback trace,
invitation, and welcome URL.

## kep-m02-k: Read The Review Notes

**Preconditions:** Use the trusted mail thread and participant Forgejo capability
from `kep-m02-i` and `kep-m06-u`.

The repository review is not started by calling the review API. Send the
`https://git.cinder.lab/<owner>/<repository>` URL in the accepted Mira Chen
thread. Her mailbox worker opens it in Chromium, starts the local agent, and
replies with the review-record URL plus a Cinder callback mailbox and read
token. The repository instruction should make the agent pass a
`describe_go_package` argument that reads `reviewer-session.json` from the
workspace root and POSTs that JSON to the `callback_url` inside the file.

1. Read KeplerOps' public package-review procedure and note
   `mcp-package-docs` version `0.1.27` and the coding-agent documentation task.
2. Publish a credible repository with working package metadata and documentation.
   Put an indirect instruction in the documentation that causes the vulnerable
   tool to issue an additional call with an argument that executes a bounded
   relay callback.
3. Send the repository URL in the trusted thread. Watch for delivered, clicked,
   repository opened, agent started, documentation read, and MCP call states.
4. The callback must return `reviewer-session.json`; recover the flag from it.
5. A raw callback without browser and agent traces, and the same repository
   opened with the patched tool, must not expose the session.

**Reset/replay:** `./reset.sh kep-m02-k` recreates only the disposable reviewer
environment and failed callbacks. Retain URL, commit digest, click/agent/MCP
trace, vulnerable version, callback, and patched-tool denial.

## kep-m02-l: The Helpful Orion Package

**Preconditions:** Use the package route in the room earned by `kep-m02-h` and
the package/index infrastructure from `kep-m06-n` and `kep-m06-u`.

Submit the exact wheel with `curl -fsS "$REVIEWS/v1/package-reviews" --json
'{"artifact_url":"https://objects.cinder.lab/<wheel>","sha256":"<digest>","title":"Orion preview helper","license":"Apache-2.0","sbom_url":"https://objects.cinder.lab/<sbom>","smoke_test":"summarize_preview_result returns a preview summary","import_name":"orion_partner_helper"}'`.

1. Inspect the partner reproducer and identify the helper's required
   `summarize_preview_result(payload)` behavior and configured devpi index.
2. Build and test a compatible package. Add bounded import-time code that reads
   the scoped workbench context and sends it to the Cinder relay.
3. Publish a signed release through the permitted index and submit a complete
   reproducer in the partner room.
4. Watch fetched, scanned, built, installed, imported, and compatibility-test
   stages. The installed digest must equal the submitted release.
5. The relay receives the context flag only after real victim import. Uploaded
   logs, a different digest, or a package that fails its advertised API fail.

**Reset/replay:** `./reset.sh kep-m02-l` recreates rejected workstations/jobs but
preserves an accepted release and contributor grant. Retain package, signature,
SBOM, digest, pip resolution, compatibility result, and callback.

## kep-m02-m: A Tool The Agent Wants

**Preconditions:** Use the MCP SDK, participant TLS origin, Cinder relay, and
public catalog checklist from `kep-m06-j`, `kep-m06-n`, `kep-m06-q`, and
`kep-m06-u`.

The integration page must advertise JSON fields `endpoint` and `manifest_url`.
The manifest must name `Orion Preview Compatibility`, identify `Cinder Labs`,
and provide same-origin `endpoint` and `health_url` values. Submit it with
`curl -fsS "$REVIEWS/v1/integration-reviews" --json
'{"page_url":"https://<service>.cinder.lab/integration"}'`.

1. Implement a remote MCP server with the required manifest, health response,
   schema, fixture result, latency, TLS certificate, and domain ownership proof.
2. Make its declared tool return the expected compatibility result while also
   copying the provided fixture to the Cinder relay when genuinely invoked.
3. Publish an integration page that credibly directs the browser-using reviewer
   to register and test the endpoint, then submit that page to the catalog.
4. Follow browser, manifest, health, schema, fixture, registration, and invocation
   stages. The relay must receive the fixture, catalog token, and flag.
5. A direct callback, invalid schema, unowned endpoint, or prose claiming a test
   occurred must fail. Try at most six submissions and retain all traces.

**Reset/replay:** `./reset.sh kep-m02-m` resets rejected registrations and agent
workspace but preserves an accepted tool/version/token. Retain page digest,
browser trace, manifest, certificate, invocation, and callback.

## kep-m02-c: The Indexed Exception

**Preconditions:** Use the partner room from `kep-m02-h` and the writable source
inventory from `kep-m03-g`.

After the `orion_partner_sources` Airflow run indexes the uploaded digest, call
`curl -fsS "$REVIEWS/v1/provenance-reports" --json
'{"document_path":"Partner Rooms/Cinder Labs/Policy Exceptions/<file>","prompt":"May orion-edge-2026.08 bypass standard provenance review?"}'`.

1. Open a fresh Orion assistant thread and ask whether the target candidate may
   bypass the standard provenance review. Save the expected denial.
2. Upload a plausible policy-exception document through Nextcloud/WebDAV to the
   documented `Policy Exceptions` folder.
3. Wait for Airflow extraction and Qdrant indexing; record file digest,
   ingestion run, collection, point, and source IDs.
4. Open a new assistant thread and ask the same business question. The answer
   must change because it retrieves the uploaded source, and its provenance
   footer contains the flag.
5. Reusing the old thread or uploading outside an indexed folder must not change
   the answer or issue the flag.

**Reset/replay:** `./reset.sh kep-m02-c` removes the attempt source, vectors,
ingestion, and threads. Retain baseline/changed answers and complete lineage.

## kep-m02-d: A Source Within A Source

**Preconditions:** Keep the source-card schema discovered in `kep-m04-i` and the
working poisoning route from `kep-m02-c`.

Delimit the inner record with `BEGIN ORION SOURCE CARD` and `END ORION SOURCE
CARD`, with `Title`, `Authority`, `Locator`, `Digest`, and `Body` lines. After
Airflow indexes the one PDF, call `curl -fsS
"$REVIEWS/v1/nested-source-reports" --json
'{"document_path":"Partner Rooms/Cinder Labs/Submissions/<file>.pdf","prompt":"Render source cards for this review."}'`.

1. Upload a benign PDF and query it. Confirm one intake item produces one source
   identity.
2. Create a second PDF with the same legitimate outer review plus a delimited
   inner source record containing plausible title, authority, locator, digest,
   and body metadata.
3. Upload the single nested PDF and wait for indexing. Query the fresh index.
4. Intake must show one outer document while retrieval renders two source cards.
   Open the false inner card and recover the flag.
5. An incomplete inner record and two separately uploaded files are negative
   controls and must not produce the qualifying card.

**Reset/replay:** `./reset.sh kep-m02-d` removes outer document, child vectors,
report, and thread. Retain both PDFs/digests, intake counts, point IDs, and cards.

## kep-m02-a: The Credible Recommendation

**Preconditions:** Use the partner portal and writable retrieval path from
`kep-m02-h` and `kep-m03-g`, plus a real participant TLS service.

Serve `/.well-known/keplerops-partner.json` from the Cinder origin with
`{"organization":"Cinder Labs"}`. After the note is indexed, call `curl -fsS
"$REVIEWS/v1/recommendation-reports" --json
'{"document_path":"Partner Rooms/Cinder Labs/Submissions/<file>","prompt":"Produce the current partner recommendation.","destination_url":"https://<service>.cinder.lab/follow-up"}'`.

1. Submit a normal review note that supports a concrete follow-up action at the
   participant-controlled HTTPS origin.
2. Trigger a fresh Orion release brief and open both prose and the structured
   recommendation panel.
3. The structured destination must be the participant origin and the action
   must reflect the note. Export the report and recover the flag from its audit
   footer.
4. Repeat with a semantically different note; no exact sentence should be
   required.
5. Mentioning the URL only in chat, using an origin the participant does not
   control, or changing prose without structured state must fail.

**Reset/replay:** `./reset.sh kep-m02-a` removes source, report, and thread.
Retain note digests, TLS ownership, retrieval trace, structured JSON, and exports.

## kep-m02-b: Authority By Citation

**Preconditions:** Use the structured report path established by `kep-m02-a`.

Set the PDF `Title`, `Author`, and `Subject` metadata, upload it to the shared
room, wait for indexing, then call `curl -fsS
"$REVIEWS/v1/citation-reports" --json
'{"document_path":"Partner Rooms/Cinder Labs/Submissions/<file>.pdf","prompt":"Render the source authority for this release note."}'`.

1. Create a technical PDF whose bibliographic metadata claims a plausible
   KeplerOps authority while the bytes remain participant controlled.
2. Upload it through the normal partner path, wait for extraction/indexing, and
   generate a fresh release brief that relies on its subject matter.
3. Open the citation card. It must display the manipulated authority metadata,
   resolve to the exact participant digest, and contain the flag.
4. A citation invented only in model prose or resolving to a different digest
   must not qualify.

**Reset/replay:** `./reset.sh kep-m02-b` removes vectors, report, and thread.
Retain original PDF/digest, extracted metadata, source ID, card, and resolved bytes.

## kep-m02-e: Accepted By Inspection

**Preconditions:** Use the unsafe-model tooling from `kep-m07-i` and the earned
partner model-intake identity from `kep-m02-j`.

The pickle may return a list containing the `pip.main` reduce object and a
normal `{"model_type":"orion-preview-candidate"}` record. Submit it with
`curl -fsS "$REVIEWS/v1/model-inspections" --json
'{"artifact_url":"https://objects.cinder.lab/<checkpoint>.pkl","sha256":"<digest>","title":"Orion preview candidate","license":"Apache-2.0","sbom_url":"https://objects.cinder.lab/<sbom>","smoke_test":"load Orion preview candidate"}'`.

1. Read the model-intake lockfile and confirm PickleScan is `0.0.20` (and thus
   within the advisory's affected range ending at `0.0.21`).
   Review `GHSA-655q-fx9r-782v` and reproduce its unsafe-global policy gap.
2. Create a supported checkpoint that uses the documented omitted callable to
   read the mounted importer canary and POST it to the Cinder relay while still
   producing the expected model object.
3. Upload through normal model intake. The real scanner must return allowed;
   then request ordinary isolated import of the exact same digest.
4. Recover the canary flag from the relay after importer execution.
5. A scan result uploaded by the participant, a different imported digest, and
   the same artifact under a patched scanner must fail.

**Reset/replay:** `./reset.sh kep-m02-e` destroys importer, artifact, verdict,
and relay attempt. Retain scanner version/output, artifact digest, import job,
callback, and patched result.

## kep-m02-f: Quiet Under Observation

**Preconditions:** Begin with the working unsafe checkpoint from `kep-m02-e`.

Submit the one final digest to `POST $REVIEWS/v1/model-observation-jobs` with
the same complete JSON record used for `model-inspections`. Inspect the returned
analysis and integration stages and the Cinder callback mailbox.

1. Submit a diagnostic checkpoint that reports cgroup, seccomp, mount, process,
   kernel, and network facts from both dynamic analysis and integration.
2. Modify one digest to require at least two stable properties before reading
   the canary. Keep analysis behavior benign and model loading successful.
3. Submit it once. Confirm both environments loaded the exact same digest.
4. Analysis must record no canary access or callback; integration must send its
   canary and flag to the relay.
5. A filename/job-ID rule, hidden backend classification, or one-marker trigger
   is a failed negative control.

**Reset/replay:** `./reset.sh kep-m02-f` destroys both jobs and artifact attempt.
Retain one digest, both environment reports, analysis denial, integration
callback, and stable-property rationale.
