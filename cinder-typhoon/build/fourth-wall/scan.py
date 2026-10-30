#!/usr/bin/env python3
"""Scan participant-facing source material for fourth-wall leakage."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import shlex
import tarfile
from typing import Any, Iterable
from urllib.parse import urlsplit

from policy import build_policy, slug


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ALLOWLIST_PATH = HERE / "allowlist.json"
DOMAIN_INTERFACES_PATH = HERE / "domain-interfaces.json"
RUNTIME_ROOTS = {
    "training": ROOT / "build" / "training" / "runtime",
    "keplerops": ROOT / "build" / "keplerops" / "runtime",
    "arwc": ROOT / "build" / "arwc" / "runtime",
}
IMAGE_ROOTS = {
    phase: ROOT / "build" / phase / "images"
    for phase in RUNTIME_ROOTS
}
CARD_ID = re.compile(r"(?i)(?<![a-z0-9])[tkw]\d{2}(?:[.-]?\d)?(?![a-z0-9])")
URL = re.compile(r"https?://[^\s`'\"<>]+", re.IGNORECASE)
API_PATH = re.compile(r"(?<![a-z0-9])/(?:api|internal)/[a-z0-9_{}%./-]+", re.IGNORECASE)
BASE64_LINE = re.compile(r"(?m)^[A-Za-z0-9+/]{60,}={0,2}\r?$")
ALIAS_KINDS = {
    "route", "operation", "filename", "magic", "service_name", "schema", "error",
    "participant_file", "response", "banner",
}
NON_ALLOWLISTABLE_RULES = {
    "domain-interface-review-required",
    "domain-interface-route-unapproved",
    "live-files-not-observed",
    "live-files-skipped",
    "live-file-limit-exceeded",
    "live-byte-limit-exceeded",
    "live-probe-failures",
    "live-probe-limit-exceeded",
    "live-responses-not-observed",
    "live-responses-truncated",
}


class ScanError(ValueError):
    pass


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def finding(
    *, source_kind: str, location: str, value: str, rule_id: str,
    match: str, card_id: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source_kind": source_kind,
        "location": location,
        "rule_id": rule_id,
        "match": match,
        "content_sha256": sha256_text(value),
    }
    if card_id:
        result["card_id"] = card_id
    return result


def scan_value(
    policy: dict[str, Any], *, source_kind: str, location: str, value: str,
) -> list[dict[str, Any]]:
    """Return value-free findings; never copy the scanned value into a report."""
    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None]] = set()

    for rule in policy["meta_rules"]:
        if rule["id"] == "dependency-oracle" and source_kind != "error":
            continue
        if re.search(rule["pattern"], value, re.IGNORECASE):
            key = (rule["id"], rule["label"], None)
            if key not in seen:
                findings.append(finding(
                    source_kind=source_kind, location=location, value=value,
                    rule_id=rule["id"], match=rule["label"],
                ))
                seen.add(key)

    if source_kind not in ALIAS_KINDS:
        return findings

    normalized = slug(value)
    delimited = f"-{normalized}-"
    for card in policy["card_aliases"]:
        title_slug = card["title_slug"]
        if title_slug and f"-{title_slug}-" in delimited:
            key = ("card-title-alias", title_slug, card["card_id"])
            if key not in seen:
                findings.append(finding(
                    source_kind=source_kind, location=location, value=value,
                    rule_id="card-title-alias", match=title_slug,
                    card_id=card["card_id"],
                ))
                seen.add(key)

    for match in CARD_ID.findall(value):
        normalized_id = match.upper().replace("-", ".")
        key = ("card-id-alias", normalized_id, normalized_id)
        if key not in seen:
            findings.append(finding(
                source_kind=source_kind, location=location, value=value,
                rule_id="card-id-alias", match=normalized_id,
                card_id=normalized_id,
            ))
            seen.add(key)
    return findings


def extracted_routes(value: str) -> Iterable[str]:
    for match in URL.findall(value):
        yield match.rstrip(".,;:)")
    yield from API_PATH.findall(value)


def scan_text(
    policy: dict[str, Any], *, source_kind: str, location: str, value: str,
) -> list[dict[str, Any]]:
    semantic_value = BASE64_LINE.sub("", value)
    findings = scan_value(
        policy, source_kind=source_kind, location=location, value=semantic_value,
    )
    routes = set() if source_kind == "route" else set(extracted_routes(semantic_value))
    for index, route in enumerate(sorted(routes)):
        findings.extend(scan_value(
            policy, source_kind="route", location=f"{location}#route-{index + 1}",
            value=route,
        ))
    return findings


def encoded_blob(key: str, value: str) -> bool:
    lowered = key.casefold()
    if any(term in lowered for term in ("base64", "ciphertext", "binary", "blob")):
        return len(value) >= 40
    compact = value.strip()
    return (
        len(compact) >= 256
        and not re.search(r"\s", compact)
        and re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", compact) is not None
    )


def scan_json_asset(
    policy: dict[str, Any], *, location: str, value: Any,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def visit(item: Any, pointer: str = "", key: str = "") -> None:
        if isinstance(item, dict):
            for child_key, child in item.items():
                escaped = str(child_key).replace("~", "~0").replace("/", "~1")
                visit(child, f"{pointer}/{escaped}", str(child_key))
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, f"{pointer}/{index}", key)
        elif isinstance(item, str) and not encoded_blob(key, item):
            field_location = f"{location}#json{pointer}"
            if key.casefold() in {"filename", "file_name", "attachment", "path"}:
                findings.extend(scan_value(
                    policy, source_kind="filename", location=field_location, value=item,
                ))
            findings.extend(scan_text(
                policy, source_kind="participant_file",
                location=field_location, value=item,
            ))

    visit(value)
    return findings


def response_fields(value: str) -> Iterable[tuple[str, str]]:
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
    result: list[tuple[str, str]] = []

    def visit(item: Any, key: str = "") -> None:
        if isinstance(item, dict):
            for child_key, child in item.items():
                visit(child, str(child_key))
        elif isinstance(item, list):
            for child in item:
                visit(child, key)
        elif isinstance(item, str):
            kind = (
                "error" if key.casefold() in {"error", "reason", "failure"}
                else "schema" if "schema" in key.casefold()
                else "service_name" if key.casefold() in {"service", "service_name"}
                else "operation"
            )
            result.append((kind, item))

    visit(parsed)
    return result


def load_allowlist(path: Path = ALLOWLIST_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {"schema_version", "entries"}:
        raise ScanError("invalid fourth-wall allowlist")
    if value["schema_version"] != 1 or not isinstance(value["entries"], list):
        raise ScanError("invalid fourth-wall allowlist header")
    required = {
        "id", "source_kind", "location", "rule_id", "match",
        "content_sha256", "rationale",
    }
    ids: set[str] = set()
    for index, entry in enumerate(value["entries"]):
        if not isinstance(entry, dict) or set(entry) != required:
            raise ScanError(f"allowlist entry {index} has invalid fields")
        if not all(isinstance(entry[field], str) and entry[field] for field in required):
            raise ScanError(f"allowlist entry {index} has empty fields")
        if entry["id"] in ids or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", entry["id"]):
            raise ScanError(f"allowlist entry {index} has invalid or duplicate id")
        if not re.fullmatch(r"[0-9a-f]{64}", entry["content_sha256"]):
            raise ScanError(f"allowlist entry {index} has invalid content hash")
        ids.add(entry["id"])
    return value


def load_domain_interfaces(path: Path = DOMAIN_INTERFACES_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {"schema_version", "phases"}:
        raise ScanError("invalid domain-interface registry")
    if value["schema_version"] != 1 or set(value["phases"]) != set(RUNTIME_ROOTS):
        raise ScanError("invalid domain-interface registry header")
    for phase, entry in value["phases"].items():
        if not isinstance(entry, dict) or set(entry) != {
            "status", "blocking_issue", "approved_route_patterns",
        }:
            raise ScanError(f"{phase}: invalid domain-interface fields")
        if entry["status"] not in {"not_applicable", "pending_review", "approved"}:
            raise ScanError(f"{phase}: invalid domain-interface status")
        if not isinstance(entry["approved_route_patterns"], list):
            raise ScanError(f"{phase}: invalid approved route patterns")
        for pattern in entry["approved_route_patterns"]:
            if not isinstance(pattern, str) or not pattern:
                raise ScanError(f"{phase}: empty approved route pattern")
            re.compile(pattern)
        if entry["status"] == "pending_review" and not isinstance(entry["blocking_issue"], int):
            raise ScanError(f"{phase}: pending domain review requires an issue")
    return value


def apply_allowlist(
    findings: list[dict[str, Any]], allowlist: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    allowed_keys = {
        tuple(entry[field] for field in (
            "source_kind", "location", "rule_id", "match", "content_sha256",
        )): entry
        for entry in allowlist["entries"]
    }
    unresolved = []
    allowed = []
    for item in findings:
        if item["rule_id"] in NON_ALLOWLISTABLE_RULES:
            unresolved.append(item)
            continue
        key = tuple(item[field] for field in (
            "source_kind", "location", "rule_id", "match", "content_sha256",
        ))
        entry = allowed_keys.get(key)
        if entry:
            allowed.append({**item, "allowlist_id": entry["id"], "rationale": entry["rationale"]})
        else:
            unresolved.append(item)
    return unresolved, allowed


def logical_dockerfile_lines(source: str) -> list[str]:
    result: list[str] = []
    current = ""
    for raw in source.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        current = f"{current} {line}".strip()
        if current.endswith("\\"):
            current = current[:-1].rstrip()
            continue
        result.append(current)
        current = ""
    if current:
        result.append(current)
    return result


def copied_sources(phase: str) -> list[tuple[Path, bool]]:
    result: dict[Path, bool] = {}
    participant_images = {
        "training": {"participant.Dockerfile"},
        "keplerops": {"k-dev.Dockerfile"},
        "arwc": {"connector.Dockerfile"},
    }
    for dockerfile in sorted(IMAGE_ROOTS[phase].glob("*.Dockerfile")):
        participant_visible_names = dockerfile.name in participant_images[phase]
        for line in logical_dockerfile_lines(dockerfile.read_text(encoding="utf-8")):
            try:
                words = shlex.split(line)
            except ValueError:
                continue
            if not words or words[0].upper() not in {"COPY", "ADD"}:
                continue
            arguments = words[1:]
            if any(item.startswith("--from=") for item in arguments):
                continue
            values = [item for item in arguments if not item.startswith("--")]
            for item in values[:-1]:
                if not item.startswith("assets/") or any(character in item for character in "$*?["):
                    continue
                path = ROOT / item
                if path.exists():
                    names_are_participant_visible = (
                        participant_visible_names and item.startswith("assets/")
                    )
                    result[path] = result.get(path, False) or names_are_participant_visible
    return sorted(result.items())


def source_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
    elif path.is_dir():
        for candidate in sorted(path.rglob("*")):
            if candidate.is_file() and "generation" not in candidate.parts:
                yield candidate


def text_from_bytes(payload: bytes, *, extract_sqlite: bool = False) -> str | None:
    if b"\x00" in payload:
        if not extract_sqlite or not payload.startswith(b"SQLite format 3\x00"):
            return None
        strings = re.findall(rb"[\x20-\x7e]{4,}", payload)
        return "\n".join(item.decode("ascii") for item in strings)
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        return None


def scan_archive(
    policy: dict[str, Any], path: Path, *, scan_names: bool,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        archive = tarfile.open(path, "r:*")
    except (tarfile.TarError, OSError):
        return findings
    with archive:
        for member in archive.getmembers():
            location = f"{path.relative_to(ROOT).as_posix()}::{member.name}"
            if scan_names:
                findings.extend(scan_value(
                    policy, source_kind="filename", location=location, value=member.name,
                ))
            if not member.isfile() or member.size > 64 * 1024 * 1024:
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            payload = handle.read()
            text = text_from_bytes(payload, extract_sqlite=True)
            if text is not None:
                if member.name.casefold().endswith(".json"):
                    try:
                        findings.extend(scan_json_asset(
                            policy, location=location, value=json.loads(text),
                        ))
                    except json.JSONDecodeError:
                        findings.extend(scan_text(
                            policy, source_kind="participant_file", location=location, value=text,
                        ))
                else:
                    findings.extend(scan_text(
                        policy, source_kind="participant_file", location=location, value=text,
                    ))
    return findings


def scan_asset(
    policy: dict[str, Any], path: Path, *, scan_names: bool,
) -> list[dict[str, Any]]:
    location = path.relative_to(ROOT).as_posix()
    findings = []
    if scan_names:
        findings.extend(scan_value(
            policy, source_kind="filename", location=location, value=path.name,
        ))
    if tarfile.is_tarfile(path):
        findings.extend(scan_archive(policy, path, scan_names=scan_names))
        return findings
    if path.stat().st_size > 64 * 1024 * 1024:
        return findings
    text = text_from_bytes(path.read_bytes(), extract_sqlite=True)
    if text is not None:
        if path.suffix.casefold() == ".json":
            try:
                findings.extend(scan_json_asset(
                    policy, location=location, value=json.loads(text),
                ))
            except json.JSONDecodeError:
                findings.extend(scan_text(
                    policy, source_kind="participant_file", location=location, value=text,
                ))
        else:
            findings.extend(scan_text(
                policy, source_kind="participant_file", location=location, value=text,
            ))
    return findings


def error_name(value: str) -> bool:
    normalized = value.casefold().replace("-", "_")
    return normalized in {
        "error", "reason", "failure", "error_message", "failure_reason",
    }


def classify_runtime_literal(
    value: str, node: ast.Constant | None = None, parent: ast.AST | None = None,
) -> str:
    if node is not None and isinstance(parent, ast.Dict):
        for key, child in zip(parent.keys, parent.values):
            if child is node and isinstance(key, ast.Constant) and isinstance(key.value, str):
                if error_name(key.value):
                    return "error"
    if node is not None and isinstance(parent, ast.Call):
        for keyword in parent.keywords:
            if keyword.value is node and keyword.arg and error_name(keyword.arg):
                return "error"
    if node is not None and isinstance(parent, (ast.Assign, ast.AnnAssign)):
        targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
        if any(isinstance(target, ast.Name) and error_name(target.id) for target in targets):
            return "error"
    if value.startswith("/") or "://" in value:
        return "route"
    if not re.search(r"\s", value) and len(value) <= 160:
        if re.search(
            r"(?:^|_)(?:error|denied|required|not_found|failed|missing|conflict)(?:_|$)",
            value.casefold(),
        ):
            return "error"
        if "schema" in value.casefold() or re.search(r"/v\d+$", value):
            return "schema"
        return "operation"
    return "response"


def scan_runtime(policy: dict[str, Any], phase: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in sorted(RUNTIME_ROOTS[phase].glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:
            raise ScanError(f"cannot parse runtime source {path}: {error}") from error
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            location = f"{path.relative_to(ROOT).as_posix()}:{node.lineno}"
            source_kind = classify_runtime_literal(
                node.value, node=node, parent=parents.get(node),
            )
            findings.extend(scan_text(
                policy, source_kind=source_kind, location=location, value=node.value,
            ))
            if source_kind == "response":
                for index, (kind, field_value) in enumerate(response_fields(node.value)):
                    findings.extend(scan_value(
                        policy, source_kind=kind,
                        location=f"{location}#field-{index + 1}", value=field_value,
                    ))
    for path in sorted(RUNTIME_ROOTS[phase].rglob("*")):
        if path.is_file() and path.suffix != ".py":
            findings.extend(scan_asset(policy, path, scan_names=False))
    return findings


def runtime_routes(phase: str) -> list[tuple[str, str]]:
    result: dict[tuple[str, str], None] = {}
    for path in sorted(RUNTIME_ROOTS[phase].glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            candidates = set(extracted_routes(node.value))
            if node.value.startswith("/"):
                candidates.add(node.value)
            for route in candidates:
                parsed = urlsplit(route) if "://" in route else None
                route_path = parsed.path if parsed else route.split("?", 1)[0]
                if route_path.startswith(("/api/", "/internal/")):
                    location = f"{path.relative_to(ROOT).as_posix()}:{node.lineno}"
                    result[(location, route_path)] = None
    return sorted(result)


def domain_interface_findings(
    phase: str, path: Path = DOMAIN_INTERFACES_PATH,
) -> list[dict[str, Any]]:
    entry = load_domain_interfaces(path)["phases"][phase]
    if entry["status"] == "not_applicable":
        return []
    if entry["status"] == "pending_review":
        value = str(entry["blocking_issue"])
        return [{
            "source_kind": "domain_interface",
            "location": phase,
            "rule_id": "domain-interface-review-required",
            "match": value,
            "content_sha256": sha256_text(value),
        }]
    patterns = [re.compile(pattern) for pattern in entry["approved_route_patterns"]]
    findings = []
    for location, route in runtime_routes(phase):
        if not any(pattern.fullmatch(route) for pattern in patterns):
            findings.append({
                "source_kind": "route",
                "location": location,
                "rule_id": "domain-interface-route-unapproved",
                "match": route,
                "content_sha256": sha256_text(route),
            })
    return findings


def deduplicate(findings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in findings:
        key = tuple(item.get(field) for field in (
            "source_kind", "location", "rule_id", "match", "card_id", "content_sha256",
        ))
        result[key] = item
    return sorted(result.values(), key=lambda item: (
        item["location"], item["rule_id"], item["match"], item.get("card_id", ""),
    ))


def static_findings(policy: dict[str, Any], phase: str) -> list[dict[str, Any]]:
    findings = [*scan_runtime(policy, phase), *domain_interface_findings(phase)]
    seen: set[Path] = set()
    for source, scan_names in copied_sources(phase):
        for path in source_files(source):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            findings.extend(scan_asset(policy, path, scan_names=scan_names))
    return deduplicate(findings)


def build_static_report(phase: str) -> dict[str, Any]:
    policy = build_policy()
    unresolved, allowed = apply_allowlist(
        static_findings(policy, phase), load_allowlist(),
    )
    return {
        "schema_version": 1,
        "report_kind": "fourth-wall-static",
        "phase": phase,
        "policy_sha256": policy["policy_sha256"],
        "overall_status": "clean" if not unresolved else "unresolved",
        "summary": {
            "finding_count": len(unresolved),
            "allowlisted_count": len(allowed),
        },
        "findings": unresolved,
        "allowlisted": allowed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=sorted(RUNTIME_ROOTS))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-clean", action="store_true")
    arguments = parser.parse_args()
    report = build_static_report(arguments.phase)
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 1 if arguments.require_clean and report["overall_status"] != "clean" else 0


if __name__ == "__main__":
    raise SystemExit(main())
