"""Production plans consume trusted enrollment, never provider credentials."""

import importlib
import subprocess
from uuid import uuid4

import pytest
from shifter_adapter_sdk.runtime import PROTOCOL, RuntimeInput, parse_result


def request(provider, phase, **changes):
    module = importlib.import_module("shifter_panw_adapter.runtime")
    manifest = module.manifest("registry.example.test/private/adapter@sha256:" + "a" * 64)
    data = dict(
        protocol=PROTOCOL,
        invocation_id=uuid4(),
        operation_id=uuid4(),
        pack_digest="sha256:" + "b" * 64,
        manifest=manifest,
        phase=phase,
        provider=provider,
        range_id=7,
        targets={
            "host": {"node_address": "node.lab", "os_family": "linux"},
            "directory": {"node_address": "node.directory", "os_family": "windows"},
        },
        parameters={"main-model": "model.main", "small-model": "model.small", "max-output-tokens": "1024"},
    )
    data.update(changes)
    return RuntimeInput(**data)


@pytest.mark.parametrize("provider", ["aws", "gcp"])
@pytest.mark.parametrize("phase", ["validate", "configure", "verify", "cleanup"])
def test_production_plans_use_only_sdk_and_trusted_guest_enrollment(provider, phase):
    invocation = request(provider, phase)
    module = importlib.import_module("shifter_panw_adapter.runtime")
    plan = module.PolarisAdapter().plan(invocation)
    assert parse_result(plan.model_dump_json(), invocation) == plan
    assert invocation.manifest.model_bindings == {"participant": "host"}
    for action in plan.actions:
        if action.binding == "host":
            syntax = subprocess.run(["bash", "-n"], input=action.script, text=True, capture_output=True, timeout=5)
            assert syntax.returncode == 0, syntax.stderr
        for forbidden in ("assume-role", "gcloud", "vertex_project_id", "role_arn", "secret_ref"):
            assert forbidden not in action.script
    if phase == "configure":
        assert [action.action_id for action in plan.actions] == [
            "directory-firewall",
            "metadata-firewall",
            "model-client-files",
            "container-bootstrap",
            "splice-watcher",
        ]
        assert plan.actions[0].binding == "directory"
        assert "Set-NetFirewallProfile" in plan.actions[0].script
        model_files = next(action.script for action in plan.actions if action.action_id == "model-client-files")
        container_bootstrap = next(
            action.script for action in plan.actions if action.action_id == "container-bootstrap"
        )
        override = container_bootstrap.split("cat > docker-compose.override.yml.new <<COMPOSE_EOF\n", 1)[1].split(
            "\nCOMPOSE_EOF", 1
        )[0]
        assert override.count("\n  dns:\n") == 1
        workstation, remainder = override.split("\n  a9-splice:\n", 1)
        assert "    entrypoint:\n      - /opt/polaris/model-client/entrypoint.sh" in workstation
        assert "\n  dns:\n" in remainder
        dns = remainder.split("\n  dns:\n", 1)[1]
        assert '      DC01_IP: "$DC_IP"' in dns
        if provider == "gcp":
            firewall = next(action.script for action in plan.actions if action.action_id == "metadata-firewall")
            assert '"$protocol" --dport 53 -j RETURN' in firewall
            assert "-d 169.254.169.254/32 -j DROP" in firewall
            assert "fd20:ce::254/128" in firewall
            assert "socket.getaddrinfo" not in model_files
            assert "socket.getaddrinfo" not in container_bootstrap
            assert "extra_hosts:" not in container_bootstrap
            assert 'DNS_FORWARDER: "169.254.169.254"' in container_bootstrap
            assert '      DNS_FORWARDER: "169.254.169.254"' in dns
        else:
            assert "socket.getaddrinfo" not in model_files
            assert "socket.getaddrinfo" not in container_bootstrap
            assert "extra_hosts:" not in container_bootstrap
            assert "DNS_FORWARDER:" not in dns
    elif phase == "verify":
        assert [action.action_id for action in plan.actions] == [
            "directory-firewall-ready",
            "bootstrap-ready",
            "model-client-ready",
            "model-client-result",
        ]
        assert plan.actions[0].binding == "directory"
        assert "Get-NetFirewallProfile" in plan.actions[0].script
        result_check = next(action.script for action in plan.actions if action.action_id == "model-client-result")
        assert 'model-client-ready) exit 0' in result_check
        assert 'broker-transport-failed) exit 43' in result_check
    elif phase == "cleanup":
        assert plan.actions
    else:
        assert not plan.actions


