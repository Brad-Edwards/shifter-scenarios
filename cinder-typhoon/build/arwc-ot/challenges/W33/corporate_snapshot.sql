SELECT jsonb_build_object(
  'tariff', jsonb_build_object(
    'record_id', t.record_id,
    'revision', t.revision,
    'planning_window', t.planning_window,
    'asset', t.asset,
    'currency', t.currency,
    'unit', t.unit,
    'rate', t.rate,
    'effective_from', t.effective_from,
    'effective_to', t.effective_to
  ),
  'allocation', jsonb_build_object(
    'record_id', a.record_id,
    'revision', a.revision,
    'planning_window', a.planning_window,
    'asset', a.asset,
    'unit', a.unit,
    'committed_volume', a.committed_volume,
    'effective_from', a.effective_from,
    'effective_to', a.effective_to
  )
) AS corporate
FROM public.settlement_tariff AS t
JOIN public.allocation_ledger AS a USING (planning_window)
WHERE t.record_id = 'TAR-CRR-DP3-R4'
  AND a.record_id = 'ALLOC-2026-DP3-R9';
