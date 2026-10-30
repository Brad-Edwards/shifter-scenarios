#!/usr/bin/env python3
"""Observe fourth-wall leakage from an unprivileged participant context.

The operator streams a bounded plan on stdin. This observer emits match names,
locations, and hashes only; it never emits file or response contents.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import sys
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import build_opener, HTTPRedirectHandler, HTTPSHandler, Request


CARD_ID = re.compile(r"(?i)(?<![a-z0-9])[tkw]\d{2}(?:[.-]?\d)?(?![a-z0-9])")
URL = re.compile(r"https?://[^\s`'\"<>]+", re.IGNORECASE)
API_PATH = re.compile(r"(?<![a-z0-9])/(?:api|internal)/[a-z0-9_{}%./-]+", re.IGNORECASE)
BASE64_LINE = re.compile(r"(?m)^[A-Za-z0-9+/]{60,}={0,2}\r?$")
ALIAS_KINDS = {
    "route", "operation", "filename", "magic", "service_name", "schema", "error",
    "participant_file", "response", "banner",
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


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
        if card["title_slug"] and f"-{card['title_slug']}-" in delimited:
            key = ("card-title-alias", card["title_slug"], card["card_id"])
            if key not in seen:
                findings.append(finding(
                    source_kind=source_kind, location=location, value=value,
                    rule_id="card-title-alias", match=card["title_slug"],
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
) -> tuple[list[dict[str, Any]], set[str]]:
    semantic_value = BASE64_LINE.sub("", value)
    parsed = None
    if source_kind == "response":
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            pass
    base_value = "" if parsed is not None else semantic_value
    findings = scan_value(
        policy, source_kind=source_kind, location=location, value=base_value,
    ) if base_value else []
    routes = set(extracted_routes(base_value))
    routes = set() if source_kind == "route" else routes
    for index, route in enumerate(sorted(routes)):
        findings.extend(scan_value(
            policy, source_kind="route", location=f"{location}#route-{index + 1}",
            value=route,
        ))
    if parsed is not None:
        def visit(item: Any, key: str = "") -> None:
            if isinstance(item, dict):
                for child_key, child in item.items():
                    visit(child, str(child_key))
            elif isinstance(item, list):
                for child in item:
                    visit(child, key)
            elif isinstance(item, str) and not encoded_blob(key, item):
                field_value = BASE64_LINE.sub("", item)
                kind = (
                    "error" if key.casefold() in {"error", "reason", "failure"}
                    else "schema" if "schema" in key.casefold()
                    else "service_name" if key.casefold() in {"service", "service_name"}
                    else "operation"
                )
                findings.extend(scan_value(
                    policy, source_kind=kind,
                    location=f"{location}#field-{key or 'value'}", value=field_value,
                ))
                field_routes = set(extracted_routes(field_value))
                routes.update(field_routes)
                for index, route in enumerate(sorted(field_routes)):
                    findings.extend(scan_value(
                        policy, source_kind="route",
                        location=f"{location}#field-{key or 'value'}-route-{index + 1}",
                        value=route,
                    ))

        visit(parsed)
    return findings, routes


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


def scan_json_file(
    policy: dict[str, Any], *, location: str, value: Any,
) -> tuple[list[dict[str, Any]], set[str]]:
    findings: list[dict[str, Any]] = []
    routes: set[str] = set()

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
            field_value = BASE64_LINE.sub("", item)
            if key.casefold() in {"filename", "file_name", "attachment", "path"}:
                findings.extend(scan_value(
                    policy, source_kind="filename", location=field_location, value=field_value,
                ))
            field_findings, field_routes = scan_text(
                policy, source_kind="participant_file",
                location=field_location, value=field_value,
            )
            findings.extend(field_findings)
            routes.update(field_routes)

    visit(value)
    return findings, routes


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


def opaque(relative: str, patterns: list[str]) -> bool:
    return any(
        relative == pattern.rstrip("/")
        or relative.startswith(pattern.rstrip("/") + "/")
        for pattern in patterns
    )


def files_in_root(root: dict[str, Any]) -> Iterable[Path]:
    base = Path(root["path"])
    if base.is_file():
        yield base
        return
    if not base.is_dir():
        return
    patterns = list(root.get("opaque", []))
    for directory, names, filenames in os.walk(base, followlinks=False):
        current = Path(directory)
        relative_directory = current.relative_to(base).as_posix()
        if relative_directory != "." and opaque(relative_directory, patterns):
            names[:] = []
            continue
        names[:] = sorted(name for name in names if not (current / name).is_symlink())
        for name in sorted(filenames):
            path = current / name
            if path.is_file() and not path.is_symlink():
                yield path


def normalized_origin(value: str) -> tuple[str, str, int] | None:
    try:
        parsed = urlsplit(value)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    return parsed.scheme, parsed.hostname, port


def safe_probe_url(
    value: str, allowed_origins: set[tuple[str, str, int]],
) -> str | None:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.username or parsed.password or normalized_origin(value) not in allowed_origins:
        return None
    if any(character in parsed.path for character in "{}[]"):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", "", ""))


def probe_location(url: str, status: int | None = None) -> str:
    parsed = urlsplit(url)
    path_hash = hashlib.sha256((parsed.path or "/").encode()).hexdigest()
    suffix = "" if status is None else f":status-{status}"
    return f"live-probe:{parsed.scheme}://{parsed.netloc}:path-sha256-{path_hash}{suffix}"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def probe(
    policy: dict[str, Any], url: str, *, max_bytes: int, tls_ca: str | None,
) -> tuple[list[dict[str, Any]], int, int]:
    request = Request(url, method="GET", headers={"User-Agent": "CinderSurfaceAudit/1"})
    context = ssl.create_default_context(cafile=tls_ca)
    opener = build_opener(HTTPSHandler(context=context), NoRedirect())
    status = 0
    headers = ""
    payload = b""
    truncated = 0
    try:
        with opener.open(request, timeout=4) as response:
            status = response.status
            headers = "\n".join(f"{name}: {value}" for name, value in response.headers.items())
            raw_payload = response.read(max_bytes + 1)
            truncated = int(len(raw_payload) > max_bytes)
            payload = raw_payload[:max_bytes]
    except HTTPError as error:
        status = error.code
        headers = "\n".join(f"{name}: {value}" for name, value in error.headers.items())
        raw_payload = error.read(max_bytes + 1)
        truncated = int(len(raw_payload) > max_bytes)
        payload = raw_payload[:max_bytes]
    except (OSError, URLError, TimeoutError, ValueError):
        return [], 1, 0
    location = probe_location(url, status)
    findings, _ = scan_text(
        policy, source_kind="banner", location=location, value=headers,
    )
    text = text_from_bytes(payload)
    if text is not None:
        response_findings, _ = scan_text(
            policy, source_kind="response", location=location, value=text,
        )
        findings.extend(response_findings)
    return findings, 0, truncated


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


def observe(plan: dict[str, Any]) -> dict[str, Any]:
    policy = plan["policy"]
    allowed_origins = {
        origin for value in plan["base_urls"]
        if (origin := normalized_origin(value)) is not None
    }
    max_file_bytes = plan.get("max_file_bytes", 4 * 1024 * 1024)
    max_files = plan.get("max_files", 10_000)
    max_total_bytes = plan.get("max_total_bytes", 128 * 1024 * 1024)
    max_response_bytes = plan.get("max_response_bytes", 1024 * 1024)
    max_probes = plan.get("max_probes", 256)
    findings: list[dict[str, Any]] = []
    routes: set[str] = set()
    scanned_files = 0
    scanned_bytes = 0
    skipped_files = 0
    visited_files = 0
    file_limit_exceeded = 0
    byte_limit_exceeded = 0

    for root in plan["roots"]:
        for path in files_in_root(root):
            if visited_files >= max_files:
                file_limit_exceeded = 1
                break
            visited_files += 1
            location = path.as_posix()
            findings.extend(scan_value(
                policy, source_kind="filename", location=location, value=path.name,
            ))
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if not os.access(path, os.R_OK):
                continue
            if size > max_file_bytes:
                skipped_files += 1
                continue
            try:
                with path.open("rb") as handle:
                    payload = handle.read(max_file_bytes + 1)
            except OSError:
                continue
            if len(payload) > max_file_bytes:
                skipped_files += 1
                continue
            if scanned_bytes + len(payload) > max_total_bytes:
                byte_limit_exceeded = 1
                break
            text = text_from_bytes(payload, extract_sqlite=True)
            scanned_files += 1
            scanned_bytes += len(payload)
            if text is None:
                continue
            if path.suffix.casefold() == ".json":
                try:
                    file_findings, file_routes = scan_json_file(
                        policy, location=location, value=json.loads(text),
                    )
                except json.JSONDecodeError:
                    file_findings, file_routes = scan_text(
                        policy, source_kind="participant_file", location=location, value=text,
                    )
            else:
                file_findings, file_routes = scan_text(
                    policy, source_kind="participant_file", location=location, value=text,
                )
            findings.extend(file_findings)
            routes.update(file_routes)

    for base_url in plan["base_urls"]:
        routes.add(f"{base_url.rstrip('/')}/")
        routes.add(f"{base_url.rstrip('/')}/api")
    all_probe_urls = sorted({
        candidate
        for route in routes
        if (candidate := safe_probe_url(route, allowed_origins)) is not None
    })
    probe_limit_exceeded = max(0, len(all_probe_urls) - max_probes)
    probe_urls = all_probe_urls[:max_probes]
    probe_errors = 0
    truncated_responses = 0
    for url in probe_urls:
        findings.extend(scan_value(
            policy, source_kind="route", location=probe_location(url), value=url,
        ))
        probe_findings, error_count, truncated_count = probe(
            policy, url, max_bytes=max_response_bytes, tls_ca=plan.get("tls_ca"),
        )
        findings.extend(probe_findings)
        probe_errors += error_count
        truncated_responses += truncated_count

    return {
        "schema_version": 1,
        "report_kind": "fourth-wall-observation",
        "phase": plan["phase"],
        "policy_sha256": policy["policy_sha256"],
        "identity": {"uid": os.geteuid(), "unprivileged": os.geteuid() != 0},
        "summary": {
            "scanned_file_count": scanned_files,
            "scanned_byte_count": scanned_bytes,
            "skipped_file_count": skipped_files,
            "visited_file_count": visited_files,
            "file_limit_exceeded": file_limit_exceeded,
            "byte_limit_exceeded": byte_limit_exceeded,
            "probed_response_count": len(probe_urls) - probe_errors,
            "probe_error_count": probe_errors,
            "probe_limit_exceeded": probe_limit_exceeded,
            "truncated_response_count": truncated_responses,
            "finding_count": len(deduplicate(findings)),
        },
        "findings": deduplicate(findings),
    }


def main() -> int:
    plan = json.load(sys.stdin)
    if os.geteuid() == 0:
        raise SystemExit("fourth-wall observer refuses to run as uid 0")
    json.dump(observe(plan), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
