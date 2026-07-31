# Session checklist

## Before participants enter

- Confirm the range was launched from merged `dev`.
- Confirm `build/health-check.sh` passes.
- Confirm the participant endpoint opens from the allowed source CIDR.
- Confirm the participant can reach the Kasm workstation.
- Confirm the lab portal and receipt/proof surfaces respond.
- Record the range instance, participant id, reset generation, and source CIDR
  in the sanity or playtest log.

## During the session

- Capture participant timing, confusion points, and broken affordances.
- Avoid giving hidden predicates or walkthrough steps unless the session is an
  explicitly guided/debug playtest.
- If a participant hits a suspected defect, record the exact challenge,
  visible symptom, approximate time, and whether reset was used.

## After the session

- Export telemetry/evidence before teardown when research capture is in scope.
- Record whether receipts were issued and verified.
- Record any challenge that was solved by an unintended shortcut.
- Tear down or retain the range according to the event coordinator decision.
