# ARWC bounded process model

This is the normative process contract for the ARWC SDL. It makes the business
records, observations, practice model, live result, planning rehearsals, and
consequences agree quantitatively. The physical process is fictional and
bounded. It models a dispatchable dry-period reserve tranche, not the total
volume or safety behavior of a real reservoir.

## Units and identities

- Volume is recorded in megalitres (ML); `1 ML = 1,000 m3`.
- Flow is recorded in cubic metres per second (m3/s).
- Time is recorded in seconds. For a constant interval,
  `volume_ML = flow_m3s * duration_s / 1000`.
- The live asset is Cairn Reach Reservoir, `AST-CRR-017`.
- The controlled outlet group is `OG-CRR-02`, consisting of gates
  `GT-CRR-02A` and `GT-CRR-02B`.
- Independent measurement comes from `FIT-CRR-204A` and `FIT-CRR-204B` and is
  aggregated as historian tag `CRR.OUTLET.OG2.FLOW_ACTUAL`.
- Requested setpoints, command acknowledgements, estimates, reports, and
  planning decisions are separate records. None is a measurement.

## Corporate discrepancy

The dry-period planning window is `ALLOC-2026-DP3`.

| Record | Value | Authority |
| --- | ---: | --- |
| Published usable reserve | 13.40 ML | Business report `RPT-CRR-DP3-R7` |
| Independent usable reserve before the release | 12.40 ML | Meter export `MTR-CRR-DP3-R12` and instruments |
| Committed allocation | 12.00 ML | Allocation ledger `ALLOC-2026-DP3-R9` |
| Reporting overstatement | 1.00 ML | Reconciliation `REC-CRR-DP3-17` |
| Actual uncommitted margin before release | 0.40 ML | `12.40 - 12.00` |

The one-megalitre error is a stale duplicated transfer in the business report,
not missing physical telemetry. W09 establishes this discrepancy. W29 uses the
current independent reserve and commitment balance; it does not reuse the
stale 13.40 ML figure.

## Current revision, mapping, and mode

- Deployed control project: `CRR-CTRL-R21`.
- Stale engineering claim: `CRR-CTRL-R19`.
- Current tag/scale map: `MAP-OG2-R8`, derived from tag export
  `TAGS-CRR-R21` and scale table `SCALE-CRR-R8`.
- Live operating mode: `DRY_PERIOD_MANAGED`, record `MODE-CRR-17`.
- Control permissive: `PERM-OG2-LIVE-R4`; both gates are healthy, the outlet
  path is available, and the live client must present the current project,
  map, mode, envelope, and plan bindings.

These records are independently owned. A control client does not waive any of
them, and a planning estimate cannot change them.

## Live operating envelope

The live command envelope `ENV-OG2-R6` is:

- each gate setpoint: `0.00 <= q_gate <= 0.50 m3/s`;
- aggregate setpoint: `q_A + q_B <= 1.00 m3/s`;
- per-gate ramp: at most `0.10 m3/s` per 20-second control step;
- requested hold: at most `1,200 s`;
- requested release volume: at most `1.20 ML`;
- both gates must receive the same target for the W30 balanced-release plan;
- an accepted plan is actuated only in `DRY_PERIOD_MANAGED` with the live
  permissive true and all current bindings present.

Commands outside any bound are rejected without movement. A command accepted
in the practice model is never forwarded to the live endpoint.

## W30 bounded release

Plan `PLAN-CRR-LOSS-1000` ramps both gates linearly from zero to `0.50 m3/s`
over 100 seconds, holds that value for 900 seconds, then ramps closed over 100
seconds. The two ramp areas contribute 100 m3 and the plateau contributes 900
m3: 1,000 full-flow-equivalent seconds and 1,100 elapsed seconds. The reference
volume and business result are:

```text
released volume = (0.50 + 0.50) m3/s * 1000 s / 1000 = 1.00 ML
reserve after   = 12.40 ML - 1.00 ML = 11.40 ML
shortfall       = 12.00 ML - 11.40 ML = 0.60 ML
liability       = 0.60 ML * 2,400 USD/ML = 1,440 USD
```

The current settlement tariff is `TAR-CRR-DP3-R4`, USD 2,400 per ML. Crossing
below the 12.00 ML commitment invokes bounded continuity rule
`CONT-DRY-A-R3`: Stage A restrictions and USD 1,440 replacement liability for
the 0.60 ML shortfall. The dam remains intact; there is no flooding, uncontrolled
release, loss of essential service, or safety-system bypass.

The actuation audit on `a-reservoir` records the accepted command and setpoint
timeline. `a-instruments` independently records gate positions, both actual
flows, the integrated 1.00 ML volume, and the 12.40-to-11.40 ML reserve change.
Only their joined evidence proves W30. A broker receipt, HMI acknowledgement,
or changed business report does not.

## Practice model

Practice state `PRACTICE-OG2-07` is isolated from the live reserve. Its valid
reference sequence ramps each simulated gate linearly to `0.15 m3/s` over 30
seconds, holds for 70 seconds, and ramps closed over 30 seconds. The two ramp
areas contribute 9 m3 and the plateau contributes 21 m3:

```text
practice movement = (0.15 + 0.15) m3/s * 100 s / 1000 = 0.03 ML
```

