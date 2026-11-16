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
REVOKE ALL ON public.allocation_ledger, public.settlement_tariff,
  public.meter_export, public.business_reserve_report FROM PUBLIC, planning_reader;
GRANT USAGE ON SCHEMA reporting TO planning_reader;
GRANT SELECT ON reporting.reserve_report TO planning_reader;
GRANT SELECT ON public.reserve_report_current TO planning_reader;
COMMIT;
