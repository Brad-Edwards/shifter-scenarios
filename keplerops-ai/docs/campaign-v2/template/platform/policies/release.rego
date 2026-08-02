package keplerops.release

import rego.v1

default allow := false

valid_digest(value) if {
  regex.match("^sha256:[a-f0-9]{64}$", value)
}

valid_evaluation if {
  input.evaluation.decision == "accepted"
  valid_digest(input.evaluation.digest)
}

valid_approval if {
  input.approval.status == "approved"
  valid_digest(input.approval.digest)
}

allow if {
  input.schema == "keplerops.release/v2"
  input.model_family == "release-risk"
  valid_digest(input.source.digest)
  valid_digest(input.dataset.digest)
  valid_digest(input.training.digest)
  valid_digest(input.model.digest)
  valid_digest(input.serving_image.digest)
  valid_digest(input.gitops.digest)
  valid_evaluation
  valid_approval
  input.model.format == "onnx"
  input.serving_image.runtime == "onnxruntime-cpu"
  input.signature.transparency_status == "published"
  input.runtime.expected_model_digest == input.model.onnx_digest
  input.runtime.expected_image_digest == input.serving_image.image_digest
}

default assistant_approval := {"allow": false, "reason": "approval is outside delegated policy"}

assistant_approval := {
  "allow": true,
  "reason": "validated non-production candidate",
  "decision_id": sprintf("opa-sandbox-17-%s", [input.validation.run_id]),
} if {
  input.schema == "keplerops.release.approval/v1"
  input.principal == "svc-orion-agent"
  input.candidate == "sandbox-17"
  regex.match("^[0-9]+$", input.validation.run_id)
  regex.match("^[0-9a-f]{64}$", input.validation.artifact_sha256)
  startswith(input.validation.run_url, "https://git.keplerops.lab/svc-orion-agent/release-runbook-validation/actions/runs/")
}
