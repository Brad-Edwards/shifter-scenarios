# Participant-run telemetry data dictionary

Operator/research surface only. The machine-readable contract is
the ACES `content.core.research-telemetry-contract` dataset. This dictionary describes
the version-1 envelope; module implementations add catalogued event rows without creating
new transports or authority planes.

## Authority boundary

Research telemetry is observational and fail-open. It cannot create oracle
evidence, receipts, flags, solves, or reset state. The award-bearing contract
remains the ACES-native evidence requirements plus
`content.core.proof-policy`.

Internal adapters may use `range_instance`, `participant`, and
`reset_generation` after server-side authentication. Export replaces the first
two values with generation-aware `study_run_id` and `session_id` pseudonyms.
Participant-visible identity, IP addresses, credentials, tokens, flags,
receipts, proof bodies, SQL, stack traces, and model bodies are not operational
export fields.

## Correlation and ordering

| Field | Meaning |
|---|---|
| `study_run_id` | Operator-keyed pseudonym grouping declared sessions. |
| `session_id` | Operator-keyed pseudonym bound to one reset generation. |
| `event_id` | Stable idempotency identifier for one emitted event. |
| `trace_id`, `span_id`, `parent_span_id` | Trusted server-created OTel causal context. |
| `source_id`, `source_sequence` | Source identity and monotonic gap-detection sequence. |
| `occurred_at`, `observed_at`, `clock_source` | Source and collector clocks; neither is rewritten. |
| `module_id`, `challenge_id`, `challenge_version` | Versioned SDL-owned challenge attribution. |
| `attempt_sequence`, `path_variant` | Retry number and declared route. |
| `method_class`, `participant_interface` | Bounded method and UI surface. |
| `reset_generation` | Current canonical lifecycle generation. |

Operational challenge measures also include optional declared
`assistance_mode`; `hint_tier` and `hint_cost`; bounded `failure_class`,
`verdict_class`, `rank`, and `score_bucket`; `query_count`, `iteration_count`,
`perturbation_count`, and `retry_count`; range-local `workflow_run_id`, `model_revision`, and
`policy_revision`; and artifact/state digests. Assistance mode is never
inferred from submission bursts. Scores and ranks are bucketed when a raw value
would expose a hidden threshold.

Model-extraction rows additionally carry server-owned `query_budget` and
`coverage_count` values plus aggregate `diagnostic_fidelity`,
`private_fidelity`, and `minimum_slice_fidelity` ratios. These aggregates are
also participant-visible challenge diagnostics; raw probes, teacher outputs,
corpus text, predictions, and proxy weights are never operational fields.

Model-backdoor rows additionally carry bounded evaluation kind/count, trigger
rate/confidence, clean accuracy, approval kind/scope, policy allow/confusion and
reason class, registry alias and numeric version transition, actor-
authorization state, and the eligible Module 07 source item. The approval actor
name, signed object, token claims, and raw model behavior never enter the
operational field policy.

Exports use the total order declared in the contract rather than wall clock
alone. Sampling, accepted/dropped counts, sequence gaps, missing lifecycle
markers, and clock status are explicit bundle data.
The operator reset path emits canonical `reset.requested` and
`reset.completed` events alongside the session-boundary markers
`session.reset_started`, `session.closed`, `session.started`, and
`session.reset_completed`.

The operational bundle contains canonical JSONL events, this dictionary, the
machine-readable schema, a missingness summary, an environment manifest, a
member manifest, and checksums. The environment manifest records the resolved
runtime image digests plus combined model, adapter, dataset, challenge, oracle,
and instrumentation digests. It is sufficient to join and compare sessions
without participant-visible identity.

## Capture modes

Operational mode is automatic and records bounded metadata such as status,
duration, counts, keyed/artifact digests, sampling rate, and capture status.
Raw content is disabled by default.

Full-content signals are independently configured for prompts, completions,
tool calls, tool results, terminal command lines, terminal input/output PTY
chunks, terminal-session lifecycle records, browser navigation/download
records, Jupyter notebook/file saves, Airflow workflow state, generated
workflow artifacts, and selected HTTP bodies. Enabled content is encrypted into
its own operator-only store and is never copied into ordinary OTel attributes,
proof JSON, MLflow tags, Airflow XCom, object metadata, exception logs, or the
operational bundle. Non-proof runtime producers send enabled content through
the fail-open research emitter to the proof owner. Content generated inside the
proof runtime is persisted directly through the same encrypted store so it is
not dependent on the outbound emitter worker.

