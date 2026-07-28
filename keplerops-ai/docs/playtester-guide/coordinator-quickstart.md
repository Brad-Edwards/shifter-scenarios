# Coordinator quickstart

Use this guide from the repository root unless a command says otherwise.

## Source branch

Use merged `dev` for delivery and Shifter porting. The sanity pass recorded in
this folder is run against the shipped scenario pack.

## Stand up a range

From `keplerops-ai`:

```sh
build/launch.sh \
  --project-id prod-ksqdkj \
  --range-instance <range-instance> \
  --participant <participant-id> \
  --participant-source-cidr <operator-or-playtester-ip>/32 \
  --research-profile off
```

Use a unique range instance per standalone playtester copy unless the event
coordinator explicitly wants shared-state testing. Do not use `0.0.0.0/0`.

## Credential sanity

Before launching, confirm the active account and project:

```sh
gcloud auth list --filter=status:ACTIVE --format='value(account)'
gcloud config get-value project
gcloud projects describe prod-ksqdkj --format='value(lifecycleState)'
```

If Terraform reports a deleted project number that does not match
`prod-ksqdkj`, check whether `GOOGLE_APPLICATION_CREDENTIALS` is set in the
operator shell. A stale credential file can override the active gcloud session.
Unset it for the launch shell or refresh that credential before retrying.

## Check health

```sh
build/health-check.sh \
  --range-instance <range-instance> \
  --participant <participant-id>
```

## Get the participant endpoint

```sh
terraform -chdir=build/gcp output \
  -state="build/.operator/<range-instance>-<participant-id>/terraform.tfstate" \
  -raw participant_endpoint
```

## Run a focused participant smoke

For a retained range:

```sh
uv run --no-project \
  --with 'raes==2.0.0' \
  --with 'pyyaml>=6,<7' \
  --with 'playwright>=1.55,<2' \
  python tests/module_04_rehearsal.py \
  --project-id prod-ksqdkj \
  --range-instance <range-instance> \
  --participant <participant-id> \
  --participant-source-cidr <operator-or-playtester-ip>/32 \
  --use-existing-range \
  --retain-until-phase-e
```

Module 04 is a good sanity representative because it exercises participant
entry, gateway auth, model-facing behavior, receipt issuance, and proof
verification without requiring the longer workflow-chain prerequisites.
