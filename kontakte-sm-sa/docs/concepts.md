# KONTAKTE

This pack describes the source workstation and a GCP range project's IAM and
Secret Manager state. Identifiers in the source are sanitizer aliases.

The cloud state contains 44 service accounts, 391 secrets with one enabled
version each, 562 IAM member bindings, and one audit configuration. Each secret
requires automatic replication. The project must record Secret Manager
`DATA_READ` audit logs.

The workstation stays as the author supplied it: Ubuntu 22.04, one CPU, 2 GiB
of RAM, SSH access, and the source LAN. Its credential file stays at
`/home/analyst/.config/foothold/credential.json`. The pack adds no workstation
software, attached cloud identity, or foothold account.

The client maps all 71 outside principal placeholders to existing identities.
The exercise author selects one of the 44 source accounts for foothold key
issuance. The adapter creates a key for that account after provisioning and
removes it on teardown.

See [client inputs](client-inputs.md) for the named file asset and prerequisites.
See [realization](realization.md) for the source mapping and readiness limits.
