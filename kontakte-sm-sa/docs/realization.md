# Realization

## Authoritative source

The cloud model comes from the bundle's `cloud-terraform/main.tf.json`.
The workstation comes from `shifter-pack/sdl/kontakte-sm-sa.sdl.yaml`.
The source digests and exact Terraform declarations are kept in the repository's
private design record for issue 276. They are not client configuration.

| Source declaration | Count | SDL representation |
| --- | ---: | --- |
| Service account | 44 | Scoped service-account subject |
| Secret | 391 | Native secret ID with explicit automatic replication |
| Secret version | 391 | One enabled version; payload left open |
| Secret IAM member | 489 | Resource-policy permission binding |
| Project IAM member | 26 | Project-scope permission binding |
| Service-account IAM member | 47 | Subject-attached permission binding |
| Audit configuration | 1 | Project-owned Secret Manager `DATA_READ` audit log |

The root SDL preserves the source workstation and LAN. One pinned local module
adds one cloud node with both the IAM authority and the Secret Manager
application. Its compute realization is open. It does not require another VM.
The source workstation keeps its exact virtual-machine constraint.

## Exact values and open inputs

Account IDs, full display names, native secret IDs, roles, policy attachments,
and bindings remain exact. Portable secret IDs serve only as RAES reference
identities. Where two native IDs differ only by case, the portable IDs have a
digest suffix; `native_id` keeps the source spelling.

The range-project scope has no native project ID. BigRAE binds it to the
registered project. No client file can override that project or its lease.

All outside principals remain distinct. They have operator origin and no
range-project ownership scope. The cloud module parameterizes their full IAM
member names with the author's aliases as defaults. RAES binds those defaults
at module import; its composition provenance must retain their parameterized
explicitness. This permits the administrator-bound adapter to hydrate declared
inputs without changing exact values. The adapter must not create stand-in
accounts or omit bindings.

Secret version payloads remain unspecified in SDL. The adapter supplies each
value from `secret_values`, or uses `synthetic-range-secret` when that key is
absent. A supplied empty string stays supplied. No additional payload file is
declared. `foothold_credential` and the source credential file stay intact.

The Terraform does not build the further secret versions or account keys listed
as unbuilt in the source manifest. This pack does not add them.

## Lifecycle

One active range may use a registered project. BigRAE records the baseline and
must restore it on teardown. Create service accounts before their bindings,
with bounded retries while the accounts propagate. Remove the bindings before
deleting accounts, including owned `deleted:serviceAccount` policy members.
The adapter removes its issued foothold key too.

A parity check must compare all account names and display names, secret IDs and
replication, version state and protected payload equality, every binding, and
the audit configuration with the mapped source record. A difference is a
failure. Never print payloads or credential bytes in that record.

## Runtime requirements and readiness

Use RAES 10.6.0 and env-packs 7.2.2 for this SDL and its pinned local import.
A successful pack check establishes structural validity. It does not establish
that a tenant can launch the range.

BigRAE must also supply general file assets, the adapter pre-provisioning phase,
and cloud IAM and Secret Manager realization in registered projects. Those
capabilities are tracked in BigRAE issues 2719, 2718, and 2716. The private
runtime adapter and repeated cloud setup and teardown qualification are still
required. Keep the pack in draft status until those checks pass.
