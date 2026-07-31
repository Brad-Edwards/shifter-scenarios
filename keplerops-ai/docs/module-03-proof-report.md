# Module 03 Participant-Proof Report

## Result

All six module-03 context-poisoning challenges are `participant-proven` on the
`gcp_full` profile. The generation-55 manual walkthrough had already completed
all six paths and independently verified all six current-generation receipts.
On 2026-07-18, the dedicated reliability runner then entered through the
external Kasm browser terminal and passed the declared reliability gates:

| Challenge | Class | Result | Required | Wilson 95% interval |
|---|---|---:|---:|---:|
| `kep-m03-a` | deterministic | 10 / 10 | 10 / 10 | 0.722460–1.000000 |
| `kep-m03-b` | deterministic | 10 / 10 | 10 / 10 | 0.722460–1.000000 |
| `kep-m03-c` | model-sensitive | 30 / 30 | 27 / 30 | 0.886483–1.000000 |
| `kep-m03-d` | model-sensitive | 30 / 30 | 27 / 30 | 0.886483–1.000000 |
| `kep-m03-e` | model-sensitive | 30 / 30 | 27 / 30 | 0.886483–1.000000 |
| `kep-m03-f` | model-sensitive | 30 / 30 | 27 / 30 | 0.886483–1.000000 |

This closes Module 03's declared pre-playtest reliability gate for Module 03 implementation.
It is not a scenario-wide reliability claim or a golden claim. Modules 04
through 10 retain their own reliability work, so the pack remains `draft`.

## Participant-Surface Path

The manual and automated runs used the synthetic in-world participant identity
and the same Kasm desktop, gateway, and receipt routes available to a
participant. They did not use SSH, Terraform, cloud-console, database,
proof-store, or generated-secret access to satisfy a challenge. Together they
established that:

- all six item receipts were unavailable before their qualifying actions;
- a participant document was chunked, embedded by the pinned MiniLM ONNX
  model, stored in PostgreSQL with pgvector, and returned by real vector search;
- participant content outranked a trusted baseline without removing that
  baseline from the comparison set;
- separate server-owned model controls and retrieval-backed calls established
  the changed decision and citation outcomes;
- the live model, real OPA policy, and broker produced the contained notice
  effect; and
- a genuine document revision and reindex influenced a new server-owned
  session and produced the contained higher-authority approval effect.

Each item remained bound to its distinct evidence predicate. A stored but
unretrieved row, caller-authored rank or verdict, model text without a brokered
effect, revision one, or a reused session could not substitute for the required
path.

## Reliability Method

The campaign began with one canonical full-range reset into generation 20 and
full health/reset verification. Challenges A and B then ran once in each of ten
clean module-state samples. Between samples, the runner quiesced, reset, and
verified only the minimal context dependency closure: the PostgreSQL/pgvector
dataset store and the inference gateway that recreates the trusted retrieval
chunks and runtime boot baseline. This avoided restarting unrelated services
while preserving the SDL-declared clean-state invariant.

After a final scoped reset, challenges C through F ran for 30 attempts each.
The participant program created and searched a real document, completed the
A/B prerequisites, reindexed the document for each later path, and exercised
the live model, citation, policy, and broker predicates. Deterministic paths
required 10/10. Model-sensitive paths required at least 27/30; all four
achieved 30/30.

The participant calls declared the Python interface and `none` assistance mode,
so the existing research telemetry contract can distinguish these unassisted
reliability attempts without storing prompt or document bodies. Observational
telemetry did not participate in objective or reliability scoring.

An atomic owner-only checkpoint retained only completed aggregate counts. It
was bound to the exact range, participant, deployment state, runtime sources,
rehearsal sources, and lifecycle sources; it failed closed after a lifecycle
source change and was removed after the final report was written.

## Reset, Health, And Scope

The reliability campaign left the retained range ready at reset generation 20.
The canonical health report covered all 15 assets and services. Every scoped
cycle passed both node-local reset verifiers, including the datastore's
zero-participant-state and trusted-baseline checks. No account, project,
billing, or IAM resource was created or changed, and the existing range remains
retained for the next module.

The earlier completed Phase-E teardown belongs to the prior proof range and is
recorded separately. It does not imply teardown of this intentionally retained
range.

## Evidence Handling

Raw reports and checkpoints remain owner-only and gitignored. This snapshot
contains aggregate counts and intervals only. It excludes cloud project, range
and resource identifiers, addresses, credentials, browser state, tokens,
receipts, prompts, completions, model data, and raw telemetry.
