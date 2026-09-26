# FieldKest report provider interface

The `report-consumer-v2` job loads a Python module named `provider.py` and calls:

```python
def render_report(fixture: dict) -> dict:
    ...
```

The returned object must use schema `fieldkest.report/v2`. The consumer rejects
changes to `asset_id`, `connector_revision`, `captured_at`, or `observations`.
It permits a provider to supply its own `assessment.rating` and
`assessment.summary`.

The job input archive contains `provider.py` and `fixture.json` at its root.

