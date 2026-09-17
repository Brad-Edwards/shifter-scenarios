"""Release preparation rejects incompatible SDK inputs before creating output."""

import importlib.util
import zipfile
from pathlib import Path

import pytest


@pytest.mark.parametrize("name,version", [("other-sdk", "0.1.0"), ("shifter-adapter-sdk", "9.0.0")])
def test_incompatible_sdk_cannot_prepare_a_worker(tmp_path, name, version):
    script = Path(__file__).resolve().parents[1] / "prepare_release.py"
    spec = importlib.util.spec_from_file_location("prepare_release", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    wheel = tmp_path / "sdk.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("sdk.dist-info/METADATA", f"Name: {name}\nVersion: {version}\n")
    output = tmp_path / "candidate"
    with pytest.raises(ValueError, match="exact SDK dependency"):
        module.prepare(wheel, output)
    assert not output.exists()
