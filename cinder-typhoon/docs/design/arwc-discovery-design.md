# ARWC Domain API and Discovery Map

Operator-only. Not shipped to the participant. Approved for #220–#222 implementation.

This document maps the 120 ARWC cards (W01–W35) onto resource-oriented domain
APIs for the Alterra Resource Water Corporation fictional environment. Each card
addresses a weakness in a real service interface, not a challenge-only endpoint.

---

## Discovery mechanism

Each ARWC service serves `GET /.well-known/arwc-client` returning:

```json
{
  "schema": "arwc.client-documents/v1",
  "service": "<hostname>",
  "title": "<service title>",
  "routes": [
    {"key": "<service>.<resource>", "method": "<METHOD>", "template": "https://..."}
  ],
  "related": ["https://<other-service>/.well-known/arwc-client"]
}
```

The `customer-transition.json` handover (ARWC starting material) names the
first client reference URL at key `client_reference`. The participant follows
`related` links from there. All route keys used by the known-solution suite
must appear in the graph.

---

## Service domains

### 1. customer_handover — `corporate.arwc.test`

Corporate work order and customer handover management.

| Route key | Method | Template | Cards |
|---|---|---|---|
| `corporate.handover` | GET | `.../api/handovers/{handover_id}` | W01.1 |
| `corporate.work-order` | GET | `.../api/work-orders/{wo_id}` | W01.2 |
| `corporate.continuity-plan` | GET | `.../api/continuity-plans/{plan_id}` | W01.3 |
| `corporate.work-order-update` | PATCH | `.../api/work-orders/{wo_id}` | W01.4 |

Related: `business.arwc.test/.well-known/arwc-client`

**Normal use**: operations staff read the current customer delivery handover,
open work orders, and published continuity plans. Planners update work orders
with inspection attachments.

---

### 2. business_workplace — `business.arwc.test`

Business asset records, associations, reports, and procurement.

| Route key | Method | Template | Cards |
|---|---|---|---|
| `business.asset-bundle` | GET | `.../api/asset-bundles/{bundle_id}` | W02.1 |
| `business.association-record` | GET | `.../api/association-records/{assoc_id}` | W02.2 |
| `business.work-order-attachment` | GET | `.../api/work-order-attachments/{attach_id}` | W02.3, W03.1 |
| `business.work-order-references` | GET | `.../api/work-orders/{wo_id}/references` | W03.2 |
| `business.integration-contract` | GET | `.../api/integration-contracts/{contract_id}` | W03.3 |
| `business.report-sources` | GET | `.../api/reports/{report_id}/sources` | W10.1 |
| `business.report-row` | GET | `.../api/reports/{report_id}/rows/{district_id}` | W10.2 |
| `business.report-document` | GET | `.../api/reports/{report_id}/document` | W10.3 |
| `business.procurement-quote` | GET | `.../api/procurement-quotes/{quote_id}` | W35.1 |
| `business.district-quote` | GET | `.../api/procurement-quotes/{quote_id}/districts/{district_id}` | W35.2 |
| `business.invoice` | GET | `.../api/invoices/{invoice_id}` | W35.3 |

Related: `planning.arwc.test/.well-known/arwc-client`

**Normal use**: business staff manage asset-work associations, retrieve
attachments for open orders, query district reports, and review procurement
quotes and invoices.

---

### 3. retained_archive — `archive.arwc.test`

Retained archive contracts, bundles, and cold archive access.

| Route key | Method | Template | Cards |
|---|---|---|---|
| `archive.contract` | GET | `.../api/archive-contracts/{contract_id}` | W04.1 |
| `archive.archived-query` | GET | `.../api/archived-queries/{query_id}` | W04.2 |
| `archive.run-operation` | POST | `.../api/archive-operations` | W04.3 |
| `archive.bundle` | GET | `.../api/bundles/{bundle_id}` | W08.1 |
| `archive.bundle-collection-policy` | GET | `.../api/bundles/{bundle_id}/collection-policy` | W08.2 |
| `archive.bundle-integrity` | POST | `.../api/bundles/{bundle_id}/integrity-checks` | W08.3 |
| `archive.sequencer-spec` | GET | `.../api/sequencer-specs/{spec_id}` | W16.1 |
| `archive.observations` | POST | `.../api/observations` | W16.2 |
| `archive.signal-experiment` | POST | `.../api/signal-experiments` | W16.3 |
| `archive.instrument-history` | GET | `.../api/instrument-history/{instrument_id}` | W16.4 |
| `archive.cold-archive-job` | POST | `.../api/archive-jobs` | W12.1 |
| `archive.cold-archive-job-status` | GET | `.../api/archive-jobs/{job_id}` | W12.2 |
| `archive.cold-archive-result` | GET | `.../api/archive-jobs/{job_id}/result` | W12.3 |

