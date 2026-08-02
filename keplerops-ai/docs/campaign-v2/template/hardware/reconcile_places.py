#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path

import yaml


def run(client: list[str], *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*client, *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coordinator", required=True)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
    client = ["labgrid-client", "--coordinator", args.coordinator]

    if run(client, "version").stdout.strip() != manifest["labgrid_version"]:
        raise SystemExit("labgrid client version does not match the pool manifest")

    for declared in manifest["places"]:
        name = declared["name"]
        if run(client, "--place", name, "show", check=False).returncode != 0:
            run(client, "--place", name, "create")

        match = f'{declared["exporter"]}/{declared["group"]}/*/*'
        run(client, "--place", name, "add-match", match)
        run(
            client,
            "--place",
            name,
            "set-comment",
            "KeplerOps physical AI bench; real hardware required",
        )
        declared_tags = dict(declared["tags"])
        declared_tags[manifest["selection_tag"]] = name.replace("-", "_")
        tags = [f"{key}={value}" for key, value in sorted(declared_tags.items())]
        run(client, "--place", name, "set-tags", *tags)

    print(f'reconciled {len(manifest["places"])} labgrid places')
    return 0


if __name__ == "__main__":
    sys.exit(main())
