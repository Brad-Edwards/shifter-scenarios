-- Raw records preserve native JSON types, status, source time, and collection time.
CREATE OR REPLACE VIEW ot_history.sample_details AS
SELECT m.time AS source_time, to_timestamp((m.fields->>'collected_at_ns')::numeric / 1e9) AS collected_time,
       m.ingested_at, m.tags->>'asset' AS asset, m.tags->>'variable' AS variable,
       m.tags->>'series' AS tag, m.tags->>'unit' AS unit,
       CASE jsonb_typeof(m.fields->'value')
         WHEN 'number' THEN (m.fields->>'value')::double precision
         WHEN 'boolean' THEN CASE WHEN (m.fields->>'value')::boolean THEN 1.0 ELSE 0.0 END
         ELSE NULL END AS value,
       m.fields->>'Quality' AS native_status
FROM ot_history.process_samples m;

CREATE OR REPLACE VIEW public.process_history AS
SELECT m.source_time, m.ingested_at, m.asset, m.tag, m.unit, m.value,
       CASE WHEN m.native_status IN ('Good','The operation succeeded. StatusGood (0x0)')
            THEN 'Good' ELSE coalesce(m.native_status,'Unknown') END AS transport_quality,
       CASE WHEN m.native_status NOT IN ('Good','The operation succeeded. StatusGood (0x0)') OR m.native_status IS NULL
            THEN 'BadTransport'
            WHEN m.collected_time IS NULL OR m.value IS NULL THEN 'Unknown'
            WHEN m.collected_time-m.source_time > interval '3 seconds' OR m.source_time-m.collected_time > interval '1 second'
            THEN 'Stale'
            WHEN q.value = 1 AND q.native_status IN ('Good','The operation succeeded. StatusGood (0x0)')
            THEN 'Good' ELSE 'FieldUnavailable' END AS process_quality,
       m.collected_time, c.node_id, c.register_sha256, m.collected_time-m.source_time AS source_age
FROM ot_history.sample_details m
JOIN ot_history.tag_catalog c USING(variable)
LEFT JOIN LATERAL (
  SELECT q.value,q.native_status FROM ot_history.sample_details q
  WHERE q.variable='IoHealthy' AND q.source_time <= m.source_time
    AND q.asset=m.asset
    AND q.source_time >= m.source_time-interval '2 seconds'
  ORDER BY q.source_time DESC LIMIT 1
) q ON true;

CREATE OR REPLACE VIEW public.command_history AS
SELECT time AS source_time, ingested_at, tags->>'asset' AS asset, tags->>'channel' AS channel,
       tags->>'decision' AS decision, (fields->>'value')::integer AS sequence,
       'OpenPLC native OPC UA decision observation'::text AS origin,
       fields->>'Quality' AS native_status,
       to_timestamp((fields->>'collected_at_ns')::numeric / 1e9) AS collected_time
FROM ot_history.command_signals
WHERE fields->>'observation'='transition' AND (fields->>'value')::integer > 0;

CREATE OR REPLACE VIEW public.alarm_history AS
SELECT name,type,ontime,offtime,acktime,acknowledging_user,text,alarm_group,value,native_status,origin,observed_at
FROM ot_history.alarm_events;

CREATE OR REPLACE VIEW public.historian_tag_catalog AS SELECT * FROM ot_history.tag_catalog;
CREATE OR REPLACE VIEW public.dmz_process_history AS
SELECT asset,source_time,tag,value,unit,process_quality
FROM public.process_history WHERE tag IN ('level_m','usable_volume_ml','total_flow_m3s');

GRANT SELECT ON public.process_history,public.command_history,public.alarm_history,public.historian_tag_catalog TO reader;
GRANT SELECT ON public.dmz_process_history TO dmz_reader;
