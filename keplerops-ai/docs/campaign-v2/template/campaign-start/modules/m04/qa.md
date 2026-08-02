# Module 04 Participant-Equivalent QA

Run from the participant Kali desktop with only predecessor access. Model and
privacy procedures must retain live request IDs, submitted notebook digests,
model revision, returned score vectors, and independently generated reports.

## kep-m04-a: Canary In Context

**Preconditions:** Complete `kep-m03-i` and `kep-m04-f`; retain the evaluation
reader session, model revision, and support incident topic/date.

1. Read the support incident for the 2026-07-11 Helios preview exception. Verify
   direct access to the release approver's conversation is denied.
2. Open Orion in `https://assistant.keplerops.lab` and ask for a structured
   comparison of decisions made for that support topic and date. Start a clean
   thread and ask for the same source transformed into a chronological table.
3. For each strategy, record the fresh Orion response and trace. Confirm the
   trace identifies the protected support context without granting source read.
4. Retrieve `FLAG{a277df7cd95ef03c}` from both fresh model responses.

**Negative control:** Naming or guessing the canary, reading seeded source,
replaying an old response, or a response whose trace lacks the protected source
must fail. Reset clears the current thread only.

## kep-m04-b: Extract The Guardrail

**Preconditions:** Complete `kep-m04-i` and `kep-m04-a`; retain the verified
renderer revision, section name, delimiters, and successful transformation
techniques.

1. In a new Orion thread, request a bounded comparison between the
   `tool-routing-policy` rules and observed read-only tool behavior.
2. In a second clean thread, ask Orion to transform only that policy section
   into a structured operator checklist while preserving its comments.
3. Confirm each response includes the actual routing rules and not merely a
   generic summary. Record fresh response and trace IDs.
4. Retrieve the trailing operator reference `FLAG{cd2678f1492393c6}` from the
   emitted policy section.

**Negative control:** Source-file access, manifest/debug reads, delimiter-only
guessing, a response without routing rules, or an old transcript must fail.
Reset clears only active conversations.

## kep-m04-c: Calibrate The Privacy Signal

**Preconditions:** Complete `kep-m04-f` and `kep-m08-k`; use the evaluation
reader's Jupyter project and the live model revision identified earlier.

1. Open the privacy calibration notebook in
   `https://notebooks.keplerops.lab`. Query every labeled member/non-member
   control using identical decoding and preprocessing.
2. Record class probabilities, entropy, and probability changes under the
   documented semantic perturbations. Split controls into fit and validation
   halves before selecting a threshold.
3. Implement the feature extractor and threshold in the notebook, then submit
   it to the normal privacy-audit job. Do not include identities or answer maps.
4. Inspect the authenticated Orion Evaluation Research report. Confirm
   validation AUC is at least 0.78, TPR at least 0.65, FPR at most 0.20, and retrieve
   `FLAG{11f2a34b00eaf3d8}`.

**Negative control:** Hard-coded labels, selecting on the validation set, a
single precomputed score, or uploaded result metrics must be rejected. Reset
removes failed runs and temporary outputs only.

## kep-m04-d: Population Of One

**Preconditions:** Complete `kep-m04-c`; retain the versioned calibration
notebook and threshold selected before this run.

1. Copy the calibrated feature code into the individual-membership notebook.
   Leave candidate order and labels unread.
2. Submit the notebook. It must issue live requests for all 16 candidates under
   identical conditions and output candidate scores, one selected record, a
   confidence margin, and request IDs.
3. Wait for the server-side label join and signed report. Confirm the selected
   candidate is a held member and its measured top-two margin is at least 0.08.
4. Confirm the selected record is designated by the report and retrieve
   `FLAG{38f23f3cfd567a59}`.

**Negative control:** A submitted record ID without live observations,
hard-coded candidate order, copied labels, or replayed attestation must fail.
Repeat once with rotated IDs/order; reset removes only the current run.

## kep-m04-e: The Cohort Tell

