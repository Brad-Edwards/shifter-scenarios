#!/usr/bin/env python3
"""Validate the author discovery map and emit image-scoped client references."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT / "authoring" / "client_documents.json"
DEFAULT_OUTPUT = ROOT / "runtime" / "client-references"
SCHEMA = "fieldkest.client-documents/v1"
REFERENCE_PATH = "/.well-known/fieldkest-client"
IMAGE_NAME = re.compile(r"^[a-z][a-z0-9-]*$")
METHODS = {"GET", "PATCH", "POST", "PUT"}


class DiscoveryMapError(ValueError):
    """The author map or its generated fragments violate the discovery design."""


def canonical_json(value: object) -> bytes:
    """Return stable, reviewable JSON bytes."""
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def validate_and_render(value: object) -> dict[str, bytes]:
    """Validate an author map and return the exact fragment file set."""
    if not isinstance(value, dict):
        raise DiscoveryMapError("discovery map must be an object")
    if (
        value.get("schema") != SCHEMA
        or value.get("audience") != "author"
        or value.get("path") != REFERENCE_PATH
    ):
        raise DiscoveryMapError("discovery map schema or path is invalid")
    documents = value.get("documents")
    images = value.get("images")
    if not isinstance(documents, dict) or not documents:
        raise DiscoveryMapError("discovery map has no service documents")
    if not isinstance(images, dict) or not images:
        raise DiscoveryMapError("discovery map has no image assignments")

    assigned_hosts: list[str] = []
    route_keys: set[str] = set()
    for image, host in images.items():
        if not isinstance(image, str) or not IMAGE_NAME.fullmatch(image):
            raise DiscoveryMapError(f"invalid image name: {image!r}")
        if not isinstance(host, str) or host not in documents:
            raise DiscoveryMapError(
                f"image {image} has unknown service document: {host!r}"
            )
        assigned_hosts.append(host)
    if len(assigned_hosts) != len(set(assigned_hosts)):
        raise DiscoveryMapError("a service document is assigned to more than one image")
    if set(assigned_hosts) != set(documents):
        missing = sorted(set(documents) - set(assigned_hosts))
        raise DiscoveryMapError(
            f"service documents without image assignment: {missing}"
        )

    for host, document in documents.items():
        if not isinstance(host, str) or not isinstance(document, dict):
            raise DiscoveryMapError("service documents must be host/object pairs")
        routes = document.get("routes")
        related = document.get("related")
        if not isinstance(routes, list) or not isinstance(related, list):
            raise DiscoveryMapError(
                f"service document {host} has invalid routes or related links"
            )
        for route in routes:
            if not isinstance(route, dict):
                raise DiscoveryMapError(
                    f"service document {host} has a non-object route"
                )
            key = route.get("key")
            method = route.get("method")
            template = route.get("template")
            if not isinstance(key, str) or not key:
                raise DiscoveryMapError(
                    f"service document {host} has a route without a key"
                )
            if key in route_keys:
                raise DiscoveryMapError(f"duplicate route key: {key}")
            if method not in METHODS:
                raise DiscoveryMapError(
                    f"route {key} has unsupported method: {method!r}"
                )
            if not isinstance(template, str) or urlsplit(template).scheme != "https":
                raise DiscoveryMapError(f"route {key} has an invalid HTTPS template")
            route_keys.add(key)
        for link in related:
            parsed = urlsplit(link) if isinstance(link, str) else None
            if (
                parsed is None
                or parsed.scheme != "https"
                or parsed.path != REFERENCE_PATH
                or parsed.hostname not in documents
            ):
                raise DiscoveryMapError(
                    f"service document {host} has an invalid related link: {link!r}"
                )

    start = "source.keplerops.test"
    if start not in documents:
        raise DiscoveryMapError(f"discovery graph has no starting document: {start}")
    reachable: set[str] = set()
    pending = [start]
    while pending:
        host = pending.pop(0)
        if host in reachable:
            continue
        reachable.add(host)
        pending.extend(
            urlsplit(link).hostname
            for link in documents[host]["related"]
            if urlsplit(link).hostname not in reachable
        )
    if reachable != set(documents):
        raise DiscoveryMapError(
            f"unreachable service documents: {sorted(set(documents) - reachable)}"
        )

    return {
        f"{image}.json": canonical_json(
            {
                "schema": SCHEMA,
                "path": REFERENCE_PATH,
                "documents": {host: documents[host]},
            }
        )
        for image, host in sorted(images.items())
    }


def load_and_render(source: Path) -> dict[str, bytes]:
    """Load one UTF-8 JSON author map and render its fragments."""
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DiscoveryMapError(
            f"cannot load discovery map {source}: {error}"
        ) from error
    return validate_and_render(value)


def check_output(output: Path, fragments: dict[str, bytes]) -> None:
    """Fail when the generated directory differs from the author map."""
    actual_names = (
        {path.name for path in output.glob("*.json")} if output.is_dir() else set()
    )
    if actual_names != set(fragments):
        raise DiscoveryMapError(
            f"generated fragment set drift: expected={sorted(fragments)} actual={sorted(actual_names)}"
        )
    for name, expected in fragments.items():
        try:
            actual = (output / name).read_bytes()
        except OSError as error:
            raise DiscoveryMapError(
                f"cannot read generated fragment {name}: {error}"
            ) from error
        if actual != expected:
            raise DiscoveryMapError(f"generated fragment drift: {name}")


def write_output(output: Path, fragments: dict[str, bytes]) -> None:
    """Replace only generated JSON fragments with the validated file set."""
    output.mkdir(parents=True, exist_ok=True)
    for path in output.glob("*.json"):
        if path.name not in fragments:
            path.unlink()
    for name, payload in fragments.items():
        (output / name).write_bytes(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        fragments = load_and_render(arguments.source)
        if arguments.check:
            check_output(arguments.output, fragments)
        else:
            write_output(arguments.output, fragments)
    except DiscoveryMapError as error:
        print(f"client-reference generation failed: {error}", file=sys.stderr)
        return 1
    action = "validated" if arguments.check else "generated"
    print(f"{action} {len(fragments)} image-scoped client references")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
