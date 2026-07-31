package keplerops.guardrails

import rego.v1

default allow := false

allow if {
  input.session.range_instance != ""
  input.session.participant != ""
  input.action in {"infer", "read_context", "submit_evaluation"}
}

# Module 04 exposes bounded inference and privacy-population probes. Private
# labels remain server-side; the gateway supplies the challenge identifier.
allow if {
  input.session.range_instance != ""
  input.session.participant != ""
  "participant" in input.session.roles
  input.action == "secrets_probe"
  input.challenge_id in {
    "kep-m04-a", "kep-m04-b", "kep-m04-c", "kep-m04-d", "kep-m04-e",
    "kep-m04-f", "kep-m04-g", "kep-m04-h", "kep-m04-i",
    "kep-m04-j", "kep-m04-k", "kep-m04-l", "kep-m04-m",
  }
}

# Module 10 joins already-earned participant lineage to the promoted model,
# the contained policy broker, and range-local artifact/exfil stores. The
# gateway supplies the bounded challenge identifier and owns all verdicts.
allow if {
  input.session.range_instance != ""
  input.session.participant != ""
  "participant" in input.session.roles
  input.action == "ai_capstone"
  input.challenge_id in {
    "kep-m10-a", "kep-m10-b", "kep-m10-c", "kep-m10-d",
    "kep-m10-e", "kep-m10-f", "kep-m10-g",
    "kep-m10-h", "kep-m10-i", "kep-m10-j", "kep-m10-k",
    "kep-m10-l", "kep-m10-m", "kep-m10-n", "kep-m10-o",
    "kep-m10-p", "kep-m10-q",
  }
}

# Module 02 probes are issued only by the authenticated inference gateway. The
# participant supplies a candidate; the gateway supplies the bounded challenge
# identifier and keeps the control prompts out of the request surface.
allow if {
  input.session.range_instance != ""
  input.session.participant != ""
  "participant" in input.session.roles
  input.action == "evasion_probe"
  input.challenge_id in {
    "kep-m02-a", "kep-m02-b", "kep-m02-c",
    "kep-m02-d", "kep-m02-e", "kep-m02-f",
    "kep-m02-h", "kep-m02-i", "kep-m02-j", "kep-m02-k", "kep-m02-l", "kep-m02-m",
  }
}

# Module 06 stores participant-created artifacts and evaluates them only through
# the authenticated gateway's bounded disclosed and held-out real-model probes.
allow if {
  input.session.range_instance != ""
  input.session.participant != ""
  "participant" in input.session.roles
  input.action == "adversarial_probe"
  input.challenge_id in {
    "kep-m06-a", "kep-m06-b", "kep-m06-c",
    "kep-m06-d", "kep-m06-e", "kep-m06-f",
    "kep-m06-g", "kep-m06-h", "kep-m06-i", "kep-m06-j",
    "kep-m06-k", "kep-m06-l", "kep-m06-m", "kep-m06-n",
    "kep-m06-o", "kep-m06-p", "kep-m06-q", "kep-m06-r",
    "kep-m06-s", "kep-m06-t", "kep-m06-u", "kep-m06-v",
  }
}

# Module 07 permits authenticated participants to version bounded poisoned rows,
# queue the corresponding real training job, and request server-owned evaluation.
allow if {
  input.session.range_instance != ""
  input.session.participant != ""
  "participant" in input.session.roles
  input.action == "training_poison"
  input.challenge_id in {
    "kep-m07-a", "kep-m07-b", "kep-m07-c",
    "kep-m07-d", "kep-m07-e", "kep-m07-f",
    "kep-m07-g", "kep-m07-h", "kep-m07-i",
  }
}

# Module 08 permits authenticated participants to spend a server-owned teacher
# budget, collect a participant-scoped corpus, and train a bound proxy. Private
# probes, teacher artifacts, and cross-participant corpora remain unavailable.
allow if {
  input.session.range_instance != ""
  input.session.participant != ""
  "participant" in input.session.roles
  input.action == "model_extract"
  input.challenge_id in {
    "kep-m08-a", "kep-m08-b", "kep-m08-c",
    "kep-m08-d", "kep-m08-e", "kep-m08-f",
    "kep-m08-g", "kep-m08-h", "kep-m08-i",
    "kep-m08-j", "kep-m08-k",
  }
}

# Module 09 evaluates only server-bound candidates through the participant
# gateway. The separate approval document below intentionally contains the
# exercise's signed-object scope confusion.
allow if {
  input.session.range_instance != ""
  input.session.participant != ""
  "participant" in input.session.roles
  input.action == "model_backdoor"
  input.challenge_id in {
    "kep-m09-a", "kep-m09-b", "kep-m09-c", "kep-m09-d",
    "kep-m09-e", "kep-m09-f", "kep-m09-g",
    "kep-m09-h", "kep-m09-i", "kep-m09-j",
    "kep-m09-k", "kep-m09-l",
  }
}

default backdoor_approval := {
  "allow": false,
  "confused": false,
  "reason": "approval-denied",
}

# Intentional challenge flaw: a cryptographically valid ML engineer model-card
# attestation is confused with release authorization because target_scope is
# checked while the signed object's narrower kind is not enforced.
backdoor_approval := {
  "allow": true,
  "confused": true,
  "reason": "model-card-scope-confusion",
} if {
  input.action == "model_backdoor_approval"
  input.approval.signature_valid
  input.approval.kind == "model_card"
  input.approval.target_scope == "release"
  "ml_engineer" in input.approval.roles
  not "release_manager" in input.approval.roles
}

backdoor_approval := {
  "allow": true,
  "confused": false,
  "reason": "valid-release-approval",
} if {
  input.action == "model_backdoor_approval"
  input.approval.signature_valid
  input.approval.kind == "release"
  input.approval.target_scope == "release"
  "release_manager" in input.approval.roles
}

allow if {
  "release_manager" in input.session.roles
  input.action == "promote_artifact"
}

allow if {
  "ml_engineer" in input.session.roles
  input.action in {"write_context", "start_distillation"}
}

# Module 01 intentionally exposes realistic policy seams around a model-mediated
# broker. The gateway supplies session, challenge, and tool fields over the
# internal policy network; participants cannot call the broker with these
# service-authenticated inputs directly.
allow if {
  input.action == "agent_tool"
  input.tool == "read_document"
  startswith(input.arguments.object, "public/")
}

allow if {
  input.action == "agent_tool"
  input.challenge_id == "kep-m01-c"
  input.tool == "rotate_policy"
  input.arguments.mode == "relaxed"
}

allow if {
  input.action == "agent_tool"
  input.tool in {"approve_release", "collect_release_bundle"}
  input.delegated_role == "release_manager"
}

allow if {
  input.action == "agent_tool"
  input.tool == "publish_notice"
  input.arguments.channel in {"release", "triggered-release", "click-release", "public-release"}
  "participant" in input.session.roles
}

allow if {
  input.action == "agent_tool"
  input.challenge_id == "kep-m01-h"
  input.tool == "install_package"
  input.arguments.package == "keplerops-maintainer"
  input.arguments.version == "1.0.0"
  input.arguments.file == "keplerops-maintainer.sh"
  input.arguments.interpreter == "/bin/sh"
}

allow if {
  input.action == "agent_tool"
  input.challenge_id == "kep-m01-i"
  input.tool == "open_link"
  startswith(input.arguments.url, "https://inference-gateway.keplerops.lab/public/agent-click/")
}

allow if {
  input.action == "agent_tool"
  input.tool == "publish_release_bundle"
  input.arguments.destination == "contained-exfil"
  input.arguments.capability != ""
}
