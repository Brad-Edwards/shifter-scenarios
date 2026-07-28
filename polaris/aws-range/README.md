# Polaris AWS Range Tooling

This directory restores the historical Polaris AWS operator tooling under the
scenario folder. It used to live at `scripts/polaris-aws-range/`; keeping it
here makes the Polaris pack self-contained.

Key entrypoints:

- `main.tf`, `ranges.tf`, `shared.tf`, `variables.tf`, `versions.tf` — AWS
  range infrastructure.
- `user_data.sh.tpl` — bootstraps the range host from the Polaris build
  tarball and starts `scenarios/polaris/build/docker-compose.yml`.
- `orchestrate_provisioning.py`, `provisioning_batch.py`,
  `provisioning_state.py` — range provisioning orchestration.
- `check_range_health.py`, `range_health.py` — fleet and range health checks.
- `reset.sh` — SSM-run reset script for a running Polaris range host.
- `polaris_ctf_setup.py`, `polaris_ctf_attach.py`,
  `polaris_ctf_cleanup.py` — CTF registration and lifecycle helpers.

The scripts still assume operator AWS credentials come from the host or AWS
credential chain. Do not commit generated Terraform state, operator credentials,
range registration output, or live CTFd tokens.
