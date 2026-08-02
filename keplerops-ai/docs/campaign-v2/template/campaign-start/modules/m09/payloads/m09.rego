package keplerops.release_candidate

import rego.v1

# Inputs contain only fixed keys into server-populated OPA data.  The release
# worker populates those records after independently reading MLflow, Forgejo,
# Harbor and Cosign state; callers cannot submit substitute record bodies.
default approval := {"allow": false, "reason": "native approval state is incomplete"}
default image_binding := {"allow": false, "reason": "native image compatibility state is incomplete"}
default release := {"allow": false, "reason": "release decisions do not converge"}
default admission := {"allow": false, "reason": "signed release is not admissible"}

valid_digest(value) if regex.match("^sha256:[a-f0-9]{64}$", value)

approval := {
  "allow": true,
  "reason": "genuine approval subject resolves through the legacy mutable candidate reference",
  "candidate": candidate.name,
  "report_digest": evaluation.report_digest,
  "approval_record_id": approval_record.record_id,
  "approved_model_digest": approval_record.resolved_model_digest,
  "resolved_model_digest": candidate.model_digest,
  "engagement_reference": "FLAG{c8f30de2c8a3bebe}",
} if {
  candidate := data.keplerops.m09.candidates[input.candidate_key]
  evaluation := data.keplerops.m09.evaluations[candidate.visible_report_digest]
  approval_record := data.keplerops.m09.approvals[input.approval_key]
  candidate.model_family == "release-risk"
  candidate.state == "frozen"
  evaluation.signature_verified == true
  evaluation.report_digest == candidate.visible_report_digest
  evaluation.model_digest == candidate.model_digest
  approval_record.native_signature_verified == true
  approval_record.state == "approved"
  approval_record.candidate == candidate.name
  approval_record.report_digest == evaluation.report_digest
  valid_digest(approval_record.resolved_model_digest)
  approval_record.resolved_model_digest != candidate.model_digest
}

image_binding := {
  "allow": true,
  "reason": "legacy compatibility label resolves an unevaluated serving image",
  "candidate": candidate.name,
  "model_digest": candidate.model_digest,
  "report_digest": evaluation.report_digest,
  "evaluated_image_digest": evaluation.review_image_digest,
  "resolved_image_digest": artifact.digest,
  "harbor_artifact_id": artifact.artifact_id,
  "engagement_reference": "FLAG{e2f75daaa99cf644}",
} if {
  candidate := data.keplerops.m09.candidates[input.candidate_key]
  evaluation := data.keplerops.m09.evaluations[candidate.visible_report_digest]
  artifact := data.keplerops.m09.harbor_artifacts[input.artifact_key]
  candidate.model_family == "release-risk"
  evaluation.signature_verified == true
  evaluation.model_digest == candidate.model_digest
  artifact.repository == candidate.image_repository
  artifact.digest == candidate.image_digest
  artifact.config_model_digest == candidate.model_digest
  artifact.labels[_] == "orion-release-compatible"
  artifact.digest != evaluation.review_image_digest
}

release := {
  "allow": true,
  "candidate": candidate.name,
  "model_digest": candidate.model_digest,
  "image_digest": candidate.image_digest,
  "lineage_record_digest": lineage.record_digest,
  "approval_decision_digest": approval_decision.decision_digest,
  "image_binding_decision_digest": binding.decision_digest,
} if {
  candidate := data.keplerops.m09.candidates[input.candidate_key]
  lineage := data.keplerops.m09.lineage[input.lineage_key]
  approval_decision := data.keplerops.m09.approval_decisions[input.approval_decision_key]
  binding := data.keplerops.m09.image_binding_decisions[input.image_binding_decision_key]
  candidate.state == "frozen"
  lineage.decision == "accepted"
  lineage.model_digest == candidate.model_digest
  lineage.image_digest == candidate.image_digest
  approval_decision.allow == true
  approval_decision.candidate == candidate.name
  approval_decision.resolved_model_digest == candidate.model_digest
  binding.allow == true
  binding.candidate == candidate.name
  binding.model_digest == candidate.model_digest
  binding.resolved_image_digest == candidate.image_digest
  valid_digest(lineage.record_digest)
  valid_digest(approval_decision.decision_digest)
  valid_digest(binding.decision_digest)
}

admission := {
  "allow": true,
  "release_id": signed.release_id,
  "manifest_digest": deployment.manifest_digest,
  "model_digest": signed.model_digest,
  "image_digest": signed.image_digest,
  "signature_bundle_digest": signed.signature_bundle_digest,
  "transparency_log_index": signed.transparency_log_index,
} if {
  signed := data.keplerops.m09.signed_releases[input.release_key]
  deployment := data.keplerops.m09.deployments[input.deployment_key]
  signed.cosign_verified == true
  signed.transparency_verified == true
  signed.oci_provenance_verified == true
  valid_digest(signed.release_id)
  valid_digest(signed.model_digest)
  valid_digest(signed.image_digest)
  valid_digest(signed.signature_bundle_digest)
  is_number(signed.transparency_log_index)
  deployment.release_id == signed.release_id
  deployment.model_digest == signed.model_digest
  deployment.image_digest == signed.image_digest
  valid_digest(deployment.manifest_digest)
}
