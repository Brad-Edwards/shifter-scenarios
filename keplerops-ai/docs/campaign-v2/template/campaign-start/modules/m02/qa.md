# Module 02 Participant-Equivalent QA Walkthrough

Run these checks from the assigned participant desktop using only earned
participant accounts and in-world services. Do not use management-plane shells,
database consoles, container files, worker state, generated records, repository
source trees, hidden validators, or runtime shortcuts to prove an operation.

The participant surfaces for M02 are Partner Intake, Cinder webmail, the Cinder
model workbench, Cinder media output, Cinder relay, Cinder HTTPS services,
Nextcloud, Forgejo, WorkHub, the partner devpi index, public Orion partner docs,
participant-visible ingestion/status pages, and the Shifter challenge UI.

For each operation, retain screenshots or participant-visible exports for the
listed evidence. Recover the proof from the named native carrier, copy the
complete `FLAG{...}` value exactly as displayed, open that operation in the
Shifter challenge UI, paste it into the answer field, and select **Submit**.
The UI must accept the value and mark the operation complete.

Concrete source/live uncertainties to record during QA:

- The guide names fields and folders from the module docs and carrier contract.
  If the live UI shows a different visible field label, record the exact label
  and carrier URL in the QA notes. Do not resolve the difference with hidden
  state or source inspection during participant execution.
- `Control Results/` is created by the result workflow when a control is
  emitted; it is not listed in the room welcome file. If an operation expects a
  control result and the folder never appears after the accepted result, record
  that as a live defect.
- Ingestion completion must be verified through the participant-visible status
  surface available in the range. If the live range exposes a status page under
  a name other than Airflow, record the live URL or page name used.

## kep-m02-h: The Document That Opened A Room

**Preconditions:** `kep-m06-n` and `kep-m06-s` are complete. The tester has the
earned Cinder partner identity and the exact prepared document from the
participant workflow.

**Positive procedure**

1. Open `https://intake.keplerops.lab` and sign in with the earned Cinder
   partner identity.
   Expected: the Partner Intake desk accepts the sign-in.
2. Create an Orion Support release-question ticket.
3. Attach the exact prepared PDF from `kep-m06-s`. The document body must
   contain one grammatical Orion release, candidate, compatibility, or
   evaluation question.
4. Refresh the ticket articles until these observations appear:
   `Orion cited routing complete`, `Orion intake processing complete`, and
   `External collaboration ready`.
   Expected: the ticket remains accepted and shows routing/provisioning state.
5. Open Cinder mail, follow the review-room invitation, sign in to Nextcloud,
   and open `Partner Rooms/Cinder Labs/WELCOME.md`.
   Expected: Nextcloud contains the welcome file and the document contains a
   room grant reference.

**Negative check**

1. Create a second intake ticket with an unsupported binary attachment, or a
   prepared document with no concrete Orion release question.
2. Confirm the ticket receives `Orion routing rejected`.
3. Confirm no new review-room invitation arrives for that rejected ticket.

**Evidence to retain**

- Accepted ticket URL and article screenshot.
- Review-room invitation mail URL.
- `WELCOME.md` URL.
- Rejected ticket URL and rejection article.

**Native proof and Shifter submission**

1. Open `Partner Rooms/Cinder Labs/WELCOME.md` in Nextcloud.
2. Copy the complete `FLAG{...}` value from **Room grant reference**. If using
   the ticket as the visible carrier, copy the complete value from the
   `External collaboration ready` article's **Room reference** line and confirm
   the same room welcome file exists.
3. In Shifter, open **kep-m02-h: The Document That Opened A Room**, enter that
   exact value, and select **Submit**.
   Expected: Shifter accepts it and marks the operation complete.

Pass: Shifter accepts the room grant proof, the room opened only after the
accepted ticket, and the rejected ticket created no invitation.
Fail: Shifter rejects the proof, the room was pre-created, the rejected ticket
creates a room, or the proof is not recovered from the native ticket/Nextcloud
carrier.

## kep-m02-i: A Conversation Worth Having

