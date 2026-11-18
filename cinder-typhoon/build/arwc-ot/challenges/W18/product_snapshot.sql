-- Read-only adapter input for W18. The thin adapter groups catalog rows and
-- samples into arwc.native-tag-observation/v1 without changing their values.
SELECT c.variable,
       c.series,
       c.node_id,
       c.unit,
       c.register_sha256,
       c.definition,
       c.scaling,
       h.source_time,
       h.collected_time,
       h.ingested_at,
       h.value,
       h.transport_quality,
       h.process_quality
FROM public.historian_tag_catalog AS c
LEFT JOIN public.process_history AS h ON h.tag = c.series
WHERE c.variable IN (
  'LevelM', 'PositionPct', 'PositionBPct', 'FlowM3s', 'FlowBM3s',
  'ProjectRevision'
)
  AND (h.source_time IS NULL OR h.source_time >= current_timestamp - interval '2 hours')
ORDER BY c.variable, h.source_time;
