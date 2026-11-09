"""Cinder runtime planning is limited to public-CA pairing and readiness."""

import subprocess
from uuid import uuid4

import pytest
from shifter_adapter_sdk.runtime import PROTOCOL, RuntimeInput, parse_result

from shifter_panw_adapter.runtime_cinder import CinderTyphoonDirectAdapter, manifest


def request(phase="configure", provider="gcp"):
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
            "training": {"node_address": "provision.node.training-host", "os_family": "linux"},
            "keplerops": {"node_address": "provision.node.keplerops-host", "os_family": "linux"},
            "arwc": {"node_address": "provision.node.arwc-host", "os_family": "linux"},
        },
    )


@pytest.mark.parametrize("phase", ["validate", "configure", "verify"])
def test_cinder_plan_is_authorized_and_shell_valid(phase):
    invocation = request(phase)
    plan = CinderTyphoonDirectAdapter().plan(invocation)
    assert parse_result(plan.model_dump_json(), invocation) == plan
    for action in plan.actions:
        syntax = subprocess.run(["bash", "-n"], input=action.script, text=True, capture_output=True, timeout=5)
        assert syntax.returncode == 0, (action.action_id, syntax.stderr)
        assert "gcloud" not in action.script
        assert "terraform" not in action.script
        assert "PRIVATE KEY" not in action.script


def test_configure_only_pairs_existing_image_helpers():
    actions = CinderTyphoonDirectAdapter().plan(request("configure")).actions
    assert [action.action_id for action in actions] == [
        "keplerops-ca-export",
        "arwc-ca-export",
        "keplerops-peer-import",
        "arwc-peer-import",
        "keplerops-ca-export-stop",
        "arwc-ca-export-stop",
    ]
    assert actions[2].runtime_values["arwc-address"].field == "private_address"
    assert actions[2].runtime_values["arwc-address"].binding == "arwc"
    assert actions[3].runtime_values["keplerops-address"].binding == "keplerops"
    assert all("/usr/local/libexec/cinder-peer-ca" in action.script for action in actions)


def test_verify_delegates_to_image_owned_readiness():
    actions = CinderTyphoonDirectAdapter().plan(request("verify")).actions
    assert [action.action_id for action in actions] == ["training-ready", "keplerops-ready", "arwc-ready"]
    assert [action.binding for action in actions] == ["training", "keplerops", "arwc"]
    assert all("/usr/local/libexec/cinder-image-verify" in action.script for action in actions)


def test_cinder_variant_rejects_other_clouds():
    with pytest.raises(ValueError, match="Incompatible Cinder Typhoon"):
        CinderTyphoonDirectAdapter().plan(request(provider="aws"))