The optional full-content export is a second archive containing only
AES-256-GCM ciphertext, nonce, signal, pseudonymous session, and causal trace
metadata. Its key is never included. Enabling or exporting one signal does not
enable another signal or change the operational archive.

The research telemetry research profile now declares the operator-only storage roots and
readback tool in the SDL-owned research contract. `research_cli.py readback`
verifies checksums, manifest member digests, contract ordering, missingness,
network-flow completeness records, and encrypted full-content bundles. When an
operator explicitly supplies the content key from the range, readback can
decrypt captured content and emit either digests/counts or raw base64 content
for an approved research export. The key is never written into the archive.

The research telemetry research profile now has source-implemented coverage for CTFd, reset
lifecycle, proof/runtime content, Airflow workflow state and artifacts,
module-06 HTTP bodies, late-module content, browser navigation/download
records, Jupyter notebook/file saves, and participant workstation shell and
filesystem capture. Remaining research telemetry work is reconciliation of module-local
capture completeness, emitted-event coverage, and any new challenge-specific
joins discovered during playtest; it is not a separate transport or award
authority. Every module issue must preserve fail-open scoring.

## KasmVNC replay scope

Full KasmVNC frame, pointer, and keyboard replay is not required for the
current research profile. The event study can reconstruct participant and
participant-agent behavior from the action/content sources above: PTY input and
output, parsed commands, process lifecycle, workstation file changes, browser
navigation/download rows, notebook saves, scenario HTTP bodies, model/workflow
state, proof/receipt transitions, reset markers, CTFd events, and mapped
network-flow observations.

The explicit reconstruction limit is pixel-level UI state. If a future study
must prove what a participant saw at an exact screen coordinate, replay pointer
motion, or recover UI state that left no terminal, process, browser,
filesystem, HTTP, notebook, workflow, proof, CTFd, or network-flow signal, this
decision must be reopened. The follow-on implementation would need to be
SDL-authored, operator-only, encrypted, lifecycle-bounded, storage-budgeted,
and fail-open with missingness accounting; it must not affect participant
access, challenge scoring, proof, reset, or teardown. Until that requirement
exists, KasmVNC frame replay remains intentionally out of scope rather than an
unimplemented dependency.

## Module 01 capture

Challenge version 3 attributes every agent-control observation to one of
`kep-m01-a` through `kep-m01-j`. The gateway records participant interface and
declared assistance mode, attempt sequence, duration, bounded token/query/tool
counts, model and policy revisions, direct/indirect path variant, verdict and
failure classes, and keyed artifact/state digests. The award path additionally
records the minimum item-specific fields required by the private oracle:

| Item | Bounded award fields |
|---|---|
| `kep-m01-a` | denied tool class, policy-denied stage, actor/asset/object and digest |
| `kep-m01-b` | normalized object id, two-boundary record count, digest |
| `kep-m01-c` | executed policy object, service-mediated state digest |
| `kep-m01-d` | delegated-role stage, approval object and digest |
| `kep-m01-e` | context workflow id, direct/indirect variant, two-boundary record count |
| `kep-m01-f` | two-tool record count, contained destination, byte count and digest |
| `kep-m01-g` | signed artifact workflow id, future-trigger stage, four-boundary record count and digest |
| `kep-m01-h` | exact package object/digest, interpreter stage, process-backed record count and byte count |
| `kep-m01-i` | click-trap workflow id, model-browser-click stage, rendered byte count and four-boundary record count |
| `kep-m01-j` | anonymous Redmine workflow id, ingestion stage, four-boundary record count and digest |

Operational exports do not contain prompt/completion bodies, retrieved document
content, raw tool arguments/results, capabilities, Keycloak tokens, proof bodies,
or receipts. When separately enabled, each full-content signal remains encrypted
under the existing independent capture switches. OPA/firewall denials and
gateway events share trusted server-created trace and reset-generation context;
they do not create a second award authority.

