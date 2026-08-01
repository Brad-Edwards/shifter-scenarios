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
}
