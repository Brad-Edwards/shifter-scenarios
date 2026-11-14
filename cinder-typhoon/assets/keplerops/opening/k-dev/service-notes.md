# FieldKest developer service notes

Internal services use the workstation CA. The saved Gitea credential is also
accepted by Jenkins and the FieldLink report service.

## Source

- Repository remote: `https://source.keplerops.test/fieldkest/fieldlink-connector.git`
- Source browser: `https://source.keplerops.test/`
- Handovers: `https://source.keplerops.test/fieldkest/fieldlink-connector/issues`
- Repository content: `GET https://source.keplerops.test/api/v1/repos/fieldkest/fieldlink-connector/contents/{path}?ref={revision}`
- SSH remote: `git@source.keplerops.test:fieldkest/fieldlink-connector.git`

Add your public SSH key to your Gitea account before using the SSH remote.
Compiler and archive operations have their own reference at
`https://source-tools.keplerops.test:8443/.well-known/fieldkest-client`.

## Builds

Jenkins is at `https://ci.keplerops.test/`. The connector report job is
`fieldlink-report`; its retained build number is 1842. Its build page includes
Console Output, Artifacts, Changes, and Workspace.

- Build record: `GET https://ci.keplerops.test/job/fieldlink-report/{build_number}/api/json`
- Build log: `GET https://ci.keplerops.test/job/fieldlink-report/{build_number}/consoleText`
- Build artifact: `GET https://ci.keplerops.test/job/fieldlink-report/{build_number}/artifact/reports/{filename}`

## FieldLink report review

The report service runs submitted providers in isolated workers and publishes
compatible results to support. It is separate from Jenkins build history.

- Client reference: `GET https://review.keplerops.test/.well-known/fieldkest-client`
- Review import: `POST https://review.keplerops.test/api/reviews/import`
- Submit an isolated report: `POST https://review.keplerops.test/api/jobs`
- Read its result: `GET https://review.keplerops.test/api/jobs/{job_id}`

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
is published to the current support handover. The consumer binds
`fixture.json` to the baseline by the SHA-256 digest of its exact file bytes;
copy the recovered file directly into the ZIP instead of re-serializing it.

## Support

- Conversation: `GET https://support.keplerops.test/api/conversations/{conversation_id}`
- Current handover: `GET https://support.keplerops.test/api/handovers/current`

The support service expects its ordinary browser session cookie.


## Document previews

Gotenberg is at `https://preview.keplerops.test/`. The native multipart route
`POST /forms/chromium/convert/html` accepts an `index.html` plus its CSS, images,
and other local assets in the `files` fields. It returns a PDF directly.
The review draft and stylesheet are in `work/previews/`.

The service also accepts URLs through `/forms/chromium/convert/url` and exposes
ordinary status at `/health` and version information at `/version`.
Use the workstation CA with ordinary HTTPS clients. Store the returned PDF with
its source files when handing a review to another engineer.
