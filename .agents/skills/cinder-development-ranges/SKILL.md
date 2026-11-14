---
name: cinder-development-ranges
description: Use when provisioning, accessing, inspecting, synchronizing, or resetting the isolated Cinder FieldLink and ARWC development VMs in GCP. Do not use this skill for golden or BigRAE participant ranges.
---

# Cinder development ranges

These development VMs protect the existing goldens while FieldLink and ARWC
are replatformed. Read
`cinder-typhoon/docs/design/development-ranges.md` before changing their cloud
layout or reset behavior.

## Confirm the project

Before the first `gcloud` or range-management command in a task, ask the user
for the GCP project ID. Do not infer it from earlier work. Then set it once:

```sh
export CINDER_GCP_PROJECT=<confirmed-project-id>
export CINDER_GCP_ZONE=us-central1-a
```

Verify that the active account is `bedwards@paloaltonetworks.com`. Never read a
credential file or print tokens, generated credentials, certificates, or
operator state.

## Use the guarded wrapper

Run commands from the repository root. The only target aliases are
`fieldlink` and `arwc`.

```sh
bash cinder-typhoon/build/development-ranges/manage.sh describe fieldlink "$CINDER_GCP_PROJECT"
bash cinder-typhoon/build/development-ranges/manage.sh describe arwc "$CINDER_GCP_PROJECT"

bash cinder-typhoon/build/development-ranges/manage.sh ssh fieldlink "$CINDER_GCP_PROJECT"
bash cinder-typhoon/build/development-ranges/manage.sh ssh arwc "$CINDER_GCP_PROJECT"
```

For one remote command, use `run` and pass one quoted command string. Use
`sudo` only for the remote operation that needs it.

Synchronize the target-specific source tree without applying Terraform,
building images, or restarting services:

```sh
bash cinder-typhoon/build/development-ranges/manage.sh sync fieldlink "$CINDER_GCP_PROJECT"
bash cinder-typhoon/build/development-ranges/manage.sh sync arwc "$CINDER_GCP_PROJECT"
```

The sync action updates only that target's build and development-tool paths. It
does not delete other source paths, and it excludes operator state and generated
credentials. Keep all source changes in the repository; do not edit a golden or
treat a VM-only edit as durable work.

## Provisioning

Preserve FieldLink once, then provision each development VM:

```sh
bash cinder-typhoon/build/development-ranges/manage.sh preserve fieldlink "$CINDER_GCP_PROJECT"
bash cinder-typhoon/build/development-ranges/manage.sh provision fieldlink "$CINDER_GCP_PROJECT"
bash cinder-typhoon/build/development-ranges/manage.sh provision arwc "$CINDER_GCP_PROJECT"
```

Provisioning is idempotent. It never replaces an existing instance or machine
image. The development VMs have no external IP and no service account.

## Reset

FieldLink has an in-place application reset:

```sh
bash cinder-typhoon/build/development-ranges/manage.sh reset fieldlink "$CINDER_GCP_PROJECT"
```

The current ARWC pristine reset recreates only its development VM from the
qualified OT machine image. It deletes all uncommitted state on that VM and
therefore requires the exact destination name:

```sh
bash cinder-typhoon/build/development-ranges/manage.sh reset arwc \
  "$CINDER_GCP_PROJECT" cinder-arwc-dev
```

Keep source changes in Git before this reset. Never substitute a golden name,
call the old golden deploy wrappers, or run ARWC image-preparation scripts on a
development VM.
