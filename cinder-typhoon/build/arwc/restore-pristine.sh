#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

docker compose -f compose.yaml down -v --remove-orphans
docker compose -f compose.yaml up -d --force-recreate a-connector a-business a-archive a-identity a-data-bridge a-data a-contractors a-contractor-bridge a-approval a-hmi a-historian a-engineering a-instruments a-diagnostics

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
    bridge=$(docker exec --user arwc-data-bridge cinder-arwc-data-bridge \
      cat /var/lib/arwc-data-bridge/state/integration.json 2>/dev/null || true)
    bridge_audit=$(docker exec --user arwc-data-bridge cinder-arwc-data-bridge \
      sh -c 'wc -c </var/lib/arwc-data-bridge/audit/events.jsonl' 2>/dev/null || true)
    contractors=$(docker exec --user arwc-contractors cinder-arwc-contractors \
      cat /var/lib/arwc-contractors/state/contractor.json 2>/dev/null || true)
    contractors_audit=$(docker exec --user arwc-contractors cinder-arwc-contractors \
      sh -c 'wc -c </var/lib/arwc-contractors/audit/events.jsonl' 2>/dev/null || true)
    field_gateway=$(docker exec --user arwc-contractor-bridge cinder-arwc-contractor-bridge \
      cat /var/lib/arwc-contractor-bridge/state/field-gateway.json 2>/dev/null || true)
    field_gateway_audit=$(docker exec --user arwc-contractor-bridge cinder-arwc-contractor-bridge \
      sh -c 'wc -c </var/lib/arwc-contractor-bridge/audit/events.jsonl' 2>/dev/null || true)
    approval=$(docker exec --user arwc-approval cinder-arwc-approval \
      cat /var/lib/arwc-approval/state/maintenance-review.json 2>/dev/null || true)
    approval_audit=$(docker exec --user arwc-approval cinder-arwc-approval \
      sh -c 'wc -c </var/lib/arwc-approval/audit/events.jsonl' 2>/dev/null || true)
    hmi=$(docker exec --user arwc-hmi cinder-arwc-hmi \
      cat /var/lib/arwc-hmi/state/service.json 2>/dev/null || true)
    hmi_audit=$(docker exec --user arwc-hmi cinder-arwc-hmi \
      sh -c 'wc -c </var/lib/arwc-hmi/audit/events.jsonl' 2>/dev/null || true)
    historian=$(docker exec --user arwc-historian cinder-arwc-historian \
      cat /var/lib/arwc-historian/state/service.json 2>/dev/null || true)
    historian_audit=$(docker exec --user arwc-historian cinder-arwc-historian \
      sh -c 'wc -c </var/lib/arwc-historian/audit/events.jsonl' 2>/dev/null || true)
    engineering=$(docker exec --user arwc-engineering cinder-arwc-engineering \
      cat /var/lib/arwc-engineering/state/service.json 2>/dev/null || true)
    engineering_audit=$(docker exec --user arwc-engineering cinder-arwc-engineering \
      sh -c 'wc -c </var/lib/arwc-engineering/audit/events.jsonl' 2>/dev/null || true)
    instruments=$(docker exec --user arwc-instruments cinder-arwc-instruments \
      cat /var/lib/arwc-instruments/state/service.json 2>/dev/null || true)
    instruments_audit=$(docker exec --user arwc-instruments cinder-arwc-instruments \
      sh -c 'wc -c </var/lib/arwc-instruments/audit/events.jsonl' 2>/dev/null || true)
    diagnostics=$(docker exec --user arwc-diagnostics cinder-arwc-diagnostics \
      cat /var/lib/arwc-diagnostics/state/service.json 2>/dev/null || true)
    diagnostics_audit=$(docker exec --user arwc-diagnostics cinder-arwc-diagnostics \
      sh -c 'wc -c </var/lib/arwc-diagnostics/audit/events.jsonl' 2>/dev/null || true)
    data_copy=$(docker exec --user postgres cinder-arwc-data \
      psql -d arwc -Atc 'SELECT count(*) FROM reconciliation_copy' 2>/dev/null || true)
    if [[ $state == *'"record_id":"PLN-HO-CRR-17"'* \
      && $state == *'"revision":3'* \
      && $state == *'"filename":"inspection-summary-r2.md"'* \
      && $audit_size == 0 \
      && $business == '{"association_table":false,"foreign_excerpt_observed":false,"foreign_quote_observed":false,"linked_document_observed":false,"procurement_catalog_observed":false,"procurement_order":null,"restricted_handover":false,"source_selection_observed":false}' \
      && $business_audit == 0 \
      && $archive == *'"enrollment_consumed":false'* \
      && $archive == *'"issued_certificates":[]'* \
      && $archive == *'"protected_record_observed":false'* \
      && $archive == *'"helper_handover_copied":false'* \
      && $archive == *'"planner_handover_token":null'* \
      && $archive == *'"work_bundle_observed":false'* \
      && $archive == *'"exchange_reconstructed":false'* \
      && $archive == *'"collector_reconstructed":false'* \
      && $archive == *'"collector_config_recovered":false'* \
      && $archive == *'"quarantine_observed":false'* \
      && $archive == *'"protection_reconstructed":false'* \
      && $archive == *'"cold_archive_recovered":false'* \
      && $archive == *'"current_session":null'* \
      && $archive == *'"current_data_observed":false'* \
      && $archive == *'"sequencer_descriptor_observed":false'* \
      && $archive == *'"sequencer_boundary_observed":false'* \
      && $archive == *'"sequencer_signal_discriminated":false'* \
      && $archive == *'"sequencer_calibration_recovered":false'* \
      && $archive == *'"sequencer_experiment_count":0'* \
      && $archive == *'"sequencer_request_ids":[]'* \
      && $archive_audit == 0 \
      && $identity == *'"starter_observed":false'* \
      && $identity == *'"roster_observed":false'* \
      && $identity == *'"preview_attached":false'* \
      && $identity == *'"planner_session":null'* \
      && $identity_audit == 0 \
      && $data == *'"adjustment_observed":false'* \
      && $data == *'"allocation_observed":false'* \
      && $data == *'"meter_observed":false'* \
      && $data == *'"query_definition_observed":false'* \
      && $data == *'"reconciliation_copy_created":false'* \
      && $data == *'"reserve_reconciled":false'* \
      && $data == *'"relation_contract_observed":false'* \
      && $data == *'"relation_exchange_observed":false'* \
      && $data == *'"lineage_observed":false'* \
      && $data_audit == 0 \
      && $data_copy == 0 \
      && $bridge == '{"current_feed_observed":false,"process_session":null}' \
      && $bridge_audit == 0 \
      && $contractors == *'"appointment_observed":false'* \
      && $contractors == *'"roster_observed":false'* \
      && $contractors == *'"field_bag_observed":false'* \
      && $contractors == *'"contractor_session":null'* \
      && $contractors == *'"attendee":"northbank.inspector.117"'* \
      && $contractors == *'"revision":1'* \
      && $contractors_audit == 0 \
      && $field_gateway == '{"current_read_observed":false,"manifest_observed":false,"nonces":[],"process_session":null}' \
      && $field_gateway_audit == 0 \
      && $approval == '{"approval_observed":false,"association_observed":false,"cached_response":null,"review_capability":null}' \
      && $approval_audit == 0 \
      && $hmi == '{"envelope_observed":false,"ineffective_requests_observed":false,"mode_observed":false,"note_observed":false,"practice_conditions_observed":false,"practice_sequence_observed":false,"present_observed":false,"trace_correlated":false}' \
      && $hmi_audit == 0 \
      && $historian == '{"mapping_observed":false,"scale_observed":false,"tag_export_observed":false,"unit_change_interpreted":false}' \
      && $historian_audit == 0 \
      && $engineering == '{"compatibility_reproduced":false,"concealed_reviewer_used":false,"deployed_revision_observed":false,"diagnostic_observed":false,"hidden_check_recovered":false,"legacy_mapping_recovered":false,"project_bundle_observed":false,"sealed_project_opened":false,"viewer_observed":false,"vm_reconstructed":false}' \
      && $engineering_audit == 0 \
      && $instruments == '{"deployment_observed":false,"flash_observed":false,"image_rewrite_accepted":false,"inspection_recovered":false,"mapping_observed":false,"practice_observed":false,"trace_observed":false}' \
      && $instruments_audit == 0 \
      && $diagnostics == '{"false_estimate_observed":false,"protected_state_controlled":false,"side_effect_observed":false}' \
      && $diagnostics_audit == 0 ]] \
      && docker exec --user arwc-archive cinder-arwc-archive \
        test ! -e /var/lib/arwc-archive/handover/W06-access.json \
      && docker exec --user arwc-identity cinder-arwc-identity \
        test ! -e /var/lib/arwc-identity/planning/planner-session.json \
      && docker exec --user arwc-business cinder-arwc-business \
        test ! -e /var/lib/arwc-business/archive/W08-source.json \
      && docker exec --user arwc-identity cinder-arwc-identity \
        test ! -e /var/lib/arwc-identity/archive/W08-source.json \
      && docker exec --user arwc-business cinder-arwc-business \
        test ! -e /var/lib/arwc-business/integration/W09-read.json \
      && docker exec --user arwc-data cinder-arwc-data \
        test ! -e /var/lib/arwc-data/integration/W09-data.json \
      && docker exec --user arwc-business cinder-arwc-business \
        test ! -e /var/lib/arwc-business/relation/W02-association.json \
      && docker exec --user arwc-data cinder-arwc-data \
        test ! -e /var/lib/arwc-data/archive/W11-lineage.json \
      && docker exec --user arwc-contractors cinder-arwc-contractors \
        test ! -e /var/lib/arwc-contractors/handover/contractor-session.json \
      && docker exec --user arwc-historian cinder-arwc-historian \
        sh -c 'test ! -e /run/arwc-ot-read/corporate.json && test ! -e /run/arwc-ot-read/contractor.json' \
      && docker exec --user arwc-historian cinder-arwc-historian \
        sh -c 'find /run/arwc-process-evidence -type f -print -quit | grep -q . && exit 1 || exit 0'; then
      echo "Alterra authored initial state restored"
      exit 0
    fi
  fi
  sleep 1
done

echo "Alterra connector did not initialize" >&2
exit 1
