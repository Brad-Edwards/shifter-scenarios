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
the local test wrapper supplies them only to a one-shot, read-only test container.
The four stateful live suites are intentionally a first-build acceptance pass:
they exercise single-redemption and append-only behavior and therefore require
fresh named volumes if they are to be repeated from their initial conditions.

The automated materialization gate and an initial participant-side play pass
have passed. The play pass followed only the published workstation and desk
materials through all 16 Training cards, including a fresh registry-to-consumer
publication and the complete 200 L practice transfer. This hand build is the
current Training golden range; further observed playtest issues must still be
reconciled to the SDL and this implementation before any bake is taken.

Provision or reconcile the private carrier with:

```sh
./gcp/deploy.sh prod-hwmvjy
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
