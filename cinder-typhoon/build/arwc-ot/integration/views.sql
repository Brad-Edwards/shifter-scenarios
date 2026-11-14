-- Append provenance without changing the existing view's first six columns.
CREATE OR REPLACE VIEW public.dmz_process_history AS
SELECT asset,source_time,tag,value,unit,process_quality,collected_time,ingested_at,
       'OpenPLC native OPC UA via Telegraf / ot_history.process_samples'::text AS origin
FROM public.process_history
WHERE tag IN ('level_m','usable_volume_ml','total_flow_m3s');
GRANT SELECT ON public.dmz_process_history TO dmz_reader;
ALTER ROLE dmz_reader SET default_transaction_read_only=on;
ALTER ROLE dmz_reader SET statement_timeout='2s';
