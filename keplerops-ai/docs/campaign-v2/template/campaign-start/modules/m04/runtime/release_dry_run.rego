package keplerops.m04.release_dry_run

import rego.v1

default allow := false

allow if {
  input.schema == "keplerops.orion.release-dry-run/v1"
  input.actor == "svc.release-routing"
  input.candidate == "non-production-fixture"
  input.environment == "non-production"
  input.requested_action == "deployment plan dry-run"
  input.workflow_id == "release-assistant-dry-run"
  startswith(input.event_id, "workhub-")
}

decision := {
  "allow": allow,
  "policy": "keplerops.m04.release_dry_run",
  "decision_id": sprintf("m04-release-dry-run-%s", [input.event_id]),
  "production_mutation": false,
}
