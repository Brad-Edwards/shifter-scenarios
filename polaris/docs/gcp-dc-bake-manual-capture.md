# Baking the Polaris DC on GCP: manual capture for IAP-only projects

Part of the Polaris GCP operator docs; see the
[GCP Shifter operator runbook](gcp-shifter-operator-runbook.md).

The pre-promoted `boreas.local` DC image is baked from the shared Shifter GCP
Packer template `googlecompute.dc-prebaked` with the `polaris` profile
(`shifter/packer/gcp` in `PaloAltoNetworks/shifter`). On a project whose build
network allows external IPs, the standard build captures the image directly and
no manual step is needed. On a project whose build network forbids external IPs
(the `compute.vmExternalIpAccess` organization policy, so the bake must run over
IAP with `use_internal_ip=true`), the packer capture step fails and you finish
the image by hand. This runbook covers that manual capture.

## Why the standard bake fails over IAP

The `dc-prebaked` `finalize.ps1` provisioner runs elevated as `Administrator`
after the promotion reboot, and inside it the content seed `a2_setup.ps1` resets
the domain `Administrator` password to the baked value. Over a direct
external-IP WinRM connection packer tolerates this. Over an IAP tunnel packer
cannot re-authenticate to poll its own elevated scheduled task once the password
changes, so the build ends with:

```
Build 'googlecompute.dc-prebaked' errored ...: Script exited with non-zero exit status: 16001
```

This is a capture-time failure, not a content failure. The finalize scheduled
task keeps its original logon token and runs to completion on the VM: it seeds
the AD content, stages the UEFI fallback bootloader, and strips the build
secrets. Only packer's image capture is skipped. The fix is to keep the build
VM, confirm the DC finished, and capture the image by hand.

## Step by step

### 1. Bake so packer keeps the VM on failure

Add `-on-error=abort` so packer leaves the promoted build VM in place when the
capture step fails (`winrm_bootstrap_password` and `dc_dsrm_password` are
supplied as `PKR_VAR_*`, generated per build):

```bash
cd shifter/packer/gcp
packer init .
packer build -on-error=abort -only=googlecompute.dc-prebaked \
  -var-file=dc-profiles/polaris.pkrvars.hcl \
  -var="project_id=<project>" -var="zone=<zone>" \
  -var="network=<image-build-network>" -var="subnetwork=<image-build-subnet>" \
  -var="service_account_email=<build-sa>" \
  -var="image_prefix=shifter" -var="source_revision=<40-char-git-sha>" \
  -var="machine_type=e2-standard-4" -var="use_internal_ip=true" .
```

The build reaches the promotion, reboots, then fails at `finalize` with `16001`.
Record the retained instance name (`packer-...`).

### 2. Confirm the DC finished (the empty transcript is expected)

`finalize` deletes its own transcript as its last step, so an empty
`C:\dc-prebaked-finalize.log` means it completed, not that it did nothing. Read
the real state instead. A non-interactive way is a startup script that prints the
state to the serial console:

```bash
cat > /tmp/dc-state.ps1 <<'PS1'
$ErrorActionPreference='SilentlyContinue'
Write-Output "=====DCSTATE_START====="
Write-Output "a2_setup_present: $(Test-Path C:\polaris\a2_setup.ps1)"
Import-Module ActiveDirectory
try { $d = Get-ADDomain -ErrorAction Stop; Write-Output "domain: $($d.DNSRoot)/$($d.NetBIOSName)" } catch { Write-Output "domain: ERROR" }
Write-Output "aduser_count: $((Get-ADUser -Filter * | Measure-Object).Count)"
mountvol S: /S; Start-Sleep 2
Write-Output "esp_fallback_bootx64: $(Test-Path S:\EFI\Boot\bootx64.efi)"
mountvol S: /D
Write-Output "=====DCSTATE_END====="
PS1
gcloud compute instances add-metadata <vm> --zone <zone> \
  --metadata-from-file=windows-startup-script-ps1=/tmp/dc-state.ps1
gcloud compute instances reset <vm> --zone <zone>
# after the VM boots (about 3 minutes):
gcloud compute instances get-serial-port-output <vm> --zone <zone> --port 1 \
  | awk '/DCSTATE_START/{f=1} f{print} /DCSTATE_END/{f=0}'
```

A finished Polaris DC reports `domain: boreas.local/BOREAS`, a non-zero
`aduser_count` (around 18), `a2_setup_present: False` (the seed was cleaned up),
and `esp_fallback_bootx64: True`. If the AD content is missing, finalize did not
run its seed; debug the bake rather than capturing.

### 3. Capture the image from the boot disk

Remove the bake startup script, stop the VM, and create the custom image into the
`shifter-polaris-dc` family:

```bash
gcloud compute instances remove-metadata <vm> --zone <zone> --keys=windows-startup-script-ps1
gcloud compute instances stop <vm> --zone <zone>
gcloud compute images create shifter-polaris-dc-$(date +%s) \
  --source-disk=<vm> --source-disk-zone=<zone> \
  --family=shifter-polaris-dc \
  --guest-os-features=UEFI_COMPATIBLE,WINDOWS \
  --labels="project=shifter,image-type=polaris-dc,source-revision=<git-sha>" \
  --project=<project>
```

The baked domain `Administrator` password is the content-seed default; the live
credential is rotated per range at runtime by `plans/dc_setup.py`
(`DC_DOMAIN_PASSWORD`), so the baked value never reaches a participant.

### 4. Publish to GHCR (optional, for cross-tenant reuse)

Export the custom image to a GCS disk tarball and push it as an
`application/vnd.shifter.gce-image.v1` artifact, the same contract the base
images use. On an IAP-only project the export must pin the build subnet and the
build service account, and it needs `--quiet` because it grants the Cloud Build
service account storage access non-interactively:

```bash
gcloud compute images export --quiet \
  --image=shifter-polaris-dc-<ts> \
  --destination-uri=gs://<staging-bucket>/polaris-dc-<ts>.tar.gz \
  --project=<project> --zone=<zone> --subnet=<image-build-subnet> \
  --cloudbuild-service-account=<build-sa> --compute-service-account=<build-sa> \
  --log-location=gs://<staging-bucket>/export-logs

gcloud storage cp gs://<staging-bucket>/polaris-dc-<ts>.tar.gz ./polaris-dc.tar.gz
printf '%s' "$GHCR_TOKEN" | oras login ghcr.io -u <user> --password-stdin
oras push --disable-path-validation \
  --artifact-type application/vnd.shifter.gce-image.v1 \
  --annotation org.opencontainers.image.source=https://github.com/PaloAltoNetworks/shifter \
  --annotation org.opencontainers.image.revision=<git-sha> \
  --annotation com.shifter.image.role=polaris-dc \
  ghcr.io/paloaltonetworks/shifter/polaris-dc:gce-<ts> \
  ./polaris-dc.tar.gz:application/vnd.shifter.gce-image.tar.gz
```

`--disable-path-validation` is required because the tarball is referenced by an
absolute path. Keep the polaris packages private (internal), unlike the public
base images.

### 5. Clean up

Delete the retained build VM and its boot disk, and remove the export tarball
from the staging bucket. Record the immutable image reference and digest with the
run evidence.

## Alternative: bake over external IP

If the project allows external IPs (no `compute.vmExternalIpAccess` denial), run
the standard bake with `use_internal_ip=false`; packer then captures the image
directly and no manual step is needed. This matches the `packer-gcp.yml` default.
The manual capture above is only for projects where external IPs are blocked and
the bake must use IAP.
