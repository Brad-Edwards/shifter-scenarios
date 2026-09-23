# Private runtime adapter

The `polaris` worker entry point builds against `shifter-adapter-sdk[runtime]==0.1.0`
alone. It imports no Shifter application code. `runtime.PolarisAdapter` produces
configure, verify and cleanup plans for both AWS and GCP and requires the
`participant` model grant on its `host` binding. Shifter owns cloud realization,
enrollment, authorization, budget enforcement and grant revocation.

The adapter transfers the trusted guest enrollment into its own tmpfs directory
and mounts that whole directory into the participant container. The SDK helper
refreshes the opaque broker capability atomically. Provider credentials are never
required. The provisioner's enrollment directory and lock retain their original
ownership, so a configure retry can enroll again. Cleanup stops the consumer and
removes its session; Shifter must still revoke the grant and destroy the range.

The pinned client is version **2.1.108**. Its private fetch shim removes only the
known inert client/effort annotations and bounded `metadata.user_id` telemetry,
normalizes identical duplicate authentication schemes, and rejects unknown betas,
conflicting authentication, destinations, queries and unsupported top-level
features. Thinking, caching and experimental features are disabled. Shifter's
closed protocol and billing rules are unchanged. Logical model aliases and the
maximum output token count are explicit administrator parameters; the broker
independently enforces its approved models and limits.

`bootstrap.build_plan` and the old provider scripts remain for migration behavior
comparison only. The registered production entry point does not invoke those
credential paths and has no provider fallback.

## Packaging

Build the SDK wheel separately, then this package with `uv build --wheel`.
Use the locally built SDK wheel or download Shifter's SDK candidate artifact and
verify its `SHA256SUMS`. SDK publication is not required. The preparation command
accepts the explicit wheel and checks the exact dependency:

```sh
python runtime-adapter/prepare_release.py \
  --sdk-wheel /absolute/path/shifter_adapter_sdk-0.1.0-py3-none-any.whl \
  --output /tmp/private-adapter-release
docker build --platform linux/amd64 --network=none \
  --tag private-adapter:candidate /tmp/private-adapter-release
```

Preparation requires Python 3.12 or later with pip, and uv. It builds this distribution and
downloads the hash-pinned Linux amd64 dependencies. It refuses an existing output
directory. `build-inputs.json` records every wheel hash and the Dockerfile hash;
retain it with the resulting registry digest. The image build verifies dependency
closure with `pip check`. Neither command publishes or deploys anything.

The worker image consumes a `wheels/` directory containing the two wheels and
all runtime dependency wheels, plus a `requirements.txt` with exact local wheel
paths and SHA-256 hashes. Install neither Shifter's application nor its provisioner
in this image. Docker performs a network-free, hash-checked installation and
`pip check`; build with `docker build --network=none`.

On GCP, the configure plan forwards the scenario DNS service to the VM's
`169.254.169.254` resolver so the participant container can resolve the
tenant-private broker hostname. The GCP metadata firewall allows only DNS
traffic to that address from containers; HTTP and HTTPS metadata access remain
blocked. The verify plan runs the real Claude Code launcher inside the
participant container and reports ready only after the request succeeds.

The selected worker registry is the GitHub Container Registry package
`ghcr.io/paloaltonetworks/shifter-scenarios/runtime-adapter`. Its approved visibility
is `internal`, matching this repository. The image carries this repository's
source label; the package API does not report a repository link. Verify the
intended visibility before each publication; a source label alone does not
establish access control. For a new package, use a content-free placeholder to
establish access settings first. Retain the returned registry digest after
publication. Tenant administrators provide
a registry credential with read-only package access through the adapter UI.
Do not place a publishing credential in the manifest or tenant installation.

After publishing the image to the owner's registry, generate the upload manifest
from `shifter_panw_adapter.runtime.manifest(actual_image_reference)`. The reference
must include the registry's actual `@sha256:` digest. Upload it through the tenant
adapter administration page, inspect and enable it, then bind the installed pack
digest and explicit host/directory targets. Assign the approved `participant`
model policy separately. Never substitute an image tag or fabricated digest.

This is a **local qualification candidate**, not a live-qualified release.
Core AWS and GCP realization are now wired, and `../runtime-pack/` produces the
separate tenant-uploadable launch package. The previously recorded participant
container candidate used client 2.1.273 and is superseded: that package no
longer contains the `cli.js` entry point required by this adapter. The source
recipe now pins 2.1.108, which passes the isolated loopback wire test; a new
container build and cloud guest image bake remain pending. The worker
candidate is now available by digest: authenticated pull and isolated inspection
passed. The upload manifest is
`../migration/runtime-adapter-candidate-manifest.json`, with registry readback in
`../migration/worker-registry-candidate.json`. Both cloud qualifications remain
pending.

## Local evidence

The Python tests exercise both provider plan variants, plan authorization,
parameter rejection, shell syntax, secure enrollment transfer and retry, launcher
credential handling, and actual SDK inspection/planning from installed wheels.
Run them in a clean environment with only the SDK, this wheel and pytest installed:

```sh
python -m pytest tests -q
node --test tests/node/client-compat.test.cjs
```

`tests/node/client-wire.cjs` runs the actual pinned client against a loopback fake
endpoint with external networking disabled. It exercises helper authentication,
a streaming tool request, a real local file read and the returned tool result.
It emits only a bounded verdict, never captured prompts, responses or tokens.
The unpacked client package belongs at `/client` and this directory at `/work`:

```sh
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --pids-limit 128 --memory 768m --cpus 2 \
  --tmpfs /tmp:rw,nosuid,nodev,size=128m \
  --mount type=bind,src="$CLIENT_PACKAGE_DIR",dst=/client,readonly \
  --mount type=bind,src="$PWD",dst=/work,readonly \
  node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 \
  node /work/tests/node/client-wire.cjs
```

The npm archive used for this check has SHA-512 (base64)
`MSYnRJQNwPSlJrQZrbhyGGcvbVwJMkYqaH3VD3M4n4/3pH73spulZrCo1hZWxl5VaJRIJpc62AkEDGk0jlVjzA==`.

For the rebuilt participant container, set `CLIENT_PACKAGE_ROOT` to
`/usr/local/lib/node_modules/@anthropic-ai/claude-code` and run the same wire test
with `--entrypoint node`, the read-only `/work` mount and the same isolation flags.
The bounded result and local image identity are recorded in
`../migration/participant-container-candidate.json`.

Required live acceptance targets are **AWS and GCP**. Both require tenant
installation, pack assignment, real guest configuration/readiness, model budget
and revocation checks, retry, cancellation and verified cleanup. Local tests and
installed-wheel inspection are not cloud qualification. Keep deployment evidence
in this private repository. No live environment has been used for these checks.