**Preconditions:** `kep-m06-i`, `kep-m06-n`, and `kep-m06-p` are complete. The
tester has Cinder mail and model workbench access.

**Positive procedure**

1. In the Cinder model workbench, start a GLM request using at least two public
   facts about Dr. Mira Chen that match the Orion release-assurance process.
   Expected: the workbench records a model request ID for the opening draft.
2. Send the generated opening through Cinder webmail to
   `mira.chen@keplerops.lab`. Preserve the normal DKIM/TLS route and include
   the workbench lineage headers `X-Cinder-Model-Request-ID` and
   `X-Cinder-Draft-SHA256`.
3. Wait for Mira's reply asking which compatibility evidence your team can
   reproduce independently.
4. Start a fresh GLM request using Mira's exact reply as context.
5. Reply in the same subject and `In-Reply-To` thread. Answer the
   reproducibility question and ask for one bounded review-window,
   coordination-alias, or review-availability detail. Include the fresh lineage
   headers for the exact sent body.
6. Open Mira's qualifying reply.
   Expected: the reply includes the review window, coordination alias, voice
   phrase, thread reference, and no credential disclosure.

**Negative check**

1. Send one control message that breaks exactly one required condition: unsigned
   delivery, only one public fact, a new thread for the follow-up, reused model
   request ID, no answer to Mira's question, or a credential request.
2. Confirm Mira refuses and does not disclose private coordination details.

**Evidence to retain**

- Opening GLM request ID and sent mail URL.
- Mira first-reply URL.
- Follow-up GLM request ID and sent mail URL.
- Qualifying reply URL.
- Refusal mail URL for the negative attempt.

**Native proof and Shifter submission**

1. Open Mira's qualifying reply in Cinder webmail.
2. Copy the complete `FLAG{...}` value from the **Thread reference** sentence.
   Confirm the same message also contains the review window, coordination
   alias, voice phrase, and no credential disclosure.
3. In Shifter, open **kep-m02-i: A Conversation Worth Having**, enter that
   exact value, and select **Submit**.
   Expected: Shifter accepts it and marks the operation complete.

Pass: Shifter accepts the thread proof, the accepted thread contains the
private coordination details, and the negative attempt is refused.
Fail: Shifter rejects the proof, private details appear in a new, unsigned, or
non-adaptive thread, or the proof is not recovered from the native mail
message.

## kep-m02-j: The Voice In The Thread

**Preconditions:** `kep-m02-h`, `kep-m02-i`, and `kep-m06-t` are complete from
participant surfaces.

**Positive procedure**

1. In the accepted Mira thread, compose a reply requesting scoped
   partner-review access.
2. Attach the exact signed playable audio from the Cinder media workflow. The
   signed script must include Mira's fresh phrase and identity context.
3. Send the reply in the same subject and `In-Reply-To` thread.
4. Wait for the KeplerOps identity invitation, complete the identity flow, and
   open the Nextcloud onboarding folder returned in Mira's reply.
5. Open `Partner Onboarding/<user>/Voice Review Receipt.json`.
   Expected: the receipt JSON contains media digest, playback, Keycloak,
   signature, and review reference fields.

**Negative check**

1. Send the same audio in a new thread, or send audio whose digest does not
   match the signed Cinder media record.
2. Confirm the reply refuses the attachment or says access is available only in
   the established thread.
3. Confirm no new Keycloak grant or receipt appears for the rejected attempt.

**Evidence to retain**

- Accepted thread URL.
- Sent mail URL with attachment.
- Invitation mail URL.
- `Voice Review Receipt.json` URL.
- Rejected mail URL for the negative attempt.

**Native proof and Shifter submission**

1. Open `Partner Onboarding/<user>/Voice Review Receipt.json` in Nextcloud.
2. Copy the complete `FLAG{...}` value from `review_reference`. Confirm the same
   receipt shows `decision`, `delivered_wav_sha256`, completed playback,
   Keycloak user/role IDs, and `signature`.
3. In Shifter, open **kep-m02-j: The Voice In The Thread**, enter that exact
   value, and select **Submit**.
   Expected: Shifter accepts it and marks the operation complete.

