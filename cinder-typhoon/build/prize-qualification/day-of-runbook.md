# Event prize day-of runbook

Use only the release candidate whose prize qualification command passes against
the committed summary. Confirm the event's configured stage closes, nomination
close, event close, claim deadline, and finalization match the owner-approved
event schedule before activation.

## Monitor

- Keep the authorized 50-slot operator dashboard open.
- Watch its trigger, notification, allocation, pack, claimed-time, and
  fail-closed columns.
- Treat any dashboard error, content/policy mismatch, missing occurrence, or
  inventory-count error as a stop condition for that prize action. Participant
  scoring and access continue independently.
- Retry a failed notification through the approved event communication action.
  The stable intent key keeps the selected participant unchanged.

## Handover

1. Ask the participant to present the claim code or QR from their authenticated
   event prize page.
2. Scan or enter that value and the number printed on the physical pack.
3. Confirm that the operator receipt shows the expected public alias, award,
   and pack number.
4. Hand over that numbered pack. An identical submission retry returns the same
   receipt and does not consume another pack.

## Recovery

- For a declined or otherwise unclaimed prize before finalization, an event
  administrator records a reasoned void. The final scheduled occurrence fills
  the open slot from the prior-winner-safe fallback.
- At the published claim deadline, run the single scheduled deadline action.
  Monitor its void count, then allow the scheduled finalization action to fill
  open slots.
- Never void a claimed allocation. For a damaged or incorrectly recorded pack,
  an event administrator records a reasoned custody correction to an unused
  pack. Keep the original claim and corrected-out pack history.
- After restart, reopen the same bound state and confirm all 50 dashboard rows.
  If the state cannot be recovered, rebuild from the bound authoritative input,
  nomination close, and recorded voids; require the stored selection-proof
  digest to match before resuming handover.

Do not calculate winners, export scores, check duplicates in a spreadsheet,
replace an allocation, or perform a manual draw during the event.
