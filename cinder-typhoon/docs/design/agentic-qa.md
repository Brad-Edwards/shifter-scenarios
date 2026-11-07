# Participant-view agentic QA

Status: implementation design for issue #328.

## Decision

Run one isolated agent session for each operation against the immutable Cinder
goldens. A session receives only the published cards for that operation, hints
that it explicitly requests, and one participant proxy. The proxy can execute
commands only as the real participant user in the matching workstation
container. It cannot expose GCP, Docker, host paths, repository source, runtime
source, tests, operator records, or generated credentials to the agent.

The three phase runs preserve campaign state. Training starts pristine.
KeplerOps and ARWC start pristine together, KeplerOps earns the selected
customer transition, and ARWC continues from that earned transition. Operation
sessions within a phase retain the participant home and range state. Every
operation carries one shared campaign identity while each phase keeps its own
stable participant-container reset identity. KeplerOps completes before ARWC
starts, and operation sessions in each phase cannot overlap or run out of
catalog order. Every operation also uses the same exact agent identity and
configuration.

## Trust boundaries

```text
published cards and hints
          |
          v
isolated agent workspace ----> participant proxy ----> exact golden instance
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

The agent process runs from a temporary directory outside the checkout. Its
only command tool is the proxy executable. The proxy uses an operator-owned GCP
session, but the agent cannot invoke `gcloud`, SSH, Docker, or local file tools
directly. The remote command always enters one fixed container with the phase's
participant user, home, working directory, dropped capabilities, and existing
`no-new-privileges` control.

Raw agent messages, participant commands, responses, credentials, payloads,
and target artifacts remain in an operator-only temporary evidence directory.
The committed report contains only bounded classifications, counts, elapsed
times, expected points, and SHA-256 bindings.

## Session protocol

Each operation runs in catalog order. The agent must:

1. Read the published card descriptions through the proxy.
2. Mark a card as started before its first participant command.
3. Work only through the participant proxy.
4. Request a published hint through the proxy when needed.
5. Mark the card passed only after it observes the expected participant-visible
   evidence. Otherwise it records a failed attempt and one bounded failure
   category.
6. Record confusing, misleading, or fragile behavior even when a later attempt
   passes.

The proxy maintains a SHA-256 hash chain over card lifecycle events, the exact
score result, hint requests, participant command digests, response digests,
byte counts, and exit status. This provides a content-free start and end
observation for every card. It rejects missing card lifecycle events and
commands outside the selected phase.

## Result and failure classification

The final report has exactly one result for every card in the versioned
challenge catalog. Each result repeats the exact agent product, model, client
version, configuration, and tool list. It also records:

- card, operation, and segment;
- campaign and phase reset identities;
- start and end participant-view hash-chain states;
- elapsed time, attempt count, and released hint levels;
- passed or failed outcome;
- expected points and score result;
- participant command count and transcript digest;
- any bounded confusing, misleading, or fragile observations; and
- `agent_strategy` or `implementation` for a failed result.

The candidate-bound known-solution assertion named by the card-coverage
registry is the independent range-evidence check. The assembler accepts this
evidence only after the existing reliability validator accepts the complete
reliability report for the same candidate.

The agent records the score result that it observed through the participant
proxy. The proxy requires an accepted result with the card's exact points for
a passing attempt. The assembler copies this result and never creates an
accepted score from the attempt outcome.

An agent failure with passing independent evidence is an agent-strategy
failure. A failed independent assertion is an implementation failure. A
passing final report requires both accepted score results and passing
independent evidence for every card.

## Findings and retests

Every material implementation, clarity, or fragility finding receives one
GitHub issue and becomes a native blocker of #328. The original failed result
remains in operator evidence. After the fix is merged and deployed, the harness
restores a fresh pristine state and reruns the affected operation with the same
agent configuration. The final report identifies the finding issue and the
passing retest run without including raw transcripts or answer material.

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
operation exports share one campaign identity, and exports for one phase use
one reset identity. Every agent tool list is exactly `cinder-participant`.

## Invariants

1. The report binds to one immutable candidate and release manifest.
2. The report card IDs equal the 240-card catalog exactly.
3. Each card has one participant command, lifecycle timing, and a changed
   participant-view audit state.
4. Released hints are valid levels from the candidate-bound hint catalog.
5. Agent claims cannot produce an accepted score without independent
   candidate-bound range evidence.
6. Source, tests, operator paths, host control, and general local tools are
   unavailable to the agent.
7. No credential, payload, raw response, command, private path, or transcript
   enters the committed report.
8. Failures and bounded adverse observations remain visible when a later
   attempt succeeds.
9. A material finding blocks #328 until its focused fresh-state retest passes.
10. The assembler validates the reliability report instead of trusting its
    status fields.
11. A passing card carries an explicit accepted score with its exact points.
12. All operations share one campaign identity, each phase keeps one reset
    identity, KeplerOps precedes ARWC, and every operation uses the same agent
    configuration.