Related: `business.arwc.test/.well-known/arwc-client`

**Normal use**: engineers access retained archive contracts, query stored
instrument history, check bundle integrity, and request cold archive retrieval.

---

### 4. corporate_identity — `identity.arwc.test`

Identity management, temporary credentials, and planner sessions.

| Route key | Method | Template | Cards |
|---|---|---|---|
| `identity.provisioning-package` | GET | `.../api/provisioning-packages/{package_id}` | W05.1 |
| `identity.activation-roster` | GET | `.../api/activations/{roster_id}` | W05.2 |
| `identity.temporary-credential` | GET | `.../api/temporary-credentials/{cred_id}` | W05.3 |
| `identity.session-audit` | GET | `.../api/sessions/{session_id}/audit` | W06.1 |
| `identity.drawing-context` | GET | `.../api/drawing-contexts/{context_id}` | W06.2 |
| `identity.sessions` | POST | `.../api/sessions` | W06.3 |

Related: `planning.arwc.test/.well-known/arwc-client`

**Normal use**: identity administrators manage provisioning packages, review
activation rosters, and issue temporary credentials. Planners authenticate
through the session API and access drawing contexts.

---

### 5. planning_data — `planning.arwc.test`

Planning queries, water allocation ledgers, and integration sessions.

| Route key | Method | Template | Cards |
|---|---|---|---|
| `planning.saved-query` | GET | `.../api/saved-queries/{query_id}` | W07.1 |
| `planning.query-run` | POST | `.../api/query-runs` | W07.2, W07.3 |
| `planning.allocation-ledger` | GET | `.../api/allocation-ledgers/{ledger_id}` | W09.1 |
| `planning.meter-allocation` | GET | `.../api/meter-allocations/{meter_id}` | W09.2 |
| `planning.allocation-discrepancy` | GET | `.../api/allocation-discrepancies/{disc_id}` | W09.3 |
| `planning.live-feed` | GET | `.../api/live-feeds/{feed_id}` | W09.4 |
| `planning.relation-schema` | GET | `.../api/relation-schemas/{schema_id}` | W11.1 |
| `planning.relation-exchange` | POST | `.../api/relation-exchanges` | W11.2 |
| `planning.asset-lineage` | GET | `.../api/asset-lineage/{asset_id}` | W11.3 |
| `planning.integration-session` | POST | `.../api/integration-sessions` | W16.5 |

Related: `archive.arwc.test/.well-known/arwc-client`,
`process.arwc.test/.well-known/arwc-client`

**Normal use**: planners run saved queries against water allocation records,
view meter allocations, identify discrepancies, and establish integration
sessions to the live process feed.

---

### 6. contractor_portal — `contractors.arwc.test`

Contractor appointments, check-ins, and field kit management.

| Route key | Method | Template | Cards |
|---|---|---|---|
| `contractors.appointment-window` | GET | `.../api/appointment-windows/{date}` | W13.1 |
| `contractors.expected-visitors` | GET | `.../api/appointment-windows/{date}/visitors` | W13.2 |
| `contractors.appointment` | GET | `.../api/appointments/{appointment_id}` | W13.3 |
| `contractors.check-in` | POST | `.../api/check-ins` | W13.4 |
| `contractors.field-kit` | GET | `.../api/field-kits/{kit_id}` | W14.1 |

Related: `field.arwc.test/.well-known/arwc-client`

**Normal use**: site staff view expected contractor visits, manage appointment
windows, and issue field kits at check-in.

---

### 7. field_gateway — `field.arwc.test`

Field instrumentation readings and instrument management.

| Route key | Method | Template | Cards |
|---|---|---|---|
| `field.instrument` | GET | `.../api/instruments/{instrument_id}` | W14.2 |
| `field.current-reading` | GET | `.../api/readings/{instrument_id}/current` | W14.3 |

Related: `process.arwc.test/.well-known/arwc-client`

**Normal use**: engineers read current field instrument measurements and look
up instrument metadata.

---

### 8. maintenance_review — `maintenance.arwc.test`

Maintenance drawing cache and approval workflows.

| Route key | Method | Template | Cards |
|---|---|---|---|
| `maintenance.drawing-cache` | GET | `.../api/drawing-cache/{cache_id}` | W15.1 |
| `maintenance.drawing-cache-update` | PUT | `.../api/drawing-cache/{cache_id}` | W15.2 |
| `maintenance.drawing-approval` | POST | `.../api/drawing-approvals` | W15.3 |
| `maintenance.approval-token` | GET | `.../api/approval-tokens/{token_id}` | W15.4 |

Related: `identity.arwc.test/.well-known/arwc-client`

