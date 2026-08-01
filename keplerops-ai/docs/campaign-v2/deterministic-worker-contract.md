# Deterministic Workflow Worker Contract

## Boundary

KeplerOps has no ambient green, grey or white agents in campaign-v2. The only
synthetic actors are deterministic workers required to execute ordinary company
workflows that a participant cannot perform as the victim. They consume actual
mail, browser, repository, package, model and application state. They do not
read challenge IDs, flags, hints, score state or participant intent.

Each worker is a versioned queue consumer with a normal application identity,
idempotency key, visible stages, maximum completion time and objective acceptance
rules. A hidden LLM judgment such as “credible,” “useful” or “interesting” is
never a gate.

## Common Lifecycle

1. The owning application creates a normal queue item and visible correlation
   ID.
2. The worker authenticates as its named recipient/reviewer identity and claims
   only that item.
3. Every network fetch, mailbox action, browser navigation, download, install,
   load, model/tool call and application update is recorded under the same ID.
4. Stage status is visible to the participant through the ordinary ticket,
   thread, review, CI or audit surface.
5. Acceptance is a conjunction of published objective facts. Failure names the
   failed fact and preserves enough information to revise the attempt.
6. A duplicate item returns the existing terminal result; it does not repeat
   harmful effects or create another flag.
7. Attempt cleanup removes only the disposable profile/job. A successful native
   record remains immutable.

Default queue start is under 30 seconds and terminal completion under five
minutes, except model training/evaluation and physical reservations, which
publish their own bounds and progress.

## Objective Worker Matrix

| Operations | Worker and ordinary role | Published acceptance facts | Visible stages and negative controls |
|---|---|---|---|
| `kep-m02-i` | Stalwart mail recipient handling a known external research contact | Authenticated thread, valid DKIM/TLS, referenced public conference identity, request concerns the recipient's documented review window | received, identity checked, replied, review context shared; wrong identity/unsigned new thread is rejected |
| `kep-m02-j` | Recipient Chromium/voice-review job | Existing trusted thread, exact recipient, fresh challenge phrase, audio intelligibility and pinned speaker-similarity/liveness thresholds | media fetched, decoded, phrase checked, similarity/liveness reported, invitation sent; prerecorded wrong phrase and sub-threshold audio fail |
| `kep-m02-k` | Recipient Chromium/local-agent workstation | Link occurs in accepted thread, HTTPS/domain ownership is valid, page renders, requested review action is within published policy | opened, rendered, local agent invoked, callback observed; raw callback without browser/agent trace fails |
| `kep-m02-h` | Zammad intake/ingestion worker | Supported document format, required business fields, malware scan clean, extraction succeeds, document contains a relevant declared Orion release question | ticket, object, extraction, index, cited triage, invitation; unsupported or unextractable documents report why |
| `kep-m02-l`, `kep-m01-h` | Package review/install worker | Package metadata/SBOM/license present, exact declared API, clean visible tests, signed participant release, install resolves through normal registry | fetched, scanned, built, installed, imported, compatibility test; uploaded logs, missing API and different digest fail |
| `kep-m02-m` | MCP catalog compatibility worker | Valid MCP manifest/schema, HTTPS ownership, health, exact declared tools, fixture request/result schema, latency and egress policy | discovered, schema checked, fixture called, result validated, cataloged; prose usefulness is never judged |
| `kep-m01-g`, `kep-m02-e`, `kep-m09-i` | Model intake/review worker | Model card/schema present, accepted format, visible static scan/policy result and ordinary loader eligibility | acquired, scanned, queued, loaded, smoke tested; a participant cannot upload a claimed loader result |
| `kep-m03-d` | Dependency-resolution worker | Assistant output names a syntactically valid unresolved dependency; participant domain provides matching signed metadata/package; normal resolver policy permits public fallback | name extracted, DNS/TLS, metadata, signature, resolver selection, fetch; no hard-coded package name or semantic-taste check |
| `kep-m01-e`, `kep-m03-j`, `kep-m03-k` | Intake/assistant handoff workers | Supported source, successful extraction/index, correct workflow event, ordinary assistant/tool result | each generation and trigger is visible with source/chunk/tool IDs; text alone without downstream event fails |
| `kep-m04-l` | Support preview browser | Actual Zammad draft and attachment, generated Markdown selected by normal template, Chromium render completes | draft loaded, Markdown rendered, subresources requested, preview saved; server-side HTTP request without Chromium render fails |
| `kep-m09-k` | Model review workstation | Mirrored immutable digest, model card, supported loader, smoke-test input schema and assigned review request | opened, downloaded, loaded, inference, report; different digest or management load fails |
| `kep-m10-m` | Two partner contract-monitor workers | Live Ghost RSS revision contradicts the signed incident facts already held by each distinct partner | independent RSS fetch, fact comparison, subscription suspension, signed Zammad complaint; preview, one partner or matching claim fails |

## Model-Mediated Workers

Where a worker calls an Orion model, the model is not the acceptance oracle. The
worker records the model output and then applies a published, testable business
rule to typed fields or metrics. The operation contract identifies the model
behavior being attacked; negative controls distinguish that behavior from
queue volume, arbitrary text or worker failure.

For operations whose objective is semantic model behavior rather than a fixed
schema, implementation freezes a small public rubric, exposes stage-level
observations, and accepts multiple strategies during reference runs. If two
fresh AI-security-new testers cannot understand why a valid attempt failed, the
operation is redesigned rather than classified as harder.

## Reliability And Diagnostics

- Queue, browser, mail, dependency, model and application errors are separate
  terminal states.
- Worker image, browser, model, prompt/rubric and policy digests appear in the
  participant-visible record.
- Facilitators receive read-only logs and may restart a failed worker to replay
  its existing queue item. They cannot edit the result or issue a flag.
- Candidate testing runs every worker from two semantically distinct valid
  inputs plus its negative controls, then under representative concurrent load.
- A worker that misses its SLA or accepts only one author-shaped input is a
  scenario defect and blocks the affected operation.
