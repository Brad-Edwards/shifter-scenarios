BEGIN;
CREATE SCHEMA IF NOT EXISTS reporting;
CREATE TABLE IF NOT EXISTS public.allocation_ledger (
  record_id text PRIMARY KEY,
  revision integer NOT NULL,
  district text NOT NULL,
  asset text NOT NULL,
  planning_window text NOT NULL,
  committed_ml numeric(8,3) NOT NULL,
  unit text NOT NULL CHECK (unit = 'ML'),
  effective_from timestamptz NOT NULL,
  effective_to timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS public.settlement_tariff (
  record_id text PRIMARY KEY,
  revision integer NOT NULL,
  planning_window text NOT NULL,
  asset text NOT NULL,
  currency text NOT NULL,
  rate_per_ml numeric(9,2) NOT NULL,
  unit text NOT NULL,
  effective_from timestamptz NOT NULL,
  effective_to timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS public.meter_export (
  record_id text PRIMARY KEY,
  revision integer NOT NULL,
  planning_window text NOT NULL,
  usable_reserve_ml numeric(8,3) NOT NULL,
  unit text NOT NULL,
  instrument_a text NOT NULL,
  instrument_b text NOT NULL
);
CREATE TABLE IF NOT EXISTS public.business_reserve_report (
  record_id text PRIMARY KEY,
  revision integer NOT NULL,
  planning_window text NOT NULL,
  reported_ml numeric(8,3) NOT NULL,
  duplicate_transfer text,
  asset text NOT NULL,
  unit text NOT NULL,
  as_of timestamptz NOT NULL
);
INSERT INTO public.allocation_ledger VALUES
 ('ALLOC-2026-DP3-R9',9,'Cairn Reach','AST-CRR-017','ALLOC-2026-DP3',12.00,'ML',
  '2026-11-01T00:00:00Z','2026-12-01T00:00:00Z')
ON CONFLICT DO NOTHING;
INSERT INTO public.settlement_tariff VALUES
 ('TAR-CRR-DP3-R4',4,'ALLOC-2026-DP3','AST-CRR-017','USD',2400.00,'USD/ML',
  '2026-11-01T00:00:00Z','2026-12-01T00:00:00Z')
ON CONFLICT DO NOTHING;
INSERT INTO public.meter_export VALUES
 ('MTR-CRR-DP3-R12',12,'ALLOC-2026-DP3',12.40,'ML','FIT-CRR-204A','FIT-CRR-204B')
ON CONFLICT DO NOTHING;
INSERT INTO public.business_reserve_report VALUES
 ('RPT-CRR-DP3-R7',7,'ALLOC-2026-DP3',13.40,'TRN-DP3-118','AST-CRR-017','ML','2026-11-09T00:00:00Z')
ON CONFLICT DO NOTHING;
INSERT INTO public.business_reserve_report
 SELECT format('RPT-%s-2026-11',site), 1, 'ALLOC-2026-11', reserve_ml, NULL,
        asset, 'ML', '2026-11-09T00:00:00Z'::timestamptz
 FROM (VALUES
  ('PINE-HILL','AST-PIN-005',18.20), ('PINE-NORTH','AST-PIN-012',8.75),
  ('RIVER-EAST','AST-RIV-004',14.50), ('RIVER-WEST','AST-RIV-021',11.60),
  ('CAIRN-UPPER','AST-CRR-009',7.90), ('PINE-SOUTH','AST-PIN-019',9.25)
 ) AS ordinary(site,asset,reserve_ml)
ON CONFLICT DO NOTHING;
CREATE OR REPLACE VIEW reporting.reserve_report AS
 SELECT record_id, revision, planning_window, reported_ml, asset, unit, as_of
 FROM public.business_reserve_report;
CREATE OR REPLACE VIEW public.reserve_report_current AS
 SELECT record_id, revision, planning_window, reported_ml, asset, unit, as_of
 FROM public.business_reserve_report
 WHERE planning_window = (
   SELECT planning_window FROM public.business_reserve_report
   WHERE record_id = 'RPT-CRR-DP3-R7');
-- W07.3 SECURITY DEFINER execution target: reconciliation_copy is inaccessible to
-- planning_reader directly; arwc_reconcile_copy(text) runs as its owner (corporate)
-- and inserts into reconciliation_copy when invoked by the planner query session.
-- The participant reaches it via a UNION injection that calls the function.
CREATE TABLE IF NOT EXISTS public.reconciliation_copy (
  record_id text PRIMARY KEY,
  revision integer NOT NULL,
  source_record text NOT NULL,
  database_identity text NOT NULL
);
-- Use distinct RETURNS TABLE column names (copy_*) to avoid PL/pgSQL ambiguity
-- with the reconciliation_copy table's own column names inside the function body.
CREATE OR REPLACE FUNCTION public.arwc_reconcile_copy(requested text)
RETURNS TABLE(copy_id text, copy_revision integer, copy_source text, copy_identity text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS
$func$
DECLARE
  v_identity text := session_user;
BEGIN
  IF requested IS DISTINCT FROM 'REC-CRR-DP3-17' THEN
    RAISE EXCEPTION 'reconciliation record % is not available', requested;
  END IF;
  INSERT INTO public.reconciliation_copy (record_id, revision, source_record, database_identity)
  VALUES (requested || '-COPY', 1, requested, v_identity)
  ON CONFLICT (record_id) DO UPDATE
    SET revision = public.reconciliation_copy.revision + 1,
        database_identity = v_identity;
  RETURN QUERY
    SELECT rc.record_id, rc.revision, rc.source_record, rc.database_identity
    FROM public.reconciliation_copy AS rc
    WHERE rc.record_id = requested || '-COPY';
END;
$func$;
-- planning_reader can EXECUTE the function but NOT query reconciliation_copy directly.
REVOKE ALL ON public.reconciliation_copy FROM PUBLIC;
REVOKE ALL ON public.reconciliation_copy FROM planning_reader;
GRANT EXECUTE ON FUNCTION public.arwc_reconcile_copy(text) TO planning_reader;
-- W07.2 injection target: district_allocation_adjustment contains ADJ-CRR-DP3-17.
-- planning_reader has SELECT (required for UNION to work) but no Metabase route
-- exposes it directly; it is only reachable via quoted-identifier injection in
-- QRY-RESERVE-R7. The ordinary WHERE reported_ml > 0 filters it out from the
-- normal reserve_report_current result.
CREATE OR REPLACE VIEW public.district_allocation_adjustment AS
 SELECT
   'ADJ-CRR-DP3-17'::text AS record_id,
   1::integer AS revision,
   'ALLOC-2026-DP3'::text AS planning_window,
   -1.000::numeric(8,3) AS reported_ml,
   'AST-CRR-017'::text AS asset,
   'ML'::text AS unit,
   '2026-11-09T00:00:00Z'::timestamptz AS as_of;
REVOKE ALL ON public.allocation_ledger, public.settlement_tariff,
  public.meter_export, public.business_reserve_report FROM PUBLIC, planning_reader;
GRANT USAGE ON SCHEMA reporting TO planning_reader;
GRANT SELECT ON reporting.reserve_report TO planning_reader;
GRANT SELECT ON public.reserve_report_current TO planning_reader;
GRANT SELECT ON public.district_allocation_adjustment TO planning_reader;
-- W09.1: planning_reader reads allocation_ledger via native Metabase question.
GRANT SELECT ON public.allocation_ledger TO planning_reader;
-- W09.2: planning_reader reads meter_export via native Metabase question.
GRANT SELECT ON public.meter_export TO planning_reader;
-- W10.1: report_source_selection view for SEL-CRR-DP3-7.
CREATE OR REPLACE VIEW public.report_source_selection AS
 SELECT
   'SEL-CRR-DP3-7'    AS record_id,
   7                   AS revision,
   al.district,
   al.planning_window,
   al.record_id        AS allocation_source,
   me.record_id        AS meter_source,
   rr.record_id        AS reserve_report_source,
   rr.duplicate_transfer
 FROM public.allocation_ledger al
 JOIN public.meter_export me ON al.planning_window = me.planning_window
 JOIN public.business_reserve_report rr
   ON al.planning_window = rr.planning_window AND al.asset = rr.asset
 WHERE al.planning_window = 'ALLOC-2026-DP3';
GRANT SELECT ON public.report_source_selection TO planning_reader;
-- W09.3: planning_reader reads business_reserve_report and the reconciliation view.
GRANT SELECT ON public.business_reserve_report TO planning_reader;
CREATE OR REPLACE VIEW public.reserve_reconciliation AS
 SELECT
   al.record_id  AS allocation_record,
   al.planning_window,
   al.district,
   al.asset,
   al.committed_ml,
   me.record_id  AS meter_record,
   me.usable_reserve_ml,
   rr.record_id  AS reserve_report,
   rr.reported_ml,
   rr.duplicate_transfer,
   rr.reported_ml - me.usable_reserve_ml AS overstatement_ml,
   me.usable_reserve_ml - al.committed_ml AS uncommitted_margin_ml
 FROM public.allocation_ledger al
 JOIN public.meter_export me ON al.planning_window = me.planning_window
 JOIN public.business_reserve_report rr
   ON al.planning_window = rr.planning_window AND al.asset = rr.asset
 WHERE al.planning_window = 'ALLOC-2026-DP3';
GRANT SELECT ON public.reserve_reconciliation TO planning_reader;
COMMIT;
