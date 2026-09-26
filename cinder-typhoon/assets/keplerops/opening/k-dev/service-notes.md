# FieldKest developer service notes

All three services use the workstation CA. The saved Gitea credential is also
accepted by the developer CI routes.

## Source

- Repository remote: `https://source.keplerops.test/fieldkest/fieldlink-connector.git`
- Current handover: `GET https://source.keplerops.test/api/fieldkest/handovers/current`
- Repository content: `GET https://source.keplerops.test/api/v1/repos/fieldkest/fieldlink-connector/contents/{path}?ref={revision}`

## CI

- Run record: `GET https://ci.keplerops.test/api/runs/{run_id}`
- Run log: `GET https://ci.keplerops.test/api/runs/{run_id}/log`
- Review import: `POST https://ci.keplerops.test/api/reviews/import`
- Submit an isolated job: `POST https://ci.keplerops.test/api/jobs`
- Read a job result: `GET https://ci.keplerops.test/api/jobs/{job_id}`

The review importer accepts `fieldkest.review-import/v1` JSON with `run_id` and
an `object` beneath `inputs/`.

The `report-consumer-v2` job accepts JSON shaped as:

```json
{
  "template": "report-consumer-v2",
  "input": {
    "archive_base64": "BASE64_OF_ZIP"
  }
}
```

The ZIP layout and report-provider interface are in the repository's
`docs/report-provider.md` and the corresponding review note. Successful output
is published to the current support handover.

## Support

- Conversation: `GET https://support.keplerops.test/api/conversations/{conversation_id}`
- Current handover: `GET https://support.keplerops.test/api/handovers/current`

The support service expects its ordinary browser session cookie.

