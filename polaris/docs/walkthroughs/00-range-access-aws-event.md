# AWS event participant access

The `aws_event` profile is the same compact layout used for Polaris events.
The pack provisions one isolated VPC/subnet containing the compose range host
and a real Windows BOREAS domain controller.

It is an event-runtime proof surface, not a doctrine-complete golden binding.

1. Receive the range-scoped A14 SSH or RDP connection from the event operator.
2. Connect to A14 as the unprivileged `kali` user; the walkthrough commands
   start there.
3. Read the A14 welcome material and continue with
   `flags-01-06-osint.md`.

AWS console, SSM, Terraform output, host Docker access, and generated
credentials are operator-only. They are not participant entry or proof paths.
