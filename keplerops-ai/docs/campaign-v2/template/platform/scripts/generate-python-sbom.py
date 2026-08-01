#!/usr/bin/env python3

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def spdx_id(name: str, version: str) -> str:
    value = re.sub(r"[^A-Za-z0-9.-]", "-", f"{name}-{version}")
    return f"SPDXRef-Package-{value}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packages", required=True, type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    packages = sorted(json.loads(args.packages.read_text()), key=lambda item: item["name"].lower())
    namespace = hashlib.sha256(args.image.encode()).hexdigest()
    document = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"Orion Release Risk {args.image}",
        "documentNamespace": f"https://keplerops.lab/spdx/{namespace}",
        "creationInfo": {
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "creators": ["Tool: keplerops-python-inventory/1.0"],
        },
        "packages": [
            {
                "name": item["name"],
                "SPDXID": spdx_id(item["name"], item["version"]),
                "versionInfo": item["version"],
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:pypi/{item['name']}@{item['version']}",
                    }
                ],
            }
            for item in packages
        ],
    }
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
