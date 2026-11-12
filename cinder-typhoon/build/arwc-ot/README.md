# ARWC OT compatibility slice

This directory implements issue #363. Status: setup and qualification in progress.
The [platform plan](../../docs/design/arwc-ot-platform-plan.md) defines the target.

Observed on 12 November 2026: the dedicated VM is running, IAP SSH works, and
Docker 29.9.3 is installed. Official OpenPLC and FUXA sources were fetched and
product image downloads started. Download completion and protocol compatibility
are not yet verified. GCP requested interactive reauthentication during the next
SSH connection. Resume from the same VM after renewing operator authentication.

The preparation log is `/tmp/arwc-ot-upstream.log` on that VM. Candidate versions
are OpenPLC Runtime v4.3.2, OpenPLC Editor v4.3.4, and FUXA v1.3.5. These version
choices are not a passed compatibility result.

## Test VM

Run all container builds, compilation, and compatibility checks on the dedicated
GCP VM. Do not build this slice on the local workstation or a golden host.

| Setting | Current value |
| --- | --- |
| Project | `prod-mgau4w` |
| VM | `cinder-arwc-ot-compat-363` |
| Zone | `us-central1-a` |
| VPC | `cinder-arwc-golden` |
| Subnet | `cinder-arwc-carrier` |
| Private address | `10.77.59.6` |
| Profile | `e2-standard-4`, 80 GB balanced disk |
| Access | IAP SSH, no public IP, OS Login |
| Cloud identity | No service account or OAuth scopes |
| Work directory | `/opt/arwc-ot-compat` |

The VM uses the existing NAT and IAP firewall rules. It has no route through
the golden host and requires no change to its running services. Stop the test
VM when active qualification ends. Keep its disk for continued development.

## Reproduce setup

Use the approved project explicitly. The create script verifies the golden VPC
and refuses an existing VM name through the Compute Engine API.

```sh
bash cinder-typhoon/build/arwc-ot/create-test-vm.sh prod-mgau4w
```

The startup script installs Docker and writes `/var/lib/arwc-ot-compat-ready`.
Transfer this directory through IAP after SSH becomes available. Run
`prepare-upstream.sh` on the VM with sudo. Its hostname check prevents local use.

The scripts fetch official public sources and product images. They do not
transfer GitHub or cloud credentials into the VM. Product version tags are
initial candidates; qualification must record immutable digests and exact
source revisions before publishing a completed compatibility result.

## Qualification boundaries

Exercise normal operation of only this slice. Do not point its clients or
controllers at golden containers or participant ranges. Keep its Compose
networks and state separate. A running container is setup evidence only;
product interoperability and participant workflows require their own results.
