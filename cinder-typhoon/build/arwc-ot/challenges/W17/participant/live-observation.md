# Cairn Reach live observation sheet

Use this sheet for a read-only operating observation of site `AST-CRR-017`.
Do not change a proposed setting or apply a request for W17.

Use three ordinary product views:

1. The FUXA Cairn Reach overview for the live operator view.
2. The OPC UA browser for the controller's live tag value and source time.
3. Cairn Reach process history for the same measured value over a bounded
   interval.

Record UTC times. Values without a unit or values taken outside the recorded
interval cannot be reconciled. Requested or accepted settings are not measured
position, flow, level, or usable volume, even when the numbers happen to match.

## Current observation

- UTC observation time:
- Measured level (m):
- Usable volume (ML):
- Outlet A measured position (%):
- Outlet B measured position (%):
- Outlet A measured flow (m³/s):
- Outlet B measured flow (m³/s):
- Measured total flow (m³/s):
- Accepted outlet A setting (%):
- Accepted outlet B setting (%):
- Accepted automatic-flow setting (m³/s):

## Operating state

- Actual mode:
- Command owner:
- Field data state:
- Outlet A permissive:
- Outlet B permissive:

## Correlated trace

- UTC interval start:
- UTC interval end:
- FUXA variable:
- OPC UA NodeId:
- Historian series:
- First and last values (m³/s):
- Minimum and maximum values (m³/s):
- Number of good historian samples:

The trace is complete only when all three views identify the same live point and
the historian interval contains good product-owned samples. A screenshot or a
locally copied value is supporting material, not the process record.
