"""Direct Vertex is a separate, broker-free plugin with real guest verification."""

import subprocess
from uuid import uuid4

import pytest
from shifter_adapter_sdk.runtime import PROTOCOL, RuntimeInput, parse_result

from shifter_panw_adapter.runtime_direct import PolarisDirectAdapter, manifest


def request(phase="configure", provider="gcp", parameters=None):
    return RuntimeInput(
        protocol=PROTOCOL,
        invocation_id=uuid4(),
        operation_id=uuid4(),
        pack_digest="sha256:" + "b" * 64,
        manifest=manifest("registry.example.test/private/adapter@sha256:" + "a" * 64),
        phase=phase,
        provider=provider,
        range_id=7,
        targets={
            "host": {"node_address": "node.lab", "os_family": "linux"},
            "directory": {"node_address": "node.directory", "os_family": "windows"},
        },
        parameters=parameters or {
            "project": "prod-qjpjnv",
            "region": "us-east5",
            "main-model": "claude-sonnet-4-6",
            "small-model": "claude-haiku-4-5",
        },
    )


@pytest.mark.parametrize("phase", ["validate", "configure", "verify", "cleanup"])
def test_direct_plan_uses_container_identity_without_broker(phase):
    invocation = request(phase)
    plan = PolarisDirectAdapter().plan(invocation)
    assert parse_result(plan.model_dump_json(), invocation) == plan
    assert invocation.manifest.model_bindings == {}
    for action in plan.actions:
        if action.binding == "host":
            syntax = subprocess.run(["bash", "-n"], input=action.script, text=True, capture_output=True, timeout=5)
            assert syntax.returncode == 0, syntax.stderr
        assert "/run/polaris-model-access" not in action.script
        assert "model-client/entrypoint.sh" not in action.script
    if phase == "configure":
        assert [action.action_id for action in plan.actions] == [
            "directory-firewall", "container-bootstrap", "vertex-shell-env", "splice-watcher"
        ]
        bootstrap = plan.actions[1].script
        assert 'CLAUDE_CODE_USE_VERTEX: "1"' in bootstrap
        assert 'CLOUD_ML_REGION: "us-east5"' in bootstrap
        assert 'ANTHROPIC_VERTEX_PROJECT_ID: "prod-qjpjnv"' in bootstrap
        assert 'DNS_FORWARDER: "169.254.169.254"' in bootstrap
        assert "- /usr/local/libexec/polaris-splice-credential.py" in bootstrap
        shell_env = plan.actions[2].script
        assert "export CLAUDE_CODE_USE_VERTEX=1" in shell_env
        assert "export ANTHROPIC_VERTEX_PROJECT_ID=prod-qjpjnv" in shell_env
        assert "export CLOUD_ML_REGION=us-east5" in shell_env
        assert "/etc/profile.d/polaris-vertex.sh" in shell_env
        assert "/home/kali/.bashrc" in shell_env
    if phase == "verify":
        assert [action.action_id for action in plan.actions] == [
            "directory-firewall-ready", "bootstrap-ready", "vertex-ready"
        ]
        assert "/usr/local/bin/claude -p" in plan.actions[2].script
        assert "--output-format json" in plan.actions[2].script
        assert 'response.get("is_error")' in plan.actions[2].script
        assert 'get("output_tokens",0)' in plan.actions[2].script


def test_direct_variant_rejects_other_clouds():
    with pytest.raises(ValueError, match="Incompatible direct Vertex"):
        PolarisDirectAdapter().plan(request(provider="aws"))


def test_direct_variant_rejects_shell_metacharacters():
    with pytest.raises(ValueError, match="Invalid project"):
        PolarisDirectAdapter().plan(request(parameters={
            "project": "prod-qjpjnv; touch /tmp/bad",
            "region": "us-east5",
            "main-model": "claude-sonnet-4-6",
            "small-model": "claude-haiku-4-5",
        }))
