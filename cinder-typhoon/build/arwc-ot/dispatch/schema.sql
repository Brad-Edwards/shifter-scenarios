CREATE SCHEMA IF NOT EXISTS ot_dispatch;
CREATE TABLE IF NOT EXISTS ot_dispatch.requests (
    id uuid PRIMARY KEY, fingerprint text NOT NULL, request jsonb NOT NULL,
    principal text NOT NULL, received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    sequence integer, status text NOT NULL, detail jsonb NOT NULL DEFAULT '{}',
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS ot_dispatch.transitions (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request_id uuid NOT NULL REFERENCES ot_dispatch.requests(id) ON DELETE CASCADE,
    time timestamptz NOT NULL DEFAULT clock_timestamp(), status text NOT NULL, detail jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS dispatch_transitions_request ON ot_dispatch.transitions(request_id,time);
GRANT USAGE ON SCHEMA ot_dispatch TO dispatcher;
GRANT SELECT,INSERT,UPDATE ON ot_dispatch.requests TO dispatcher;
GRANT SELECT,INSERT ON ot_dispatch.transitions TO dispatcher;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA ot_dispatch TO dispatcher;
CREATE OR REPLACE VIEW public.dispatch_history AS
SELECT e.time,r.id,r.principal,r.sequence,e.status,e.detail,r.request,
       'Authenticated MQTT dispatcher and observed PLC feedback'::text AS origin
FROM ot_dispatch.transitions e JOIN ot_dispatch.requests r ON r.id=e.request_id;
GRANT SELECT ON public.dispatch_history TO reader;
