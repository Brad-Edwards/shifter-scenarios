# Private runtime adapter

## Direct Vertex plugin

`polaris_direct` (`panw.polaris-direct`) is the adapter's only plugin. It is
GCP-only. The broker-backed `polaris` plugin is retired until Shifter's model
gateway work replaces the parked broker.

Claude Code is never baked into the participant image. The pack declares the
`claude-code` feature on the `a14-kali` host. Shifter acquires the binary,
delivers it to `/opt/shifter/bin/claude` on the host, and verifies its digest
before this plugin's configure phase runs. Compose bind-mounts `/opt/shifter/bin`
read-only into the participant container, where the image links
`/usr/local/bin/claude` to it.

The direct plan sets Claude Code's Vertex project, region and model environment
in the participant container and uses the range host's attached GCE service
account through metadata. It installs no broker client, broker session, API key,
or per-range service-account key. The GCP tenant must enable Private Google
Access and attach a range-host identity with Vertex prediction permission. The
verify action runs a real `claude -p` request inside the participant container;
local tests alone do not establish live qualification.

The direct participant container can obtain the host's metadata identity. Keep
that identity restricted to model invocation and low-risk telemetry permissions;
do not grant it broad project access.

Private Google Access only reaches approved Google APIs; it does not provide
general web research. If participants need web search from Kali, configure the
host profile's opt-in public web egress and a working shared-VPC Cloud NAT path
before launching an event, then verify public DNS and HTTP/HTTPS from the
participant terminal. A profile flag alone is insufficient when its workspace
has no NAT. Do not treat a successful model call as proof of internet access.

Docker Compose pins the additional Google API hostname used by Claude Code to
the Private Google Access VIP, so the mapping survives a workstation-container
restart. The configure plan synchronizes the provisioned desktop account's
password verifier from the host into the participant container after the XRDP
repair, without handling plaintext in the adapter action or its logs. The pack
must declare the matching RDP participant access account and endpoint; the
adapter cannot add an undeclared endpoint. The same configure action writes the
non-secret Vertex settings to the Kali container's PAM login environment, so SSH
and XRDP sessions receive them instead of relying on Docker Compose environment
inheritance. The verify action checks that both login services load this file;
live participant sessions must still be tested with a real Claude Code response.

The worker entry point builds against `shifter-adapter-sdk[runtime]==0.1.0`
alone. It imports no Shifter application code.

`bootstrap.build_plan` and the old provider scripts remain for migration behavior
comparison only. The registered entry point does not invoke those credential
paths and has no provider fallback.

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

The selected worker registry is the GitHub Container Registry package
`ghcr.io/paloaltonetworks/shifter-scenarios/runtime-adapter`. Its approved visibility
is `internal`, matching this repository. The image carries this repository's
source label; the package API does not report a repository link. Verify the
intended visibility before each publication; a source label alone does not
establish access control. Retain the returned registry digest after publication.
Tenant administrators provide a registry credential with read-only package
access through the adapter UI. Do not place a publishing credential in the
manifest or tenant installation.

After publishing the image, generate the upload manifest from
`shifter_panw_adapter.runtime_direct.manifest(actual_image_reference)`. The
reference must include the registry's actual `@sha256:` digest. Upload it
through the tenant adapter administration page, inspect and enable it, then bind
the installed `polaris-direct` pack digest and explicit host/directory targets.
Never substitute an image tag or fabricated digest.

## Local evidence

The Python tests exercise the direct plan, plan authorization, parameter
rejection, shell syntax, the participant image's delivered-client contract, and
actual SDK inspection/planning from installed wheels. Run them in a clean
environment with only the SDK, this wheel, pytest and PyYAML installed:

```sh
python -m pytest tests/test_runtime_direct.py tests/test_participant_image.py \
  tests/test_bootstrap.py tests/test_release.py -q
```

Live acceptance requires tenant installation, pack assignment, real guest
configuration and readiness, Claude Code delivery, retry, cancellation and
verified cleanup. Local tests and installed-wheel inspection are not cloud
qualification. Keep deployment evidence in this private repository, and do not
claim qualification until the complete participant walkthrough has passed.
