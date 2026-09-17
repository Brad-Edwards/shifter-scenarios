"""Guest enrollment transfer and launch boundaries use synthetic credentials."""

import importlib.util
import json
import os
from pathlib import Path

import pytest


def module():
    asset = Path(__file__).parents[1] / "src/shifter_panw_adapter/assets/model-client-setup.py"
    spec = importlib.util.spec_from_file_location("guest_setup", asset)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_atomic_transfer_keeps_enrollment_parent_and_lock_owned_by_provisioner(tmp_path):
    source, target = tmp_path / "enrollment", tmp_path / "client"
    source.mkdir(mode=0o700)
    session = source / "session.json"
    session.write_text(json.dumps({"synthetic": "opaque guest capability"}))
    session.chmod(0o600)
    (source / "helper.py").write_text("# trusted helper")
    (source / "session.lock").write_text("")
    (source / "session.lock").chmod(0o600)
    setup = module()
    setup.transfer_enrollment(source, target, os.getuid(), os.getgid())
    assert not session.exists()
    assert json.loads((target / "session.json").read_text()) == {"synthetic": "opaque guest capability"}
    assert (source / "session.lock").stat().st_uid == os.getuid()
    assert source.stat().st_mode & 0o777 == 0o700
    assert target.stat().st_mode & 0o777 == 0o700
    assert (target / "session.json").stat().st_mode & 0o777 == 0o600
    assert (target / "helper.py").read_text() == "# trusted helper"
    # A fresh host enrollment on retry can use the original root-owned lock.
    session.write_text('{"synthetic":"replacement"}')
    session.chmod(0o600)
    setup.transfer_enrollment(source, target, os.getuid(), os.getgid())
    assert json.loads((target / "session.json").read_text()) == {"synthetic": "replacement"}


@pytest.mark.parametrize("attack", ["source-link", "target-link", "readable-session", "hardlink"])
def test_unsafe_state_is_rejected_before_replacing_client_state(tmp_path, attack):
    setup = module()
    source, target = tmp_path / "enrollment", tmp_path / "client"
    source.mkdir(mode=0o700)
    target.mkdir(mode=0o700)
    session = source / "session.json"
    session.write_text("{}")
    session.chmod(0o600)
    (source / "helper.py").write_text("# trusted helper")
    (target / "session.json").write_text("incumbent")
    if attack == "source-link":
        actual = source
        source = tmp_path / "source-link"
        source.symlink_to(actual)
    elif attack == "target-link":
        actual = target
        target = tmp_path / "target-link"
        target.symlink_to(actual)
    elif attack == "readable-session":
        session.chmod(0o644)
    else:
        os.link(session, source / "linked-state")
    with pytest.raises(ValueError):
        setup.transfer_enrollment(source, target, os.getuid(), os.getgid())
    assert (target / "session.json").read_text() == "incumbent"


def test_launcher_removes_provider_credentials_and_uses_refresh_helper_without_token_arguments():
    asset = Path(__file__).parents[1] / "src/shifter_panw_adapter/assets/model-client.py"
    spec = importlib.util.spec_from_file_location("guest_launcher", asset)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    config = {
        "broker_url": "https://broker.example.test",
        "main_model": "model.main",
        "small_model": "model.small",
        "max_output_tokens": 1024,
    }
    argv, env = loaded.launch_command(
        config,
        ["-p", "hello"],
        {
            "HOME": "/home/kali",
            "AWS_SECRET_ACCESS_KEY": "synthetic-provider-secret",
            "GOOGLE_APPLICATION_CREDENTIALS": "/some/key.json",
            "ANTHROPIC_API_KEY": "synthetic-key",
            "CLAUDE_CODE_USE_VERTEX": "1",
            "NODE_OPTIONS": "--require /untrusted.js",
            "HTTPS_PROXY": "http://untrusted.example.test",
        },
    )
    assert argv[-2:] == ["-p", "hello"]
    assert env["HOME"] == "/home/kali"
    assert env["ANTHROPIC_BASE_URL"] == config["broker_url"]
    assert env["CLAUDE_CODE_API_KEY_HELPER_TTL_MS"] == "1000"
    assert env["DISABLE_PROMPT_CACHING"] == "1"
    assert env["DISABLE_INTERLEAVED_THINKING"] == "1"
    for key in (
        "AWS_SECRET_ACCESS_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "ANTHROPIC_API_KEY",
        "CLAUDE_CODE_USE_VERTEX",
        "NODE_OPTIONS",
        "HTTPS_PROXY",
    ):
        assert key not in env
    assert all("synthetic" not in item for item in argv)
    assert "--require" in argv and "--settings" in argv
