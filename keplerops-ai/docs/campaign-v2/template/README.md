# Campaign-v2 Event Template

This directory records the exact event-delivery implementation applied to the
GCP KeplerOps campaign-v2 template. It is intentionally separate from the
legacy scenario realization. The event build uses the proven nested carrier
and participant desktop, but creates the enterprise and campaign state from
these files.

The implementation order is fixed:

1. run `scripts/bootstrap-host.sh` on a dedicated template clone;
2. run `scripts/start-foundation.sh` and pass the foundation health gate;
3. provision the Samba AD and domain-member guests;
4. start the collaboration, engineering, core AI platform, business, and
   Cinder service groups without a placeholder release-risk model;
5. reconcile M07 first, initialize GitOps without a placeholder deployment, and
   materialize the exact clean training run through immutable candidate,
   Forgejo/Argo/KServe release, signed Vertex GLM 5.2 runtime capture, business
   identity activation, continuity, and full platform readiness;
6. apply M01-M06 and M08-M10 start states and only then write campaign readiness;
7. pass all clean-enterprise and participant-equivalent checks before
   producing a machine image.

The repeatable entry points are:

```bash
sudo /opt/keplerops-v2/scripts/start-all.sh build
sudo /opt/keplerops-v2/scripts/start-all.sh resume
sudo /opt/keplerops-v2/scripts/check-all.sh
sudo /opt/keplerops-v2/baseline/cinder-surfaces.sh
sudo /opt/keplerops-v2/baseline/document-intake.sh
sudo /opt/keplerops-v2/baseline/source-ci-registries.sh
sudo /opt/keplerops-v2/baseline/data-training-lineage.sh
sudo /opt/keplerops-v2/baseline/release-runtime-continuity.sh
sudo /opt/keplerops-v2/baseline/business-workflows.sh
sudo /opt/keplerops-v2/baseline/observability-correlation.sh
sudo env KEPLEROPS_TEMPLATE_REPLACEMENT_CONFIRM=campaign-v2-clean-template-worker-replacement \
  /opt/keplerops-v2/baseline/worker-replacement.sh
```

`build` performs the initial image pulls, derivative builds, guest creation,
core platform install, and convergence. `resume` starts and reconciles an
already built template without pulling or rebuilding unrelated images. Both
materialize or safely reuse the release bound to m07 before later campaign
modules, then finish at the same component-substrate readiness gate. That gate
is necessary but does not claim
the fourteen workflow proofs in `../enterprise-architecture.md`; the clean
baseline is complete only when those participant-visible workflow proofs pass.
`cinder-surfaces.sh` exercises the real participant container and proves its
TLS routes, tools, direct and OpenCode GLM access, object store, Knative request
relay, and cross-domain threaded mail path.
`document-intake.sh` submits a real Orion Support attachment and waits for the
scheduled Airflow workflow to extract it with Tika, index it in Qdrant, triage
it through the Orion assistant, create a WorkHub issue, preserve the exact
document in Nextcloud, and write completion state back to Zammad.
`source-ci-registries.sh` proves that the latest Forgejo main revision completed
its Actions workflow and that the matching Python package, Node package, OCI
image revision, immutable tag, moving clean tag, and digest exist through the
normal devpi, Verdaccio, and Harbor APIs.
`data-training-lineage.sh` exports the fully annotated clean Label Studio
project, recomputes its canonical hash, and requires the latest scheduled
Airflow run, exact lakeFS commit, DVC descriptor, MLflow run, lineage artifacts,
training metric, and downloaded LoRA adapter digest to agree.
`release-runtime-continuity.sh` joins the visible evaluation, policy, signing,
GitOps, KServe, and live runtime identities by immutable digest.
`business-workflows.sh` exercises all eight bounded Orion decisions through
their owning OSS products and proves idempotency, cross-range denial, native
effects, notifications, and compensation.
`observability-correlation.sh` issues one ordinary Orion inference and joins its
trace, metric, alert, searchable audit event, and runtime cost record through
the normal observability APIs.
`worker-replacement.sh` admits only a clean campaign-v2 template, captures
product-owned durable state, replaces only `review01` and `integration01`,
waits for fresh cloud-init/domain joins, and proves the captured state is
unchanged. It requires the explicit confirmation shown above and refuses a host
with participant, range, or CTF metadata.

Do not run these scripts on a live participant range. `bootstrap-host.sh`
requires the GCE instance label `campaign=v2` and refuses any other host.

Synthetic credentials in this directory are range content. They are not
operator or production credentials.
