# FieldLink 7.4.2 review export

Release ID: `REL-FLK-7.4.2-09`

Exported by Rowan Ito at 2026-09-18T15:06:31Z.

## Unresolved comments

- `REV-219`: Keep `asset_id`, `connector_revision`, `captured_at` and
  `observations` unchanged when a `fieldkest.report/v2` provider adds an
  assessment.
- `REV-224`: A successful build state is not report provenance. The handover
  must retain the report digest and the producing job ID.
- `REV-231`: Confirm that the support view renders the provider's assessment,
  not a cached baseline summary.

