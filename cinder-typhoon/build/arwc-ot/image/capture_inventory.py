"""Record the qualified cached images for a manual private VM bake."""
import argparse
import json
import os
import pathlib
import socket
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
IT = pathlib.Path("/opt/arwc-ot-compat/it/cinder-typhoon/build/arwc")


def main():
    if socket.gethostname() != "cinder-arwc-ot-compat-363":
        raise SystemExit("Capture the qualified set on the approved development VM")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()
    environment = dict(os.environ, ARWC_OT_OPERATOR_DIR=str(ROOT / ".operator"))
    commands = [
        ["sudo", "docker", "compose", *[part for file in ("compose.yaml", "site/compose.yaml", "historian/compose.yaml",
            "dispatch/compose.yaml", "workstation/compose.yaml", "integration/compose.yaml") for part in ("-f", str(ROOT / file))]],
        ["sudo", "--preserve-env=ARWC_OT_OPERATOR_DIR", "docker", "compose", "-f", str(IT / "compose.yaml"),
         "-f", str(ROOT / "integration/it-compose.yaml")],
    ]
    tags = set()
    for command in commands:
        result = subprocess.run(command + ["config", "--images"], cwd=ROOT, env=environment,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        tags.update(result.stdout.splitlines())
    images = {}
    for tag in sorted(tags):
        images[tag] = subprocess.check_output(["sudo", "docker", "image", "inspect", "--format", "{{.Id}}", tag], text=True).strip()
    args.output.write_text(json.dumps({"schema": "arwc.cached-images/v1", "images": images}, indent=2)+"\n")
    print(f"Recorded {len(images)} cached image identities; no credentials or mutable state included.")


if __name__ == "__main__":
    main()
