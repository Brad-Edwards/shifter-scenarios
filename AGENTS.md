# Agent operational notes

Hard-won operational knowledge for agents working on this repository. Read the
relevant section before rebuilding the runtime adapter, baking scenario images,
or debugging range readiness. This file is scenario-repo specific. Platform and
provisioner concerns live in the platform repository (`Brad-Edwards/shifter`)
under `docs/dev`.

This repository holds Shifter scenario content (polaris, cinder-typhoon,
keplerops-ai) and the `runtime-adapter` that Shifter installs as a runtime
plugin to bring scenario ranges up.

## Runtime adapter (`runtime-adapter/`)

One plugin: `panw.polaris-direct` (keyless Vertex, GCP only). The broker-backed
`panw.polaris` plugin is retired. Claude Code is never baked into an image: the
`polaris-direct` pack declares it and Shifter delivers it to the host's
`/opt/shifter/bin`, which Compose bind-mounts into `a14-kali`.
Published to GHCR as
`ghcr.io/paloaltonetworks/shifter-scenarios/runtime-adapter:<version>`.

### Rebuild and publish

1. Bump the version in `runtime-adapter/pyproject.toml` AND the manifest
   (the `version=` in `runtime_direct.py`). The SDK caps
   `GuestAction.timeout_seconds` at 300; exceeding it fails `plan()`, and the
   install probe does not catch that (only live provisioning does).
2. `python3 prepare_release.py --sdk-wheel <shifter_adapter_sdk-*.whl> --output /tmp/adapter-release-<v>`.
   This is network-free and hash-pinned. The SDK source lives in the platform
   repository under `shifter/shifter_adapter_sdk/`. It builds the adapter wheel,
   downloads the runtime-dependency wheels, and writes a hashed
   `requirements.txt` plus the Dockerfile.
3. `docker build -t ghcr.io/paloaltonetworks/shifter-scenarios/runtime-adapter:<v> /tmp/adapter-release-<v>`
   then `docker push`. Capture the registry digest with
   `docker inspect --format '{{json .RepoDigests}}' <tag>`.

### Test locally

The SDK is not on PyPI, so install it from the platform repository checkout:

```
uv venv /tmp/av
uv pip install --python /tmp/av pytest pydantic pyyaml
uv pip install --python /tmp/av --no-deps -e <platform>/shifter/shifter_adapter_sdk
uv pip install --python /tmp/av --no-deps -e runtime-adapter
/tmp/av/bin/python -m pytest tests/ -q
```

The worker tests spawn `python -m shifter_adapter_sdk.worker` as a subprocess,
which needs both packages installed, not merely on `PYTHONPATH`. The
`test_runtime*.py` tests assert the exact configure and verify `action_id`
lists and indices, so update them when you add or remove a step.

### Install and bind on a tenant (platform Django shell)

- `engine.services._runtime_plugins.install_runtime_plugin(user, org_uuid, manifest_dict)`.
  The `manifest_dict` is the prior install's `RuntimePluginInstallation.manifest`
  with `version` bumped and `worker_image` set to the new `@sha256:` digest.
  `get_or_create` keys on (org, plugin_id, version) and rejects a digest change
  for an existing version, so always bump the version for a new image. State
  starts `checking`; an async probe (about 45 seconds) pulls the image and
  verifies the worker's reported manifest, then moves to `ready`.
- `engine.services._runtime_plugin_bindings.bind_runtime_plugin(user, RuntimePluginScope(org, pack_id, pack_digest), installation_id, bindings_dict)`.
  This does `update_or_create` on (org, pack_id); reuse the prior binding's
  `bindings` value (targets, parameters, and image_profiles). It requires the
  install state to be `ready`.

## Preconfigured-machine-host readiness marker

Polaris range hosts use `bootstrap_capability == preconfigured-machine-host`.
The platform's `PreconfiguredMachineHostPlan` canary (the
`wait_for_preconfigured_machine_host` provisioner step) gates the range on three
conditions polled together: the file `/run/shifter/preconfigured-range-host.ready`
exists, the `a14-kali` container is running, and host port `127.0.0.1:3389`
(RDP) accepts a connection.

The adapter owns writing that marker, because polaris brings the compose stack
up through the adapter rather than a self-starting baked image.
`WRITE_PRECONFIGURED_HOST_READY_MARKER` in `_polaris_scripts_aux.py` is wired
into the `runtime_direct.py` verify phase, before the
model checks. It waits (bounded) for the container and RDP, then writes the
marker atomically. The write is best-effort and the platform canary is the
authoritative gate. Any new preconfigured-host scenario must write this marker
too. This was added in adapter 0.1.22.

Debugging note: range hosts are locked to the provisioner transport (rotated
keys, no OS Login), so you cannot `gcloud compute ssh` in, even with a
temporary IAP firewall rule (the tunnel connects but auth is refused).
Diagnose from the provisioner log (look for
`step=wait_for_preconfigured_machine_host` then `FAILED ... attempt=N/5`) and
from whether the range reaches `Range.status=ready`.

## Scenario images, the compose stack, and the private build tree

- The range VM images (the `polaris-vm` host and the `polaris-dc` Windows DC)
  are GCP Compute Engine images (for example `shifter-polaris-vm-*` and
  `shifter-polaris-dc-*` in the tenant project), not GHCR artifacts. GHCR holds
  only the OCI container images: the runtime adapter and the compose service
  containers that are baked into `polaris-vm`. AWS uses AMIs for the VM images.
- The compose stack is fetched at bake time, not from the repository checkout.
  GCP stages it in Cloud Storage (`POLARIS_STACK_BUCKET` and key, for example
  `gs://<project>-polaris-stack/polaris/stack/polaris-stack.tar.gz`). AWS uses
  the S3 bake tarball.
- `scenario-dev/polaris/build/` is intentionally gitignored, because the flags
  and solutions are scenario-sensitive (the tree was removed in commit
  `b7c0972dc`). A fresh public-repository checkout has no `build/`, so the bake
  cannot build `polaris-vm` from the checkout. The operator must supply the
  private stack tarball (upload it to the stack bucket). The public tree keeps
  only scenario-agnostic pieces (`containers/`, `content-packages/`, `sdl/`,
  `design/`). Do not restore `build/` from the stale branches that still carry
  it, because that re-leaks the solutions.

## Runtime

Polaris runs on the GCP Compute Engine range-cell backend: one range cell per
participant, holding a Linux host VM that runs the compose stack plus a Windows
Server DC for `BOREAS.LOCAL`. The older GDC VM-Runtime path was abandoned; the
GCE range-cell is canonical. The platform and provisioner deploy-side knobs and
gotchas (range service-account IAM, `DC_DOMAIN_PASSWORD`,
`GCP_RANGE_KALI_IMAGE=shifter-polaris-vm`, disk sizes, Private Google Access,
and the in-range SSH timeout) live in the platform repository under
`docs/dev/polaris-gcp-range-cell.md` and `docs/dev/gcp-range-cell-deploy.md`.
