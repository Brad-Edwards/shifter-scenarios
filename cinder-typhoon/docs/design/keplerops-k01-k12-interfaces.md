# KeplerOps K01–K12 interface acceptance

This report fixes the legitimate user, baseline workflow, discovery path, and
normal interface for each opening operation. The machine-readable contract is
`keplerops-k01-k12-interfaces.json`; the KeplerOps design gate checks it against
the published client-reference inventory and the known-solution route use.

## Interface model

| Operation | Intended user | Normal interface family | Supplied source or reproducer |
| --- | --- | --- | --- |
| K01 | Connector developer resuming work | Git, handover, browser state, local helper | None |
| K02 | Developer repairing a failed report build | Repository history, CI run/import/job, support handover | None |
| K03 | Developer reconstructing an interrupted collection | Workstation artifacts and local helpers | None |
| K04 | Developer reproducing a native indexer defect | Bundle index collection | Offline binary reproducer promised by the design |
| K05 | Package maintainer reconciling a consumer | Package, release, reconciliation, resolver resources | None |
| K06 | Package maintainer importing and rehearsing a release | Import, package, view, CI rehearsal resources | None |
| K07 | Package assessor comparing inspector interpretations | Inspection collection, trace, envelope resources | None |
| K08 | Release maintainer validating retained compatibility | Entitlement record and compatibility-check resources | None |
| K09 | Build engineer investigating retained review output | CI run, artifact links, review-job collection | None |
| K10 | Support developer reproducing a preview collision | Attachment association, document, render resources | None |
| K11 | Release engineer migrating a retained compiler | Git migration kit, evaluation collection, nonce collection | Retained binary and migration artifacts promised by the design |
| K12 | Preview operator processing an assigned review | Assignment, one-use action, reviewer render resources | None |

K01–K03 deliberately begin from assigned workstation state rather than the
public client-reference graph. K04–K12 use ordinary service references and
response links. No operation has a card-title route or a separate completion
endpoint.

## Trust boundaries and data flow

```text
assigned workstation state or published service reference
                         |
                         v
normal authenticated resource and ordinary response links
                         |
                         v
vulnerable behavior on that same resource
                         |
                         v
service-owned audit and independent objective evaluation
```

The participant never receives the author contract, the complete route map, or
the known-solution suite. K04 receives only the promised offline reproducer and
must derive its layout and sentinel by analysis and probing. K11 receives the
promised migration repository; opcode semantics and the complete constraint
program come from the retained binary rather than a service-published answer or
unexplained constants in the known solution.

## Failure behavior

The static gate fails if an operation is missing, a route key is unpublished,
the known solution uses an undeclared route key, another operation gains source
or a reproducer, or an opening route uses exercise, challenge, or completion
vocabulary. Service tests separately retain normal, denied, persistence, audit,
and isolation cases.

Automated checks prove the authored interface contract and known path. They do
not prove discovery quality, fairness, difficulty, or duration; those blind
human-plus-agent observations remain tracked by issue #229.
