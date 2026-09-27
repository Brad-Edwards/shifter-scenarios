#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

docker compose -f compose.yaml down -v --remove-orphans
docker compose -f compose.yaml up -d --force-recreate a-connector a-business a-archive a-identity a-data

for _ in $(seq 1 60); do
  if docker exec --user arwc-connector cinder-arwc-connector \
    test -s /var/lib/arwc-connector/state/planner-handover.json; then
    state=$(docker exec --user arwc-connector cinder-arwc-connector \
      cat /var/lib/arwc-connector/state/planner-handover.json)
    audit_size=$(docker exec --user arwc-connector cinder-arwc-connector \
      sh -c 'wc -c </var/lib/arwc-connector/audit/events.jsonl')
    business=$(docker exec --user arwc-business cinder-arwc-business \
      cat /var/lib/arwc-business/state/discoveries.json 2>/dev/null || true)
    business_audit=$(docker exec --user arwc-business cinder-arwc-business \
      sh -c 'wc -c </var/lib/arwc-business/audit/events.jsonl' 2>/dev/null || true)
    archive=$(docker exec --user arwc-archive cinder-arwc-archive \
      cat /var/lib/arwc-archive/state/archive.json 2>/dev/null || true)
    archive_audit=$(docker exec --user arwc-archive cinder-arwc-archive \
      sh -c 'wc -c </var/lib/arwc-archive/audit/events.jsonl' 2>/dev/null || true)
    identity=$(docker exec --user arwc-identity cinder-arwc-identity \
      cat /var/lib/arwc-identity/state/identity.json 2>/dev/null || true)
    identity_audit=$(docker exec --user arwc-identity cinder-arwc-identity \
      sh -c 'wc -c </var/lib/arwc-identity/audit/events.jsonl' 2>/dev/null || true)
    data=$(docker exec --user arwc-data cinder-arwc-data \
      cat /var/lib/arwc-data/state/planning.json 2>/dev/null || true)
    data_audit=$(docker exec --user arwc-data cinder-arwc-data \
      sh -c 'wc -c </var/lib/arwc-data/audit/events.jsonl' 2>/dev/null || true)
    data_copy=$(docker exec --user postgres cinder-arwc-data \
      psql -d arwc -Atc 'SELECT count(*) FROM reconciliation_copy' 2>/dev/null || true)
    if [[ $state == *'"record_id":"PLN-HO-CRR-17"'* \
      && $state == *'"revision":3'* \
      && $state == *'"filename":"inspection-summary-r2.md"'* \
      && $audit_size == 0 \
      && $business == '{"association_table":false,"restricted_handover":false}' \
      && $business_audit == 0 \
      && $archive == *'"enrollment_consumed":false'* \
      && $archive == *'"issued_certificates":[]'* \
      && $archive == *'"protected_record_observed":false'* \
      && $archive == *'"helper_handover_copied":false'* \
      && $archive == *'"planner_handover_token":null'* \
      && $archive_audit == 0 \
      && $identity == *'"starter_observed":false'* \
      && $identity == *'"roster_observed":false'* \
      && $identity == *'"preview_attached":false'* \
      && $identity == *'"planner_session":null'* \
      && $identity_audit == 0 \
      && $data == '{"adjustment_observed":false,"query_definition_observed":false,"reconciliation_copy_created":false}' \
      && $data_audit == 0 \
      && $data_copy == 0 ]] \
      && docker exec --user arwc-archive cinder-arwc-archive \
        test ! -e /var/lib/arwc-archive/handover/W06-access.json \
      && docker exec --user arwc-identity cinder-arwc-identity \
        test ! -e /var/lib/arwc-identity/planning/planner-session.json; then
      echo "Alterra authored initial state restored"
      exit 0
    fi
  fi
  sleep 1
done

echo "Alterra connector did not initialize" >&2
exit 1
