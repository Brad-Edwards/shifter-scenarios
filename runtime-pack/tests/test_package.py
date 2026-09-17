"""The installable outer runtime package is validated independently of Shifter."""

import importlib.util
import shutil
import tarfile
from pathlib import Path

import yaml
from raes.scenarios import load_scenario
from raes_env_packs import pack_content_digest, validate_pack, verify_pack_content_digest

ROOT = Path(__file__).parents[1] / "polaris"


def test_package_is_conformant_and_digest_bound():
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


def test_archive_is_reproducible_and_contains_exactly_the_validated_package(tmp_path):
    spec = importlib.util.spec_from_file_location("pack_builder", ROOT.parent / "build.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.ROOT = tmp_path / "polaris"
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
