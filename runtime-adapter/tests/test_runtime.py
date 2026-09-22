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
        if provider == "gcp":
            assert "socket.getaddrinfo" not in model_files
            assert "socket.getaddrinfo" in container_bootstrap
            assert "BROKER_HOST_ENTRY" in container_bootstrap
            assert "extra_hosts:" in container_bootstrap
            assert '"$BROKER_HOST_ENTRY"' in container_bootstrap
        else:
            assert "socket.getaddrinfo" not in model_files
            assert "socket.getaddrinfo" not in container_bootstrap
            assert "extra_hosts:" not in container_bootstrap
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
        assert 'test "$client_status" = "model-client-ready"' in result_check
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
