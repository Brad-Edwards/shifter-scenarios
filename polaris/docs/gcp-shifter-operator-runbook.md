# GCP Shifter operator runbook

This is the supported operator path for installing Polaris in a GCP Shifter
tenant, creating a one-participant CTF event, validating the participant
surface, and cleaning up the temporary event resources. Perform tenant changes
through the Shifter administration and CTF interfaces. Do not modify deployed
portal files, databases, workloads, or range resources by hand.

## Inputs and access

The operator needs:

- an active Shifter tenant organization-administrator account with the CTF
  Organizer role;
- permission to install tenant adapters and environment packs;
- read access to the internal GHCR worker image;
- GCP permission to publish the two tenant-owned guest image artifacts;
- a tenant workload-identity principal that can invoke the approved Vertex AI
  models; and
- the current checkout of this repository.

Use separate operator and participant identities. Store operator recovery
material in the tenant's approved secret store and never place it in this
repository, an adapter manifest, a pack archive, a CTF description, or an
acceptance report.

Record the immutable artifact references used for a qualification run. Do not
reuse a deleted image name, an image tag, or a previously downloaded pack
archive merely because its filename looks current.

## Build and verify the environment pack

From the repository root, build the upload archive from the authoritative
`runtime-pack/polaris/` source:

```sh
python -m pip install -r runtime-pack/requirements.txt
python runtime-pack/build.py --output /tmp/private-runtime-pack/polaris-0.2.2.tar
python -m pytest runtime-pack/tests -q
```

Retain the canonical digest printed by the builder with the run evidence. The
archive is deterministic and must be rebuilt when its source changes.

## Prepare the adapter

The tenant installs an immutable worker image plus an upload manifest. Build the
worker as described in [`../../runtime-adapter/README.md`](../../runtime-adapter/README.md),
publish it to the approved internal registry, and verify that the manifest's
`worker_image` contains the registry-returned `@sha256:` digest. The manifest
must declare:

- protocol `shifter.runtime-plugin/v1`;
- entry point `polaris`;
- bindings `host` and `directory`;
- parameters `main-model`, `small-model`, and `max-output-tokens`; and
- model binding `participant` on `host`.

Give the tenant a read-only registry credential. A publishing credential does
not belong in Shifter.

## Publish the GCP guest images

Polaris needs two tenant-owned artifacts:

1. a Linux GCE custom boot image containing the compose host and participant
   workstation built from `polaris/build/build-v1.tar.gz`; and
2. a Windows Server 2022 image containing the pre-promoted `boreas.local`
   directory controller.

Publish both in the tenant's GCP project. Cold-boot each artifact before
installing it: the Linux host must accept the management SSH connection on port
2222 as `hostadmin`, and the directory image must accept the management SSH
connection on port 22 as `Administrator`. Record their full project-qualified
references. The Linux binding uses image kind `image` with bootstrap capability
`preconfigured-machine-host`; the directory uses its normal Compute Engine
image reference.

On a tenant project that blocks external IPs (the `compute.vmExternalIpAccess`
organization policy), the shared `dc-prebaked` bake cannot capture the DC image
over IAP and fails at `finalize` with exit `16001`, even though the DC finishes
promoting and seeding. Follow
[Baking the Polaris DC on GCP: manual capture for IAP-only projects](gcp-dc-bake-manual-capture.md)
to keep the build VM, confirm the DC, and capture the image by hand.

Before capturing the Linux boot image, stop the bake VM and detach its
build-time service account (`gcloud compute instances set-service-account`
with `--no-service-account`). Confirm the stopped VM reports no attached
service account. Publish an exact, project-qualified custom image from the
stopped host's **boot disk** and verify it is `READY`. The complete host runtime
must live on that one boot disk; custom images do not capture secondary disks.
Set the binding's boot disk size to at least the image's disk size (currently
220 GiB). Do not bind an image family or a bare name. The range VM gets its
identity from Shifter's administrator-owned range-host selection, not the bake
VM. Never grant the range provisioner impersonation permission on the build
identity.

