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

Run `./apply.sh` only after the clean enterprise is healthy. Run
`./validate.sh --static` before applying state, then `./validate.sh --all`
against the integrated candidate. `./export-shifter.py` produces the single
digest-pinned `shifter-ctf-content/v1` bundle used by Shifter's native scenario
content hydration path. Shifter's prerequisite graph is conjunctive; operations
with multiple alternative in-world ingress paths remain unlocked on the board
and rely on the enterprise access controls to enforce those alternatives.
