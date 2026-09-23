"""Private acceptance of the packaged planner on both clouds; no cloud mutations."""

import ast
import importlib.util
import re
import subprocess
from importlib.resources import files
from uuid import uuid4

import pytest
from shifter_adapter_sdk.runtime import PROTOCOL, PluginManifest, RuntimeInput, parse_result

from shifter_panw_adapter.bootstrap import AwsModelAccess, GcpModelAccess, build_plan


@pytest.fixture(params=["aws", "gcp"])
def provider(request):
    return request.param


def model_access(provider, **changes):
    data = {"provider": provider, "range_id": 7, "main_model": "model.main", "small_model": "model.small"}
    if provider == "aws":
        data.update(
            role_arn="arn:aws:iam::123456789012:role/range-7-model",
            region="us-east-2",
            environment="acceptance",
            session_seconds=900,
            refresh_seconds=300,
        )
        cls = AwsModelAccess
    else:
        data.update(project="test-project", region="global", secret_ref="projects/test-project/secrets/range-7-model")
        cls = GcpModelAccess
    data.update(changes)
    return cls.model_validate(data)


def invocation(provider, phase):
    manifest = PluginManifest(
        protocol=PROTOCOL,
        plugin_id="panw.polaris",
        version="0.1.0",
        distribution="shifter-panw-adapter",
        entry_point="polaris",
        worker_image="registry.example.test/private/adapter@sha256:" + "a" * 64,
        capabilities=["guest.configure", "guest.verify"],
        required_bindings=["host", "directory"],
    )
    return RuntimeInput(
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
    )


@pytest.mark.parametrize("phase", ["validate", "configure", "verify", "cleanup"])
def test_both_clouds_produce_authorized_bounded_sdk_plans(provider, phase):
    request = invocation(provider, phase)
    plan = build_plan(request, model_access(provider))
    assert parse_result(plan.model_dump_json(), request) == plan
    for action in plan.actions:
        result = subprocess.run(["/bin/bash", "-n"], input=action.script, text=True, capture_output=True, timeout=5)
        assert result.returncode == 0, (action.action_id, result.stderr)
        assert not re.search(r"\{\{\s*[a-z_][a-z0-9_]*\s*\}\}", action.script)
    if phase in {"validate", "cleanup"}:
        assert not plan.actions


def test_firewall_precedes_container_recreation_on_aws():
    plan = build_plan(invocation("aws", "configure"), model_access("aws"))
    assert [a.action_id for a in plan.actions] == [
        "metadata-firewall",
        "container-bootstrap",
        "splice-watcher",
        "model-access",
    ]
    assert "169.254.169.254/32" in plan.actions[0].script
    assert "fd00:ec2::254/128" in plan.actions[0].script
    assert "DOCKER-USER" in plan.actions[0].script


def test_runtime_values_are_deferred_and_no_core_fetch_is_planned(provider):
    plan = build_plan(invocation(provider, "configure"), model_access(provider))
    bootstrap = next(a for a in plan.actions if a.action_id == "container-bootstrap")
    assert bootstrap.runtime_values["directory-address"].binding == "directory"
    assert bootstrap.runtime_values["participant-key"].field == "participant_ssh_public_key"
    assert "$(read_runtime_value directory-address)" in bootstrap.script
    assert "{{.Names}}" in bootstrap.script  # Docker templates survive author rendering.
    assert "polaris-splice-credential.py" in bootstrap.script
    assert "docker exec -i a14-kali chpasswd --encrypted" in bootstrap.script
    assert "getent shadow kali" in bootstrap.script
    assert all("fetch" not in a.action_id for a in plan.actions)
    assert all("PRESIGNED_URL" not in a.script for a in plan.actions)


def test_cloud_access_cannot_be_replayed_to_another_range_or_provider(provider):
    request = invocation(provider, "configure")
    with pytest.raises(ValueError, match="does not match"):
        build_plan(request, model_access(provider, range_id=8))
    with pytest.raises(ValueError, match="does not match"):
        build_plan(request, model_access("gcp" if provider == "aws" else "aws"))


@pytest.mark.parametrize("field", ["region", "main_model", "small_model"])
def test_model_values_cannot_inject_shell(provider, field):
    with pytest.raises(ValueError):
        model_access(provider, **{field: 'value"; touch /tmp/unsafe; #'})


def test_missing_exact_secret_reference_cannot_fall_back_to_platform_environment(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "platform-project")
    with pytest.raises(ValueError):
        model_access("gcp", secret_ref="")


def test_refresh_is_bounded_and_requires_time_before_expiry():
    with pytest.raises(ValueError):
        model_access("aws", session_seconds=900, refresh_seconds=900)


def test_installed_package_has_assets_and_no_core_dependencies():
    assert importlib.util.find_spec("shared") is None
    assert importlib.util.find_spec("django") is None
    assert importlib.util.find_spec("executors") is None
    package = files("shifter_panw_adapter")
    assert package.joinpath("assets/polaris-splice-credential.py").read_bytes().startswith(b"#!/usr/bin/env python3")
    for source in package.iterdir():
        if source.name.endswith(".py"):
            tree = ast.parse(source.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and not node.level:
                    assert node.module.split(".")[0] in {
                        "__future__",
                        "importlib",
                        "typing",
                        "pydantic",
                        "shifter_adapter_sdk",
                    }
