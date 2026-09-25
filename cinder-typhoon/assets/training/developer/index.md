# Developer artifacts desk

- Forge repository: `http://developer.training:8081/cinder/delivery-formatter`
- Failed build record: `http://developer.training:8082/jobs/BLD-204/log`
- Registry: `http://developer.training:8083/`
- Consumer: `http://developer.training:8084/`
- [Current formatter contract](consumer-contract.md)
- [Unpacked sample package](sample-package/package.json)

The Forge repository is read-only. Registry publication is limited to the
formatter package. The consumer always resolves afresh when a report is run.

Registry access uses a bearer value. Read the channel with
`GET /api/channels/rehearsal/manifest`. Publish with
`PUT /api/packages/@cinder/delivery-formatter/{version}` and JSON containing
exactly `name`, matching `version`, and `files`; `files` contains UTF-8 strings
named `package.json` and `index.js`.

Run the consumer with `POST http://developer.training:8084/api/consumer/run`
and the empty JSON object `{}`. Retained receipts are available at
`GET /api/consumer/receipts`.
