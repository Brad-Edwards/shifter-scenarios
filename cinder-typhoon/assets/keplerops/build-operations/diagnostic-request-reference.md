# FieldKest review jobs: diagnostic requests

Build Operations · request format revision 3 · 14 September 2026

Submit review jobs to `POST /api/review-jobs`. Keep the retained input reference
from the completed review in `support_input`; the job history records it beside
the resolved input revision. `diagnostic` is a separate object in that same
request. Integration diagnostics require that retained reference, not the
unresolved input link. References belong to the submitting account and its
current workspace generation. Ordinary support inputs do not carry an
integration diagnostic context.

The regular support review uses:

```json
{"profile": "render-review"}
```

Build Operations uses `runner-command` for command-line diagnostics. This profile
is restricted to build maintainers. Set `argv` to an array whose first string is
the executable and whose remaining strings are its arguments. Commands start
in `/workspace`. For example, the ordinary working-directory check is:

```json
{"profile": "runner-command", "argv": ["/bin/pwd"]}
```

Arguments are passed directly to the program. To use a pipeline, redirection,
or shell variables, invoke `/bin/sh` with `-c` and the command string explicitly.
The internal service handover is `/srv/fieldlink-ci/runner/runner-operations.md`.
It documents the connection check and the worker's client configuration.

The job's Files view uploads and downloads files in the submitting account's
private `/workspace`. The same directory is mounted in subsequent runs. Save
scripts, responses, and client material there; temporary files elsewhere and
running processes do not survive job exit. Files are not shared with another
submitting account. Use the Cancel action to stop a stuck run before retrying.

Client configuration is supplied under `/run/fieldlink-ci` for each run. Select
the appropriate configuration when a command needs the worker's service identity.
Commands can instead select their own credential files. Do not put passwords,
private keys, or tokens in `argv`: command arguments are retained in job history.

Each submission creates a new run. The result records the selected profile,
process identity, exit status, standard output, standard error, and saved files.
A queued run is not a completed command. Keep any request ID returned by a
receiving service when asking that team to check its log.

Retry from the retained request in job history. Change only the diagnostic
object when comparing commands against the same support input. A failed run
does not remove the workspace or an earlier result. Job exit revokes that run's
worker credentials; the next run receives fresh ones. Reset workspace is a
separate destructive action, not part of Retry or Cancel.
