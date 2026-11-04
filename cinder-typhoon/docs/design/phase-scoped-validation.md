# Phase-scoped validation

Issue #324 makes the shared Cinder validation tools work from the exact source
set deployed for one phase. It does not copy another phase's runtime or tests to
a golden and does not weaken the complete repository release gates.

## Data flow and trust boundaries

```text
complete reviewed repository
  |-- ARWC client-reference source ----> generated client-route contract
  |-- KeplerOps surface manifest -------^
  |-- all three suites and runtimes ----> complete provenance validation
  |
  +---- phase deploy archive --------------------------+
                                                        v
                                                one GCP golden
                                                  |-- common contracts
                                                  |-- selected suite
                                                  |-- selected runtime
                                                  v
                                       phase-local hint/provenance gates
                                                  |
                                                  v
                                       participant-boundary execution
                                                  |
                                                  v
                                  boundary result recorded before enrichment
```

The reviewed repository is authoritative for generating and checking shared
contracts. A phase golden is authoritative only for its selected phase files,
running images, participant boundary, and live results. A participant process
never receives the route contract, provenance ledger, test source, or operator
report.

## Client-route contract

`build/hint-delivery/published-client-routes.json` is the complete,
content-free set of route identifiers that hints may cite. The generator reads
KeplerOps client-reference disclosures from its participant-surface manifest
and ARWC route dictionaries from the runtime source. Training publishes no
client-route identifiers.

Repository validation must regenerate the set and reject any difference from
the committed contract. Phase-local hint validation reads the committed
contract and therefore does not require another phase's runtime tree. The
contract contains identifiers only. It contains no route templates, request
values, credentials, response content, or solution material.

## Provenance modes

Complete mode remains the release-authoring gate. It reads all three known-
solution suites and runtime trees, recomputes every request, Python comparison,
and non-Python source inventory, and compares the full result with the ledger.

Phase mode accepts exactly one of `training`, `keplerops`, or `arwc`. It still
requires the ledger's complete top-level shape, but it recomputes and validates
only the selected phase's suite and runtime entries. Its report contains only
that phase. A missing, extra, or changed selected-phase entry fails closed.
Entries for phases that are not deployed are neither trusted nor reported by
that golden; complete mode validates them in the repository and promotion
workflow.

## Report ordering and failure behavior

The runner validates and records the participant boundary result, sanitized
events, and stdout/stderr sizes and hashes immediately after the participant
process exits. Provenance enrichment runs afterward.

If enrichment fails, the overall report fails and records the enrichment error,
but retains the participant result and base evidence. Raw stdout, stderr,
request paths, bodies, headers, tokens, and response content remain absent.
This ordering distinguishes a scenario failure from an operator evidence
failure without allowing either one to pass.

## Invariants

1. A phase deployment never needs another phase's runtime or suite.
2. Complete validation still detects cross-phase inventory drift.
3. Phase validation detects all selected-phase inventory drift.
4. The committed route contract must equal a fresh complete-repository build.
5. A route removal and a selected-phase provenance mutation must both fail.
6. Provenance enrichment cannot change a failed participant result into a pass.
7. Provenance enrichment failure cannot erase a completed participant result.
8. Reports remain content-free and credential-free.
