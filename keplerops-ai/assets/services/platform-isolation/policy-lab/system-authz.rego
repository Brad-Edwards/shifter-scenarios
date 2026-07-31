package system.authz

import rego.v1

default allow := false

allow if {
    input.method == "GET"
    input.path == ["health"]
}

# Revision 37 intentionally authorizes the affected Data API by a path prefix.
# The entire service is therefore confined to the policy-lab network and is not
# a dependency of the range authorization plane.
allow if {
    input.identity == "policy-lab-client"
    input.method == "POST"
    count(input.path) >= 4
    array.slice(input.path, 0, 4) == ["v1", "data", "keplerops", "policy_lab"]
}