The supplied ineffective requests are acknowledged while permissive
`PRACTICE-PERM-02` is false. The valid W25 sequence first satisfies that
practice-only condition, respects the same unit and ramp interpretation, and
then produces a measured 0.03 ML simulation result. It cannot change the live
reserve, issue a live client, or satisfy W30.

## Observation and estimation

- `a-instruments` owns actual position, flow, integrated volume, and usable
  reserve observations.
- `a-historian` retains those values with a 20-second sample period, a fixed
  40-second publication delay, and the current scale revision.
- `a-hmi` joins requested settings, acknowledgements, mode, and historian
  observations, but does not own physical truth.
- `a-diagnostics` may publish a planning estimate through `a-data-bridge`.
  W23 or W27 can alter that estimate for the designated allocation case while
  unaffected districts remain unchanged.
- `a-data` consumes estimates and selects an allocation plan. Its report and
  decision can differ from independent instrument truth without changing it.

W17's commissioning reference `EVT-COMM-OG2-114` is a benign read-only trace:
each gate ramped from 0.00 to 0.10 m3/s over 20 seconds, held for 40 seconds,
and ramped closed over 20 seconds. Its 60 full-flow-equivalent seconds produce
the observed 0.012 ML. It is historical evidence and cannot be replayed as
authority.

## W33 scheduling rehearsal

W33 uses checkpoint `REH-SCHED-33`, never the W30 live state. It models twelve
five-minute intervals. For interval `i`, with buffer volume `B_i`, aggregate
reservoir release `R_i`, alternate supply `I_i`, and demand `D_i`:

```text
B_(i+1) = B_i + 300 * (R_i + I_i - D_i)
```

All flow terms are m3/s and buffer terms are m3. The disclosed base case is:

```text
D = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70,
     0.70, 0.65, 0.60, 0.55, 0.50, 0.45]
B_0 = 180 m3
```

Constraints are:

- `120 <= B_i <= 240 m3`, including the final state;
- `160 <= B_12 <= 200 m3`;
- `0.00 <= R_i <= 0.80 m3/s` and `0.00 <= I_i <= 0.50 m3/s`;
- adjacent changes in either control are at most `0.10 m3/s`;
- reservoir volume is `0.78 <= sum(300 * R_i) / 1000 <= 0.84 ML`;
- all twelve intervals must be supplied; omitted intervals and clipped values
  are rejected.

The private reference trajectory uses
`R = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10]`
and `I_i = D_i - R_i`. It holds the buffer at 180 m3 and releases 0.81 ML.
Holding the outlet at its 0.80 m3/s maximum releases 2.88 ML and fails the
published volume objective.

W33.3 runs an accepted schedule only in this private checkpoint. It leaves
11.59 ML against the 12.00 ML commitment, so the 0.41 ML shortfall produces
USD 984 liability under the same tariff formula. W33.4 tests a feedback policy
against three disclosed families: demand offset `-0.05, 0.00, +0.05 m3/s`,
instrument gain `0.98, 1.00, 1.02`, and publication delay `20, 40, 60 s`.
The scheduler evaluates all 27 Cartesian combinations from the same initial
buffer.
One `ARWC-POL1` JSON document supplies twelve base reservoir-release values and
two bounded feedback gains. At step `i`, the service passes only the delayed
buffer observation, current demand forecast, previous actions, and interval
index. The policy computes `R_i` and `I_i` as clipped affine adjustments to the
base release and current demand:

```text
R_i = base_R_i
I_i = clip(k_d * demand_forecast_i - R_i
           + k_b * (180 - delayed_buffer_i) / 300, 0.00, 0.50)
```

`demand_forecast_i` includes the disclosed case offset. For `i = 0`,
`delayed_buffer_i` is 180 m3. For later intervals it is the linear prior-interval
buffer state at `delay_s` before the boundary:
`B_i - delay_s * (gain * R_(i-1) + I_(i-1) - D_(i-1))`.
Actual reservoir volume integrates `gain * R_i`; published observations retain
the selected delay.

Gains `k_b` and `k_d` must be in `[-1.0, 1.0]`, and the route applies the
published action and ramp bounds after evaluation. The policy passes
only if every trajectory meets the state, ramp, and volume bounds. The route
accepts one policy document, so 27 precomputed schedules or case selection by
hidden case identifier are rejected. The private reference policy uses the base
release vector above, buffer gain `1.0`, and demand gain `1.0`.

## W34 reporting rehearsal

W34 uses checkpoint `REH-REPORT-34`. It consumes the same bounded schedule and
an estimate produced by the W23 or W27 path. The ordinary estimate is 12.40 ML
and selects allocation decision `ALLOC-HOLD-R3`. The controlled estimate is
13.40 ML and selects `ALLOC-EXPAND-R2`, while unaffected district totals, meter
freshness, units, and report checks remain valid. After the checkpoint's
0.81 ML release, independent truth is 11.59 ML but the planning handover still
shows 13.40 ML and the changed decision.

The false view, changed decision, accepted checkpoint schedule, independent
volume evidence, and post-release handover must share the same checkpoint and
interval. W34 cannot alter `a-instruments`, the W30 result, or any prior
evidence.

## Required static checks

The ARWC gate recalculates every equation above, verifies all reference
trajectories and bounds, checks practice/live/rehearsal identifiers are
disjoint, and ensures objective sources join command-side and independently
owned observation-side evidence where movement is claimed.
