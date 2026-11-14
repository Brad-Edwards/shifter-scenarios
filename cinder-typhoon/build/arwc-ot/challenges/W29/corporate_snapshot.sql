-- Read-only corporate planning records for W29. The adapter groups each JSON
-- record by record_type and never substitutes these rows for process history.
SELECT 'tariff'::text AS record_type,
       jsonb_build_object(
         'record_id', record_id, 'revision', revision,
         'planning_window', planning_window, 'asset', asset,
         'currency', currency, 'rate_per_ml', rate_per_ml::double precision,
         'unit', unit,
         'effective_from', to_char(effective_from AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
         'effective_to', to_char(effective_to AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
       ) AS record
FROM public.settlement_tariff
WHERE record_id = 'TAR-CRR-DP3-R4'
UNION ALL
SELECT 'allocation'::text,
       jsonb_build_object(
         'record_id', record_id, 'revision', revision,
         'planning_window', planning_window, 'asset', asset,
         'committed_ml', committed_ml::double precision, 'unit', unit,
         'effective_from', to_char(effective_from AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
         'effective_to', to_char(effective_to AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
       )
FROM public.allocation_ledger
WHERE record_id = 'ALLOC-2026-DP3-R9'
UNION ALL
SELECT 'report'::text,
       jsonb_build_object(
         'record_id', record_id, 'revision', revision,
         'planning_window', planning_window, 'asset', asset,
         'reported_ml', reported_ml::double precision, 'unit', unit,
         'as_of', to_char(as_of AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
       )
FROM public.business_reserve_report
WHERE record_id = 'RPT-CRR-DP3-R7';
