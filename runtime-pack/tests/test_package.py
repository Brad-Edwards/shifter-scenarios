"""The installable outer runtime package is validated independently of Shifter."""

import importlib.util
import json
import shutil
import tarfile
from pathlib import Path

import yaml
from raes.scenarios import load_scenario
from raes_env_packs import pack_content_digest, validate_pack, verify_pack_content_digest

ROOT = Path(__file__).parents[1] / "polaris-direct"
CINDER_ROOT = Path(__file__).parents[1] / "cinder-typhoon-direct"


def test_package_is_conformant_and_digest_bound():
    # The pack declares no broker model demand; the direct plugin uses Vertex.
    assert not (ROOT / "model-needs.json").exists()
    result = validate_pack(ROOT)
    assert result.errors == []
    digest = pack_content_digest(ROOT)
    assert verify_pack_content_digest(ROOT, digest)


def test_outer_hosts_use_allocated_addresses_and_explicit_participant_access():
    source = ROOT / "sdl/polaris.sdl.yaml"
    load_scenario(source)
    data = yaml.safe_load(source.read_text())
    assert set(data["nodes"]) == {"a14-kali", "dc01"}
    assert "infrastructure" not in data
    access = data["agents"]["participant"]["interactive_access"]["kali_ssh"]
    assert access == {"target_ref": "a14-kali", "channel": "ssh", "account_ref": "kali_login"}
    assert data["accounts"]["kali_login"]["auth_method"] == "key"
    rdp = data["agents"]["participant"]["interactive_access"]["kali_rdp"]
    assert rdp == {"target_ref": "a14-kali", "channel": "rdp", "account_ref": "kali_desktop_login"}
    assert data["accounts"]["kali_desktop_login"]["auth_method"] == "password"
    assert data["nodes"]["a14-kali"]["os_distribution"] == "debian"
    assert data["nodes"]["a14-kali"]["os_version"] == "12"
    assert data["nodes"]["dc01"]["os_distribution"] == "windows-server"
    assert data["nodes"]["dc01"]["os_version"] == "2022"


def test_archive_is_reproducible_and_contains_exactly_the_validated_package(tmp_path):
    spec = importlib.util.spec_from_file_location("pack_builder", ROOT.parent / "build.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.ROOT = tmp_path / "polaris-direct"
    shutil.copytree(ROOT, builder.ROOT)
    first, second = tmp_path / "first.tar", tmp_path / "second.tar"
    digest = builder.build(first)
    assert builder.build(second) == digest
    assert first.read_bytes() == second.read_bytes()
    expected = {
        str(path.relative_to(tmp_path)): path.read_bytes() for path in builder.ROOT.rglob("*") if path.is_file()
    }
    with tarfile.open(first) as archive:
        assert set(archive.getnames()) == set(expected)
        for member in archive.getmembers():
            assert member.isfile() and member.mode == 0o644
            assert archive.extractfile(member).read() == expected[member.name]
        pack = yaml.safe_load(archive.extractfile("polaris-direct/pack.yaml").read())
        assert pack["name"] == "polaris-direct"
        scenario = yaml.safe_load(archive.extractfile("polaris-direct/sdl/polaris.sdl.yaml").read())
        assert scenario["name"] == "polaris-direct"


def test_binding_matches_the_host_build():
    import hashlib

    binding = json.loads((ROOT.parent / "polaris-direct.binding.json").read_text())
    host = binding["image_profiles"]["host"]
    readiness = ROOT.parents[1] / "polaris/build/a14/participant-readiness.json"
    assert host["participant_readiness_manifest_sha256"] == hashlib.sha256(readiness.read_bytes()).hexdigest()
    image = host["image_ref"].rsplit("/", 1)[1]
    guide = (ROOT.parent / "BINDING.md").read_text()
    assert f"| Host image | `{image}` |" in guide
    assert f"| Host readiness digest | `{host['participant_readiness_manifest_sha256']}` |" in guide


def test_cinder_package_is_conformant_and_uses_only_three_outer_hosts():
    result = validate_pack(CINDER_ROOT)
    assert result.errors == []
    source = CINDER_ROOT / "sdl/cinder-typhoon.sdl.yaml"
    load_scenario(source)
    data = yaml.safe_load(source.read_text())
    assert set(data["nodes"]) == {"training-host", "keplerops-host", "arwc-host"}
    assert "infrastructure" not in data
    assert all(
        constraint["domain"] == {"kind": "exact", "value": "virtual-machine"}
        for constraint in data["realization"]["constraints"]
    )
    assert set(data["agents"]["participant"]["interactive_access"]) == {"training_rdp", "keplerops_rdp"}
    assert {access["channel"] for access in data["agents"]["participant"]["interactive_access"].values()} == {
        "rdp"
    }


def test_cinder_registry_mapping_uses_exact_private_images_and_current_readiness_manifests():
    import hashlib

    binding = json.loads((CINDER_ROOT.parent / "cinder-typhoon-direct.binding.json").read_text())
    assert binding["parameters"] == {}
    assert set(binding["targets"]) == {"training", "keplerops", "arwc"}
    assert binding["image_profiles"] == {}

    source = yaml.safe_load((CINDER_ROOT / "sdl/cinder-typhoon.sdl.yaml").read_text())
    mappings = json.loads((CINDER_ROOT.parent / "cinder-typhoon-direct.image-mappings.json").read_text())
    assert {mapping["source_name"] for mapping in mappings} == {
        node["source"]["name"] for node in source["nodes"].values()
    }
    by_phase = {
        mapping["source_name"].removeprefix("cinder-").removesuffix("-host"): mapping
        for mapping in mappings
    }
    expected_images = {
        "training": ("event-2026.11.11-01", "cinder-training-event-20261111-01"),
        "keplerops": ("event-2026.11.11-01", "cinder-keplerops-event-20261111-01"),
        "arwc": ("event-2026.11.09-02", "cinder-arwc-event-20261109-02"),
    }
    for phase, mapping in by_phase.items():
        assert mapping["provider"] == "gce"
        source_version, image = expected_images[phase]
        assert mapping["source_version"] == source_version
        assert mapping["image_kind"] == "image"
        assert mapping["image_ref"] == f"projects/prod-2hl4ce/global/images/{image}"
        assert "/global/images/" in mapping["image_ref"]
        node = source["nodes"][f"{phase}-host"]
        assert node["source"] == {
            "name": mapping["source_name"],
            "version": source_version,
        }
    for phase in ("training", "keplerops"):
        readiness = CINDER_ROOT.parents[1] / f"cinder-typhoon/build/{phase}/participant-readiness.json"
        assert by_phase[phase]["participant_readiness_manifest_sha256"] == hashlib.sha256(
            readiness.read_bytes()
        ).hexdigest()
    assert by_phase["arwc"]["bootstrap_capability"] == "standard"


def test_cinder_archive_is_reproducible(tmp_path):
    spec = importlib.util.spec_from_file_location("pack_builder", CINDER_ROOT.parent / "build.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    copied = tmp_path / "runtime-pack" / "cinder-typhoon-direct"
    shutil.copytree(CINDER_ROOT, copied)
    first, second = tmp_path / "first.tar", tmp_path / "second.tar"
    builder.CINDER_ROOT = copied
    digest = builder.build_cinder(first)
    assert builder.build_cinder(second) == digest
    assert first.read_bytes() == second.read_bytes()