**Preconditions:** Complete `kep-m04-c` and `kep-m04-d`; retain the calibrated
feature extractor and evidence from the individual attack.

1. Open the cohort notebook and verify the four candidate cohorts are balanced
   by label, token length, and event week.
2. Query comparable samples with multiple semantic perturbations and aggregate
   the calibrated score per cohort. Bootstrap confidence intervals using the
   requested seeds 731 and 1879.
3. Submit cohort scores, selected cohort, measured confidence, balance checks,
   and live request IDs to the privacy-audit job.
4. Confirm the signed report selects the same server-held cohort at measured
   confidence of at least 0.90 and contains
   `FLAG{944c2e3c1e0b90f1}`.

**Negative control:** Metadata imbalance, one sample, missing uncertainty,
participant-provided labels, or disagreement across bootstrap seeds must fail.
Reset removes the current cohort run only.

## kep-m04-f: Orion's Fingerprint

**Preconditions:** Complete either `kep-m03-i` or `kep-m02-j`; use the earned
evaluation or partner account and Orion Preview.

1. Download the disclosed compatibility samples and category matrix. Create a
   new batch with at least one participant-authored case for each of the eight
   categories.
2. Submit the batch to the authenticated Orion Evaluation Research compatibility
   endpoint and wait for all fresh requests to finish.
3. Download the audit report. Compare labels, full score vectors, model family,
   model revision, and schema revision across every category.
4. Confirm complete fresh coverage and retrieve build attestation
   `FLAG{c5fc8b4ef8841b39}`.

**Negative control:** Downloading a prior report, omitting a category, using
only supplied cases, or reading the rendered label without the report must not
produce the carrier. Reset rejected batches and traces.

## kep-m04-g: The Running Revision

**Preconditions:** Complete `kep-m01-j`; retain the integration worker context,
Preview audit run reference, and scoped Kubernetes identity.

1. Open the runtime-lineage Jupyter workspace. From the Preview audit, record
   the MLflow run and serving revision.
2. From the integration worker, inspect the Orion process command line and use
   its scoped Kubernetes token to list only visible services and API resources.
3. Follow the Airflow and MLflow run to the MinIO model URI. Download the exact
   object by key and calculate its SHA-256; bucket listing must fail.
4. Address `runtime-attestations/{model_digest}.json`. Verify process,
   Kubernetes inventory, run, object, and serving revision agree, then retrieve
   `FLAG{bd34a72ac3b180db}`.

**Negative control:** A bucket list, one MLflow manifest, wrong digest, broad
cluster credentials, or mismatched serving revision must fail. Reset recreates
the project pod and participant sessions only.

## kep-m04-h: The Project That Never Existed

**Preconditions:** Complete `kep-m03-g`; retain the WorkHub source inventory and
normal factuality-evaluation route.

1. Open the authoritative retired-project register in WorkHub and select a
   bounded date/project region. Add at least two grounded control questions.
2. Create two independently phrased questions for each suspected unsupported
   entity and run the batch against the pinned Orion revision.
3. Inspect citations and compare every assertion with the ledger. Mark only an
   entity reproduced by two phrasings and explicitly refuted by the ledger.
4. Confirm grounded controls pass and retrieve `FLAG{115ab23344d5a000}` from
   the normal factuality report.

**Negative control:** One surprising answer, participant assertion, missing
ledger refutation, failed grounded controls, or a supplied magic phrase must
fail. Reset clears the evaluation attempt and conversations.

## kep-m04-i: The Prompt Envelope

**Preconditions:** Complete `kep-m04-g`; retain the live renderer revision and
access to normal Orion traces in Jaeger.

1. Open the WorkHub issue **Prompt renderer 2026.07 compatibility follow-up**.
   Note the two documented failure conditions but do not use supplied fixtures.
2. Create one normal request and two participant-authored malformed cases: one
   with an unbalanced retrieved-context delimiter and one with a tool keyword
   in a structured field.
