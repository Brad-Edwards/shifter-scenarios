# SDL validation record

This record covers the design-only hand-build boundary for all three Cinder
Typhoon phases. It does not approve a realization, runtime, deployment, or
golden range.

## Checked state

Recorded on **2026-09-25** with pinned `raes==5.0.0` and
`raes-env-packs==6.1.0`:

| Check | Result |
| --- | --- |
| Native RAE parse, composition, and semantic validation | Pass; 127 imported modules |
| Native instantiation and whole-scenario compilation | Pass; 3,460 realization requirements |
| Explicit compiled observation sources | Pass; 281 observations |
| Training hand-build design gate | Pass; 16 cards and 47 exact files |
| KeplerOps hand-build design gate | Pass; 104 cards and 104 deterministic service contracts |
| ARWC hand-build design gate | Pass; 120 cards and 120 deterministic service contracts |
| Portfolio and dependency design | Pass; all 240 cards are Technical drafts with the 60/94/52/27/7 tier distribution preserved |
| Native relationship semantics | Pass; no meaning-bearing private relationship properties, challenge-surface edges, contexts, relays, or private decoder remain |
| In-world content boundary | Pass; Training assets and KeplerOps/ARWC service configurations contain no CTF, flag, hint, score, player, challenge, difficulty, hand-build, or fictional-world commentary |
| Focused regression suites | Pass; 15 Training, 13 KeplerOps, 17 K09 handoff, and 16 ARWC tests; four type-valid narrative SDL mutations rejected |
| Design validators | Pass; 240 cards, full AND/OR closures, both ordinary entry routes, all 16 finale route combinations, and 27 deliberately broken graphs rejected |
| KeplerOps and ARWC authoring generators | Idempotent when run in sequence |

The `sdl/` tree contains 128 YAML documents: one entry point and 127 imported
modules. Their aggregate SHA-256 is
`3e20302db98aa5ba0fe1fc682246915f0a5413f14f282336fdaf2298d09c98fc`.
The digest processes YAML paths relative to `sdl/` in sorted order, appending
each path, a NUL byte, its exact file bytes, and another NUL byte.

## Native-semantics result

The primary validator reads native nodes, runtimes, application routes,
identities, authorizations, content, workflows, action contracts, evidence,
propositions, assertions, events, and injects. It has no decoder for
`cinder_kind`, `flow_kind`, `context_kind`, `modes`, `guard`, or any equivalent
project-private relationship language. The focused phase gates reject the
return of those properties.

The root and every module declare:

```yaml
realization:
  default: open
```

Compilation confirms that unspecified substrate, architecture, and version
choices remain open while explicit OS and Kali distribution choices remain
exact. No resource sizing or backend is selected by this design.

## ARWC result

ARWC has eighteen fixed logical systems across five native network groups,
exact node addresses, listeners, application routes, local and application
identities, grants, owned storage, and ordinary business integrations. Seventeen
service-owned content modules carry one deterministic initial-state and behavior
contract for each of the 120 cards. Every contract resolves to its declared
application route and, where applicable, an inventoried offline artifact path.

The cards and SDL agree on normal behavior, the exact weakness or interpretation
mechanic, accepted and denied inputs, mutable and persistent state, independent
evidence, downstream joins, and isolation. Exploit-sensitive contracts freeze
the relevant parser order, authorization omission, protocol, binary layout,
instruction set, integer behavior, cryptographic construction, compiler flags,
memory layout, query budget, and process quantities. Existing narrative
artifacts are referenced by exact object ID and are not copied into challenge
fixtures.

The bounded process gate independently recalculates:

- the 13.40 ML business report, 12.40 ML independent reserve, 12.00 ML
  commitment, 1.00 ML error, and 0.40 ML initial margin;
- the 0.012 ML commissioning trace and isolated 0.030 ML practice movement;
- the balanced 1.00 ML live release, 11.40 ML remaining reserve, 0.60 ML
  shortfall, USD 1,440 liability, and Stage A restriction;
- the twelve-interval 0.81 ML scheduling rehearsal, 11.59 ML independent
  reserve, 0.41 ML shortfall, and USD 984 liability; and
- all 27 Cartesian demand-offset, outlet-gain, and observation-delay cases for
  the single observation-driven `ARWC-POL1` policy, including state, action,
  ramp, final-buffer, and reservoir-volume bounds.

Practice, live, scheduling-rehearsal, and reporting-rehearsal storage are
disjoint. A planning estimate cannot change independent instrument truth, an
acknowledgement cannot prove movement, and a consequence event cannot issue or
repeat the action whose already-owned evidence triggered it.

## Narrative and compilation result

The eight digest-versioned workplace collections retain their source versions,
service bindings, owners, and observed readback requirements after compilation.
The pack's narrative validators continue to check the source artifacts and
reader boundaries independently. Those collections supply ordinary in-world
context; they do not replace the exact challenge-specific records.

All 281 compiled observations retain exact producer component references. This
includes 273 challenge/capability observations and eight workplace readbacks.
Joined results require all named independently owned producers for the same
tenant instance and correlation.

## Reproduction

From the repository root, use the environment and command in
[tests/README.md](../tests/README.md). The complete native gate is:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/cinder-sdl-check/bin/python \
  cinder-typhoon/tests/validate_sdl.py \
  --pack-check --pack-max-members 2048 \
  --training-hand-build-gate \
  --keplerops-hand-build-gate \
  --arwc-hand-build-gate
```

The explicit 2,048-member author budget is required because the source pack is
larger than the upstream default 1,024-member ingest budget. The validation uses
the pinned environment-pack author-CI entry point so local imports are resolved.
It does not claim that an unflattened author tree is a consumer delivery bundle.

## Boundary

These checks establish a complete, internally consistent, legal native SDL
design ready to hand-build. They do not establish that a service, binary,
container, process model, evidence adapter, or range exists; that a built
weakness is exploitable; that isolation works under load; or that the proposed
difficulty and timing survive playtesting. Those are later golden-range,
integration-test, and playtest gates. No materialization was performed during
this design pass.
