# Polaris AWS event-range tooling

This is the authoritative `aws_event` binding. It is the same compact
topology used for Polaris events: a per-participant isolated subnet, one range
host running the complete compose environment, and one real Windows Server
domain controller. Terraform creates a dedicated VPC, gateway, artifact bucket,
IAM boundary, and pinned Ubuntu/Windows instances; it has no dependency on a
pre-existing portal VPC, peering connection, NAT gateway, custom AMI, or bucket.

This proves automated execution of the event path, not
participant-equivalent package or golden status. The fictional OT services are
authored event simulations rather than an authentic vendor twin, and the
compose services do not realize every SDL host as separate infrastructure.

The event artifact is carried by the pack as
`../build/build-v1.tar.gz`, with its digest beside it. It is reproducibly
repacked from the pack's `build/` source, including the digest-pinned Kali
release image. The archive expands to `/opt/polaris/polaris/build`.

Key entrypoints:

- `main.tf`, `ranges.tf`, `shared.tf`, `variables.tf`, `versions.tf` — AWS
  range infrastructure.
- `user_data.sh.tpl` — bootstraps the range host from the Polaris build
  tarball and starts `polaris/build/docker-compose.yml`.
- `orchestrate_provisioning.py`, `provisioning_batch.py`,
  `provisioning_state.py` — range provisioning orchestration.
- `check_range_health.py`, `range_health.py` — fleet and range health checks.
- `reset.sh` — SSM-run reset script for a running Polaris range host.
- `polaris_ctf_setup.py`, `polaris_ctf_attach.py`,
  `polaris_ctf_cleanup.py` — CTF registration and lifecycle helpers.
- `../tests/aws_event_rehearsal.py` — creates an ephemeral participant key,
  provisions the standalone range, executes the complete path through A14's
  public key-authenticated SSH endpoint, resets, repeats start-state checks,
  destroys the range, and verifies empty Terraform state plus empty live
  service inventories in EC2, S3, and IAM.

Run the live proof from a clean pack tree:

```console
python3 polaris/tests/aws_event_rehearsal.py \
  --profile <aws-profile> --region us-east-2
```

The named profile uses the normal AWS credential chain; SSO is not required.
Event-fleet registration and CTFd scripts support specialized operations but
are not part of the standalone rehearsal lifecycle. Do not retain generated
Terraform state, operator credentials, range registration output, or live CTFd
tokens.
