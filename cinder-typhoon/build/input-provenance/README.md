# Solution-input provenance

This operator-only ledger makes the source of every known-solution request
input reviewable without copying answers, secrets or exploit recipes into a
participant image. It serves two related gates:

- every request callsite in the Training, KeplerOps and ARWC known-solution
  suites has a normalized SHA-256 snapshot and a provenance entry;
- every fixed literal comparison in phase runtime Python has a normalized
  SHA-256 snapshot, so a new or changed comparison requires ledger review;
- every non-Python runtime source file has a full-source SHA-256 ratchet, so
  shell, C, C++, C#, Go, Nim and assembly comparisons cannot bypass the gate.

The static report identifies request and comparison source locations, hashes,
provenance classes, citations and unresolved issues. It never includes literal
values, request bodies, credentials, cookies, certificates, bearer tokens or
response contents. The participant-boundary runner adds the applicable entry
to each live request event by test method. A request from an unlisted method, a
new callsite, a changed input expression or a changed fixed runtime comparison
fails validation.

Permitted provenance classes are:

- `supplied_starting_surface`;
- `normal_interface_or_artifact`;
- `earlier_accepted_response`;
- `deterministic_transformation`;
- `computed_from_participant_visible_inputs`.

A citation names the exact participant-visible file, interface, response,
calculation or computation and the relevant locator. A protocol constant is
complete only when its participant-visible schema or implementation is cited.
Anything else remains in `unresolved` with a fingerprint and remediation issue;
it is not silently accepted through a generic phase profile.

Generate the credential-free report with:

```sh
python3 cinder-typhoon/build/input-provenance/provenance.py \
  --output /tmp/cinder-provenance-report.json
```

The release form exits nonzero while any input or fixed comparison remains
unresolved:

```sh
python3 cinder-typhoon/build/input-provenance/provenance.py --require-complete
```

The current ledger passes that release form. Updating an inventory hash merely
acknowledges a code change; a remediation is complete only when every changed
input also has a specific participant-visible citation and no unresolved entry.

For a new scenario only, `--new-unresolved-ledger PATH` creates a fail-closed
review skeleton and refuses to overwrite an existing file. It marks every
request and comparison unresolved; it is not a way to approve changes.

The ledger is test and release evidence only. It does not establish that a
fresh participant can discover, understand or complete the path.
