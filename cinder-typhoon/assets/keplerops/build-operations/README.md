# Build Operations records

These are authored in-world documents, not runtime service implementations.
Native `content` file entries in `sdl/modules/operations/k09.yaml` carry their
exact text. They belong to `k-ci`, not to the developer workspace or the general
staff document library.

**Approved design change:** `runner-command` executes ordinary commands in a
restricted job environment, including shells, scripts, and native authentication
clients. It can use separately earned identities instead of forcing every call
to use the worker's identity. This resolves the request-only interface decision;
it does not complete the downstream certificate/delegation designs or demonstrate
a live solve. No fictional identity API or completion-triggered access grant is
introduced. Host/CI administration and general network transit remain excluded.

| Asset | Native content entry | Placement and audience |
| --- | --- | --- |
| `diagnostic-request-reference.md` | `k09.diagnostic-request-reference` | `/srv/fieldlink-ci/reviews/diagnostic-request-reference.md`; maintained reference included in the protected review recovered through K09.3. |
| `runner-operations.md` | `k09.runner-operations-note` | `/srv/fieldlink-ci/runner/runner-operations.md`; worker-owned internal record, read-only inside the command job and unavailable to direct developer reads or ordinary review output. |

The file placement does not itself implement access control. The K09 action
contracts require the reference/note separation and denied direct reads. The
run IDs, request IDs, authenticated status response, and audit records must be
produced by actual jobs and receiving services; they are not seeded successes.
Service resource indexes must resolve the documented paths, describe accepted
request fields, and retain the destination's independent authorization checks.

The source connection uses Gitea's [authenticated repository-list API](https://docs.gitea.com/api/1.25/operations/user-current-list-repos/),
with its `/api/v1` base path. The package connection uses Verdaccio's native
package-metadata route for the existing `@keplerops/fieldlink-connector` package,
not an invented package-list API; see the upstream [route declarations](https://github.com/verdaccio/verdaccio/blob/master/packages/middleware/src/middlewares/api-urls.ts)
and [access-checked package handler](https://github.com/verdaccio/verdaccio/blob/master/packages/api/src/package.ts).
The staff, policy, build-record, and maintenance paths are requirements for the
authored business interfaces, not claims that FreeIPA, Windows certificate
services, or Kubernetes implement those URLs. Certificate enrollment and
authentication use the actual selected service protocols and installed clients,
whose endpoints and options belong in the staff service records. Their complete
downstream designs remain required before acceptance.

`connections.env` and the six per-service curl configurations in the operations
note are required runtime files, not authored credential-bearing assets. Native
action and starting-record contracts retain their requirements. Resolve base
URLs without trailing slashes from the configured service endpoints; preserve
encoded scoped-package names. Curl configurations contain service-scoped
authentication and certificate trust, not an overriding URL, method, body, or
redirect option. No default curl configuration or credential-injecting proxy
may replace a client's independently selected identity. No actual credentials
belong in these documents or in source control.

The job's Files view must preserve private files, including binary downloads,
scripts, and independently earned client material. Treat its contents and
command output as untrusted. Worker credentials are readable inside the job;
isolation comes from their limited role, per-run lease and origin checks, plus
external enforcement of destination and host boundaries. Trusted execution and
file-read evidence cannot come from a log the command can overwrite. A receiving
service request ID alone is not sufficient proof of execution in the job.

`test_k09_handoff.py` checks the document bytes, placement, request example,
downstream route preservation, proof ownership, and difficulty allocation.
Live authorization, exploitability, and discovery time remain golden-range
acceptance checks, not claims from those static tests.
