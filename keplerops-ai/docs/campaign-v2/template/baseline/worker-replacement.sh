#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly STATE_DIR="$ROOT/state/worker-replacement"

[[ $EUID -eq 0 ]] || { echo 'worker-replacement.sh must run as root' >&2; exit 2; }
for command in grep jq python3 sed sha256sum tail tee; do
  command -v "$command" >/dev/null || {
    printf 'missing required command: %s\n' "$command" >&2
    exit 2
  }
done

"$ROOT/scripts/assert-clean-template-host.sh"
install -d -m 0750 "$STATE_DIR"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# These existing gates identify immutable source and training ancestors before
# the disposable-worker proof creates fresh, normal mail and intake records.
"$ROOT/baseline/source-ci-registries.sh"
"$ROOT/baseline/data-training-lineage.sh"

mail_output=$("$ROOT/baseline/mail-roundtrip.py")
printf '%s\n' "$mail_output"
mail_correlation=$(sed -n 's/^mail roundtrip passed: \(review-[[:alnum:]-]*\)$/\1/p' \
  <<<"$mail_output" | tail -n 1)
[[ -n $mail_correlation ]] || {
  echo 'mail acceptance did not return a workflow correlation' >&2
  exit 3
}

intake_output=$("$ROOT/baseline/document-intake.sh")
printf '%s\n' "$intake_output"
intake_line=$(grep '^partner intake passed:' <<<"$intake_output" | tail -n 1)
[[ -n $intake_line ]] || {
  echo 'document intake did not return durable record identifiers' >&2
  exit 3
}

field() {
  local key=$1
  sed -n "s/.*${key}=\\([^[:space:]]*\\).*/\\1/p" <<<"$intake_line"
}
ticket_number=$(field ticket)
ticket_id=$(field ticket_id)
issue_id=$(field issue)
point_id=$(field point)
document_sha=$(field sha256)
[[ -n $ticket_number && -n $ticket_id && -n $issue_id && -n $point_id && $document_sha =~ ^[a-f0-9]{64}$ ]] || {
  echo 'document intake record identifiers are malformed' >&2
  exit 3
}

"$ROOT/scripts/capture-worker-host-state.sh" >"$work/host-before.json"
"$ROOT/scripts/durable-worker-state.py" capture \
  --manifest "$work/durable-before.json" \
  --host-state "$work/host-before.json" \
  --mail-correlation "$mail_correlation" \
  --ticket-number "$ticket_number" \
  --ticket-id "$ticket_id" \
  --issue-id "$issue_id" \
  --point-id "$point_id" \
  --document-sha256 "$document_sha"

"$ROOT/scripts/replace-disposable-workers.sh" | tee "$work/replacement.json"

"$ROOT/scripts/capture-worker-host-state.sh" >"$work/host-after.json"
"$ROOT/scripts/durable-worker-state.py" verify \
  --manifest "$work/durable-before.json" \
  --host-state "$work/host-after.json"

install -m 0640 "$work/durable-before.json" "$STATE_DIR/last-preserved-state.json"
jq -n \
  --arg completed_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg manifest_sha256 "$(sha256sum "$work/durable-before.json" | awk '{print $1}')" \
  --arg mail_correlation "$mail_correlation" \
  --arg ticket_number "$ticket_number" \
  '{
    schema: "keplerops.clean-enterprise.worker-replacement-result/v1",
    completed_at: $completed_at,
    preserved_manifest_sha256: $manifest_sha256,
    normal_enterprise_records: {
      mail_correlation: $mail_correlation,
      intake_ticket_number: $ticket_number
    },
    replaced_workers: ["review01", "integration01"]
  }' | jq -S . >"$STATE_DIR/last-success.json"
chmod 0640 "$STATE_DIR/last-success.json"

echo 'clean-enterprise gate 13 passed: disposable workers replaced and durable state preserved'
