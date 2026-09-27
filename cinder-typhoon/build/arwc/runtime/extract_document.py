#!/usr/bin/env python3
import json
import pathlib
import sys


def main() -> None:
    package_path, document_name, output_path = sys.argv[1:]
    package = json.loads(pathlib.Path(package_path).read_text(encoding="utf-8"))
    matches = [item for item in package["documents"] if item["name"] == document_name]
    if len(matches) != 1:
        raise SystemExit(f"expected one {document_name!r} document, found {len(matches)}")
    document = matches[0]
    if document["media_type"] != "text/markdown":
        raise SystemExit("unexpected document media type")
    pathlib.Path(output_path).write_text(document["text"], encoding="utf-8")


if __name__ == "__main__":
    main()
