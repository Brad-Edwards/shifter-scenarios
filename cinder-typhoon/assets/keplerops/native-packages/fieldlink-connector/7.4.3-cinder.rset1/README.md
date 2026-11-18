# FieldLink connector 7.4.3-cinder.rset1

The connector summarizes callback observations for a named customer asset.
It exports `consume(request)` and accepts `fieldkest.connector/v3` requests.
Provide `tenant_id`, `asset_id`, and an optional `measurements` object with
`callback_latency_ms` and `sample_count`.

This rehearsal build keeps the 7.4.2 behavior and adds a diagnostic-summary
path. When the request `operation` is `diagnostic_summary`, the connector runs a
calibration review for the asset and reports `calibration-review`. All other
requests keep the 7.4.2 latency and sample-count logic from `limits.json`.

The result retains the tenant and asset, states the connector version, and
reports observed values rather than invented samples. Invalid units or negative
measurements are rejected.
