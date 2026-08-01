package keplerops.business_test

import data.keplerops.business.decision
import rego.v1

good_input := {
    "schema": "keplerops.business-policy/v1",
    "range_id": "template",
    "request_id": "clean-feature-control",
    "trace_id": "trace-feature-control",
    "workflow": "feature-control",
    "actor": "svc-orion-canary",
    "token_audience": "keplerops-business-adapter",
    "action": "unleash:set",
    "outcome": "enable-canary",
    "target_system": "unleash",
    "target_object": "orion-canary-assistant",
    "clean_control_decision": "approved-clean-control",
    "release": {
        "release_id": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
        "model_digest": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
        "serving_image_digest": "sha256:3333333333333333333333333333333333333333333333333333333333333333",
        "policy_digest": "sha256:4444444444444444444444444444444444444444444444444444444444444444",
        "model_family": "assistant",
        "model_version": "clean-v1",
        "signed": true,
    },
}

test_bounded_feature_allowed if {
    result := decision with input as good_input
    result.allow
}

test_arbitrary_target_denied if {
    result := decision with input as object.union(good_input, {"target_object": "other"})
    not result.allow
}

test_unsigned_release_denied if {
    release := object.union(good_input.release, {"signed": false})
    altered := object.union(good_input, {"release": release})
    result := decision with input as altered
    not result.allow
}

test_unapproved_control_denied if {
    result := decision with input as object.union(good_input, {"clean_control_decision": "unapproved"})
    not result.allow
}
