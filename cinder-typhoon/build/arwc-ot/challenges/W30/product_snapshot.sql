-- Read-only adapter input for W30. The thin adapter groups rows by record_type
-- and adds the hash-verified image configuration without changing product data.
SELECT 'sample'::text AS record_type,
       h.source_time,
       c.variable,
       h.value,
       h.unit,
       h.process_quality AS quality,
       NULL::text AS channel,
       NULL::text AS decision,
       NULL::integer AS sequence,
       NULL::text AS native_status,
       NULL::uuid AS request_id,
       NULL::text AS principal,
       NULL::text AS dispatch_status,
       NULL::jsonb AS detail,
       NULL::jsonb AS request,
       NULL::text AS origin
FROM public.process_history AS h
JOIN public.historian_tag_catalog AS c ON c.series = h.tag
WHERE h.asset = 'AST-CRR-017'
  AND c.variable IN (
    'ProjectRevision', 'IoHealthy', 'Owner', 'AutoMode', 'HmiRemoteEnabled',
    'PermissiveA', 'PermissiveB', 'MovingA', 'MovingB', 'TravelFaultA',
    'TravelFaultB', 'RemoteSeen', 'RemoteAccepted', 'RemoteRejected',
    'RemoteRejectReason', 'HmiSeen', 'HmiAccepted', 'HmiRejected',
    'HmiRejectReason', 'RequestedTargetPct', 'RequestedTargetBPct',
    'RequestedFlowM3s', 'PositionPct', 'PositionBPct', 'FlowM3s',
    'FlowBM3s', 'TotalFlowM3s'
  )
  AND h.source_time >= current_timestamp - interval '30 minutes'
UNION ALL
SELECT 'command'::text,
       source_time,
       NULL::text,
       NULL::double precision,
       NULL::text,
       NULL::text,
       channel,
       decision,
       sequence,
       native_status,
       NULL::uuid,
       NULL::text,
       NULL::text,
       NULL::jsonb,
       NULL::jsonb,
       origin
FROM public.command_history
WHERE asset = 'AST-CRR-017'
  AND source_time >= current_timestamp - interval '30 minutes'
UNION ALL
SELECT 'dispatch'::text,
       time,
       NULL::text,
       NULL::double precision,
       NULL::text,
       NULL::text,
       NULL::text,
       NULL::text,
       sequence,
       NULL::text,
       id,
       principal,
       status,
       detail,
       request,
       origin
FROM public.dispatch_history
WHERE request->>'asset' = 'AST-CRR-017'
  AND time >= current_timestamp - interval '30 minutes'
ORDER BY source_time, record_type;
