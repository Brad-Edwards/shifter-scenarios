# Participant-view agentic QA

Status: implementation design for issue #328.

## Decision

Run one white-box participant-experience session for each operation against the
immutable Cinder goldens. The QA operator can inspect the repository's briefs,
tests, registry, and known solution before guiding the session. Participant
actions still use one participant proxy. The proxy can execute commands only as
the real participant user in the matching workstation container. It cannot
expose GCP, Docker, host paths, operator records, or generated credentials to
the participant session.

The three phase runs preserve campaign state. Training starts pristine.
KeplerOps and ARWC start pristine together, KeplerOps earns the selected
customer transition, and ARWC continues from that earned transition. Operation
sessions within a phase retain the participant home and range state. Every
operation carries one shared campaign identity. A phase normally keeps one
participant-container reset identity. The report can declare an operation as a
reset boundary when an operator reset is necessary and earlier operations must
not be replayed. The reset record preserves whether the first accepted
operation began `pristine` or `retained`, and it must use the declared new
identity. A `retained` label is valid when operator setup or state repair occurs
after the reset but before that operation. Every ARWC operation records the
phase's `transition-earned` condition. KeplerOps completes before ARWC starts,
and operation sessions in each phase cannot partially overlap. A fully nested
interval is valid when the outer operation was paused while complete inner
operations ran. Catalog order controls the report and reset-state chain, but a
completed operation remains valid if an operator correction changes completion
order. This avoids destructive replay of already verified participant work.
Within an operation, every proxy-backed card uses the same session identity
and configuration.

## Trust boundaries

```text
published cards and hints
          |
          v
participant workspace -------> participant proxy ----> exact golden instance
       |                              |                       |
       | no repository               | fixed container       | scenario services
       | no general shell            | fixed participant     | and participant state
       | no GCP or Docker             | command only          |
       v                              v                       v
operator-only raw transcript     hash-chain audit       range evidence
          |                              |                       |
          +------------------------------+-----------------------+
                                         |
                                         v
                       credential-free per-card report
```

The QA operator inspects source outside this boundary. The participant session
runs from a temporary directory outside the checkout.
Its only range command tool is the proxy executable. The proxy uses an
operator-owned GCP session, but the participant session cannot invoke `gcloud`,
SSH, Docker, or host file tools directly. The remote command always enters one
fixed container with the phase's participant user, home, working directory,
dropped capabilities, and existing `no-new-privileges` control.

Raw agent messages, participant commands, responses, credentials, payloads,
and target artifacts remain in an operator-only temporary evidence directory.
The committed report contains only bounded classifications, counts, elapsed
times, expected points, and SHA-256 bindings.

## Session protocol

Operations normally run in catalog order. If an ordering mistake is found, the
operator completes only untested work and retains clean, non-overlapping
exports from work that is already verified. For each operation, the QA operator
must:

1. Inspect the published card and its expected path before participant work.
2. Mark a card as started before its first participant command.
3. Run all participant actions through the participant proxy.
4. Guide the session directly to the expected path when necessary.
5. Mark the card passed only after the participant-visible score is accepted.
6. Record a failed attempt only when the expected path fails.
7. Record confusing, misleading, or fragile product behavior.

Agent discovery mistakes, wrong turns, and operator guidance are not product
failures. They do not enter the final report.

The proxy maintains a SHA-256 hash chain over card lifecycle events, the exact
score result, hint requests, participant command digests, response digests,
byte counts, and exit status. This provides a content-free start and end
observation for every card. It rejects missing card lifecycle events and
commands outside the selected phase.

## Result and failure classification

The final report has exactly one result for every card in the versioned
challenge catalog. A normal `participant_proxy` result repeats the exact agent
product, model, client version, configuration, and tool list. It also records:

- card, operation, and segment;
- campaign and phase reset identities;
- start and end participant-view hash-chain states;
- elapsed time, attempt count, and released hint levels;
- passed or failed outcome;
- expected points and score result;
- participant command count and transcript digest;
- any bounded confusing, misleading, or fragile product observations; and
- `implementation` for a failed expected-path attempt.

The candidate-bound known-solution assertion named by the card-coverage
registry is the independent range-evidence check. The assembler accepts this
evidence only after the existing reliability validator accepts the complete
reliability report for the same candidate.

The session records the score result that it observed through the participant
proxy. The proxy requires an accepted result with the card's exact points for
a passing attempt. The assembler copies this result and never creates an
accepted score from the attempt outcome.

The assembler can replace a failed exploratory result with a
`candidate_reliability` result only when the operator explicitly names that
card. This result contains no participant score, attempts, session metadata, or
agent errors. It binds the card to its passing registry assertion and the
validated candidate reliability report. This option is for product evidence
that predates the white-box method; it does not create an accepted participant
score.

A failed expected path is an implementation failure. A passing final report
requires passing independent evidence for every card. Each card also requires
either an accepted participant score or an explicit passing
`candidate_reliability` result.

## Findings and retests

Every material implementation, clarity, or fragility finding receives one
GitHub issue and becomes a native blocker of #328. After the fix is merged and
deployed, the harness restores a fresh pristine state and reruns the affected
operation with the same configuration. The final report identifies the finding
issue and the passing retest run without including raw transcripts or answer
material.

A candidate change invalidates the complete report. A focused retest accepts
the remediation before the final full-catalog run. The final run then binds all
240 results to the updated immutable candidate.

## Checked evidence flow

The implementation enforces this order:

1. `prepare.py` binds one operation to the current immutable candidate and
   release manifest.
2. `proxy.py` writes one strict operation export from its locked audit state.
3. `assemble.py` validates every operation export and the existing reliability
   report before it creates the final report.
4. `validate.py` checks the final report against the current candidate,
   release manifest, challenge catalog, card registry, and report invariants.

The assembler requires exactly one operation export for each catalog
operation. Within each export, card audit states form an unbroken chain. All
operation exports share one campaign identity. Exports for one phase use one
reset identity unless the report declares the exact operation where the
identity changed. Every participant-session tool list is exactly
`cinder-participant`.

## Invariants

1. The report binds to one immutable candidate and release manifest.
2. The report card IDs equal the 240-card catalog exactly.
3. Each `participant_proxy` card has one participant command, lifecycle timing,
   and a changed participant-view audit state.
4. Released hints are valid levels from the candidate-bound hint catalog.
5. Agent claims cannot produce an accepted score without independent
   candidate-bound range evidence.
6. Operator source and test inspection stays outside the participant proxy and
   its committed evidence.
7. No credential, payload, raw response, command, private path, or transcript
   enters the committed report.
8. Product failures and bounded adverse observations remain visible when a
   later expected-path attempt succeeds.
9. A material finding blocks #328 until its focused fresh-state retest passes.
10. The assembler validates the reliability report instead of trusting its
    status fields.
11. A passing card carries an accepted score with its exact points or an
    explicit candidate-reliability evidence basis.
12. All operations share one campaign identity. Each undeclared reset change
    fails validation. KeplerOps precedes ARWC, and each proxy-backed operation
    uses one consistent session configuration.
