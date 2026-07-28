# Telemetry and evidence

KeplerOps AI includes participant-run data capture intended to support
playtesting and later research analysis. Collection policy is an event
configuration decision; this guide records the operational surfaces, not the
research protocol.

## Operator evidence

Operator state is under:

```text
keplerops-ai/build/.operator/<range-instance>-<participant-id>/
```

This directory is owner-only deployment state and must not be handed to
participants.

## Export commands

Use the pack export tooling after a session when evidence capture is needed:

```sh
build/export-telemetry.sh \
  --range-instance <range-instance> \
  --participant <participant-id> \
  --output /operator/evidence/<range-instance>-telemetry.tar
```

If content capture is enabled for the event profile, export it according to the
operator playtest guide.

## Data to reconcile

- range instance;
- participant id;
- reset generation;
- challenge receipts issued;
- participant terminal/browser/file telemetry if enabled;
- operator smoke reports;
- defect notes and timing.
