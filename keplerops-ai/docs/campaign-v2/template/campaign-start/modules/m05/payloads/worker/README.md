# Orion dataset worker

The disposable dataset worker is pinned to MLflow 2.8.1 for compatibility with
the evaluation migration recorded in WorkHub. HTTP dataset sources are loaded
into `/var/lib/orion-dataset-worker/datasets`; the worker-owned Python import
directory is `/var/lib/orion-dataset-worker/python`.

Child evaluation jobs inherit only the `svc-orion-trainer` application token.
The token permits approved training/source reads, external contribution
branches, owned MLflow runs and the bounded support-export workflow. It does not
permit hidden-label reads, signer access, arbitrary object-store prefixes,
release approval, Argo administration or business-system access.
