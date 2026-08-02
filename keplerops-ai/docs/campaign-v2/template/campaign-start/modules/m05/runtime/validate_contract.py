#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1]
CAMPAIGN = MODULE.parents[1]
TEMPLATE = CAMPAIGN.parent
SHARED_AGENT = TEMPLATE / "platform/images/orion-agent/agent_service.py"


def function_args(path: Path, name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return [item.arg for item in node.args.args]
    raise AssertionError(f"{path}: missing {name}")


def shell_dispatch(path: Path, prefix: str) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(re.findall(rf"^{re.escape(prefix)}(m05_[a-q])\(\)", text, re.MULTILINE))


def main() -> None:
    operations = json.loads((MODULE / "operations.json").read_text(encoding="utf-8"))
    ids = [item["id"] for item in operations]
    assert ids == [f"kep-m05-{suffix}" for suffix in "abcdefghijklmnopq"]
    assert sum(int(item["points"]) for item in operations) == 4000
    assert len({item["flag"] for item in operations}) == 17

    shared_abi = function_args(SHARED_AGENT, "run_agent")
    campaign_abi = function_args(MODULE / "runtime/release_assistant_extensions.py", "campaign_run_agent")
    assert shared_abi == campaign_abi == [
        "prompt", "actor", "conversation_id", "metadata", "request_id", "trace_id", "traceparent"
    ]

    expected_dispatch = {f"m05_{suffix}" for suffix in "abcdefghijklmnopq"}
    assert shell_dispatch(MODULE / "apply.sh", "apply_") == expected_dispatch
    assert shell_dispatch(MODULE / "validate.sh", "validate_") == expected_dispatch
    assert shell_dispatch(MODULE / "reset.sh", "reset_") == expected_dispatch

    agent_text = (MODULE / "runtime/release_assistant_extensions.py").read_text(encoding="utf-8")
    validator_text = (MODULE / "validate.sh").read_text(encoding="utf-8")
    reset_text = (MODULE / "reset.sh").read_text(encoding="utf-8")
    assert "_qualifying_preference" not in agent_text
    assert "request.user" not in agent_text
    assert "prompt_sha256" in agent_text and "causal_context" in agent_text
    assert "/v1/campaign/" not in agent_text + validator_text
    assert "TRANSCRIPT" not in validator_text
    assert "_URL" not in "\n".join(line for line in validator_text.splitlines() if "require_env" in line)
    assert "replace-disposable-workers.sh" not in reset_text
    assert "removed_messages" in agent_text and "orion:attempt:" in reset_text
    assert "M05_ACCEPTED_OPERATIONS" not in reset_text
    assert "M05_ACTOR" not in reset_text and "M05_CONVERSATION_ID" not in reset_text
    assert "M05_LIBRECHAT_CONVERSATION_ID" not in reset_text
    assert "M05_ATTEMPT_ID" in reset_text and "attempt_id=?" in reset_text
    assert "resource_keys" in agent_text and "source_workflow_id" in reset_text
    for causal_reference in (
        "causal_context.memory.record_id",
        "causal_context.shared_room.planting_actor",
        "causal_context.configuration.reference",
    ):
        assert causal_reference in validator_text

    tool_workflow = (MODULE / "payloads/repositories/orion-release-tools/.forgejo/workflows/tool-contract-and-publish.yml").read_text()
    config_workflow = (MODULE / "payloads/repositories/orion-agent-config/.forgejo/workflows/config-contract-and-publish.yml").read_text()
    for workflow in (tool_workflow, config_workflow):
        for required in ("buildctl build", "cosign sign", "cosign verify", "orion-agent-gitops"):
            assert required in workflow
        assert "runs-on: m05-orion-release-linux" in workflow
        assert "RELEASE_ADMISSION_USER" in workflow
        assert "actions/checkout" not in workflow
    assert "runtime/" not in tool_workflow
    assert "reports/deployments/${GITHUB_SHA}.json" in config_workflow
    drift_workflow = (MODULE / "payloads/gitops/drift-workflow.yml").read_text()
    assert "WORKFLOW_RUN_ID" in drift_workflow and "M05_DRIFT_RUN_ID" in validator_text
    assert "/deployed/release-source.json" not in (MODULE / "runtime/release_source_service.py").read_text()
    assert "selection_proof" in (MODULE / "runtime/release_source_service.py").read_text()

    apply_text = (MODULE / "apply.sh").read_text(encoding="utf-8")
    opa_manifest = (TEMPLATE / "platform/manifests/opa.yaml").read_text(encoding="utf-8")
    workhub_policy = opa_manifest.split("workhub.rego: |", 1)[1].split("---", 1)[0]
    release_policy = opa_manifest.split("release.rego: |", 1)[1].split("workhub.rego: |", 1)[0]
    assert "configure_agent_policy" not in apply_text
    for tool in (
        "save_release_preference",
        "forgejo_ci_status",
        "inspect_release_source",
        "review_registry_status",
    ):
        assert tool in workhub_policy and tool not in release_policy

    gateway = (MODULE / "runtime/orion_session_gateway.py").read_text(encoding="utf-8")
    for required in (
        "MONGO.conversations.find_one",
        'headers.get("X-LibreChat-User-ID")',
        'body["user"] = actor',
        '"conversation_id": identifier',
        '"audience": SESSION_AUDIENCE',
        '"request_sha256": request_sha256',
        '"nonce": secrets.token_hex(16)',
        "expires_at",
    ):
        assert required in gateway
    assert 'resolved_identity(str(body.get("user")' not in gateway
    assert "IDENTITY_TOKENS" not in gateway
    for required in (
        '@app.middleware("http")',
        'payload.get("provider") != "librechat"',
        'request.url.path == "/v1/chat/completions"',
        'hashlib.sha256(body).hexdigest()',
        'payload.get("conversation_id")',
        'orion:session-assertion:',
        'nx=True',
    ):
        assert required in agent_text
    librechat = (MODULE / "payloads/librechat/librechat.yaml").read_text(encoding="utf-8")
    assert "{{LIBRECHAT_USER_ID}}" in librechat

    for forbidden in (
        "M05_MLFLOW_APPLICATION_TOKEN",
        "M05_SUPPORT_SESSION",
        "M05_HARBOR_ROBOT_SECRET",
    ):
        assert forbidden not in validator_text
    protected_validation = validator_text[
        validator_text.index("validate_m05_h()") : validator_text.index("validate_m05_l()")
    ]
    assert "-X DELETE" not in protected_validation
    assert "access-evidence/v1" in apply_text
    for operation in ("kep-m05-h", "kep-m05-i", "kep-m05-j", "kep-m05-k"):
        assert f"evidence_for {operation}" in validator_text
    assert "M05_EFFECT_REQUEST_ID" in validator_text
    assert "prompt_sha256" in validator_text

    compose = (MODULE / "compose.overlay.yaml").read_text(encoding="utf-8")
    assert "payloads/librechat/librechat.yaml:/app/librechat.yaml:ro" in compose
    assert "m05-orion-dataset-worker" in compose and "m05-cinder-transport" in compose
    assert "m05-worker-authority" in compose and "m05-orion-session-gateway" in compose
    assert "/var/run/docker.sock" not in compose
    assert "m05-source-admission" in compose and "m05-buildkit" in compose
    assert 'user: "1000:1000"' in compose and "read_only: true" in compose
    worker = (MODULE / "runtime/orion_dataset_worker.py").read_text(encoding="utf-8")
    assert "/v1/c2/carrier" not in worker and "/internal/transport-carrier" not in worker
    assert "/v1/release-reconciliation/current" in worker and "/v1/review-exports/pending" in worker
    assert 'path.startswith("/v1/agents/registration-")' in worker
    admission = (MODULE / "runtime/source_admission.py").read_text(encoding="utf-8")
    assert '"orion-release-tools": (re.compile(r"^tool/release-source\\.json$")' in admission
    assert '"orion-agent-config": (re.compile(r"^agent\\.yaml$")' in admission
    assert "required_path in" in admission and "merge_when_checks_succeed" in admission
    bridge = (MODULE / "runtime/host_bridge.py").read_text(encoding="utf-8")
    assert 'policy.get("attempt_id")' in bridge and 'policy.get("expires_at")' in bridge
    runtime = (MODULE / "runtime/orion_agent_runtime.py").read_text(encoding="utf-8")
    assert "provider-binding.json" in runtime and "reports/latest-status.json" in runtime
    transport = (MODULE / "runtime/cinder_transport.py").read_text(encoding="utf-8")
    assert "worker_registration_id" in transport and "worker_proof" in transport
    assert "tasks_attempt_nonce_unique" in transport
    assert "result does not match the worker proof recorded at claim" in transport
    assert "SELECT * FROM worker_proofs WHERE proof=? AND registration_id=?" in transport
    assert "COALESCE(worker_registration_id,'')=?" in transport
    reset = (MODULE / "reset.sh").read_text(encoding="utf-8")
    for exact_dispatch in (
        'reset_m05_e() { require_env M05_ATTEMPT_ID; reset_source_attempt orion-release-tools',
        'reset_m05_l() { require_env M05_ATTEMPT_ID; reset_worker_attempt',
        'reset_m05_m() { require_env M05_ATTEMPT_ID; reset_source_attempt orion-agent-config',
        'reset_m05_n() { require_env M05_ATTEMPT_ID; reset_worker_attempt',
        'reset_m05_o() { require_env M05_ATTEMPT_ID; reset_bridge_attempt',
        'reset_m05_q() { require_env M05_ATTEMPT_ID; reset_transport_attempt',
    ):
        assert exact_dispatch in reset
    assert "DELETE FROM worker_proofs WHERE task_id IN" in reset
    assert "db.messages.deleteMany" in reset and "db.conversations.delete" not in reset
    worker = (MODULE / "runtime/orion_dataset_worker.py").read_text(encoding="utf-8")
    assert "attempt_id does not name a server-issued worker attempt" in worker
    assert "process identity changed; refusing reset" in worker
    assert "dataset bytes changed after this attempt; refusing reset" in worker
    authority = (MODULE / "runtime/worker_authority.py").read_text(encoding="utf-8")
    assert '"attempt_id": attempt_id' in authority and "def reset_attempt(attempt_id" in authority
    admission = (MODULE / "runtime/source_admission.py").read_text(encoding="utf-8")
    assert '"parent_commit": str(pull["base"]["sha"])' in admission
    assert "source moved after this attempt; refusing to overwrite unrelated work" in admission
    assert "def reset_attempt(repository: str, commit: str)" in admission
    assert "def reset_attempt(attempt_id: str)" in bridge
    integrations = json.loads((MODULE / "integrations.json").read_text(encoding="utf-8"))
    assert set(integrations["operations"]) == set(ids)
    network = integrations["network_contract"]
    assert len(network) == len({(row["source"], row["destination"], row["protocol"], row["ports"]) for row in network})
    assert all(not row["destination"].startswith("label:") for row in network)
    assert any(row["source"] == "kep-v2-m05-source-admission" and row["destination"] == "kep-v2-forgejo" and row["ports"] == "3000" for row in network)
    assert any(row["source"] == "kep-v2-m05-buildkit" and row["destination"] == "kep-v2-caddy" and row["ports"] == "443" for row in network)

    participant_payloads = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (MODULE / "payloads").rglob("*")
        if path.is_file()
    )
    assert not re.search(r"kep-m05-[a-q]", participant_payloads)
    assert not re.search(r"m05-runtime|FORGEJO_M05|agent_campaign|mcp_campaign", participant_payloads)
    assert not re.search(r"\bparticipant\b|\bchallenge\b|\bvalidator\b|negative control", participant_payloads, re.IGNORECASE)
    print("m05 contract validation passed: metadata, ABI, dispatch, native evidence, reset, and integrations")


if __name__ == "__main__":
    main()