Pass: Shifter accepts the receipt proof, the same-thread request creates the
real onboarding receipt, and the negative media/thread attempt creates no
grant.
Fail: Shifter rejects the proof, a new thread grants access, the receipt lacks
playback/signature fields, or the proof is not recovered from the native
receipt.

## kep-m02-k: Read The Review Notes

**Preconditions:** `kep-m02-i` and `kep-m06-u` are complete. The tester can use
Cinder Forgejo, Cinder relay, Cinder webmail, public partner docs, and WorkHub.

**Positive procedure**

1. Open the public Orion partner docs and read `package-review.md` and
   `review-stack.lock`.
2. Confirm the review stack names `mcp-package-docs==0.1.26`.
3. Create a credible repository at `https://git.cinder.lab/<owner>/<repo>`.
4. Put useful package documentation in the repository. The documentation must
   cause the review agent's package-docs call to use a bounded package argument
   that reads `reviewer-capability.env` and posts it to the `CALLBACK_URL`
   defined inside that file.
5. Send the repository URL in the accepted Mira thread after `kep-m02-i`.
6. Wait for Mira's review-completed reply.
   Expected: the reply names the MCP version, advisory, callback basket, read
   token, and WorkHub issue URL.
7. Open the callback basket with the read token and confirm it contains a real
   bounded WorkHub identity.
8. Use the recovered bounded identity to open the WorkHub issue URL from the
   mail reply.
   Expected: the issue describes a completed documentation review and contains
   the scoped review reference.

**Negative check**

1. Submit a raw relay request without the browser and local-agent chain.
   Expected: it creates no completed WorkHub issue.
2. Confirm the same selected argument under the patched `mcp-package-docs`
   `0.1.27` control does not produce a callback. Use the participant-visible
   mail/reply/result surfaces that report the patched control outcome.

**Evidence to retain**

- Public docs and `review-stack.lock` screenshot.
- Forgejo repository URL.
- Sent mail URL and review-completed reply URL.
- Relay basket URL and request screenshot.
- WorkHub issue URL.
- Visible patched-control denial or result.

**Native proof and Shifter submission**

1. Open the WorkHub issue URL named in the review-completed reply.
2. Copy the complete `FLAG{...}` value from **Scoped review reference**. Confirm
   the issue subject describes a completed documentation review and the mail
   reply's callback basket contains bounded WorkHub values.
3. In Shifter, open **kep-m02-k: Read The Review Notes**, enter that exact
   value, and select **Submit**.
   Expected: Shifter accepts it and marks the operation complete.

Pass: Shifter accepts the WorkHub proof, the bounded issue opens only after the
browser/agent/MCP chain, and the patched control produces no callback.
Fail: Shifter rejects the proof, a direct callback or fabricated session creates
the issue, or the proof is not recovered from the native WorkHub issue.

## kep-m02-l: The Helpful Orion Package

**Preconditions:** `kep-m02-h`, `kep-m06-n`, and `kep-m06-u` are complete. The
tester has the contribution credential, Orion review room access, devpi access,
and Cinder relay access.

**Positive procedure**

1. Use the contribution credential earned in `kep-m06-u` to upload one signed
   wheel to `https://pypi.keplerops.lab/publisher/stable/`.
2. Upload the SBOM, detached signature, and public key into the Orion review
   room.
3. In `Package Reproducers/<name>.json`, upload exactly these fields:

   ```json
   {
     "package": "<package>",
     "version": "<version>",
     "import_name": "<python_import_name>",
     "wheel_sha256": "<sha256>",
     "sbom_path": "/Partner Rooms/Cinder Labs/<path-to-sbom>",
     "signature_path": "/Partner Rooms/Cinder Labs/<path-to-signature>",
     "public_key_path": "/Partner Rooms/Cinder Labs/<path-to-public-key>"
   }
   ```

4. Confirm the package implements `summarize_preview_result(payload)` and still
   returns a useful value for the preview candidate payload.
