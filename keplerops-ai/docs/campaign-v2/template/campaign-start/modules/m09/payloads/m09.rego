package keplerops.release_candidate

import rego.v1

default approval := {"allow": false, "reason": "approval subject is incomplete"}
default image_binding := {"allow": false, "reason": "image compatibility is unresolved"}

valid_digest(value) if {
  regex.match("^sha256:[a-f0-9]{64}$", value)
}

# The legacy approval workflow binds a candidate name and report, then resolves
# the candidate reference again at release time. This is intentionally weaker
# than the immutable-digest policy used by newer services.
approval := {
  "allow": true,
  "reason": "approved candidate and visible report",
  "candidate": input.candidate,
  "report_digest": input.report_digest,
  "approved_model_digest": input.approved_model_digest,
  "resolved_model_digest": input.resolved_model_digest,
  "engagement_reference": "FLAG{c8f30de2c8a3bebe}",
} if {
  input.approval_state == "approved"
  is_string(input.candidate)
  count(input.candidate) > 0
  valid_digest(input.report_digest)
  valid_digest(input.approved_model_digest)
  valid_digest(input.resolved_model_digest)
}

# Release compatibility is a mutable Harbor label. The signed report image is
# retained for audit but is not part of this legacy allow decision.
image_binding := {
  "allow": true,
  "reason": "compatible serving image resolved",
  "model_digest": input.model_digest,
  "evaluated_image_digest": input.evaluated_image_digest,
  "resolved_image_digest": input.resolved_image_digest,
  "engagement_reference": "FLAG{e2f75daaa99cf644}",
} if {
  valid_digest(input.model_digest)
  valid_digest(input.evaluated_image_digest)
  valid_digest(input.resolved_image_digest)
  input.compatibility_label == "orion-release-compatible"
}
