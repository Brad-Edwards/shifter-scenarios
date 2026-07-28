# KeplerOps CTFd reference loader

This operator-only adapter projects the validated `gcp_full`, SDL-owned event
bundle, or custom challenge selection directly from the modular ACES SDL into
CTFd. `aces_contract.py`
derives this operational view from governed challenge extensions; there is no
committed flag or challenge ledger. The adapter does not award oracle outcomes or install static
answers. Each challenge uses the bundled `keplerops_oracle` flag type, which
accepts only a signed proof-service receipt whose flag, outcome, evidence,
`range_instance`, participant, expiry, and reset generation match the current
CTFd account binding. The proof service issues that receipt only after fresh
evidence passes the existing negative gates. `local_reduced` intentionally
produces an empty board.

Install `plugins/keplerops_oracle_flags/` as a CTFd plugin before syncing. At
runtime, set `KEPLEROPS_CTFD_RECEIPT_KEY_FILE` to the proof-service HMAC key and
`KEPLEROPS_CTFD_BINDINGS_FILE` to an operator-managed JSON document shaped as
`{"accounts":{"<ctfd-account-id>":{"range_instance":"...","participant":"...","reset_generation":1}}}`.
Both files must be regular, owner-only files. They are deployment state: never
commit them, pass their contents in process arguments, or place them in the
repository environment file. Reset must advance `reset_generation`, which
invalidates old receipts even before their wall-clock expiry.

The plugin can also emit content-free research events for challenge views,
challenge starts, dependency unlock/block observation, receipt-backed flag
submissions, stale-receipt rejection, attempt completion, successful solves,
hint views, and hint unlocks. Events carry bounded CTFd correlation fields such
as challenge id, module id, hint tier/cost, reset generation, source sequence,
failure class, and the current dropped-event count. This adapter is
observational, bounded, asynchronous, and fail-open; it never sends the
submitted receipt, flag, hint text, response body, prerequisite ids, or
participant IP. Configure it with:

- `KEPLEROPS_CTFD_RESEARCH_URL` set to the internal port-4319 proof hostname;
- `KEPLEROPS_CTFD_RESEARCH_TOKEN_FILE` containing the `lab-portal` producer token;
- `KEPLEROPS_CTFD_RESEARCH_CA_FILE`, `KEPLEROPS_CTFD_RESEARCH_CERT_FILE`, and
  `KEPLEROPS_CTFD_RESEARCH_KEY_FILE` selecting the range-issued mutual-TLS files;
- `KEPLEROPS_CTFD_TELEMETRY_SEQUENCE_FILE` selecting an owner-only persistent
  sequence file outside participant content.

If these settings or the sink are unavailable, receipt comparison, challenge
views, submissions, solves, and hint behavior continue unchanged. The operator
export reports missing events through sequence gaps and source-health
summaries; later accepted CTFd events also carry `dropped_event_count`.
Richer reset joins remain part of the CTFd flow and shared research lifecycle
contract rather than inferred from CTFd alone.

Run a redacted preview:

```sh
python3 keplerops-ai/ctfd/sync_keplerops_ctfd.py \
  --base-url https://ctf.example.invalid --dry-run
```

To preview a named event bundle, pass `--profile novice-manual`,
`--profile intermediate-manual`, `--profile mixed-cohort`, or another
SDL-defined bundle id. If a selected bundle contains a planned challenge, the
loader fails before writing and reports the blocking challenge id. In the
current pre-hardware stack that deliberately blocks `advanced-manual` and
`agent-heavy` because both include `kep-m02-g`. For an operator-defined custom
board, repeat `--challenge-id`; prerequisite closure is added automatically
from the canonical SDL.

For a live sync, provide the admin token through `CTFD_TOKEN` or `--token-file`.
Token files must be regular, non-symlink files with no group/world permissions.
The loader accepts HTTPS and explicit loopback HTTP only, blocks redirects,
paginates administrative reads, reconciles only rows carrying the stable
`shifter:keplerops-ai:<flag_id>` tag, and verifies the result after writing.
ACES prerequisites are projected into CTFd challenge requirements after all
managed challenge IDs exist; readback verifies that the live board remains
dependency-closed. Duplicate owned identities fail before any write. Rerunning
repairs partial writes. It never prints receipts, tokens, API bodies, or raw
proof.
