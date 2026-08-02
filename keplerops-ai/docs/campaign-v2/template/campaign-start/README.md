# Campaign Start Overlay

This directory layers the Cinder Typhoon campaign onto the neutral KeplerOps AI
Systems enterprise. It does not provide a challenge runtime or proof service.
Each operation is realized through normal enterprise records, identities,
services, jobs, artifacts, and effects.

Each `modules/mXX` directory owns:

- `operations.json`: Shifter-facing metadata and native carrier declarations;
- `apply.sh`: idempotent enterprise state reconciliation;
- `validate.sh`: participant-surface positive and negative checks;
- `reset.sh`: the smallest safe operation-local reset;
- `qa.md` and `facilitator.md`: executable QA and teaching material; and
- `payloads/`: ordinary in-world content.

Run `./apply.sh` only after the clean enterprise is healthy. The default full
apply deploys the 132 software operations and writes
`/run/shifter/keplerops-v2-software.ready`; it does not mark `kep-m08-i` or
`kep-m06-m` ready and never writes the all-challenges marker. Run
`./apply.sh --all-challenges` only when a real physical place is attached and
`KEPLEROPS_HARDWARE_GATE14_PLACE` names it. That mode requires the real-place
evidence exercise and the Kali reservation/acquisition/release gate before it
writes `/run/shifter/keplerops-v2-campaign.ready`. Applying a single
non-physical operation does not require the external bench. Applying either
physical operation remains fail-closed.

Full apply first reconciles M07's clean baseline independently of catalog order.
Shared orchestration then initializes the GitOps repository without a
placeholder deployment, materializes or safely reuses the exact immutable
candidate, promotes and signs it through Forgejo/Argo/KServe, captures the
admitted Vertex GLM 5.2 assistant runtime, activates the business identities,
and passes release continuity plus full platform readiness. Only then are
M01-M06 and M08-M10 start states applied; M07 is skipped because its start state
is already reconciled. This infrastructure phase creates no operation
checkpoint or accepted/success state. Campaign readiness is written only after
all remaining modules and final shared-service convergence finish.

Run
`./validate.sh --static` before applying state, then `./validate.sh --all`
against the integrated candidate with `CAMPAIGN_EVIDENCE_MANIFEST` naming the
walkthrough evidence JSON. The manifest is keyed by operation ID; each value is
an object containing the `PARTICIPANT_*` values and, where required, the
module-scoped `Mxx_*` captured evidence values used by that validator, for
example:

```json
{
  "kep-m01-a": {
    "PARTICIPANT_CARRIER_URL": "https://workhub.keplerops.lab/issues/101",
    "PARTICIPANT_NEGATIVE_URL": "https://release.keplerops.lab/v1/release-calendar/orion-edge-2026.08"
  }
}
```

This file is generated during the participant-equivalent walkthrough and is not
part of campaign start state. `./export-shifter.py` produces the single
digest-pinned `shifter-ctf-content/v1` bundle used by Shifter's native scenario
content hydration path. Shifter's prerequisite graph is conjunctive. A mixed
path may declare `board_prerequisites` for only the prerequisites that are
always required; pure alternatives remain unlocked on the board. The complete
boolean path is still enforced by enterprise access controls.

Module apply scripts may temporarily converge a shared service with only the
module overlay needed for their own setup. The root apply always finishes by
converging Airflow and the Cinder Forgejo runner with every module overlay plus
the root overlay, then validates and reloads Caddy from the base file and every
module fragment. This final pass prevents a later module from discarding
earlier DAGs, runtime mounts, runner access, or public routes.