The gateway's current encrypted-content adapter records prompt, completion,
tool, selected scenario HTTP bodies, and participant-workstation terminal
signals when their independent switches are enabled. The package and browser
workers also persist bounded server-side process lineage used by proof. Pixel-
level browser UI state outside terminal/process/browser navigation/download
signals remains explicitly out of scope for the current research profile;
operational scoring is fail-open with respect to that research path.

## Module 02 capture

Challenge version 2 attributes every model-evasion observation to one of
`kep-m02-a` through `kep-m02-f`. `workflow_run_id` carries a keyed range-local
pair id; `artifact_digest` carries the keyed candidate digest. Operational rows
also record model and policy revisions, participant interface, declared
assistance mode, attempt sequence, paired/encoding/semantic/repeatability/
transfer/ensemble path variant, total query/token/iteration/retry counts,
bounded allow-count score bucket, verdict class, duration, and telemetry loss.

The transfer exploration endpoint emits the same bounded fields with path
variant `surrogate`; it cannot award evidence. Award events contain only the
item-specific event kind, actor and range assets, target object, aggregate probe
count, keyed digest, namespace, generation, and status. Hidden controls, system
prompts, participant candidates, raw completions, individual revision verdicts,
semantic-judge bodies, receipts, and proof records never enter operational
telemetry. Prompt/completion capture remains disabled by default and, when
explicitly enabled, uses only the separate encrypted content store described
above.

## Module 03 capture

Challenge version 2 attributes retrieval observations to `kep-m03-a` through
`kep-m03-f`. Ingestion and reindex rows carry only a keyed artifact digest,
bounded chunk/document/revision counts, interface, assistance mode, and the
server-created index workflow id. Search and attempt rows carry bounded rank and
cosine score buckets, result/query/token counts, model and policy revisions,
clean-session workflow id, behavior/citation/action path variant, verdict class,
duration, and telemetry loss. The server—not the participant—creates the fixed
award query, attempt sequence, clean session, model verdict, citation decision,
broker result, and evidence event.

| Item | Bounded award fields |
|---|---|
| `kep-m03-a` | participant artifact digest, retrieved record count, top-three status |
| `kep-m03-b` | rank-one status, bounded score bucket, trusted-result coexistence |
| `kep-m03-c` | distinct control/behavior verdict classes and clean-session state digest |
| `kep-m03-d` | claimed-authority object id, citation verdict class, artifact digest |
| `kep-m03-e` | policy-backed `publish_notice` tool class and broker execution status |
| `kep-m03-f` | document/index revision counts, new clean-session id, approval tool class and broker execution status |

Document bodies, chunks, raw embeddings, vectors, exact cosine scores, model
prompts/completions, raw citations, tool arguments/results, tokens, receipts,
and proof rows do not enter operational telemetry. Document HTTP bodies and
model content can be captured only through the existing independently enabled,
encrypted full-content signals; enabling them does not alter award logic.

## Module 04 capture

Challenge version 2 attributes model-secret and privacy observations to
`kep-m04-a` through `kep-m04-e`. Inference-only rows record query/token counts,
duration, participant interface, declared assistance mode, model revision,
verdict class, and keyed prompt/state digests. They do not operationally record
the synthetic canary, hidden instruction, participant prompt, or completion.

Privacy rows record the classifier revision, bounded query count and score
bucket, member/control population sizes, calibration bucket, privacy verdict,
duration, and keyed sample/state digests. The raw sample text, exact private
membership labels, submitted selection, raw confidence/loss, model features,
oracle population, receipts, and proof records do not enter operational
telemetry. The diagnostic API deliberately discloses only its own calibration
labels to participants; the private and cohort APIs never return membership.

Award evidence contains only actor and range assets, item-specific event kind,
model or population object id, aggregate record count, keyed digest, namespace,
generation, and status. All five item paths use the existing fail-open research
transport and the independent award-bearing proof contract.

## Module 05 capture

Challenge version 2 attributes durable agent-state observations to
`kep-m05-a` through `kep-m05-e`. Operational rows record bounded duration,
query/token counts, state version and use count, participant interface,
declared assistance mode, model/policy revisions, result class, whether
retrieval and a brokered tool effect occurred, and whether a restart was
server-verified.

