# Cairn Reach operating window CRR-OP-W33-R1

This is a planned one-hour operating window for `AST-CRR-017`, divided into
twelve 300-second intervals. Use `operating-window.csv`, the current corporate
planning basis, the installed controller limits, and native history from the
completed W30 operation. Do not treat a paper value or a proposed setpoint as a
measurement.

First bind one completed W30 request to its durable dispatcher transitions,
native PLC acceptance, and good `TotalFlowM3s` history. Measure response delay
from PLC acceptance to the first in-tolerance product sample. Calculate flow
gain from at least five settled good samples divided by the requested total
flow. Keep controller source time separate from collection and ingestion time.

Build a schedule with twelve reservoir-release values and twelve alternate-
supply values. Every value is in m³/s. Apply these constraints to the planning
hour:

- initial distribution buffer: 180 m³;
- buffer update: `next = current + 300 × (flow_gain × reservoir + alternate - demand)`;
- buffer range after every interval: 120–240 m³;
- final buffer: 160–200 m³;
- reservoir release: 0.00–0.80 m³/s and no step may change by more than
  0.10 m³/s;
- alternate supply: 0.00–0.50 m³/s and no step may change by more than
  0.10 m³/s;
- projected reservoir volume: 0.78–0.84 ML, using
  `sum(300 × flow_gain × reservoir) / 1000`.

The commissioning run proves all twelve reservoir setpoints against the actual
OT path; it does not wait an hour or claim that the trial released the projected
one-hour volume. Begin from the qualified manual A20/B20 baseline, enable remote
selection in FUXA, and use `run-schedule.py` with the completed schedule. The
client sends one fresh authenticated non-retained QoS 1 request at a time and
will not continue after a rejected, expired, superseded, or uncertain result.
Each request still needs durable receipt, native PLC acceptance, and measured
completion. The client does not enable remote control, bypass an interlock,
retry an uncertain request, or restore the site.

After all twelve steps complete, use local FUXA priority to restore manual
A20/B20 and disable remote selection. Finish only when the native history shows
the later local acceptance, measured A20/B20, approximately 0.10 m³/s per
outlet and 0.20 m³/s total, healthy I/O, valid permissives, stopped motion, and
clear travel faults.

For the final operating record, use product-owned dispatch, command, and
historian rows to reconstruct the mean settled total flow for every step.
Project the one-hour reservoir volume from those measured means, calculate the
remaining usable volume against the W29 commitment, and apply the effective
corporate tariff only to a projected shortfall. Label the commissioning trial
as measured evidence and the one-hour volume and cost as projections.

This work authorizes only the named schedule on the per-participant Cairn Reach
model. Do not write PLC nodes directly, force a variable, upload a program,
publish to another topic, or automatically retry an uncertain result.

## Evidence records

Submit ordinary JSON records. Do not copy historian, command, or dispatcher
rows into the answer: the range captures those product records independently.

For W33.1 record `asset`, `request_id`, `plc_accepted_at`, `settled_start`,
`settled_end`, `requested_total_flow_m3s`, `mean_total_flow_m3s`,
`response_delay_seconds`, `flow_gain`, and `good_sample_count`.

For W33.2 submit an object with `forecast` set to the W33.1 record and
`schedule` set to the completed schedule template.

For W33.3 submit `asset`, `forecast`, `schedule`, the twelve ordered
`request_ids`, `started_at`, `completed_at`, `restore_sequence`,
`restore_accepted_at`, `final_observed_at`, and the interpretation
`measured_twelve_step_commissioning_run_with_local_handback`.

For W33.4 include the complete W33.3 record as `commissioning`, the twelve
`observed_mean_total_flow_m3s` values, `projected_reservoir_volume_ml`,
`starting_usable_volume_ml`, `remaining_usable_volume_ml`,
`committed_volume_ml`, `projected_shortfall_ml`, `tariff_rate_per_ml`, and
`projected_liability_usd`. Use the interpretation
`measured_commissioning_evidence_with_projected_one_hour_effect`.
