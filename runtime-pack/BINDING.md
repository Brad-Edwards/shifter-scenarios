# Binding the polaris-direct pack

Use these values when you install the adapter and pack from this branch. They
are the only supported combination. The machine-readable copy is
[`polaris-direct.binding.json`](polaris-direct.binding.json); replace
`<tenant-project>` with the tenant's GCP project.

| Item | Value |
| --- | --- |
| Pack | `polaris-direct` 0.3.0, built from [`polaris-direct/`](polaris-direct/) |
| Adapter | `panw.polaris-direct` 0.2.0, `ghcr.io/paloaltonetworks/shifter-scenarios/runtime-adapter@sha256:dcd596312c4543fa2f3194afcf9568f699fcab781039250ab018881e569c6f95` |
| Host image | `shifter-polaris-vm-v20261005` |
| Host readiness digest | `b3358834f9943353e02981aeee96a88976db7959f10b3494da41143879203199` |
| Directory image | `shifter-polaris-dc-1790561475` |
| Shifter prerequisite | Feature-artifact acquisition on GKE (Brad-Edwards/shifter#2510) deployed on the tenant |

Claude Code is not in the host image. The pack declares it, Shifter acquires it
and delivers it to the host's `/opt/shifter/bin` at range realization, and the
`a14-kali` container mounts that directory. A tenant without the Shifter
prerequisite cannot deliver it, and the adapter's model check fails.

## Images that are not for this pack

Do not bind these with this pack or adapter:

| Image | Why |
| --- | --- |
| `shifter-polaris-vm-1790559014` | Legacy. Claude Code baked in; pairs with the retired 0.2.x pack and adapter 0.1.22. Kept only for an existing event. Its readiness digest (`b63847b7…`) does not match this pack. |
| `shifter-polaris-vm-1791253499` | Legacy. The bake output that `shifter-polaris-vm-1790559014` was restored from. |

## Host and directory targets

| Field | Host (`provision.node.a14-kali`) | Directory (`provision.node.dc01`) |
| --- | --- | --- |
| Machine type | `e2-standard-8` | `e2-standard-4` |
| Disk | 220 GB `pd-balanced` | 100 GB `pd-balanced` |
| Bootstrap capability | `preconfigured-machine-host` | `prepromoted-domain-controller` |
| Management login | `hostadmin`, port 2222 | `Administrator`, port 22 |
| Participant | container `a14-kali`, user `kali` | none |
| Readiness | `participant-readiness/v1`, digest above | none |
| Domain | none | `boreas.local` / `BOREAS` |

Parameters: `project` is the tenant's GCP project, `region` is `us-east5`,
`main-model` is `claude-sonnet-4-6`, and `small-model` is `claude-haiku-4-5`.

## When a new host image is baked

Update the host image and readiness digest here and in the JSON in the same
change that changes `polaris/build/build-v1.tar.gz`. The readiness digest is the
SHA-256 of `polaris/build/a14/participant-readiness.json`.