Session, thread, prompt, memory-state, and prior/current worker-boot identities
are represented only by keyed SHA-256 digests. The stored memory, unique
marker, participant prompt, model completion, tool arguments/result, raw ids,
service token, database rows, receipt, and proof event do not enter operational
telemetry. Independently enabled encrypted full-content capture can observe
prompt/completion and tool content under the existing policy; it has no award
authority and cannot change runtime behavior.

Award evidence contains the participant and range scope, item-specific event
kind, durable state object id and digest, bounded use count, lifecycle stage,
generation, and status. Restart-dependent items additionally carry the
server-derived restart workflow id; the deputy item carries the contained
destination and bounded marker byte count. Reset removes memory, uses,
restarts, evidence, and receipts, then leaves one fresh worker boot for the new
generation.

## Module 06 capture

Challenge version 3 attributes adversarial-input observations to `kep-m06-a`
through `kep-m06-v`. Core rows record the declared bounded method class,
participant interface and assistance mode, attempt sequence, disclosed and
held-out query counts, token edit `perturbation_count`, semantic-check count,
model/policy revisions, bounded allow-count score bucket, verdict/failure
class, latency, and a keyed artifact digest. Expansion rows add only
digest-safe component kinds, object ids, object digests, workflow id, interface,
assistance mode, and failure class. The gateway owns the query budgets,
control prompts, revision schedule, semantic checks, required component kinds,
and objective verdict.

Raw adversarial candidates, model prompts and completions, individual hidden
revision decisions, control bodies, database rows, receipts, and proof records
do not enter operational telemetry. The candidate is retained only as
reset-owned scenario state needed for repeat and transfer evaluation. When a
research run explicitly enables the relevant content signal, raw bodies use
the existing independently encrypted content store and acquire no award
authority.

Award evidence contains only participant/range scope, the item-specific event
kind, artifact or workflow object id and keyed digest, aggregate query or
component count, generation, and status. Reset removes artifacts, disclosed
probes, attempts, platform challenge events, evidence, and receipts for the
prior generation.

## Module 07 capture

Challenge version 2 attributes training-poisoning observations to `kep-m07-a`
through `kep-m07-i`. Gateway rows record participant interface, declared
assistance mode, item id, dataset/workflow keyed digest, server-owned revision,
poison class, bounded record/total bucket, attempt sequence, path variant,
model revision, verdict/failure class, latency, and coarse target-score bucket.
Airflow rows add the server-known workflow stage and duration under the same
range, participant, generation, and stable workflow trace lineage.
Expansion rows for architecture sabotage, poisoned dataset publication, and
executable model artifacts store only digest-safe component kinds, object ids,
object digests, workflow id, interface, assistance mode, and failure class.

Participant row bodies, immutable clean rows, hidden probes, model
coefficients/vocabulary, exact probabilities, exact MLflow/MinIO locations,
workflow credentials, database rows, receipts, and proof records do not enter
operational telemetry. Dataset and artifact digests are participant-scoped
keyed digests. Explicitly enabled encrypted content capture may observe gateway
dataset, job, and attempt request bodies through the independent content
boundary; it has no award authority and cannot change dataset, training,
evaluation, or receipt results.

Award evidence contains participant/range scope, an item-specific event kind,
server-derived dataset, artifact, or expansion workflow object id and digest,
bounded record/component count, workflow id, generation, and status.
`distillation-runner-01` owns the five training/evaluation evidence events; the
gateway owns the versioned-dataset and expansion evidence events. Reset removes
participant datasets, rows, jobs, attempts, platform challenge events, MLflow
runs, MinIO poisoning artifacts, evidence, and receipts while preserving the
immutable clean base.

## Module 08 capture

Challenge version 1 attributes model-extraction observations to `kep-m08-a`
through `kep-m08-f`. Gateway rows record participant interface, declared
assistance mode, item id, server-owned query count/budget, record and behavior-
slice coverage counts, coarse score bucket, latency, and keyed corpus/artifact
digests. Airflow rows add workflow stage, duration, model revision, aggregate
diagnostic/private/minimum-slice fidelity, and MLflow/MinIO lineage presence
under the same range, participant, item, generation, and workflow trace.

