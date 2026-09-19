# SDL validation

From the repository root, create an isolated Python 3.12+ environment and install
the matching upstream releases:

```sh
python3.12 -m venv /tmp/cinder-sdl-check
/tmp/cinder-sdl-check/bin/python -m pip install -r cinder-typhoon/tests/requirements-sdl.txt
/tmp/cinder-sdl-check/bin/python cinder-typhoon/tests/validate_sdl.py --self-test --pack-check
```

The command performs these checks:

1. Native `raes.parser.parse_sdl_file` parses and composes the complete campaign
   with structural and semantic validation enabled.
2. The validator independently decodes native workflow predicates, acquisition
   events, node memberships, authority features, and relationship contracts.
   It compares the resulting graph with the preserved design and replays all
   minimal prerequisite closures and all 16 finale route combinations. Separate
   checks compare action preconditions/effects, all five technical sections of
   the 50 drafted cards, proof owners, starting-record requirements, proposition
   quantifiers, and consequence effects with the design-side contracts.
3. `instantiate_scenario` and `compile_runtime_model` run on the whole scenario.
   Assertions check that default-open intent survives both steps, that omitted
   substrate/architecture/version choices remain open, and that Linux/Kali
   remains exact. Resource sizing must remain unspecified. The 273 challenge
   and capability observations retain their producer bindings, and four workplace
   readback observations retain exact content ownership. Source artifacts and
   named workplace service bindings survive compilation.
4. `--self-test` deliberately changes native type-valid SDL structures, including
   OR gates, current revision evidence, read/control scope, and rehearsal/live
   separation. Its 28 SDL mutations also remove or corrupt observation bindings,
   technical mechanisms, scope/reset requirements, seed ownership, and evidence
   joins. Four further SDL mutations alter workplace content ownership, source
   versions, observed readback, or its selected content. Two additional mutations
   attack the compiled selectors themselves.
   It also runs the existing 26 negative topology cases on the graph decoded
   from SDL.
5. `--pack-check` runs env-packs' author validation with local module resolution.

`raes-env-packs==6.1.0` intentionally denies imports through its public
`validate_pack` untrusted-ingest API. This authoring check therefore uses its
`_validate_pack_for_author_ci` entry point, pinned to that release. No runtime
delivery bundle or flattened ingest artifact is claimed. A future packaging
step must use the appropriate upstream author-to-consumer handoff.

The full native check is CPU intensive at this campaign size and can take
several minutes. It does not start targets, contact a cloud, or create assets.
The [validation record](../docs/sdl-validation.md) states what was established.

The earlier standard-library authoring checks remain beside their inputs in
[docs/design/](../docs/design/README.md). None of these checks establishes runtime
exploitability, isolation, evidence-adapter correctness, or event capacity.

## Workplace asset checks

The same validation environment can check the authored assets independently:

```sh
python cinder-typhoon/build/render_narrative.py --check
python cinder-typhoon/tests/validate_narrative.py
python -m unittest discover -s cinder-typhoon/tests -p test_narrative_integrity.py
```

These check deterministic rendering, source hashes, message headers and bodies,
reply chains, MIME attachment bytes and publication dates, retained mailbox copies,
document readers, directory entries, calendar times and audiences, and story
coverage. Corruption checks reject an altered attachment, a private
message copied to an unrelated mailbox, changed source bytes, and a detached
reply. The full SDL check also verifies the four native materialization contracts.
