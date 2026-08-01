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
4. start the collaboration, engineering, AI platform, business, and Cinder
   service groups;
5. pass all clean-enterprise gates;
6. apply the campaign-start overlay; and
7. run participant-equivalent checks before producing a machine image.

The repeatable entry points are:

```bash
sudo /opt/keplerops-v2/scripts/start-all.sh build
sudo /opt/keplerops-v2/scripts/start-all.sh resume
sudo /opt/keplerops-v2/scripts/check-all.sh
sudo /opt/keplerops-v2/baseline/cinder-surfaces.sh
sudo /opt/keplerops-v2/baseline/document-intake.sh
sudo /opt/keplerops-v2/baseline/source-ci-registries.sh
```

`build` performs the initial image pulls, derivative builds, guest creation,
platform install, and convergence. `resume` starts and reconciles an already
built template without pulling or rebuilding images. Both finish at the same
component-substrate readiness gate. That gate is necessary but does not claim
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

Do not run these scripts on a live participant range. `bootstrap-host.sh`
requires the GCE instance label `campaign=v2` and refuses any other host.

Synthetic credentials in this directory are range content. They are not
operator or production credentials.
