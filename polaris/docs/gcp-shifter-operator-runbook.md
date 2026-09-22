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
python runtime-pack/build.py --output /tmp/private-runtime-pack/polaris-0.2.1.tar
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

1. a Linux GCE machine image containing the compose host and participant
   workstation built from `polaris/build/build-v1.tar.gz`; and
2. a Windows Server 2022 image containing the pre-promoted `boreas.local`
   directory controller.

Publish both in the tenant's GCP project. Cold-boot each artifact before
installing it: the Linux host must accept the management SSH connection on port
2222 as `hostadmin`, and the directory image must accept the management SSH
connection on port 22 as `Administrator`. Record their full project-qualified
references. The Linux binding uses image kind `machine-image`; the directory
binding uses its normal Compute Engine image reference.

Before capturing the Linux machine image, stop the bake VM and detach its
build-time service account (`gcloud compute instances set-service-account`
with `--no-service-account`). Confirm the stopped VM reports no attached
service account, then create the machine image. Compute Engine machine images
otherwise preserve the bake identity, and a range launch will either require an
unsafe `iam.serviceAccounts.actAs` grant on that build identity or fail. Never
grant that impersonation permission to the range provisioner.

The Linux build must preserve the participant readiness contract from
`polaris/build/a14/participant-readiness.json`. Calculate and record the SHA-256
of the installed readiness document; that value is the adapter binding's
readiness digest. The participant workstation must contain the pinned Claude
Code client described in the adapter README.

Do not grant model-invocation credentials to the participant-controlled range
host. The adapter receives a Shifter model grant and configures the participant
client through the broker boundary.

The GCP range plane must use broker-only egress. Set the tenant deployment's
`GCP_RANGE_PRIVATE_GOOGLE_ACCESS` variable to `false` and deploy that
configuration before launching the event. Private Google Access is a separate
direct-Google-API lane and is intentionally incompatible with source-preserving,
identity-less broker clients. General participant internet egress remains
disabled.

## Install and bind in Shifter

Open **Administer → Adapters**.

1. Upload the adapter manifest, expand the private-registry section, enter the
   read-only registry credential, review the installation, and install it.
2. Wait for the adapter state to become **ready**. For this adapter, readiness
   includes a bounded Claude Code request from the participant container through
   the broker, so allow at least two minutes and treat a readiness failure as a
   participant model-path failure rather than proceeding to event launch.
3. Open **Install packs and assign adapters**. For a first installation, upload
   the rebuilt tar as pack name `polaris`, review it, and install it. If
   `polaris` is already installed, use **Update polaris** and upload the new
   revision there; **Install new pack** is only for a new pack identity.
4. Choose **Configure polaris** and select the ready adapter.
5. Bind `host` to `provision.node.a14-kali` with:
   - image enabled;
   - kind `machine-image`;
   - the full Linux machine-image reference;
   - machine type `e2-standard-8`;
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
prompt. Require a successful response from the configured broker-backed model
and verify that the returned usage reports a nonzero output-token count. Client
startup alone is not model-access proof.

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