Participant corpus prompts, teacher completions and labels, diagnostic/private
probe bodies, individual predictions, TF-IDF vocabulary, model coefficients,
exact MLflow/MinIO locations, workflow credentials, database rows, receipts,
and proof records do not enter operational telemetry. The extraction endpoints
can invoke independently enabled encrypted content capture for participant
teacher-query prompts, live teacher completions, corpus/job/attempt request
bodies, and platform request bodies. Private evaluation probes remain
server-owned fixtures; capturing participant content does not copy private
probe populations into operational telemetry or alter award logic.

Award evidence contains only participant/range scope, the item-specific event
kind, corpus or proxy object id and keyed digest, aggregate record count,
workflow id, generation, and status. The gateway owns the two corpus evidence
events; `distillation-runner-01` owns the four trained-proxy evidence events.
Reset removes participant corpora, queries, jobs, attempts, extraction MLflow
runs, MinIO proxy artifacts, evidence, and receipts.

## Module 09 capture

Challenge version 2 attributes model-backdoor observations to `kep-m09-a`
through `kep-m09-g`. Gateway rows correlate the current participant/generation
candidate with the eligible Module 07 source item, range-local workflow id,
artifact digest, keyed state digest, model revision, numeric MLflow version,
participant interface, declared assistance mode, attempt sequence, path and
method class, latency, verdict/failure class, and bounded evaluation count.

Evaluation rows add only `diagnostic_trigger`, `diagnostic_clean`,
`hidden_joined`, or `reload_joined` kind plus aggregate trigger rate,
trigger confidence, and clean accuracy. Approval and promotion rows add only
`release` or `model_card` kind, fixed release scope, policy allow/confusion and
bounded reason class, fixed `production` alias, prior/new numeric model
versions, and whether the actor was authorized. No operational row contains an
approval username or role list.

Signed Keycloak tokens and claims, participant trigger rows, disclosed or
hidden probe bodies, individual predictions, exact probabilities, TF-IDF
vocabulary, model coefficients, raw artifacts, exact storage locations,
database rows, receipts, and proof records do not enter operational telemetry.
When independently enabled, encrypted content capture may record participant
HTTP request bodies for candidate, evaluation, approval, promotion, reload,
attempt, and platform operations. The platform-agent publication path also
captures the submitted tool plan and returned tool result under the tool
signals. Hidden behavior populations remain server-owned fixtures and are not
emitted as operational fields.

Award evidence contains participant/range scope, the item-specific event kind,
candidate object id, artifact digest, MLflow model workflow id, lifecycle
stage, generation, and status. The authenticated gateway owns all seven award
events because it performs and attests the registry, policy, evaluation,
promotion, and reload joins; MLflow remains the real stateful registry, not a
second evidence producer. Reset removes backdoor candidates, evaluations,
approvals, promotions, deployments, attempts, `keplerops-backdoor-*` MLflow
models, evidence, and receipts.

## Module 10 capture

Challenge version 1 attributes deployed-AI capstone observations to
`kep-m10-a` through `kep-m10-g`. Gateway rows correlate only server-issued
candidate, activation, effect, artifact-access, and workflow identifiers with
the current participant and reset generation. Operational fields include the
resolved numeric model version, keyed artifact and state digests, aggregate
trigger decision/confidence, participant interface, declared assistance mode,
attempt sequence, bounded path/method/failure/verdict classes, effect presence,
byte count, latency, and status.

The production-inference row stores a keyed digest of the participant prompt;
the raw prompt and classifier features never enter operational telemetry. The
contained-effect row stores the broker result digest and fixed tool/effect
classes, not the notice body or raw adversarial input. Artifact-access and
verification rows store the pinned artifact digest, expected/observed byte
counts, contained destination class, and verification result. Original model
bytes, object-store credentials, presigned URLs and signatures, bucket keys,
HTTP bodies, database rows, receipts, flags, and proof records do not enter
operational telemetry or committed reports. When independently enabled,
encrypted full-content capture may record capstone request bodies, the
production prompt and classifier decision, broker/platform-agent tool
call/result content, and contained-impact request bodies without changing
receipt derivation or operational exports.