**Normal use**: maintenance staff cache current drawings for field reference.
Approvers issue scoped approval tokens for drawing acceptance.

---

### 9. process_view — discovered via `planning.integration-session`

Process control views for reservoir, instrument, and HMI operations.
The base URL is returned by the `planning.integration-session` response.

| Route key | Method | Template | Cards |
|---|---|---|---|
| `process.state` | GET | `{view_base}/api/process-views/state` | W17.1 |
| `process.mode` | GET | `{view_base}/api/process-views/mode` | W17.2 |
| `process.active-instrument` | GET | `{view_base}/api/process-views/instruments/active` | W17.3 |
| `process.observations` | POST | `{view_base}/api/observations` | W17.4 |
| `process.tag-export` | GET | `{view_base}/api/tag-exports/current` | W18.1 |
| `process.tag-scale` | GET | `{view_base}/api/tag-scales/{tag_id}` | W18.2 |
| `process.tag-scale-history` | GET | `{view_base}/api/tag-scales/{tag_id}/history` | W18.3 |
| `process.outlet-instruments` | GET | `{view_base}/api/outlet-groups/{og_id}/instruments` | W18.4 |
| `process.diagnostic-program` | GET | `{view_base}/api/diagnostic-programs/{program_id}` | W19.1 |
| `process.diagnostic-run` | POST | `{view_base}/api/diagnostic-runs` | W19.2 |
| `process.diagnostic-result` | GET | `{view_base}/api/diagnostic-runs/{run_id}/result` | W19.3 |
| `process.firmware-image` | GET | `{view_base}/api/firmware-images/{image_id}` | W20.1 |
| `process.maintenance-record` | GET | `{view_base}/api/maintenance-records/{record_id}` | W20.2 |
| `process.maintenance-record-update` | PATCH | `{view_base}/api/maintenance-records/{record_id}` | W20.3 |
| `process.sealed-project` | GET | `{view_base}/api/sealed-projects/{project_id}` | W21.1 |
| `process.sealed-project-viewer` | GET | `{view_base}/api/sealed-projects/{project_id}/viewer` | W21.2 |
| `process.sealed-viewer-execute` | POST | `{view_base}/api/sealed-viewers/{viewer_id}/execute` | W21.3 |
| `process.estimator-task` | GET | `{view_base}/api/estimator-tasks/{task_id}` | W22.1 |
| `process.estimator-run` | POST | `{view_base}/api/estimator-runs` | W22.2 |
| `process.estimator-result` | GET | `{view_base}/api/estimator-runs/{run_id}/result` | W22.3 |
| `process.signature-record` | GET | `{view_base}/api/signature-records/{record_id}` | W23.1 |
| `process.signature-request` | POST | `{view_base}/api/signature-requests` | W23.2 |
| `process.signature-result` | GET | `{view_base}/api/signature-requests/{request_id}/result` | W23.3 |
| `process.operating-envelope` | GET | `{view_base}/api/operating-envelopes/current` | W25.1 |
| `process.movement-conditions` | GET | `{view_base}/api/movement-conditions/current` | W25.2 |
| `process.command-accept` | POST | `{view_base}/api/commands` | W25.3 |
| `process.practice-sequence` | POST | `{view_base}/api/practice-sequences` | W25.4 |
| `process.control-authority` | GET | `{view_base}/api/control-authority` | W26.1 |
| `process.control-command` | POST | `{view_base}/api/control-commands` | W26.2 |
| `process.control-consequence` | GET | `{view_base}/api/control-commands/{cmd_id}/consequence` | W26.3 |
| `process.collision-inputs` | GET | `{view_base}/api/collision-inputs/{collision_id}` | W27.1 |
| `process.collision-solve` | POST | `{view_base}/api/collision-solutions` | W27.2 |
| `process.vault-record` | GET | `{view_base}/api/vault-records/{record_id}` | W31.1 |
| `process.vault-access` | POST | `{view_base}/api/vault-access` | W31.2 |
| `process.replay-session` | GET | `{view_base}/api/replay-sessions/{session_id}` | W32.1 |
| `process.replay-execute` | POST | `{view_base}/api/replay-sessions/{session_id}/execute` | W32.2 |
| `process.replay-divergence` | GET | `{view_base}/api/replay-sessions/{session_id}/divergence` | W32.3 |
| `process.forecast` | GET | `{view_base}/api/forecasts/{forecast_id}` | W33.1 |
| `process.schedule-window` | GET | `{view_base}/api/schedule-windows/{window_id}` | W33.2 |
| `process.schedule-submit` | POST | `{view_base}/api/schedules` | W33.3 |
| `process.feedback-policy` | POST | `{view_base}/api/feedback-policies` | W33.4 |
| `process.reporting-checkpoint` | GET | `{view_base}/api/reporting-checkpoints/{checkpoint_id}` | W34.1 |
| `process.reporting-submit` | POST | `{view_base}/api/reporting-submissions` | W34.2 |
| `process.reporting-result` | GET | `{view_base}/api/reporting-submissions/{submission_id}/result` | W34.3 |

