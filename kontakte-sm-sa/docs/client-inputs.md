# Client inputs

Supply one named file asset containing JSON. The file follows a `.tfvars.json`
shape; it is adapter input, not a file that the source Terraform reads directly.
The tenant administrator binds the asset and the runtime adapter. Installing a
pack does not authorize executable adapter installation.

Start from [the template](client-input.template.json) and validate it against
[the schema](client-input.schema.json). The template is incomplete: replace all
mapping values and select the foothold account before launch.

The top-level fields are:

| Field | Required | Value |
| --- | --- | --- |
| `principal_map` | Yes | Map every full source member to one full native member. |
| `foothold_service_account` | Yes | Account ID of one of the 44 source service accounts. |
| `secret_values` | No | Map exact native secret IDs to strings; default is an empty map. |

All 71 outside placeholder keys are required. Each maps independently to one
existing principal of the same kind. Mapped values must be pairwise distinct.
The project segment in an alias email does not select a mapping or authorize
the adapter to combine identities. Preserve the full member prefix, such as
`serviceAccount:`, `user:`, `group:`, `principalSet://`, or `principal://`.
GKE workload identity members remain GKE workload identity members.

Use the source's exact, case-sensitive secret IDs as `secret_values` keys.
If a key is absent, the adapter uses `synthetic-range-secret`, exactly as the
source Terraform lookup does. If a key is present, use its value unchanged.
Do not substitute the fallback for an explicitly supplied empty string.

The selected foothold account must already be one of the source accounts.
The adapter issues a key for it after provisioning and writes the key to
`/home/analyst/.config/foothold/credential.json`. It adds no account or grants.
Teardown deletes that key.

## Prerequisites

Every outside principal must exist and be accepted by the registered project's
organization policy. Supply users and the group from an accepted identity
organization. Refusal of those identities does not permit dropping their
bindings. GKE members need the outside project's GKE workload identity pool.
Workload identity pool subjects and sets need their corresponding native pools.

The range project must be registered, have the required provider APIs and
permissions, and be free of another active range. The selected backend must
support the complete admitted declaration before it changes cloud state.

Store the completed file only through the tenant's protected file-asset path.
Do not commit client values or issued keys. The adapter must reject missing or
unknown keys, duplicate JSON keys, duplicate mapped values, wrong member kinds,
and oversized input before effects. Diagnostics must not include file contents
or secret values. The schema covers field structure; the adapter must enforce
the cross-field rules and provider checks too.
