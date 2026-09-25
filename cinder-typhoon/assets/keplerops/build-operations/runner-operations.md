# FieldKest runner service connections

Noor Aveling · Build Operations · revision 4 · 14 September 2026

The review worker has service access as `svc-fieldlink-ci`. This is not the
identity of the person submitting a review. Commands run inside the job's
restricted environment, with a private `/workspace` retained between runs.

For a build-record connection check, keep the retained `support_input` from the
previous job and replace its `diagnostic` object with:

```json
{
  "profile": "runner-command",
  "argv": [
    "/bin/sh",
    "-c",
    ". /run/fieldlink-ci/connections.env; exec curl -q --silent --show-error --fail --config /run/fieldlink-ci/build-records.curl --url \"$FIELDLINK_BUILD_RECORDS_URL/api/build-records/worker-status\""
  ]
}
```

Submit the review job again. Standard output should identify `svc-fieldlink-ci`
and report build-record availability, with the service's request ID. Keep that
ID and the run ID when investigating a failed connection. An accepted job or
zero exit status alone does not establish which identity the service accepted.

`connections.env` contains the current base URLs, without trailing slashes,
for the connections below. It contains no passwords or tokens. The read-only
client files in `/run/fieldlink-ci` are generated for the current run; do not
copy their credentials into a script for reuse after the run ends.

| Service | Starting resource (GET) | Use |
| --- | --- | --- |
| `source` | `/api/v1/user/repos` | List the repositories available to the worker. Follow their API URLs for source and revision records. |
| `packages` | `/@keplerops%2ffieldlink-connector` | Read FieldLink connector version metadata and retained package locations. |
| `staff` | `/api/service-directory` | Read service ownership, authentication endpoints, supported client commands, and enrollment references. |
| `certificates` | Enrollment service record in the staff directory | Use the enrollment and authentication protocols documented by that service, with its installed client tools. |
| `cloud-policy` | `/api/trust` | Inspect the workload trust record and the identity service's request forms. |
| `build-records` | `/api/build-records` | Read authenticated job records and their archive references. |
| `maintenance` | `/api/maintenance` | Inspect scheduling policy and manage this worker's maintenance jobs. |

The URL variables are `FIELDLINK_SOURCE_URL`, `FIELDLINK_PACKAGES_URL`,
`FIELDLINK_STAFF_URL`, `FIELDLINK_CLOUD_POLICY_URL`, `FIELDLINK_BUILD_RECORDS_URL`,
and `FIELDLINK_MAINTENANCE_URL`. The corresponding worker HTTP configuration
files are `source.curl`, `packages.curl`, `staff.curl`, `cloud-policy.curl`,
`build-records.curl`, and `maintenance.curl`, all under `/run/fieldlink-ci`.
The certificate service's record supplies its native endpoint and client
configuration; it is not a generic HTTP record store.

The staff, policy, build-record, and maintenance indexes return resource links
and accepted request fields. Source and package responses use their own API
formats. Do not send one service's credential file to another service or use
automatic cross-service redirects. Destination services enforce their own roles.

For a separate authorized identity, keep its client material in the private
`/workspace/credentials` directory and select it explicitly in the appropriate
client. Do not load the worker's credential configuration for that request.
Certificate and ticket clients use the service's documented options and cache
paths. They are installed in the job environment; no external download is needed.
Check the principal reported by the receiving service, not just the local process
name. A failed authentication is not retried as the worker automatically.

Maintenance jobs run under a separate identity. Creating a job does not make
its mounted archive readable to the submitting worker. Backup recovery likewise
uses a separate principal; the runner cannot read the source database directly.
Release approval, signing material, private release evaluation, and customer
delivery are not part of the worker's role.

Commands can run scripts and save results in `/workspace`; use the job's Files
view to move your own files in or out. Job exit stops child processes and revokes
the worker credentials, but leaves workspace files and separately issued client
material intact. Renew that material through its issuing service when required.
Retry and Cancel preserve files. Reset workspace removes them and must not be
used for an ordinary failed command. Saved commands and results remain available
for a shift handover until that explicit reset.

Network policy is enforced outside the job. The listed supplier services are
reachable on their approved protocols; the job has no general network transit,
internet access, customer connection, or access to another job's files. Changing
a command or client credential does not change that network policy.
