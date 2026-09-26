# FieldKest local helper

The helper renders an inspection summary from a supplied FieldKest sample:

```sh
curl --fail --form sample=@samples/FK-SAMPLE-017.json \
  http://127.0.0.1:8701/api/inspection-summary
```

Analysis bundles can be checked without executing their recovered script:

```sh
curl --fail --form bundle=@analysis/reconstructed-FKCOL-2841.json \
  http://127.0.0.1:8701/api/reconstruction
```

The reconstruction request is a JSON file with schema
`fieldkest.reconstruction/v1`, the collection ID, and exact base64 encodings in
fields `script_base64` and `instructions_base64`. The helper compares the
decoded bytes with the bundle's integrity markers; it never executes them.

Callback collection requests use JSON fields `endpoint_id`, `collection_id`
and `integrity` at `/api/callback/collection`.

