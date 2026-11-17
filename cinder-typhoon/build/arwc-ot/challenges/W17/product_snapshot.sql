-- Read-only adapter input for W17. Product rows remain authoritative.
SELECT c.variable,
       h.source_time,
       h.value,
       h.unit,
       h.process_quality AS quality,
       c.node_id,
       c.series
FROM public.process_history AS h
JOIN public.historian_tag_catalog AS c ON c.series = h.tag
WHERE h.asset = 'AST-CRR-017'
  AND h.source_time >= current_timestamp - interval '5 minutes'
ORDER BY h.source_time, c.variable;
