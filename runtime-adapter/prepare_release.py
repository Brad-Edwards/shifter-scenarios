"""Prepare an auditable, network-free worker build from an explicit SDK wheel."""

import argparse
import email.parser
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path


def wheel_identity(path: Path) -> tuple[str, str]:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise ValueError("Wheel must contain exactly one distribution metadata record")
        metadata = email.parser.BytesParser().parsebytes(archive.read(names[0]))
    return str(metadata["Name"]), str(metadata["Version"])


def prepare(sdk_wheel: Path, output: Path) -> None:
    root = Path(__file__).resolve().parent
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    name, version = wheel_identity(sdk_wheel)
    if name != "shifter-adapter-sdk" or f"shifter-adapter-sdk[runtime]=={version}" not in project["dependencies"]:
        raise ValueError("SDK wheel must match the adapter's exact SDK dependency")
    output.mkdir(parents=True, exist_ok=False)
    wheels = output / "wheels"
    wheels.mkdir()
    shutil.copy2(sdk_wheel, wheels / sdk_wheel.name)
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(wheels)], cwd=root, check=True,
        env={**os.environ, "SOURCE_DATE_EPOCH": "315532800"},
    )
    subprocess.run(
        [
            sys.executable, "-m", "pip", "download", "--require-hashes", "--only-binary=:all:",
            "--no-deps", "--platform", "manylinux2014_x86_64", "--python-version", "3.12",
            "--implementation", "cp", "--abi", "cp312", "--dest", str(wheels),
            "--requirement", str(root / "runtime-dependencies.txt"),
        ],
        check=True,
    )
    hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(wheels.glob("*.whl"))
    }
    (wheels / "requirements.txt").write_text("".join(
        f"/wheels/{filename} --hash=sha256:{digest}\n" for filename, digest in hashes.items()
    ))
    shutil.copy2(root / "Dockerfile", output / "Dockerfile")
    evidence = {
        "schema": "private-adapter-build-inputs/v1",
        "platform": "linux/amd64",
        "sdk_version": version,
        "adapter_version": project["version"],
        "dockerfile_sha256": hashlib.sha256((output / "Dockerfile").read_bytes()).hexdigest(),
        "wheels": hashes,
        "registry_digest": None,
        "live_qualified": False,
    }
    (output / "build-inputs.json").write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-wheel", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="New directory; never overwritten")
    args = parser.parse_args()
    prepare(args.sdk_wheel.resolve(), args.output.resolve())
