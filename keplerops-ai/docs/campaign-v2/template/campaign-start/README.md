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