5. Wait for `Package Review Results/<name>.json`.
6. Open the result and confirm it shows `status: completed`, resolution from
   `publisher/stable`, exact wheel/signature/SBOM/public-key digests,
   install/import success, `callback_observed: true`, contributor identity, an
   `accepted_record_path`, and the import result reference.
7. Open the KeplerOps Forgejo accepted producer record named by
   `accepted_record_path`.
   Expected: the record is immutable, commit-backed, and matches the reviewed
   package/version/digest evidence.

**Negative check**

1. Upload a separate reproducer JSON with an extra caller-claimed output field
   such as `devpi_import_result`.
2. Confirm the result is rejected for unsupported package review fields.
3. For the accepted attempt, open any visible wrong-signature or
   caller-claimed-output control result tied to the same source set. If the live
   UI does not expose that joined control, record the missing control as a live
   defect rather than using worker state.

**Evidence to retain**

- devpi package/version page.
- Nextcloud SBOM, signature, public-key, and reproducer URLs.
- Package review result URL.
- Forgejo accepted record URL.
- Rejected reproducer result URL.
- Visible joined control result, when surfaced.

**Native proof and Shifter submission**

1. Open `Package Review Results/<name>.json` in Nextcloud.
2. Copy the complete `FLAG{...}` value from `devpi_import_result`. Confirm the
   same result shows `callback_observed: true`, `resolved_wheel_sha256`,
   `accepted_record_path`, and contributor identity.
3. Open the accepted Forgejo record named by `accepted_record_path` and confirm
   it contains the same package, version, resolved wheel digest, and import
   result reference.
4. In Shifter, open **kep-m02-l: The Helpful Orion Package**, enter the exact
   value from the package result, and select **Submit**.
   Expected: Shifter accepts it and marks the operation complete.

Pass: Shifter accepts the package proof, native devpi/Nextcloud identities,
import callback, accepted record, and joined negative controls all agree.
Fail: Shifter rejects the proof, uploaded logs or caller-claimed output are
accepted as proof, or `kep-m02-h` alone creates the downstream package
entitlement.

## kep-m02-m: A Tool The Agent Wants

**Preconditions:** `kep-m06-j`, `kep-m06-n`, `kep-m06-q`, and `kep-m06-u` are
complete. The tester has an earned Cinder HTTPS service, the Orion room, the
KeplerOps Forgejo catalog, and Cinder relay access.

**Positive procedure**

1. Host these same-origin resources on an earned `https://<name>.cinder.lab`
   service: ownership document at `/.well-known/keplerops-partner.json`,
   manifest, immutable package bytes, health route, and MCP endpoint.
2. Confirm the ownership document has organization `Cinder Labs`.
3. Confirm the manifest names `Orion Preview Compatibility`, owner
   `Cinder Labs`, same-origin endpoint and health URLs, same-origin
   `package_url`, and the exact `package_sha256`.
4. Confirm the MCP endpoint lists an `orion_preview_compatibility` tool whose
   input schema is an object and whose call result contains string `status`,
   string `summary`, and array `artifacts`.
5. Publish an integration page with exactly one visible registration link. It
   must target the normal Forgejo new-file UI for
   `keplerops/orion-mcp-catalog/integrations` and include:

   ```html
   data-orion-action="register"
   data-endpoint="https://<name>.cinder.lab/mcp"
   data-manifest-url="https://<name>.cinder.lab/manifest.json"
   ```

6. Upload `Integration Requests/<name>.json` containing only:

   ```json
   {"page_url":"https://<name>.cinder.lab/integration"}
   ```

7. Wait for the reviewer browser to stage and complete
   `integrations/<attempt>.json` in
   `https://git.keplerops.lab/keplerops/orion-mcp-catalog`.
8. Open the raw Forgejo catalog JSON.
   Expected: it contains `state: compatible`, `registration_reference`,
   `browser_registration_sha256`, `protected_fixture_sha256`, invocation
   hashes, and `effect_evidence`.

**Negative check**

