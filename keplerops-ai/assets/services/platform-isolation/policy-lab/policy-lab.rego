package keplerops.policy_lab

import rego.v1

default allow := false

allow if {
    input.control_state == "enabled"
    input.operation in {"evaluate", "observe", "restore"}
}

decision := {
    "allow": allow,
    "engine": "open-policy-agent",
    "policy_revision": "37",
}
