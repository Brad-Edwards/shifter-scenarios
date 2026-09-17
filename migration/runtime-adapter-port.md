# Private runtime adapter port

Status: local cutover candidate. The SDK worker, model enrollment and broker
paths, native GCE and EC2 realization, tenant plugin/pack administration, and
separate installable runtime pack are implemented locally. The runtime-pack
build passes canonical validation and digest checks; its actual compiled plan
is accepted by both provider planners using synthetic image profiles.

The participant container now builds locally with the pinned client and passes
the loopback wire test. The worker candidate is published to GHCR with the
approved Internal visibility; pull by digest and isolated inspection pass.
Cloud guest image bakes and live acceptance in AWS and GCP remain outstanding. No live
qualification or deployment was performed. The following sections retain the
initial extraction inventory; current packaging instructions are in
`../runtime-adapter/README.md` and `../runtime-pack/README.md`.

## Historical extraction inventory

- Bootstrap scripts from `plans/_polaris_scripts*.py` and the splice credential
  helper are private adapter assets. The current template renderer and step
  assembly must be rewritten against SDK plans without importing Shifter's
  provisioner `config`, `plans.base`, executors or orchestrator modules.
- Pack content, answers, tests, image recipes, compose configuration and bake
  documentation remain private pack assets. Do not overwrite the maintained
  pack with the archived Shifter copy: the two trees differ.
- The S3/GCS smoke-test fetch step should become normal pack content delivery,
  removing the scenario-specific bucket, key and signed-URL helper from core.
- Verification uses this package's declared plugin entry point and private
  probes. Shifter's tests must retain only synthetic contract cases.

## Original capability gaps and their migration boundaries

- The DNS/container bootstrap requires the realized directory guest IP and a
  participant access public key. The SDK now supports typed runtime-value
  references, resolved by the host after realization and delivered to the guest
  action. The planning worker still receives no realized values. Participant
  keys come only from a verified declared account, never management credentials.
- Container participant access and credential installation must use explicit
  access bindings. The current scenario-specific host-password skip and fixed
  container selector must not simply be renamed as generic helpers.
- AWS model access currently consumes a per-range IAM role and refresh policy.
  GCP consumes a per-range model credential reference. Resolve these through
  Shifter's ADR-059 broker boundary, with bounded ownership and cleanup. The
  legacy script variants preserved in the planning library are migration
  comparison evidence, not permission to restore guest provider credentials as
  the new contract. A tenant-supplied worker must not inherit the platform cloud
  role or use unrestricted Terraform as a substitute.
- Both native AWS and GCP host implementations are now wired. Each needs
  explicit live migration acceptance, including failure and cleanup, before
  the cutover is qualified.

The `runtime-adapter/` package now builds with the SDK wheel alone. Its private
tests exercise both provider plans, shell parsing, strict model input validation,
firewall ordering, packaged helper access and absence of core imports. The registered
worker entry point produces plans using SDK contracts and broker enrollment;
legacy direct-provider scripts are retained only for migration comparison.

The final adapter image must build from a released SDK wheel and this repository
alone. The required acceptance deployments are **both AWS and GCP**, including
installation, configuration, verification, failure, retry, cancellation and
cleanup. Neither cloud has live acceptance evidence yet. Keep private deployment
evidence here, not in public Shifter issue or PR metadata.