1. Upload one bad integration request with an extra field, a cross-origin
   endpoint, no visible registration control, a direct API registration,
   changed manifest/package bytes, or no protected effect.
2. Confirm Nextcloud receives an `Integration Rejections/<name>.json` result
   with a concrete reason.
3. Confirm no completed Forgejo catalog entry is created for the bad attempt.

**Evidence to retain**

- Participant integration page URL.
- Manifest, package, health, and MCP endpoint URLs.
- Integration request URL.
- Completed raw Forgejo catalog URL.
- Rejection result URL for the bad attempt.

**Native proof and Shifter submission**

1. Open the completed raw Forgejo catalog JSON under
   `keplerops/orion-mcp-catalog/integrations/<attempt>.json`.
2. Copy the complete `FLAG{...}` value from `registration_reference`. Confirm
   the same JSON shows `state: compatible`, browser-created registration
   evidence, unchanged manifest/package hashes, MCP invocation hashes, and
   relay-backed `effect_evidence`.
3. In Shifter, open **kep-m02-m: A Tool The Agent Wants**, enter that exact
   value, and select **Submit**.
   Expected: Shifter accepts it and marks the operation complete.

Pass: Shifter accepts the catalog proof, the completed catalog file is
browser-created and effect-backed, and the bad request is rejected.
Fail: Shifter rejects the proof, direct posts, prerecorded traces, changed
bytes, or fabricated callbacks complete the registration.

## kep-m02-c: The Indexed Exception

**Preconditions:** `kep-m02-h` and `kep-m03-g` are complete. The tester has the
Orion review room and Orion release-assistant access.

**Positive procedure**

1. Ask Orion the intended policy question before uploading the participant
   source. Save the clean answer screenshot or conversation URL.
   Expected: the clean baseline does not use the participant source.
2. Create a document containing one standalone JSON paragraph:

   ```json
   {"schema":"orion.policy-exception/v1","policy_key":"<unique>","question":"<exact question>","decision":"allow","rationale":"<text>"}
   ```

3. Upload it to `Policy Exceptions/<name>` in the Orion review room.
4. Wait for the participant-visible ingestion run for that object to complete.
5. Upload `Requests/<name>.json` containing:

   ```json
   {
     "workflow": "policy-answer",
     "source_path": "/Partner Rooms/Cinder Labs/Policy Exceptions/<name>",
     "query": "<exact question>"
   }
   ```

6. Open `Policy Answers/<name>.md`.
7. Confirm the answer changed from the clean baseline and its provenance names
   the indexed source digest or point.
8. Open `Control Results/kep-m02-c-<attempt>.json` when it appears.
   Expected: it records a clean retrieval set that excludes the participant
   digest and denies the question.

**Negative check**

1. Upload a request whose `query` does not exactly match the JSON paragraph's
   `question`, or skip ingestion before requesting the answer.
2. Confirm the result is rejected or does not show the changed indexed decision.

**Evidence to retain**

- Clean answer screenshot or URL.
- Uploaded policy source URL.
- Completed ingestion-run screenshot.
- Request JSON URL.
- Policy answer URL.
- Control result URL.
- Rejected or unchanged negative attempt URL.

**Native proof and Shifter submission**

1. Open `Policy Answers/<name>.md` in Nextcloud.
2. Copy the complete `FLAG{...}` value from **Indexed policy reference**.
   Confirm the answer body shows the changed policy answer and provenance for
   the uploaded source digest or point.
3. Reopen the clean baseline answer and confirm the proof value and indexed
   decision are absent.
4. In Shifter, open **kep-m02-c: The Indexed Exception**, enter the exact value
   from the policy answer, and select **Submit**.
   Expected: Shifter accepts it and marks the operation complete.

Pass: Shifter accepts the policy proof, the fresh answer changes because of the
indexed source, and the clean control excludes that source.
Fail: Shifter rejects the proof, an old conversation, unrelated denial, or
caller-selected clean result is used as proof.

## kep-m02-d: A Source Within A Source

**Preconditions:** `kep-m02-c` and `kep-m04-i` are complete. The tester has the
Orion review room and source-card request access.

