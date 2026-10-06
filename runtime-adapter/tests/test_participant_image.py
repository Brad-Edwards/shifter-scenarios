"""The participant image never bakes Claude Code; Shifter delivers it to the host."""

import json
import tarfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD = REPO_ROOT / "polaris/build"
DELIVERY_DIR = "/opt/shifter/bin"


def test_image_links_the_delivered_client_instead_of_installing_one():
    dockerfile = (BUILD / "a14/Dockerfile").read_text()
    assert "@anthropic-ai/claude-code" not in dockerfile
    assert f"RUN ln -s {DELIVERY_DIR}/claude /usr/local/bin/claude" in dockerfile

    compose = yaml.safe_load((BUILD / "docker-compose.yml").read_text())
    assert f"{DELIVERY_DIR}:{DELIVERY_DIR}:ro" in compose["services"]["a14-kali"]["volumes"]

    readiness = json.loads((BUILD / "a14/participant-readiness.json").read_text())
    assert "client" not in readiness
    assert "/usr/local/bin/claude" not in (BUILD / "a14/shifter-participant-readiness").read_text()

    with tarfile.open(BUILD / "build-v1.tar.gz", "r:gz") as package:
        for name in ("a14/Dockerfile", "docker-compose.yml", "a14/participant-readiness.json"):
            archived = package.extractfile(f"polaris/build/{name}")
            assert archived is not None
            assert archived.read() == (BUILD / name).read_bytes()


def test_runtime_pack_declares_the_client_for_delivery_to_the_mounted_directory():
    scenario = yaml.safe_load((REPO_ROOT / "runtime-pack/polaris-direct/sdl/polaris.sdl.yaml").read_text())
    feature = scenario["features"]["claude-code"]
    assert feature == {"type": "artifact", "source": "claude-code", "destination": f"{DELIVERY_DIR}/claude"}
    host = scenario["nodes"]["a14-kali"]
    assert host["features"] == {"claude-code": "participant"}
    assert host["roles"]["participant"]["username"] == "kali"
