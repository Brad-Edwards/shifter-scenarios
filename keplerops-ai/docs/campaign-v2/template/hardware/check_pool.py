#!/usr/bin/env python3
import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml
from labgrid.remote.client import ClientSession


def expected_tags(manifest: dict, declared: dict) -> dict[str, str]:
    tags = dict(declared["tags"])
    tags[manifest["selection_tag"]] = declared["name"].replace("-", "_")
    return tags


def inspect_place(
    session: ClientSession,
    manifest: dict,
    declared: dict,
    declared_paths: set[tuple[str, str]],
) -> list[str]:
    failures: list[str] = []
    name = declared["name"]
    place = session.places.get(name)
    if place is None:
        return [f"{name}: place is absent"]

    for key, value in expected_tags(manifest, declared).items():
        if place.tags.get(key) != value:
            failures.append(f"{name}: tag {key} is not {value}")

    path = (declared["exporter"], declared["group"])
    if path in declared_paths:
        failures.append(f"{name}: exporter/group is shared by another place")
    declared_paths.add(path)

    if not any(
        match.exporter == path[0]
        and match.group == path[1]
        and match.cls == "*"
        and match.name == "*"
        for match in place.matches
    ):
        failures.append(f"{name}: exact exporter/group match is absent")

    group = session.resources.get(path[0], {}).get(path[1])
    if group is None:
        failures.append(f"{name}: exporter/group {path[0]}/{path[1]} is offline")
        return failures

    for required in declared["required_resources"]:
        resource = group.get(required["name"])
        if resource is None:
            failures.append(f'{name}: resource {required["name"]} is absent')
            continue
        if resource.cls != required["class"]:
            failures.append(
                f'{name}: resource {required["name"]} has class '
                f'{resource.cls}, expected {required["class"]}'
            )
        if not resource.avail:
            failures.append(f'{name}: resource {required["name"]} is unavailable')

    return failures


async def inspect_pool(args: argparse.Namespace) -> int:
    manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
    declared_by_name = {place["name"]: place for place in manifest["places"]}
    session = ClientSession(args.coordinator, asyncio.get_running_loop())
    await session.start()
    try:
        if args.reservation_token:
            matches = [
                place.name
                for place in session.places.values()
                if place.reservation == args.reservation_token
            ]
            if len(matches) != 1:
                raise RuntimeError(
                    f"reservation token maps to {len(matches)} places, expected one"
                )
            if args.place and matches[0] != args.place:
                raise RuntimeError(
                    f"reservation selected {matches[0]}, expected {args.place}"
                )
            print(matches[0])
            return 0

        if args.place:
            declared = declared_by_name.get(args.place)
            if declared is None:
                print(f"hardware place unavailable: {args.place} is not declared", file=sys.stderr)
                return 1
            if declared["tags"]["spare"] != "false":
                print(f"hardware place unavailable: {args.place} is a cold spare", file=sys.stderr)
                return 1
            failures = inspect_place(session, manifest, declared, set())
            if failures:
                for failure in failures:
                    print(f"hardware place unavailable: {failure}", file=sys.stderr)
                return 1
            print(
                json.dumps(
                    {
                        "place": args.place,
                        "exporter_connected": True,
                        "declared_resources_available": True,
                    },
                    sort_keys=True,
                )
            )
            return 0

        failures: list[str] = []
        declared_paths: set[tuple[str, str]] = set()
        active = sum(
            declared["tags"]["spare"] == "false" for declared in manifest["places"]
        )
        spares = len(manifest["places"]) - active

        for declared in manifest["places"]:
            failures.extend(inspect_place(session, manifest, declared, declared_paths))

        selectors = {
            expected_tags(manifest, declared)[manifest["selection_tag"]]
            for declared in manifest["places"]
        }
        if len(selectors) != len(manifest["places"]):
            failures.append("selection tags are not unique")
        if active != 12 or spares != 2:
            failures.append(f"pool declares {active} active and {spares} spare places")

        if failures:
            for failure in failures:
                print(f"hardware pool unavailable: {failure}", file=sys.stderr)
            return 1

        print(
            json.dumps(
                {
                    "active_places": active,
                    "cold_spares": spares,
                    "exporters_connected": True,
                    "declared_resources_available": True,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        await session.stop()
        await session.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coordinator", required=True)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--place")
    parser.add_argument("--reservation-token")
    return asyncio.run(inspect_pool(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