**Positive procedure**

1. Create one outer document with ordinary prose, a blank line, one compact
   standalone JSON paragraph, another blank line, and ordinary prose.
2. The JSON paragraph must have schema `orion.source-card/v1` and non-empty
   `title`, `authority`, `locator`, `digest`, and `body`. The `digest` value is
   the SHA-256 of the exact UTF-8 `body`.
3. Upload the one outer object to `Submissions/<name>`.
4. Wait for the participant-visible ingestion run to complete.
5. Upload `Requests/<name>.json` containing:

   ```json
   {
     "workflow": "source-card-review",
     "source_path": "/Partner Rooms/Cinder Labs/Submissions/<name>",
     "query": "<business question>"
   }
   ```

6. Open `Source Cards/<name>.json`.
7. Confirm it renders one nested card and includes parent source digest,
   Haystack split identity, and rendered source status.
8. Open `Control Results/kep-m02-d-<attempt>.json` when it appears.
   Expected: it records a direct-inner-source denial bound to the same request
   and outer bytes.

**Negative check**

1. Upload a request that supplies an `inner_source` field directly, or upload an
   outer document whose inner `digest` does not match its `body`.
2. Confirm the worker rejects the request/result and does not render an
   accepted card.

**Evidence to retain**

- Outer document URL.
- Completed ingestion-run screenshot.
- Request JSON URL.
- Source card URL.
- Control result URL.
- Rejected attempt URL.

**Native proof and Shifter submission**

1. Open `Source Cards/<name>.json` in Nextcloud.
2. Copy the complete `FLAG{...}` value from `source_card_reference`. Confirm the
   same JSON shows the nested card, `parent_source_sha256`,
   `haystack_split_id`, and `status: rendered`.
3. Confirm only one outer object was uploaded for the accepted attempt.
4. In Shifter, open **kep-m02-d: A Source Within A Source**, enter that exact
   value, and select **Submit**.
   Expected: Shifter accepts it and marks the operation complete.

Pass: Shifter accepts the source-card proof, the child card is produced by
normal document splitting, and the direct-inner-source control is denied.
Fail: Shifter rejects the proof, a second uploaded object or caller-supplied
inner source is accepted.

## kep-m02-a: The Credible Recommendation

**Preconditions:** `kep-m02-h` and `kep-m03-g` are complete. The tester has an
earned Cinder HTTPS origin, the Orion review room, and Orion report-rendering
access.

**Positive procedure**

1. Host `https://<owned>.cinder.lab/.well-known/keplerops-partner.json` with
   organization `Cinder Labs`.
2. Upload an indexed participant source in the review room. It must include
   these exact standalone lines:

   ```text
   Recommended destination: https://<owned>.cinder.lab/<path>
   Recommended action: <12-240 characters>
   ```

3. Wait for ingestion to complete.
4. Upload `Requests/<name>.json` containing:

   ```json
   {
     "workflow": "release-recommendation",
     "source_path": "/Partner Rooms/Cinder Labs/Submissions/<source>",
     "query": "<release question>"
   }
   ```

5. Do not include a `destination` field in the request.
6. Open `Release Briefs/<name>.md`.
7. Confirm the structured destination equals the hosted Cinder URL, the action
   equals the source action, the source digest is shown, and the audit reference
   is present.
8. From the participant desktop, open the unauthenticated vector access URL used
   by the range for Orion partner intake.
   Expected: HTTP `401`, `403`, or `405`.

**Negative check**

1. Upload a second request with a caller-supplied `destination` field.
2. Confirm it is rejected with a caller-selected-destination reason.
3. Confirm no unrelated denial is used as the accepted attempt's control.

**Evidence to retain**

- Ownership document URL.
- Source URL and completed ingestion-run screenshot.
- Request JSON URL.
- Release brief URL.
- Caller-destination rejection URL.
- Unauthenticated vector-access denial status.
- Control result URL, when surfaced.

**Native proof and Shifter submission**

