package keplerops.business

import rego.v1

default decision := {"allow": false}

allowed := {
    "feature-control": {
        "actor": "svc-orion-canary",
        "family": "assistant",
        "action": "unleash:set",
        "outcome": "enable-canary",
        "system": "unleash",
        "object": "orion-canary-assistant",
    },
    "accounting-credit": {
        "actor": "svc-orion-canary",
        "family": "release-risk",
        "action": "odoo:credit-note",
        "outcome": "approve-adjustment",
        "system": "odoo",
        "object": "KAI-CUSTOMER-001",
    },
    "incident-publication": {
        "actor": "svc-orion-release",
        "family": "assistant",
        "action": "ghost:publish",
        "outcome": "approve-publication",
        "system": "ghost",
        "object": "orion-safety-update",
    },
    "advisory-campaign": {
        "actor": "svc-orion-canary",
        "family": "release-risk",
        "action": "mautic:send",
        "outcome": "cohort-orion-edge",
        "system": "mautic",
        "object": "orion-edge-operators",
    },
    "support-triage": {
        "actor": "svc-orion-canary",
        "family": "release-risk",
        "action": "zammad:close",
        "outcome": "routine-low-risk",
        "system": "zammad",
        "object": "Routine Orion access request",
    },
    "feedback-intake": {
        "actor": "svc-orion-ingest",
        "family": "release-risk",
        "action": "feedback:ingest",
        "outcome": "accepted-signal",
        "system": "zammad-rabbitmq-qdrant",
        "object": "orion-feedback",
    },
    "feedback-maintenance": {
        "actor": "svc-orion-trainer",
        "family": "release-risk",
        "action": "lakefs:validate-partition",
        "outcome": "partition-valid",
        "system": "lakefs",
        "object": "feedback/partitions/2026-08-01/control.jsonl",
    },
    "tenant-retention": {
        "actor": "svc-data-steward",
        "family": "assistant",
        "action": "retention:delete",
        "outcome": "retention-approved",
        "system": "redmine-nextcloud-lakefs",
        "object": "acme-labs-expired",
    },
}

valid_digest(value) if {
    regex.match("^sha256:[a-f0-9]{64}$", value)
}

decision := {
    "allow": true,
    "allowed_action": expected.action,
    "decision_id": sprintf("%s:%s", [input.workflow, input.request_id]),
    "policy_revision": input.release.policy_digest,
    "range_id": input.range_id,
    "target_system": expected.system,
    "target_object": expected.object,
} if {
    input.schema == "keplerops.business-policy/v1"
    input.token_audience == "keplerops-business-adapter"
    input.clean_control_decision == "approved-clean-control"
    input.release.signed == true
    valid_digest(input.release.release_id)
    valid_digest(input.release.model_digest)
    valid_digest(input.release.serving_image_digest)
    valid_digest(input.release.policy_digest)
    expected := allowed[input.workflow]
    input.actor == expected.actor
    input.release.model_family == expected.family
    input.action == expected.action
    input.outcome == expected.outcome
    input.target_system == expected.system
    input.target_object == expected.object
}
