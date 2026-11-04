# Participant-surface manifests

This directory defines and verifies the exact surface intentionally available to
a Cinder Typhoon participant. It is operator-only build and release material. No
file in this directory is copied into a participant image.

The check has two inputs and one generated artifact:

- `manifests/<phase>.json` is the reviewed authored manifest.
- `observe.py` and a reduced probe plan are streamed to the running participant
  context and execute as that phase's unprivileged participant identity. The
  plan excludes classifications, hashes, expected results, cards and disclosure
  analysis from the operator-only manifest.
- the observed manifest is JSON written to the operator's stdout or an
  operator-selected output path.

`run.py` compares the authored and observed manifests. A missing or unexpected
file below an inventoried root, changed file metadata or reviewed content hash,
missing tool, changed DNS result, changed listener result, forbidden-path
visibility or readability, root identity, or privileged observation causes
failure.

The operator uses Docker only to enter the already-defined participant context.
The observer receives no additional mount, Docker socket, host path, operator
credential, or elevated identity. It also verifies that service-state volumes
already present in a participant container remain inaccessible to that account.
It refuses to run as uid 0. This is the same boundary currently used by the
range's participant shell. The observed manifest records this fact so a
privileged or incorrectly mounted check cannot silently pass.

The companion `build/fourth-wall/` gate uses the same unprivileged phase
containers to inspect actual readable content and safe `GET` responses for
challenge implementation language and challenge-derived names. Its reports
contain matches and hashes, not file or response contents. Participant-surface
comparison establishes what is present; the fourth-wall check establishes that
the observed content does not break the scenario's in-world boundary.

## Schema

Both formats use `schema_version: 1`.

An authored manifest contains:

- `manifest_kind`: `authored`;
- `phase` and `state`;
- `participant`: exact user, primary and supplementary groups, home, working
  directory and numeric uid/gid;
- `filesystem.roots`: exact visible trees or individual files. Each expected
  entry records its relative path, type, mode, owner, group, and optionally
  size, SHA-256 or symlink target. `opaque` paths are intentional visible
  directories whose internals are not stable enough for exact inventory and
  must be justified;
- `filesystem.forbidden_paths`: paths whose expected visibility and readability
  are recorded separately. This covers both absent operator material and names
  that are visible by design while their contents remain inaccessible;
- `tools`: commands deliberately supplied to the participant;
- `network.dns`: names and expected IPv4 results;
- `network.listeners`: non-mutating TCP-connect probes from the participant
  network. The set is an explicit reviewed probe universe, not a port scan.
  A reachable listener may set `credential_free_get` to `false` when it
  requires client authentication; the fourth-wall observer then preserves the
  TCP reachability check without attempting an unauthenticated HTTP request;
- `disclosures`: participant-visible discovery documents and the facts or route
  families they expose. This makes over-disclosure auditable without copying
  document contents into the manifest;
- `delivery`: a digest-bound reference to the canonical versioned catalog and
  the phase's exact operation, card, and score totals. Card and hint lists are
  not copied into these manifests; the catalog remains their sole authority.

An observed manifest contains the same phase/state identity plus the measured
identity, file entries, tools, DNS results, listener reachability, forbidden
path visibility and security assertions. It contains no file contents or
credential values. Regular file content is represented only by size and
SHA-256.

`schema/authored.schema.json` and `schema/observed.schema.json` are the
machine-readable JSON Schemas. `validate.py` performs dependency-free strict
validation used by the unit and live checks.

## Local checks

Start the phase in pristine state, then run:

```sh
python3 cinder-typhoon/build/participant-surface/run.py --phase training
python3 cinder-typhoon/build/participant-surface/run.py --phase keplerops
python3 cinder-typhoon/build/participant-surface/run.py --phase arwc
```

Use `--observed-output <operator-path>` to retain the generated observed
manifest. The default compares in memory and writes no participant or operator
state.

## Golden checks

After the candidate commit has been deployed to the documented stack path, run:

```sh
cinder-typhoon/build/participant-surface/check-golden.sh training
cinder-typhoon/build/participant-surface/check-golden.sh keplerops
cinder-typhoon/build/participant-surface/check-golden.sh arwc
```

The wrapper uses IAP SSH to run `run.py` at the phase's recorded stack path. It
does not copy the authored or observed manifest into a participant container.
Project, zone, instance and remote source root can be overridden with the
documented environment variables in the script.