This source choice matters for events: [Google limits a single machine image](https://cloud.google.com/compute/docs/machine-images/create-instance-from-machine-image) to
six VM creations in a rolling 60 minutes, while [custom-image API/CLI creates](https://cloud.google.com/compute/docs/instances/create-vm-from-custom-image)
support a much higher documented rate. A machine image remains appropriate
only if the host needs captured secondary disks and the launch volume fits
that limit. Capacity, CPU, disk, address, and project quotas still need to
cover participants plus warm spares before bulk launch. A ready image alone
does not prove fleet capacity.

The Linux build must preserve the participant readiness contract from
`polaris/build/a14/participant-readiness.json`. Calculate and record the SHA-256
of the installed readiness document; that value is the adapter binding's
readiness digest. The participant workstation must contain the pinned Claude
Code client described in the adapter README.

Bake the Linux host from the current `polaris/build/build-v1.tar.gz` and publish
its stopped boot disk as the custom image.
Do not bind a newly installed adapter to an image baked from an older archive:
the adapter and host image form one reviewed compatibility set, including the
participant DNS forwarding configuration used for broker access.

When refreshing a bake VM, extract the current archive, compare its `build/`
tree with the installed source, and rebuild every changed Compose service. In
particular, the GCP DNS image must contain the current `dns/entrypoint.sh` and
`dns/named.conf`; restarting an older DNS image does not apply those changes.
The preconfigured bake host needs a placeholder `DC01_IP` so DNS stays running
before any range exists, plus the GCP resolver as its forwarder. Use a
`gcp-preconfigured-host.override.yml` with a `dns.environment` section such as:

```yaml
services:
  dns:
    environment:
      DC01_IP: "10.201.0.11" # Bake-only placeholder; no directory is required.
      DNS_FORWARDER: "169.254.169.254"
```

Build and start DNS with both Compose files, then verify that the participant
container resolves a public hostname through it. Also query the tenant's
private `.internal` model-broker name against the scenario DNS service and
confirm it resolves to the expected private broker address. BIND must exempt
`.internal` from public DNSSEC validation; forwarding alone does not qualify
private-zone resolution. The adapter's range bootstrap replaces the bake-only
directory address with that range's actual controller address. Remove bake-time
SSH keys, access tags, startup scripts, and temporary payloads before capture;
the bake VM must have no attached service account at capture time.

Do not grant model-invocation credentials to the participant-controlled range
host. The adapter receives a Shifter model grant and configures the participant
client through the broker boundary.

For the broker-backed `polaris` adapter described by the steps below, set the
tenant deployment's `GCP_RANGE_PRIVATE_GOOGLE_ACCESS` variable to `false` and
deploy that configuration before launching the event. The separate
`polaris_direct` adapter described in
[`runtime-adapter/README.md`](../../runtime-adapter/README.md) instead requires
Private Google Access, a narrowly scoped range-host service account, and an
unset broker guest VIP. Do not bind that direct adapter to the broker pack or
assume the broker settings qualify its model access. Test a real `claude -p`
call from the participant's interactive workstation and require nonzero output
tokens. Participant web research also needs explicit egress; the model path
alone does not provide general internet access.

For a bulk GCP event using the direct variant, select an event workspace with
`status-quo` egress before importing participants or provisioning managed
spares. In a Shifter build with event-policy pinning and shared range-VPC NAT,
that workspace policy is the source for both participant and spare launches;
the provisioner enrolls their subnets in an explicitly scoped regional NAT
instead of creating one router per range. Confirm the tenant build has those
capabilities before depending on this path for a multi-range event. A workspace
set to `none` intentionally creates no outbound NAT path, even if the pack's
host profile opts in to public web access. Private Google Access alone does
not supply public web research. Qualify both a real Claude Code response and
public DNS/HTTP(S) from a fresh participant workstation before bulk launch.

## Install and bind in Shifter

Open **Administer → Adapters**.

1. Upload the adapter manifest, expand the private-registry section, enter the
   read-only registry credential, review the installation, and install it.
2. Wait for the adapter installation state to become **ready**. This proves
   registry access and isolated worker compatibility, not guest setup or model
   access. The range provisioner's guest verification makes a bounded Claude
   Code request, and participant acceptance repeats it with usage evidence.
3. Open **Install packs and assign adapters**. For a first installation, upload
   the rebuilt tar as pack name `polaris`, review it, and install it. If
   `polaris` is already installed, use **Update polaris** and upload the new
   revision there; **Install new pack** is only for a new pack identity.
4. Choose **Configure polaris** and select the ready adapter.
5. Bind `host` to `provision.node.a14-kali` with:
   - image enabled;
   - kind `image` and bootstrap capability `preconfigured-machine-host`;
   - the full Linux custom-image reference;
   - machine type `e2-standard-8`;
   - a boot disk at least as large as the published custom image;
   - management user `hostadmin` and port `2222`;
   - participant container `a14-kali` and user `kali`; and
   - the readiness-document SHA-256.
6. Bind `directory` to `provision.node.dc01` with:
   - image enabled;
   - the full Windows image reference;
   - machine type `e2-standard-4`;
   - management user `Administrator` and port `22`;
   - a 100 GiB `pd-balanced` disk;
   - bootstrap capability `prepromoted-domain-controller`; and
   - DNS domain `boreas.local` and NetBIOS domain `BOREAS`.
7. Set `main-model` to `coding-main`, `small-model` to `coding-small`, and
   `max-output-tokens` to `8192`.
8. Review and save the assignment.

The pack installation is tenant content administration; it does not require a
Shifter application deployment. Application deployments remain the path for
core platform changes.

## Configure model sources

In **Administer → Model Sources**, create enabled tenant sources for the logical
aliases required by the pack. For the current GCP profile:

| Alias | Vertex model | Region |
| --- | --- | --- |
| `coding-main` | `publishers/anthropic/models/claude-sonnet-4-6` | `us-east5` |
| `coding-small` | `publishers/anthropic/models/claude-haiku-4-5` | `us-east5` |

Use workload identity, the tenant GCP project, and the dedicated
model-invocation service account. Configure current quota, context-window, and
price data from the approved deployment catalog, set an explicit price-validity
date, and permit the event organization to use the sources. Do not store a
provider API key in the pack or range.

Model-source configuration does not enable a publisher model in Google Cloud.
In the same tenant project, enable each exact Anthropic model in Vertex AI Model
Garden and accept the current Marketplace terms using the approved procurement
operator. Confirm that the Vertex AI API is enabled and that the dedicated
invocation service account has only the deployment-managed predict permission.
Do this before creating the event; a Vertex `404 NOT_FOUND` that says the model
was not found or the project lacks access means Model Garden enablement is still
missing, even when the model name and region are valid.

Run one bounded prompt against each configured publisher model through the
approved invocation identity or deployment probe. Require an HTTP success and a
nonzero output-token count. Listing custom Vertex models is not a valid check:
managed publisher models do not appear in that inventory.

Before event activation, confirm that the event workspace can see both sources
and that each alias is bound to the intended source revision.

## Create and launch the CTF

Open **Operate → CTF Events** and create an event using the Polaris scenario.
Set a bounded active window, participant limit, and a spin-up allowance of at
least 45 minutes. Select the approved source for each logical model alias.

Before opening registration, render the private challenge document and import
it from the event's **Challenges → Import pack** control:

```sh
python3 polaris/ctfd/export_shifter_challenge_pack.py \
  --output /tmp/polaris-shifter-challenges.json
```

The generated file contains answer material. Keep it owner-readable, do not
attach it to tickets or reports, and delete it after import. Require exactly 38
created challenges and no per-entry errors before continuing. The importer is
the supported tenant content-administration path; do not write challenge rows
directly to the tenant database.

Open registration, invite a dedicated QA participant, and issue that identity a
temporary password through the participant-management page. Activate the event,
sign in through the participant login surface, and complete the required
password change. Back in the operator participant page, choose **Provision**.

For a multi-participant event, assign readable login handles through the
organizer participant-management control after import. The current isolated CTF
account policy requires a `range-` prefix, so a codename such as
`GraphiteRaven` uses `range-graphiteraven` to sign in; the scoreboard displays
the participant name separately. Bulk provisioning is paced across the event's
spin-up allowance: the scheduler spaces requests by the allowance divided by
the roster size, clamped to 5–120 seconds. For 20 participants with a 45-minute
allowance, the inter-request waits alone can take about 38 minutes; guest
readiness adds time. Start provisioning before participants arrive and watch
the organizer's READY count rather than treating the allowance as a completion
deadline. Request the desired warm-spare count through the organizer
spare-pool control, then verify every participant range and spare reaches
**ready**; running VMs and accepted provision requests are not readiness.

Wait until the participant range reports **ready** and exposes the declared
attack-workstation access target. A compatibility result, prepared allocation,
or running cloud VM is not a readiness verdict.

## Participant acceptance

Perform the complete manual walkthrough from the participant session on the
`a14-kali` attack workstation. The authoritative sequence is:

- [`walkthroughs/00-range-access-docker.md`](walkthroughs/00-range-access-docker.md)
- [`walkthroughs/flags-01-06-osint.md`](walkthroughs/flags-01-06-osint.md)
- [`walkthroughs/flags-07-19-front-office.md`](walkthroughs/flags-07-19-front-office.md)
- [`walkthroughs/flags-20-30-lab.md`](walkthroughs/flags-20-30-lab.md)
- [`walkthroughs/flags-31-36-bunker.md`](walkthroughs/flags-31-36-bunker.md)

Recover and submit all 38 challenge answers through the participant CTF UI.
Exercise the documented negative gates as well as the positive route: direct
lab access before the analyst pivot must fail, direct SCADA access before the
operations pivot must fail, bunker access before the splice opens must fail,
and the intended post-splice path must succeed.

Also run Claude Code from the participant workstation with a small deterministic
prompt. Require a successful response from the configured direct-Vertex or
broker-backed model path and verify that the returned usage reports a nonzero
output-token count. Client startup alone is not model-access proof.

Record only sanitized verdicts, counts, immutable artifact identifiers, and
timestamps. Never copy flags, passwords, model capabilities, session tokens, or
provider credentials into the report.

## Teardown and reconciliation

From the participant's operator page, request range destruction and wait for the
range to report **destroyed**. Then end the CTF event.

Confirm that no event-owned instances, disks, addresses, or firewall resources
remain in GCP. Remove any temporary bake VM after its image has passed
qualification. Keep the installed pack, ready adapter, qualified guest images,
and intentionally configured model sources because they are tenant deliverables.
Disable mistaken or superseded model-source records through the model-source
administration API; do not edit the database. Finally, remove local temporary
participant credentials and browser state with a secure deletion mechanism and
verify that the tenant secret store contains no temporary or orphaned secrets.