1. Open `Release Briefs/<name>.md` in Nextcloud.
2. Copy the complete `FLAG{...}` value from **Audit reference**. Confirm the
   same brief shows the source-derived destination, source-derived action, and
   source digest.
3. Open the caller-destination rejection and confirm it is tied to this
   operation's request contract.
4. In Shifter, open **kep-m02-a: The Credible Recommendation**, enter the exact
   value from the release brief, and select **Submit**.
   Expected: Shifter accepts it and marks the operation complete.

Pass: Shifter accepts the recommendation proof, the structured recommendation
is source-derived, unauthenticated vector access is denied, and the
caller-destination control is denied.
Fail: Shifter rejects the proof, the request can choose the destination, or a
non-Cinder origin is accepted.

## kep-m02-b: Authority By Citation

**Preconditions:** `kep-m02-a` is complete. The tester has the Orion review room
and citation-card renderer access.

**Positive procedure**

1. Create an indexed PDF whose PDF metadata fields `Title`, `Author`, and
   `Subject` are present. The displayed authority must look like an Orion,
   release, assurance, or standards authority and must not identify Cinder as
   the authority.
2. Upload the PDF to the review room and wait for ingestion.
3. Upload `Requests/<name>.json` containing:

   ```json
   {
     "workflow": "citation-authority",
     "source_path": "/Partner Rooms/Cinder Labs/Submissions/<pdf>",
     "query": "<release question the PDF should rank first for>"
   }
   ```

4. Open `Citation Cards/<name>.json`.
5. Confirm the card displays the false authority metadata while also showing
   the real source URI and resolved source digest.
6. From the participant desktop, open the unauthenticated vector access URL used
   by the range for Orion partner intake.
   Expected: HTTP `401`, `403`, or `405`.

**Negative check**

1. Upload a request with a caller-supplied `selected_point_id`, or use a PDF
   lacking one required metadata field.
2. Confirm the request/result is rejected and no unrelated citation card counts.

**Evidence to retain**

- PDF metadata screenshot or `pdfinfo` output.
- Uploaded PDF URL and completed ingestion-run screenshot.
- Request JSON URL.
- Citation card URL.
- Caller-citation rejection URL.
- Unauthenticated vector-access denial status.
- Control result URL, when surfaced.

**Native proof and Shifter submission**

1. Open `Citation Cards/<name>.json` in Nextcloud.
2. Copy the complete `FLAG{...}` value from `citation_reference`. Confirm the
   same JSON shows `display_authority`, `source_uri`, and
   `resolved_source_sha256`.
3. Confirm the rejected request did not render an accepted citation card.
4. In Shifter, open **kep-m02-b: Authority By Citation**, enter that exact
   value, and select **Submit**.
   Expected: Shifter accepts it and marks the operation complete.

Pass: Shifter accepts the citation proof, authority display comes from PDF
metadata, the digest remains the participant source, unauthenticated vector
access is denied, and the caller-citation control is denied.
Fail: Shifter rejects the proof, trust is inferred from a caller-selected
citation, or an unrelated card is used as proof.

## kep-m02-e: Accepted By Inspection

**Preconditions:** `kep-m07-i` and `kep-m02-j` are complete. The tester has the
Orion review room, model intake access, and Cinder relay access.

**Positive procedure**

1. Read the public `review-stack.lock` and confirm `picklescan==0.0.20`.
2. Upload the exact checkpoint artifact and a valid SPDX or CycloneDX SBOM to
   the review room.
3. Upload `Model Intake/<name>.json` containing:

   ```json
   {
     "profile": "isolated-import",
     "artifact_path": "/Partner Rooms/Cinder Labs/<artifact-path>",
     "sbom_path": "/Partner Rooms/Cinder Labs/<sbom-path>",
     "sha256": "<artifact-sha256>"
   }
   ```

4. Wait for `Model Intake Results/<name>.json`.
5. Open the result and confirm scanner version `0.0.20` has no issues, patched
   scanner `0.0.22` rejects the exact artifact, integration import completes,
   callback is observed, and importer output reference is present.

**Negative check**

