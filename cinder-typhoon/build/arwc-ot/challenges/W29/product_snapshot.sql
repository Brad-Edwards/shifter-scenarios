-- Native historian input for W29. Product source time and quality are retained.
SELECT c.variable,
       h.source_time,
       h.collected_time,
       h.ingested_at,
       h.value,
       h.unit,
       h.process_quality AS quality
FROM public.process_history AS h
JOIN public.historian_tag_catalog AS c ON c.series = h.tag
WHERE h.asset = 'AST-CRR-017'
  AND c.variable = 'UsableVolumeML'
  AND h.source_time >= current_timestamp - interval '5 minutes'
ORDER BY h.source_time;
