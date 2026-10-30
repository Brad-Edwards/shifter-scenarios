# Training golden-range hand build

This directory is the progressive hand build of the Training segment. The SDL
and authored files remain the source of truth. Implementation discoveries are
first reconciled there and then encoded here.

The target layout is one private GCE carrier with an internal Docker bridge.
The bridge preserves the SDL's exact `10.77.40.0/24` endpoints and has no route
to KeplerOps, ARWC, the carrier VPC, or the public Internet. GCP exposes none of
the target listeners. Operator access to the carrier is through IAP SSH only.

Current build status:

- T01 Workbench: locally integrated and live-validated on the GCP carrier.
- T02 Accounts: locally integrated and live-validated on the GCP carrier.
- T03 Developer: locally integrated and live-validated on the GCP carrier.
- T04 State: locally integrated and live-validated on the GCP carrier.
- Participant Kali: exact addressing, opening surfaces, and lack of an outbound
  route validated locally and on the GCP carrier.
- GCP carrier: provisioned in `prod-hwmvjy` and accepted on 25 September 2026.

The carrier acceptance pass covered all 18 black-box tests, an internal-only
bridge, no published target ports, read-only container roots, dropped Linux
capabilities, runner network isolation, Docker-socket confinement to the trusted
runner, one-shot worker cleanup, and persistence across target-service restarts.
The tests are operator material and are not copied into the participant image;
the service-contract wrapper supplies them only to a one-shot, read-only test
container. Known-solution acceptance is separate: the operator runner streams
it into the existing unprivileged `cinder` workstation process, verifies that
process has no Docker control, host paths, private service state or test files,
and retains only credential-free structured evidence outside the workstation.
The four stateful live suites are intentionally a first-build acceptance pass:
they exercise single-redemption and append-only behavior and therefore require
fresh named volumes if they are to be repeated from their initial conditions.

The automated materialization gate and operator-authored known-solution
acceptance passed on the then-current mutable golden. The encoded sequence used
the published workstation and desk materials across all 16 Training cards,
including a fresh registry-to-consumer publication and the complete 200 L
practice transfer. That result establishes known-path executability, not blind
human discovery, understanding, difficulty, or duration. The current golden
must pass the participant-surface, immutable-candidate, and blind-playtest gates
before any event bake is accepted.

Provision or reconcile the private carrier with:

```sh
./gcp/deploy.sh prod-mgau4w
```

For author access after deployment:

```sh
gcloud compute ssh cinder-training-golden \
  --project PROJECT_ID --zone us-central1-a --tunnel-through-iap
sudo docker exec -it --user cinder cinder-training-kali bash -l
```

The second command crosses only the author/operator boundary. Participants see
the Kali workspace and its Training bridge, not the carrier shell or Docker
control plane.
