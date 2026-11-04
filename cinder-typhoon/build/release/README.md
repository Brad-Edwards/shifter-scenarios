# Immutable release records

`manifest.py` generates and verifies the release record defined in
`docs/design/immutable-release-manifest.md`. Generation is intentionally
online and fail closed: the tracked release inputs must be clean, all three GCP
goldens must match those inputs and their participant-surface manifests, and
every configured Compose image must have a non-zero immutable image ID.

After committing the reviewed implementation and deploying that commit to all
three goldens:

```sh
python3 cinder-typhoon/build/release/manifest.py generate \
  --candidate-id event-YYYY.MM.DD-NN \
  --project prod-mgau4w \
  --zone us-central1-a
```

Commit the generated `build/participant-runner/candidate.json` and
`build/release/manifest.json` as the release records. Their `source_commit`
identifies the preceding clean implementation commit. Later acceptance reports
bind both file digests.

Verification on a golden is phase-specific:

```sh
python3 build/release/manifest.py verify --phase keplerops --images
```

The files contain no credential material. Do not add `.operator` state,
Terraform state, reports, private keys or generated bearer values.
