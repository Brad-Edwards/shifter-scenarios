# Cairn Reach planning reconciliation

Scope: `AST-CRR-017`, planning window `ALLOC-2026-DP3`

The corporate tariff and allocation are business records. The OpenPLC-derived
`UsableVolumeML` series in the native PostgreSQL historian is measured process
state. Preserve their separate record identities, units, revisions, and times.

For the current balance:

1. Select a fresh `usable_volume_ml` sample for `AST-CRR-017` with process
   quality `Good`.
2. Record its source time and value in ML.
3. Calculate `uncommitted margin = measured usable volume - 12.00 ML`.
4. Classify the margin from its sign; do not substitute the paper report or the
   older meter export for the current product sample.

For the paper comparison:

1. Retain report `RPT-CRR-DP3-R7` and its `2026-11-09T00:00:00Z` as-of time.
2. Calculate `signed paper variance = 13.40 ML - later measured usable volume`.
3. A positive result means the report is above the later process value; a
   negative result means it is below; a value within 0.005 ML is aligned.
4. Because the sources have different as-of times, the comparison establishes
   that the report is not current process truth. It does not, by itself,
   establish which physical or administrative event caused the difference.

This work is read-only. Do not issue a process request or manufacture a
replacement historian or corporate record.