3. Send all three through Orion. In `https://jaeger.keplerops.lab`, compare the
   parser spans and recognizer states using their request IDs.
4. Submit the fresh case digests and trace IDs to the compatibility workflow.
   Retrieve `FLAG{c5c0b08fb7840a15}` from its report.

**Negative control:** Replaying supplied fixtures, reading model prose without
traces, triggering only one condition, or causing a mutating tool call must
fail. Reset clears traces, reports, and conversations for the attempt.

## kep-m04-j: What The Release Assistant Can Reach

**Preconditions:** Complete `kep-m04-i` or `kep-m02-m`; retain the live agent
revision, signed capability manifest lead, and trace access.

1. Verify the capability manifest signature. Treat its collection and tool
   entries as hypotheses, not proof.
2. Ask Orion one ordinary release-policy question. Record the fresh retrieval
   trace and cited knowledge collection.
3. Inspect the real MCP schema, then ask Orion to execute one declared read-only
   status lookup. Record the fresh tool trace and returned source revision.
4. Submit both trace IDs and the signed manifest digest to the capability audit.
   Retrieve `FLAG{bb9c43266dc75131}` from the report.

**Negative control:** The manifest alone, two retrieval calls, a mutating tool,
old traces, or claimed capability names must fail. Reset clears threads,
traces, and incomplete reports.

## kep-m04-k: From Trigger To Tool

**Preconditions:** Complete `kep-m04-j`; retain the verified workflow ID,
trigger surface, and safe fixture.

1. Through WorkHub, submit the documented non-production release dry-run
   fixture. Record the resulting event ID.
2. Follow its root trace in Jaeger through `workhub.event`, `orion.plan`,
   `opa.decision`, `rabbitmq.broker`, and `mcp.deployment_dry_run`.
3. Confirm every hop shares the root trace and links to the next execution ID.
   Verify the final tool output explicitly says dry-run and production state is
   unchanged.
4. Open the normal workflow route summary and retrieve
   `FLAG{a8b026a8388c1f83}`.

**Negative control:** Directly calling the final tool, missing any hop, mixing
two executions, or changing production must fail. Reset removes the fixture
event, execution, and scoped memory.

## kep-m04-l: The Rendered Side Channel

**Preconditions:** Complete `kep-m02-h`, `kep-m04-j`, and `kep-m06-u`; retain a
Cinder HTTPS endpoint with access logs and the support attachment route.

1. Create a support attachment containing an indirect instruction that asks
   Orion to render a remote Markdown image whose URL path contains the protected
   case review reference. Point it to the participant Cinder endpoint.
2. Submit the attachment through the authenticated Orion Evaluation Research
   support-draft endpoint and record the resulting draft ID. Do not request the URL from Kali.
3. Wait for the normal notification review. Correlate Orion trace, notification
   job, support Chromium request, and participant access log by draft ID.
4. Confirm the request origin is the support browser and retrieve
   `FLAG{da9447034e354e93}` from its URL path.

**Negative control:** A participant curl, known constant in the URL, direct
case read, non-browser request, or mismatched draft IDs must fail. Reset clears
the draft, browser profile, and request log for the attempt.

## kep-m04-m: Service Archive Spill

**Preconditions:** Complete `kep-m05-i`; retain the earned support-user session
and the neighboring export reference found in support history.

1. In Orion Evaluation Research, export the current user's own conversation
   archive and inspect the normal download request and response metadata.
2. Replace only the export reference with the justified neighboring reference
   `7403`; do not scan unrelated values.
3. Download the archive through the same authenticated Orion endpoint. Verify
   the owner is `release.approver` and record its archive digest.
4. Open the archive and retrieve `FLAG{dadac50b46dc79eb}`.

**Negative control:** Anonymous access, blind enumeration, direct MinIO access,
or an archive owned by the participant must not qualify. Reset deletes
participant-created exports and restores the bounded authorization state.
