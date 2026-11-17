# FieldKest local helper

The helper renders an inspection summary from a supplied FieldKest sample:

```sh
curl --fail --form sample=@samples/FK-SAMPLE-017.json \
  http://127.0.0.1:8701/api/inspection-summary
```

The ordinary object-storage profile and certificate trust are documented in
`work/platform-access.md`. Retained collections are not listable;
an exact bucket, key, and digest must come from the retained operating material.