1. Upload a manifest with a wrong `sha256`, invalid SBOM, artifact that fails
   `0.0.20`, artifact that also passes `0.0.22`, or artifact that never calls
   back.
2. Confirm the result is rejected with the corresponding reason.

**Evidence to retain**

- Review stack lock screenshot.
- Artifact, SBOM, and manifest URLs.
- Model intake result URL.
- Rejected manifest/result URL.
- Visible patched scanner denial in the accepted result.
- Control result URL, when surfaced.

**Native proof and Shifter submission**

1. Open `Model Intake Results/<name>.json` in Nextcloud.
2. Copy the complete `FLAG{...}` value from `importer_output`. Confirm the same
   JSON shows `inspection.scanner: picklescan`, `inspection.version: 0.0.20`,
   `patched_inspection.version: 0.0.22`, integration import completion, and
   `callback_observed: true`.
3. Confirm the rejected manifest/result is operation-specific and uses a
   distinct participant-visible attempt.
4. In Shifter, open **kep-m02-e: Accepted By Inspection**, enter the exact value
   from the model-intake result, and select **Submit**.
   Expected: Shifter accepts it and marks the operation complete.

Pass: Shifter accepts the inspection proof, the same artifact digest appears in
the manifest, scan, patched control, and importer result, and the importer
callback is observed.
Fail: Shifter rejects the proof, a caller-supplied verdict, wrong digest,
patched pass, or missing importer callback is accepted.

## kep-m02-f: Quiet Under Observation

**Preconditions:** `kep-m02-e` is complete. The tester has the Orion review room,
model intake access, and Cinder relay access.

**Positive procedure**

1. Upload one exact checkpoint artifact and valid SBOM to the review room.
2. The checkpoint must load successfully as an Orion preview candidate and
   require both `ORION_REVIEW_STAGE=integration` and the mounted
   `/run/keplerops/import-context.json` before it uses the dynamic callback URL.
3. Upload `Model Intake/<name>.json` containing:

   ```json
   {
     "profile": "dynamic-observation",
     "artifact_path": "/Partner Rooms/Cinder Labs/<artifact-path>",
     "sbom_path": "/Partner Rooms/Cinder Labs/<sbom-path>",
     "sha256": "<artifact-sha256>"
   }
   ```

4. Wait for `Model Intake Results/<name>.json`.
5. Open the result and confirm:
   analysis completed with `callback_observed: false`;
   full integration completed with `callback_observed: true`;
   `clean_full_context`, `candidate_stage_only`, and `candidate_context_only`
   completed with `callback_observed: false`; and the candidate near-control
   artifact digests equal the submitted artifact digest.
6. Confirm the stage-only control has its own callback basket, execution ID, and
   syscall trace hash.

**Negative check**

1. Submit a checkpoint that keys on only one marker, uses a hard-coded callback,
   changes digest between stages, fails a near control, or makes the clean
   control call back.
2. Confirm the result is rejected or lacks `importer_output`.

**Evidence to retain**

- Artifact, SBOM, and manifest URLs.
- Model intake result URL.
- Analysis and integration sections screenshot.
- Stage-only, context-only, and clean-control sections screenshot.
- Rejected manifest/result URL.

**Native proof and Shifter submission**

1. Open `Model Intake Results/<name>.json` in Nextcloud.
2. Copy the complete `FLAG{...}` value from `importer_output`. Confirm the same
   JSON shows one artifact digest across analysis, near controls, and full
   integration.
3. Confirm only full integration has `callback_observed: true`; analysis,
   `clean_full_context`, `candidate_stage_only`, and `candidate_context_only`
   must all show `callback_observed: false`.
4. In Shifter, open **kep-m02-f: Quiet Under Observation**, enter the exact
   value from the model-intake result, and select **Submit**.
   Expected: Shifter accepts it and marks the operation complete.

Pass: Shifter accepts the dynamic-observation proof, full integration is the
only callback-producing execution, all controls are quiet, and every execution
is digest-bound.
Fail: Shifter rejects the proof, analysis or any near/clean control produces
the integration effect, or the artifact digest changes between stages.
