# Tank desk field and operating guide

Document TD-04, revision 1. Controller family TR-1.

## Instrument records

`requested_volume_l` is a requested setting, not an instrument reading.
`observed_volume_l` is the measured quantity. Volume is expressed in litres (`L`).
Each observation has its own sample ID, UTC timestamp, tank ID, and quality.
Only `good` quality is usable as a current measurement. A recorded capture is
labelled with its capture ID and time; it is not the live practice display.

## Controller status

Read the legend matching `controller_revision`. Bit numbers start at zero;
an asserted bit has value one. The TR-1 legend is:

| Bit | Name | Meaning when asserted |
| --- | --- | --- |
| 0 | ready | Instrument and actuator checks passed. |
| 1 | outlet_open | Outlet position feedback is open. |
| 2 | service_hold | Transfer is blocked by the operating hold. |
| 3 | transfer_active | A bounded transfer is in progress. |

`ready` is not a transfer acknowledgement. `service_hold` prevents a new
transfer even when `ready` is asserted. Reserved bits remain zero.

## Practice tank

The practice tank is PT-01. Its capacity is 1,500 L and its initial measured
volume is 1,200 L. The outlet starts closed, `ready` is asserted, and
`service_hold` is asserted. The operating request on this desk is to transfer
200 L and leave the outlet closed. There is no inlet or automatic replenishment.

The practice view provides these ordinary controls:

- Set or clear the operating hold while no transfer is active.
- Request a bounded transfer, expressed as a whole number of litres.
- Read current instrument state, requests, and observations.

The allowed transfer quantity is 1–200 L inclusive. At least 200 L must remain
in the tank. An active hold or an already active transfer rejects a new request.
Rejected requests leave volume and outlet state unchanged and record the
reason. Changing the hold during a transfer is also rejected.

An accepted transfer runs at 20 L/s and closes the outlet after the requested
quantity has moved. For an accepted request of Q litres, the outlet is open for
Q/20 seconds. Observed volume at elapsed time t is the starting volume minus
the smaller of Q and 20t. Closing occurs at the exact terminal time, including
for a quantity not divisible by 20. Measurements use 0.1 L resolution, with
no added noise. The independent final volume check allows 0.1 L difference.

The tank publishes an observation before movement, at every elapsed whole
second while movement continues, and at the exact terminal time. Every sample
identifies the request, measured volume, outlet position, status word, and
quality. The terminal sample is retained once, even when it coincides with a
whole second. Request receipts and observations are separate records.

Requests use a caller-selected request ID. Repeating the same ID with identical
contents returns its original result without moving more water. Reusing the
ID for different contents is rejected. Concurrent requests are considered in
server acceptance order. Only one transfer can be active.

Leaving the page does not stop a transfer. Reopening it shows the persisted
current state and retained records. No page action clears records, refills the
tank, or restores an earlier state.

## Request interface

The practice view uses the same interface available to desk clients:

| Method and path | Operation |
| --- | --- |
| `GET /api/practice/state` | Current tank ID, measured volume, outlet position, status word, quality and observation time. |
| `GET /api/practice/requests` | Retained request records, in acceptance order. |
| `GET /api/practice/observations` | Retained observations, in sample order. |
| `POST /api/practice/hold` | JSON fields `request_id` and boolean `active`. |
| `POST /api/practice/transfer` | JSON fields `request_id` and integer `quantity_l`. |

Request IDs contain 1–64 ASCII letters, digits, underscores or hyphens. Inputs
are JSON objects with exactly the listed fields. Missing fields, extra fields,
wrong types and out-of-range quantities return HTTP 400 without changing tank
state. Invalid requests do not reserve a request ID. Valid requests rejected
by operating conditions return HTTP 409 with the condition recorded. An accepted
hold change returns HTTP 200; an accepted transfer returns HTTP 202 with its
request ID and acceptance time. Identical retries return the original receipt
and status code. Reusing a recorded ID with different contents returns HTTP 409.

Read responses and request receipts are JSON. The request register retains the
requested action and arguments, acceptance sequence, UTC time, result, and any
rejection reason. Observation timestamps and movement use the same service
clock, independent of the browser. Unknown paths return HTTP 404; unsupported
methods return HTTP 405. There is no client operation for writing observations.

## Outlet-test review

The issued report and its source records use attempt IDs and request IDs.
Check both identifiers and the observation times when comparing a report with
the controller and instrument records. The review concerns tank RT-02, not
the live practice tank PT-01.