@pytest.mark.parametrize(
    "parameters",
    [
        {"main-model": "model.main; touch /tmp/bad", "small-model": "model.small", "max-output-tokens": "1024"},
        {"main-model": "model.main", "small-model": "model.small", "max-output-tokens": "0"},
    ],
)
def test_untrusted_parameters_cannot_become_shell_or_unbounded_model_requests(parameters):
    invocation = request("gcp", "configure", parameters=parameters)
    module = importlib.import_module("shifter_panw_adapter.runtime")
    with pytest.raises(ValueError):
        module.PolarisAdapter().plan(invocation)


def test_missing_model_binding_cannot_fall_back_to_legacy_provider_credentials():
    invocation = request("aws", "configure")
    module = importlib.import_module("shifter_panw_adapter.runtime")
    invocation = invocation.model_copy(
        update={"manifest": invocation.manifest.model_copy(update={"model_bindings": {}})}
    )
    with pytest.raises(ValueError):
        module.PolarisAdapter().plan(invocation)


@pytest.mark.parametrize(
    ("marker", "exit_code"),
    [
        ("model-client-ready", 0),
        ("client-exited-before-request", 41),
        ("request-normalization-failed", 42),
        ("broker-transport-failed", 43),
        ("broker-response-200", 44),
        ("broker-response-400", 45),
        ("broker-response-401", 46),
        ("broker-response-403", 46),
        ("broker-response-404", 47),
        ("broker-response-429", 48),
        ("broker-response-503", 49),
        ("broker-response-502-provider_unavailable", 49),
        ("broker-response-422", 50),
        ("unrecognized", 59),
    ],
)
def test_model_client_check_returns_only_bounded_diagnostic_exit_code(marker, exit_code):
    import os

    module = importlib.import_module("shifter_panw_adapter.runtime")
    script = module._CHECK_CLIENT
    fake_docker = """docker() {
  case "$*" in
    *'test -f'*) return 0 ;;
    *'cat /tmp/polaris-model-client-status'*) printf '%s\\n' "$TEST_MARKER" ;;
    *'rm -f'*) return 0 ;;
    *) return 99 ;;
  esac
}
"""
    result = subprocess.run(
        ["bash", "-c", fake_docker + script],
        env={**os.environ, "TEST_MARKER": marker},
        text=True,
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == exit_code
    assert not result.stdout
    assert not result.stderr


def test_sdk_worker_loads_the_exact_installed_entrypoint_in_a_clean_process():
    import json
    import os
    import sys

    from shifter_adapter_sdk.runtime import InspectionInput, InspectionResult

    invocation = request("gcp", "configure")
    inspection = InspectionInput(
        protocol=PROTOCOL, invocation_id=uuid4(), phase="inspect", manifest=invocation.manifest
    )
    for value in (inspection, invocation):
        result = subprocess.run(
            [sys.executable, "-m", "shifter_adapter_sdk.worker"],
            env={"PATH": os.environ.get("PATH", ""), "SHIFTER_PLUGIN_INPUT": value.model_dump_json()},
            text=True,
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        assert not result.stderr
        if isinstance(value, InspectionInput):
            observed = InspectionResult.model_validate(json.loads(result.stdout))
            observed.authorize(value)
            assert observed.status == "compatible"
        else:
            assert parse_result(result.stdout, value).status == "planned"
