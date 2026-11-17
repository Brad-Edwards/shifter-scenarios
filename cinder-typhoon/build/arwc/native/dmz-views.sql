CREATE SCHEMA IF NOT EXISTS dmz_api;
CREATE OR REPLACE VIEW dmz_api.reserve_report AS
 SELECT record_id, revision, planning_window, reported_ml, asset, unit, as_of,
   CASE WHEN record_id = 'RPT-CRR-DP3-R7' THEN 'FLAG{4c92291fb1143aea}' ELSE NULL END AS flag
 FROM public.business_reserve_report;
REVOKE ALL ON SCHEMA dmz_api FROM PUBLIC;
GRANT USAGE ON SCHEMA dmz_api TO dmz_reader;
GRANT SELECT ON dmz_api.reserve_report TO dmz_reader;