**W24 (crypto oracle)** and **W28 (utility privilege escalation)** are served
by embedded binaries (`signer24`, `utility28`) discovered through maintenance
records or project artifacts, not the process service HTTP API.

**W29 (planning window economics)** extends `process.planning-window`:

| Route key | Method | Template | Cards |
|---|---|---|---|
| `process.planning-window` | GET | `{view_base}/api/planning-windows/{window_id}` | W29.1 |
| `process.planning-economics` | GET | `{view_base}/api/planning-windows/{window_id}/economics` | W29.2 |
| `process.planning-bid` | POST | `{view_base}/api/planning-bids` | W29.3, W29.4 |

**W30 (command release)** extends `process.control-command`:

| Route key | Method | Template | Cards |
|---|---|---|---|
| `process.release-plan` | GET | `{view_base}/api/release-plans/{plan_id}` | W30.1 |
| `process.release-execute` | POST | `{view_base}/api/release-plans/{plan_id}/execute` | W30.2 |
| `process.release-confirmation` | GET | `{view_base}/api/release-plans/{plan_id}/confirmation` | W30.3 |

---

## Discovery graph

```
customer-transition.json
  -> corporate.arwc.test/.well-known/arwc-client
       -> business.arwc.test/.well-known/arwc-client
            -> planning.arwc.test/.well-known/arwc-client
                 -> archive.arwc.test/.well-known/arwc-client
                 -> process.arwc.test/.well-known/arwc-client (via integration-session result)
       -> identity.arwc.test/.well-known/arwc-client
            -> planning.arwc.test/.well-known/arwc-client
       -> contractors.arwc.test/.well-known/arwc-client
            -> field.arwc.test/.well-known/arwc-client
            -> maintenance.arwc.test/.well-known/arwc-client
```

---

## W08 — retained bundle (archive service)

The collector bundle (`BND-COLLECT-CRR-12`) is discovered through
`business.asset-bundle` (W02.1), which names the bundle identifier.
The integrity check (W08.3) requires reading the collection policy first.

## W12 — cold archive (archive service)

The cold archive job is created via `archive.cold-archive-job` then polled.
Discovery: `archive.contract` names the archive job endpoint (W04.1).

## W16 — sequencer signal (archive service)

The sequencer spec (W16.1) is discoverable from the instrument history
endpoint referenced in the retained bundle. The observation and experiment
routes are standard archive service operations.

## W19 — diagnostic binary (process service)

The diagnostic program record is fetched from `process.diagnostic-program`.
The binary artifact is at `{view_base}/api/artifacts/{program_id}`, discovered
from the program record's `binary` field.

## W20 — NOR flash image (process service)

The firmware image artifact is at `{view_base}/api/artifacts/{image_id}`,
discovered from `process.firmware-image`.

## W21 — sealed viewer (process service)

The sealed viewer binary is discovered from `process.sealed-project-viewer`.
The viewer ID and access token come from the sealed project record.

## W22 — estimator heap (process service)

The estimator binary is discovered from `process.estimator-task`. The task
record names the binary artifact URL.

## W23 — signature record (process service)

The signature record is fetched via `process.signature-record`. The program
to sign comes from the maintenance record or project artifact.

## W24 — crypto oracle (signer24 binary)

Discovered from `process.signature-record` which names the signing binary.
The binary path comes from the signature record's `signer_binary` field.

## W28 — utility privilege escalation (utility28 binary)

Discovered from a maintenance record or archive job that names the utility
binary artifact. Not served through the HTTP API.

## W33 — forecast scheduling

All W33 inputs (forecast, model, constraints, schema) are served from
`process.forecast` and `process.schedule-window`. See #223 for full
starting-material specification.

## W34 — reporting checkpoint

The reporting checkpoint ID comes from the release plan confirmation (W30.3).
The submission accepts a structured report derived from observable plant state.

---

## Route implementation rules

1. Every route must have a tested normal baseline (not-found, denied, normal
   read, normal write) independent of the exploit path.
2. Authentication uses the corporate session token from `customer-transition.json`.
   Process service routes use the process session from `planning.integration-session`.
3. Error responses describe validation failures in terms of the resource schema.
   They never reveal challenge card IDs, card titles, or expected exploit values.
4. Identifiers in routes are record IDs discoverable from earlier responses or
   the starting handover — not guessable slugs.
5. Mutation routes require the correct resource revision to prevent replay.
