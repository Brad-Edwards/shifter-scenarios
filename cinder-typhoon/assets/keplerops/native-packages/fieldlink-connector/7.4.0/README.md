# FieldLink connector 7.4.0

The connector summarizes callback observations for a named customer asset.
It exports `consume(request)` and accepts `fieldkest.connector/v3` requests.
Provide `tenant_id`, `asset_id`, and an optional `measurements` object with
`callback_latency_ms` and `sample_count`.

The result retains the tenant and asset, states the connector version, and
compares the observed latency and sample count with `limits.json`.
Missing measurements are reported as unknown values rather than invented
samples. Invalid units or negative measurements are rejected.
