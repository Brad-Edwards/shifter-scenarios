-- Read-only adapter input for W25. The thin adapter groups rows by record_type
-- and adds the hash-verified image configuration without changing product data.
SELECT 'sample'::text AS record_type,
       c.variable,
       h.source_time,
       h.value,
       h.unit,
       h.process_quality AS quality,
       NULL::text AS channel,
       NULL::text AS decision,
       NULL::integer AS sequence,
       NULL::text AS native_status
FROM public.process_history AS h
JOIN public.historian_tag_catalog AS c ON c.series = h.tag
WHERE h.asset = 'AST-CRR-017'
  AND c.variable IN (
    'ProjectRevision', 'IoHealthy', 'LowLevelAlarm', 'HmiStop', 'TravelFaultA',
    'TravelFaultB', 'Armed', 'Owner', 'AutoMode', 'PermissiveA', 'PermissiveB',
    'MovingA', 'MovingB', 'HmiSeen', 'HmiAccepted', 'HmiRejected',
    'HmiRejectReason', 'RequestedTargetPct', 'RequestedTargetBPct',
    'RequestedFlowM3s', 'PositionPct', 'PositionBPct', 'FlowM3s', 'FlowBM3s',
    'TotalFlowM3s'
  )
  AND h.source_time >= current_timestamp - interval '30 minutes'
UNION ALL
SELECT 'command'::text,
       NULL::text,
       source_time,
       NULL::double precision,
       NULL::text,
       NULL::text,
       channel,
       decision,
       sequence,
       native_status
FROM public.command_history
WHERE asset = 'AST-CRR-017'
  AND source_time >= current_timestamp - interval '30 minutes'
ORDER BY source_time, record_type;