Award evidence contains participant/range scope, the item-specific event kind,
server-derived object id and keyed digest, generation, and status. The deployed
impact event is emitted only after the gateway joins the loaded production
revision, live trigger, persisted OPA/broker effect, prior persistent deputy
effect, and passed adversarial artifact. The theft event additionally contains
only the contained destination label and verified byte count after the gateway
has read and hashed the destination object. The proof service derives the final
capstone receipt from the SDL-owned evidence join. Reset removes all capstone
rows and contained-exfil objects while preserving and re-verifying the pinned
original artifact.

## Transport and sources

OTLP traces use internal mutual TLS on port 4318. Strict research events and
encrypted content use a separate mutual-TLS listener on port 4319. Neither port
is routed from the participant subnet; the public proof listener returns 404
for research paths. Producer tokens select a catalogued source but never grant
award authority.

The `participant-workstation` source is declared in the SDL research contract
and therefore receives a producer token from the generated GCP realization. The
Kasm/Kali image wraps interactive Bash shells with a fail-open PTY recorder. It
emits encrypted `terminal_input`, `terminal_output`, parsed
`terminal_command`, and `process_lifecycle` records to the research listener
when those independent signals are enabled. Recorder failure, queue overflow,
or transport loss does not change terminal behavior, proof, scoring, reset, or
teardown.

The same workstation image starts a bounded fail-open file recorder before Kasm
launches. It polls participant-visible Desktop, Downloads, and work roots,
emits encrypted `file_content` create/modify/delete records with path, size,
mtime, SHA-256, and base64 content when bounded, and skips browser/profile
state directories. Oversized files are represented by metadata-only records
rather than blocking the workstation.

A separate fail-open browser recorder polls Chromium and Firefox history
databases for navigation and download records. It emits encrypted
`browser_interaction` records with profile path, URL, title, browser timestamp,
transition/download state, target path, MIME type, and byte count when those
fields are present. It does not copy cookies, cache bodies, or browser profile
databases; file contents created by downloads remain the responsibility of the
bounded workstation file recorder. Full KasmVNC frame, pointer, and keyboard
replay is intentionally out of scope for the current event profile per the
KasmVNC replay scope decision above.

The `notebook-runner-01` source is also SDL-declared. Its Jupyter image loads a
server extension that installs a ContentsManager pre-save hook, captures the
model content Jupyter is about to persist, and emits encrypted
`notebook_content` or `file_content` records. The hook delegates to any existing
save hook first, does not modify the model, chunks oversized payloads, and
fails open on queue or transport loss.

The `distillation-runner-01` source emits encrypted `workflow_state` and
`artifact_content` records when those signals are enabled. Captured state
includes DAG start configuration and task result summaries; captured artifacts
include the generated training-poisoning adapter, model-extraction proxy, and
legacy distillation JSON artifacts with digest metadata. This path is
fail-open and does not affect Airflow scheduling, scoring, MLflow registration,
or proof receipts.

FastAPI generates new trusted root spans after Envoy removes incoming trace and
baggage headers. Airflow creates a stable trace id from the server-known range,
participant, and DAG run and uses it across workflow start/completion events.
The current CTFd plugin queues content-free hint and objective attempt/satisfied
events in a bounded background worker. The portfolio requires it to
add presented/started, checkpoint, flag-submitted, solved, dependency, and
reset-correlation events before pilots. Transport, queue, collector, or sink
failure is swallowed by these adapters and represented through loss/gap
reporting; it cannot change a
model result, workflow result, receipt, solve, reset, or teardown result.

The GCP profile also enables 50%-sampled VPC Flow Logs at five-second
aggregation and full firewall decision logging. Operator export queries only
the session clock window in bounded time batches, maps addresses to canonical
topology asset ids, drops records unrelated to the tenant inventory, deletes
the raw temporary query responses, and writes `network-flows.jsonl` without IP
addresses. Denied egress is retained at full firewall-log sampling and
distinguished from sampled allowed flow. The network-flow completeness record
reports `captured`, `partial`, or `unavailable` plus batch and failed-batch
counts; partial capture keeps successfully sanitized batches while marking the
overall bundle incomplete.

## Versioning

`schema_version`, the OTel semantic-convention version, GenAI convention
version, challenge version, image/model/dataset/oracle digests, capture policy,
and effective sampling configuration are pinned in every session manifest.
Breaking envelope or field-policy changes require a new schema version.
