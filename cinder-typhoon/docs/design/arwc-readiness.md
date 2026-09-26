# ARWC SDL hand-build readiness

**Status:** Gate passed. Alterra Regional Water Company is ready for
hand-building.

This ledger is the durable record for the ARWC design tranche. It covers design
and SDL authoring only; no service, binary, image, process simulator, evidence
adapter, or range has been materialized.

## Exit condition

ARWC is ready for hand-building only when all 120 W cards have deterministic
in-world mechanisms, native RAE placement, exact owned starting state, ordinary
and denial behavior, persistent participant-scoped mutations, independently
owned evidence, usable downstream joins, and a coherent bounded process model.
The composed scenario must pass the pinned RAE parser, validator, processor,
environment-pack checks, the Training and KeplerOps gates, and a focused ARWC
gate. Private `cinder_kind` relationship meanings and generic starting-record
placeholders are not accepted evidence of readiness.

## Overall plan

| ID | Work | Required evidence | State |
| --- | --- | --- | --- |
| ARW-00 | Inventory the 120 cards, dependencies, existing ARWC world and route modules, narrative packages, consequences, and remaining private semantics. | A checked inventory and ownership baseline. | Complete |
| ARW-01 | Freeze native RAE vocabulary and the modular boundary. | Native-semantics note; no required project-private decoder or missing upstream semantic. | Complete |
| ARW-02 | Define the process model and consequence quantities. | Dimensionally checked reservoir, measurement, practice, live, rehearsal, cost, and restriction contracts. | Complete |
| ARW-03 | Assign every card's authoritative owner, starting artifacts, result, downstream use, evidence producer, and exact native surface. | Complete 120-row ownership matrix with narrative reuse named rather than copied. | Complete |
| ARW-04 | Complete corporate and identity systems W01-W12 and W35. | Exact routes, identities, authorization, storage, mechanics, service contracts, and technical cards. | Complete |
| ARW-05 | Complete maintenance and read-entry systems W13-W16. | Exact routes, identities, authorization, storage, mechanics, service contracts, and technical cards. | Complete |
| ARW-06 | Complete process-observation and engineering-evidence systems W17-W25. | Exact routes, binaries/data formats, observations, mechanics, service contracts, and technical cards. | Complete |
| ARW-07 | Complete control, consequence, and optional advanced systems W26-W34. | Exact issuance, command, independent measurement, planning, rehearsal, and consequence contracts. | Complete |
| ARW-08 | Replace ARWC private flow/context/relay/surface meanings with native declarations and ordinary typed relationships. | No ARWC `cinder_kind`, no generated W `challenge_surface`, and no obsolete `flows-a-*` modules. | Complete |
| ARW-09 | Synchronize all W operation modules and cards. | 120 Technical drafts; action/evidence contracts match cards and exact content; no generic seed records. | Complete |
| ARW-10 | Add focused validation and regressions. | ARWC hand-build gate, unit tests, generator idempotence, native surface resolution, denial/isolation checks, narrative-reference checks, process invariants. | Complete |
| ARW-11 | Run the complete static gate and record the checked tree. | Pinned RAE parse/compose/validate/instantiate/compile plus all three phase gates and design tests. | Complete |

## Design invariants

- Completion observes an effect already produced by an in-world service; it
  never grants the permission or creates the state needed to prove itself.
- Infrastructure recovery and submission adjudication remain external. Normal
  participant-created service state persists across retries and day-two resume.
- Corporate data, OT observations, estimate publication, practice movement,
  live command authority, actuation, and consequence accounting are distinct.
- `a-instruments` owns independent process truth. Estimate or report control
  cannot change it. Command acknowledgements do not prove movement.
- W26 and W28 issue equivalent narrowly scoped control clients through distinct
  routes. Neither route waives mapping, revision, mode, envelope, or plan joins.
- W33 and W34 use separate private rehearsal checkpoints and cannot overwrite
  the W30 live result or previously earned evidence.
- Existing narrative packages stay authoritative for ordinary workplace mail,
  documents, directory, and employment records. Challenge services refer to
  exact existing artifact IDs where relevant and do not seed copied collections.
- Participant-visible content stays in-world: no flags, hints, scores, CTF
  language, solution commentary, or fourth-wall instructions.

## Validation log

- The composed scenario passes structural and semantic validation with pinned
  `raes==5.0.0`; 127 imported modules instantiate and compile to 3,460
  realization requirements and 281 source-bound observations.
- The `raes-env-packs==6.1.0` author check passes with the explicit 2,048-member
  source-pack budget.
- The Training, KeplerOps, and ARWC native hand-build gates pass together. The
  ARWC gate resolves all 120 deterministic contracts to their owned routes and
  files, checks all 120 action/evidence contracts, and rejects private
  relationship semantics.
- The focused ARWC suite passes 16 positive and adversarial checks. The 15
  Training, 13 KeplerOps, and 17 K09 handoff checks also pass, as do the
  portfolio and dependency validators.
- The KeplerOps and ARWC authoring generators are idempotent when run in
  sequence. The [validation record](../sdl-validation.md) records the checked
  tree digest and complete boundary.

## Exit boundary

ARWC is ready for a progressive hand build. Stop here. The next authorized
work is the golden-range extension, followed by integration testing and initial
playtest observation. It has not started. Do not create repositories, binaries,
services, images, process simulators, deployment state, or evidence adapters
until that later stage is explicitly started.
