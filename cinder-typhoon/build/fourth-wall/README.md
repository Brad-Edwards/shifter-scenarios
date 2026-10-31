# Fourth-wall leakage gate

This operator-only gate rejects challenge implementation language and
challenge-derived naming from Cinder Typhoon's participant surface. It checks
the authored runtime and image inputs, then repeats the check against files,
filenames, browser state, generated artifacts, safe read-only responses,
schemas, banners, service names, routes, and errors observed from the real
unprivileged participant context.

The policy derives all 240 card IDs and normalized titles from the private card
registry. It also rejects terms such as `CTF`, `flag`, `score`, `challenge`,
`integration test`, `fixture-only`, `expected answer`, and `author contract`.
The matching value is never copied into a report: findings contain only the
matched rule or normalized alias, its location, and a SHA-256 hash.

Run a source-only author check with:

```sh
python3 cinder-typhoon/build/fourth-wall/run.py \
  --phase arwc --static-only
```

Source-only output cannot qualify a release. The release form starts the
existing phase container, streams `observe.py` and a bounded policy to its
normal participant identity, and performs only `GET` requests against the
reviewed host/port universe in the participant-surface manifest. File count,
file size, total bytes, response size, and request count are bounded; reaching
any limit fails the gate instead of silently truncating coverage:

```sh
python3 cinder-typhoon/build/fourth-wall/run.py \
  --phase arwc --require-clean \
  --output /tmp/cinder-fourth-wall-arwc.json
```

`check-golden.sh` runs the same command through the documented IAP path. The
observer receives no credentials, operator paths, solutions, request payloads,
or write methods. It uses the scenario CA for TLS. Its standalone observation
contains findings and counts only; use `--observed-output` to retain it for an
operator review or `--observation` to recheck a retained observation.

Candidate qualification observes the pristine participant surface before the
known-solution run and repeats the observation afterward. The second pass
covers generated files and the resulting read-only service state.

The current gate remains unresolved for non-route findings. KeplerOps domain
interface review is pending under #212. The ARWC domain interface is approved
as explicit resource families: every `/api/` and `/internal/` route must match
one of those reviewed patterns, so an arbitrary title or card-ID alias cannot
satisfy the check.

## Allowlist

`allowlist.json` begins empty. An in-world use may be allowed only by an exact
entry binding source kind, location, rule, match, and content SHA-256 to a
specific rationale. A broad path, regular expression, or term-only exception
is not supported. Changed content stops matching the exception.
Domain-interface approval and incomplete live observation are structural gates
and cannot be allowlisted at all.

The allowlist, policy, reports, and test code must never be copied into a
participant image. Normal business words are not silently exempted: protocol
flags, operational scores, staff training exercises, and similar uses require
the same exact review.
