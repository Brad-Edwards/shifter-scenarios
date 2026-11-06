---
name: cinder-golden-range-testing
description: Use when deploying to, resetting, inspecting, or testing the Cinder Typhoon Training, KeplerOps, or ARWC golden ranges in GCP.
---

# Cinder Typhoon golden-range testing

Use the repository's GCP wrappers instead of assembling long sequences of
remote commands. These goldens are development and QA targets. They are not
BigRAE participant ranges and do not prove 300-range capacity.

## Start with the target project

Before any `gcloud`, Terraform, deployment, reset, or live-test command, ask
the user for the GCP project ID. Do not infer it from prior work and do not
silently accept the scripts' current `prod-mgau4w` default.

After the user answers, set it for every wrapper in the task:

```sh
export CINDER_GCP_PROJECT=<user-provided-project-id>
```

The normal zone is `us-central1-a`; set `CINDER_GCP_ZONE` only when the user or
the target environment requires another zone. The normal instance names are:

- `cinder-training-golden`
- `cinder-keplerops-golden`
- `cinder-arwc-golden`

Verify the active GCP account and that these exact instances exist before a
mutating command. Never read a credential file or print tokens, generated
credentials, certificates, or private operator state.

## Choose the existing wrapper

Run commands from the repository root.

### Deploy current source to a golden

```sh
bash cinder-typhoon/build/training/gcp/deploy.sh "$CINDER_GCP_PROJECT"
bash cinder-typhoon/build/keplerops/gcp/deploy.sh "$CINDER_GCP_PROJECT"
bash cinder-typhoon/build/arwc/gcp/deploy.sh "$CINDER_GCP_PROJECT"
```

Use only the phase needed by the task. Each script applies that phase's
Terraform, replaces `/opt/cinder-typhoon` on its golden, builds the phase, and
starts its Compose stack. This is a deployment, not a harmless test command.
Do not deploy unrelated working-tree content. The scripts exclude operator
state, but the source archive is not limited to committed files.

Deploying KeplerOps or ARWC regenerates that phase's certificate authority.
Synchronize the two public peer certificates after either deployment and
before a cross-segment check or immutable candidate generation:

```sh
bash cinder-typhoon/build/kepler-arwc/deploy.sh "$CINDER_GCP_PROJECT"
```

This wrapper exchanges only the public certificate-authority certificates and
recreates the two connector services. Candidate generation rejects missing or
stale peer trust.

### Test a current KeplerOps-to-ARWC development change

```sh
bash cinder-typhoon/build/participant-runner/check-development-pair.sh \
  delivery-package <run-label>

bash cinder-typhoon/build/participant-runner/check-development-pair.sh \
  delivery-diagnostic <run-label>
```

This is the preferred issue-development path for either cross-segment route.
It transfers only the tracked paths in
`development-pair-sync-paths.txt`, builds KeplerOps, restores both goldens,
checks provenance and the KeplerOps participant surface, runs the selected
participant-boundary path, and verifies the earned ARWC transition. It is not
immutable release evidence.

### Run focused live checks

```sh
bash cinder-typhoon/build/participant-surface/check-golden.sh <phase>
bash cinder-typhoon/build/fourth-wall/check-golden.sh <phase>
bash cinder-typhoon/build/keplerops/check-service-contracts-gcp.sh <run-label>
```

`<phase>` is `training`, `keplerops`, or `arwc`. The service-contract wrapper
restores the KeplerOps and ARWC goldens before running the KeplerOps live
contract suites. Treat those restores as destructive to current test state.

### Verify an immutable candidate

Generate a candidate only after the intended source is committed and all
three goldens have that exact release deployed:

```sh
bash cinder-typhoon/build/participant-runner/generate-candidate.sh \
  --immutable --candidate-id <candidate-id>
```

Then use the candidate wrapper for a phase and operation:

```sh
bash cinder-typhoon/build/participant-runner/check-candidate.sh \
  PHASE OPERATION RESET_ID REMOTE_CANDIDATE \
  [EXPECTED_TRANSITION] [cross-segment]
```

Read `cinder-typhoon/build/participant-runner/README.md` for the required
operation, transition, and reset pairing. The wrapper verifies hints, card
coverage, provenance, fourth-wall cleanliness, participant surface, release
identity, live image identity, and the participant-boundary result. Do not use
development-mode output as candidate evidence.

### Check three independent range pairs

```sh
bash cinder-typhoon/build/keplerops/check-three-range-isolation-gcp.sh \
  <short-run-label>
```

This is not a routine golden test. It creates two machine images, six temporary
VMs, and three firewall rules, then runs cross-range replay and isolation
checks. It deletes those resources on exit unless
`CINDER_KEEP_TEST_RANGES=1`. Obtain the user's explicit approval before running
it because it creates billable resources. Do not set the keep flag unless the
user asks.

## Preserve useful evidence

- Use a short unique run label so remote logs and reports can be identified.
- Let the wrapper perform its reset; do not add a second reset unless the test
  needs a distinct pristine state.
- Reports and logs under `.operator` and `/var/tmp` are operator-only. Keep
  them out of Git unless a documented release step creates a credential-free
  report intended for the repository.
- If a wrapper fails, use its reported stage and inspect the matching remote
  log before retrying. Do not repeat the same failing cloud command without
  understanding the failure.
- Record any newly found product defect in a GitHub issue. A PR note alone is
  not sufficient.

The `test-local.sh` scripts run destructive local Docker tests. They are useful
for local development but are not substitutes for the GCP wrappers above when
the task calls for golden-range evidence.
