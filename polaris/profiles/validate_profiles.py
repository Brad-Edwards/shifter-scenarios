#!/usr/bin/env python3
"""Validate Polaris delivery bundles as content-only ACES projections."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


PROFILES_DIR = Path(__file__).resolve().parent
PACK_ROOT = PROFILES_DIR.parent
sys.path.insert(0, str(PACK_ROOT))

from aces_contract import objective_projection  # noqa: E402
from contract_source import MAX_SOURCE_BYTES, load_yaml  # noqa: E402


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"validation dependency unavailable: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SHARED_ORACLE = _load_module(
    "polaris_profile_oracle_model",
    PACK_ROOT / "validation/oracle_model.py",
)
Issue = SHARED_ORACLE.Issue

TOKEN_PATTERNS = (
    re.compile(r"\bS-[A-Z]{3,}\b"),
    re.compile(r"\bS[12]\.\d{1,2}\b"),
    re.compile(r"\bT\d{4}(?:\.\d{3})?\b"),
    re.compile(r"(?<![\w.])(?:10|[1-9])\.[A-Z](?![\w])"),
)

MANIFEST_FILENAME = "bundles.yaml"
OBJECTIVE_CONTRACT_FILENAME = "objective-contract.yaml"
SCORING_MAP_FILENAME = "scoring-hooks.yaml"
REGULAR_FILE_DETAIL = "bounded contained regular file required"
BENCHMARK_ID = "agent-benchmark"
BENCHMARK_OBJECTIVE_REL = (
    f"{BENCHMARK_ID}/participant/{OBJECTIVE_CONTRACT_FILENAME}"
)
BENCHMARK_SCORING_REL = f"{BENCHMARK_ID}/operator/{SCORING_MAP_FILENAME}"

MANIFEST_PATH = f"profiles/{MANIFEST_FILENAME}"
PACK_PATH = "pack.yaml"
COMPATIBILITY_PATH = "pack.compatibility.yaml"
PROVENANCE_PATH = "docs/provenance-ledger.yaml"
ORACLE_PATH = "oracle/polaris-oracle.yaml"
PLACEMENT_PATH = "flags/placement.yaml"
CANONICAL_SCENARIO_PATH = "sdl/polaris-operation-northstorm.sdl.yaml"
VALIDATOR_PATH = "profiles/validate_profiles.py"

REQUIRED_BUNDLE_IDS = (
    "guided",
    "unguided",
    "purple-team",
    "agent-benchmark",
    "demo",
)
EXPECTED_AUDIENCES = {
    "guided": "participant",
    "unguided": "participant",
    "purple-team": "defender",
    "agent-benchmark": "benchmark_runner",
    "demo": "presenter",
}
COMPATIBILITY_AUDIENCES = {
    "guided": "guided",
    "unguided": "unguided",
    "purple-team": "purple-team",
    "agent-benchmark": "agent-benchmark",
    "demo": "demo",
}
EXPECTED_RUNTIME_PROFILES = {
    "guided": ["aws_event"],
    "unguided": ["aws_event"],
    "purple-team": ["aws_event"],
    "agent-benchmark": ["aws_event"],
    "demo": ["local_degraded", "aws_event"],
}
EXPECTED_AUDIENCE_SET = {
    "participant",
    "defender",
    "benchmark_runner",
    "presenter",
}

MANIFEST_FIELDS = {
    "schema_version",
    "name",
    "scenario",
    "description",
    "audiences",
    "required_bundles",
    "bundles",
}
BUNDLE_FIELDS = {
    "id",
    "title",
    "audience",
    "summary",
    "runtime_profiles",
    "shared_includes",
    "participant_entrypoints",
    "operator_entrypoints",
}
BENCHMARK_FIELDS = {"objective_contract", "scoring_map"}
STRUCTURAL_PROFILE_FILES = {
    "README.md",
    MANIFEST_FILENAME,
    "validate_profiles.py",
}
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?im)\b(?:answer|credential|username|password|secret|token|"
    r"flag(?:_id|_value)?)\s*(?:is|:|=)\s*\S+"
)
RESTRICTED_PHRASES = (
    "answer key",
    "oracle-only",
    "proof predicate",
    "raw evidence",
    "next step:",
    "next-step hint",
)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[opsu]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."
               r"[A-Za-z0-9_-]{10,}\b"),
)
RESTRICTED_STRUCTURED_KEYS = {
    "answer",
    "answers",
    "award",
    "awards",
    "consumer",
    "credential",
    "credentials",
    "evidence",
    "evidence_id",
    "failure_state",
    "failure_states",
    "flag",
    "flag_id",
    "flag_value",
    "hint",
    "hints",
    "maps",
    "next_step",
    "next_steps",
    "oracle_id",
    "outcome_id",
    "path_step",
    "path_steps",
    "points",
    "predicate",
    "predicates",
    "proof",
    "proof_fields",
    "raw_evidence",
    "required_evidence",
    "scoring_map",
    "secret",
    "success_state",
    "token",
}
PARTICIPANT_STRUCTURED_SUFFIXES = {".json", ".yaml", ".yml"}


def _issue(
    issues: list[Any],
    object_type: str,
    object_id: str,
    field: str,
    invariant: str,
    detail: str,
) -> None:
    issues.append(Issue(object_type, object_id, field, invariant, detail))


def _canonical_relative_path(value: Any) -> PurePosixPath | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    candidate = PurePosixPath(value)
    if (
        candidate.is_absolute()
        or ".." in candidate.parts
        or "." in candidate.parts
        or str(candidate) != value
    ):
        return None
    return candidate


def _pack_file(root: Path, relative: Any) -> Path | None:
    canonical = _canonical_relative_path(relative)
    if canonical is None:
        return None
    try:
        root_real = root.resolve(strict=True)
    except OSError:
        return None
    candidate = root.joinpath(*canonical.parts)
    current = root
    for part in canonical.parts:
        current = current / part
        if current.is_symlink():
            return None
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root_real)
    except (OSError, ValueError):
        return None
    if not candidate.is_file() or candidate.stat().st_size > MAX_SOURCE_BYTES:
        return None
    return candidate


def _load_contract(
    root: Path,
    relative: str,
    issues: list[Any],
) -> dict[str, Any] | None:
    path = _pack_file(root, relative)
    if path is None:
        _issue(
            issues,
            "file",
            relative,
            "",
            "regular_file",
            REGULAR_FILE_DETAIL,
        )
        return None
    try:
        return load_yaml(path)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError):
        _issue(
            issues,
            "file",
            relative,
            "",
            "contract_parse",
            "bounded duplicate-key-safe YAML mapping required",
        )
        return None


def _read_text(
    root: Path,
    relative: str,
    issues: list[Any],
) -> str | None:
    path = _pack_file(root, relative)
    if path is None:
        _issue(
            issues,
            "file",
            relative,
            "",
            "regular_file",
            REGULAR_FILE_DETAIL,
        )
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        _issue(
            issues,
            "file",
            relative,
            "",
            "utf8_text",
            "UTF-8 text required",
        )
        return None


def _string_list(
    value: Any,
    issues: list[Any],
    object_id: str,
    field: str,
) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        _issue(
            issues,
            "bundle",
            object_id,
            field,
            "string_list",
            "non-empty string list required",
        )
        return []
    if len(value) != len(set(value)):
        _issue(
            issues,
            "bundle",
            object_id,
            field,
            "duplicate_list_entry",
            "list entries must be unique",
        )
    return value


def _profile_entry(
    root: Path,
    bundle_id: str,
    visibility: str,
    relative: str,
    issues: list[Any],
) -> Path | None:
    canonical = _canonical_relative_path(relative)
    if canonical is None:
        _issue(
            issues,
            "bundle",
            bundle_id,
            relative,
            "canonical_path",
            "canonical contained POSIX path required",
        )
        return None
    parts = canonical.parts
    correct_root = (
        visibility == "shared"
        and len(parts) >= 2
        and parts[0] == "_shared"
    ) or (
        visibility != "shared"
        and len(parts) >= 3
        and parts[0] == bundle_id
        and parts[1] == visibility
    )
    if not correct_root:
        _issue(
            issues,
            "bundle",
            bundle_id,
            relative,
            "visibility_root",
            f"{visibility} profile root required",
        )
        return None
    path = _pack_file(root, f"profiles/{relative}")
    if path is None:
        _issue(
            issues,
            "bundle",
            bundle_id,
            relative,
            "regular_file",
            REGULAR_FILE_DETAIL,
        )
    return path


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _normalized_key(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _contains_restricted_key(value: Any) -> bool:
    if isinstance(value, dict):
        if any(_normalized_key(key) in RESTRICTED_STRUCTURED_KEYS for key in value):
            return True
        return any(_contains_restricted_key(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_restricted_key(child) for child in value)
    return False


def _mapping_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _string_field(row: dict[str, Any], field: str) -> set[str]:
    value = row.get(field)
    return {value} if isinstance(value, str) else set()


def _nested_ids(row: dict[str, Any], fields: tuple[str, ...]) -> set[str]:
    identifiers: set[str] = set()
    for field in fields:
        for child in _mapping_rows(row.get(field)):
            identifiers.update(_string_field(child, "id"))
    return identifiers


def _collect_row_identifiers(
    value: Any,
    direct_fields: tuple[str, ...],
    nested_fields: tuple[str, ...],
) -> set[str]:
    identifiers: set[str] = set()
    for row in _mapping_rows(value):
        for field in direct_fields:
            identifiers.update(_string_field(row, field))
        identifiers.update(_nested_ids(row, nested_fields))
    return identifiers


def _hidden_identifiers(oracle: dict[str, Any]) -> set[str]:
    identifiers = _string_field(oracle, "oracle_id")
    identifiers.update(
        _collect_row_identifiers(
            oracle.get("path_steps"),
            ("success_state",),
            ("required_evidence", "optional_evidence", "failure_states"),
        )
    )
    identifiers.update(
        _collect_row_identifiers(
            oracle.get("accepted_alternates"),
            ("id",),
            ("evidence",),
        )
    )
    return identifiers


def _flag_values(placement: dict[str, Any]) -> set[str]:
    return {
        row["value"]
        for row in placement.get("flags", []) or []
        if isinstance(row, dict)
        and isinstance(row.get("value"), str)
        and row["value"]
    }


def _record_line_issue(
    text: str,
    relative: str,
    offset: int,
    invariant: str,
    detail: str,
    issues: list[Any],
) -> None:
    _issue(
        issues,
        "participant",
        relative,
        "",
        invariant,
        f"{detail} at line {_line_number(text, offset)}",
    )


def _scan_repository_tokens(
    text: str,
    relative: str,
    issues: list[Any],
) -> None:
    for pattern in TOKEN_PATTERNS:
        match = pattern.search(text)
        if match:
            _record_line_issue(
                text,
                relative,
                match.start(),
                "repository_operator_token",
                "restricted token class",
                issues,
            )


def _scan_hidden_identifiers(
    text: str,
    relative: str,
    hidden_ids: set[str],
    issues: list[Any],
) -> None:
    for identifier in sorted(hidden_ids, key=len, reverse=True):
        match = re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(identifier)}"
            rf"(?![A-Za-z0-9_])",
            text,
        )
        if match:
            _record_line_issue(
                text,
                relative,
                match.start(),
                "hidden_identifier",
                "private identifier",
                issues,
            )
            return


def _scan_flag_values(
    text: str,
    relative: str,
    flag_values: set[str],
    issues: list[Any],
) -> None:
    for value in flag_values:
        offset = text.find(value)
        if offset >= 0:
            _record_line_issue(
                text,
                relative,
                offset,
                "exact_flag_value",
                "shipped flag value",
                issues,
            )
            return


def _scan_restricted_phrases(
    text: str,
    relative: str,
    issues: list[Any],
) -> None:
    lowered = text.lower()
    for phrase in RESTRICTED_PHRASES:
        offset = lowered.find(phrase)
        if offset >= 0:
            _record_line_issue(
                text,
                relative,
                offset,
                "restricted_phrase",
                "solution-directing phrase",
                issues,
            )
            return


def _scan_sensitive_assignment(
    text: str,
    relative: str,
    issues: list[Any],
) -> None:
    match = SENSITIVE_ASSIGNMENT.search(text)
    if match:
        _record_line_issue(
            text,
            relative,
            match.start(),
            "sensitive_assignment",
            "sensitive assignment shape",
            issues,
        )


def _scan_secret_shapes(
    text: str,
    relative: str,
    issues: list[Any],
) -> None:
    for pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            _record_line_issue(
                text,
                relative,
                match.start(),
                "secret_shape",
                "common secret shape",
                issues,
            )
            return


def _scan_text(
    text: str,
    relative: str,
    hidden_ids: set[str],
    flag_values: set[str],
    issues: list[Any],
) -> None:
    _scan_repository_tokens(text, relative, issues)
    _scan_hidden_identifiers(text, relative, hidden_ids, issues)
    _scan_flag_values(text, relative, flag_values, issues)
    _scan_restricted_phrases(text, relative, issues)
    _scan_sensitive_assignment(text, relative, issues)
    _scan_secret_shapes(text, relative, issues)


def _scan_participant(
    root: Path,
    relative: str,
    hidden_ids: set[str],
    flag_values: set[str],
    issues: list[Any],
) -> None:
    pack_relative = f"profiles/{relative}"
    text = _read_text(root, pack_relative, issues)
    if text is None:
        return
    _scan_text(relative, relative, hidden_ids, flag_values, issues)
    _scan_text(text, relative, hidden_ids, flag_values, issues)
    if Path(relative).suffix.lower() in PARTICIPANT_STRUCTURED_SUFFIXES:
        document = _load_contract(root, pack_relative, issues)
        if document is not None and _contains_restricted_key(document):
            _issue(
                issues,
                "participant",
                relative,
                "",
                "restricted_structured_key",
                "operator-only structured field is forbidden",
            )


def _manifest_rows(
    manifest: dict[str, Any],
    issues: list[Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    if set(manifest) != MANIFEST_FIELDS:
        _issue(
            issues,
            "manifest",
            MANIFEST_FILENAME,
            "fields",
            "manifest_shape",
            "exact manifest fields required",
        )
    if manifest.get("schema_version") != 1:
        _issue(
            issues,
            "manifest",
            MANIFEST_FILENAME,
            "schema_version",
            "schema_version",
            "schema version 1 required",
        )
    if manifest.get("scenario") != CANONICAL_SCENARIO_PATH:
        _issue(
            issues,
            "manifest",
            MANIFEST_FILENAME,
            "scenario",
            "scenario_authority",
            "canonical Polaris ACES path required",
        )
    audiences = manifest.get("audiences")
    if (
        not isinstance(audiences, list)
        or any(not isinstance(value, str) for value in audiences)
        or set(audiences) != EXPECTED_AUDIENCE_SET
        or len(audiences) != len(EXPECTED_AUDIENCE_SET)
    ):
        _issue(
            issues,
            "manifest",
            MANIFEST_FILENAME,
            "audiences",
            "audience_vocabulary",
            "exact audience vocabulary required",
        )
    rows = manifest.get("bundles")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        _issue(
            issues,
            "manifest",
            MANIFEST_FILENAME,
            "bundles",
            "bundle_rows",
            "bundle mapping list required",
        )
        rows = []
    ids = [
        row.get("id")
        for row in rows
        if isinstance(row.get("id"), str)
    ]
    if len(ids) != len(set(ids)):
        _issue(
            issues,
            "manifest",
            MANIFEST_FILENAME,
            "bundles",
            "duplicate_bundle_id",
            "bundle ids must be unique",
        )
    if ids != list(REQUIRED_BUNDLE_IDS):
        _issue(
            issues,
            "manifest",
            MANIFEST_FILENAME,
            "bundles",
            "required_bundle_ids",
            "five canonical bundle rows in canonical order required",
        )
    if manifest.get("required_bundles") != list(REQUIRED_BUNDLE_IDS):
        _issue(
            issues,
            "manifest",
            MANIFEST_FILENAME,
            "required_bundles",
            "required_bundle_ids",
            "required bundle index must match rows",
        )
    return rows, ids


def _runtime_profile_ids(compatibility: dict[str, Any]) -> set[str]:
    return {
        row["profile_id"]
        for row in compatibility.get("runtime_profiles", []) or []
        if isinstance(row, dict) and isinstance(row.get("profile_id"), str)
    }


def _validate_bundle_shape(
    row: dict[str, Any],
    runtime_ids: set[str],
    issues: list[Any],
) -> str | None:
    bundle_id = row.get("id")
    if not isinstance(bundle_id, str) or not ID_PATTERN.fullmatch(bundle_id):
        _issue(
            issues,
            "bundle",
            str(bundle_id),
            "id",
            "bundle_id",
            "kebab-case bundle id required",
        )
        return None
    expected_fields = BUNDLE_FIELDS | (
        BENCHMARK_FIELDS if bundle_id == "agent-benchmark" else set()
    )
    if set(row) != expected_fields:
        _issue(
            issues,
            "bundle",
            bundle_id,
            "fields",
            "unknown_fields",
            "exact bundle fields required",
        )
    if row.get("audience") != EXPECTED_AUDIENCES.get(bundle_id):
        _issue(
            issues,
            "bundle",
            bundle_id,
            "audience",
            "audience_join",
            "bundle audience must match canonical vocabulary",
        )
    expected_runtime = EXPECTED_RUNTIME_PROFILES.get(bundle_id)
    actual_runtime = row.get("runtime_profiles")
    if (
        actual_runtime != expected_runtime
        or not isinstance(actual_runtime, list)
        or any(value not in runtime_ids for value in actual_runtime)
    ):
        _issue(
            issues,
            "bundle",
            bundle_id,
            "runtime_profiles",
            "runtime_profile_join",
            "runtime ids must match existing compatibility profiles",
        )
    for field in ("title", "summary"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            _issue(
                issues,
                "bundle",
                bundle_id,
                field,
                "required_text",
                "non-empty text required",
            )
    return bundle_id


def _validate_entries(
    root: Path,
    bundle_id: str,
    row: dict[str, Any],
    hidden_ids: set[str],
    flag_values: set[str],
    declared: set[str],
    issues: list[Any],
) -> dict[str, list[str]]:
    projected: dict[str, list[str]] = {}
    for field, visibility in (
        ("shared_includes", "shared"),
        ("participant_entrypoints", "participant"),
        ("operator_entrypoints", "operator"),
    ):
        entries = _string_list(row.get(field), issues, bundle_id, field)
        projected[field] = entries
        for relative in entries:
            path = _profile_entry(root, bundle_id, visibility, relative, issues)
            if path is None:
                continue
            declared.add(relative)
            if visibility in {"shared", "participant"}:
                _scan_participant(
                    root,
                    relative,
                    hidden_ids,
                    flag_values,
                    issues,
                )
    return projected


def _path_refs(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {
        row["path"]
        for row in value
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }


def _compatibility_rows(
    compatibility: dict[str, Any],
    issues: list[Any],
) -> dict[str, dict[str, Any]]:
    rows = compatibility.get("delivery_bundles")
    if not isinstance(rows, list):
        _issue(
            issues,
            "compatibility",
            COMPATIBILITY_PATH,
            "delivery_bundles",
            "bundle_index_join",
            "delivery bundle rows required",
        )
        return {}
    ids = [
        row.get("bundle_id")
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("bundle_id"), str)
    ]
    if len(ids) != len(set(ids)):
        _issue(
            issues,
            "compatibility",
            COMPATIBILITY_PATH,
            "delivery_bundles",
            "duplicate_bundle_id",
            "compatibility bundle ids must be unique",
        )
    return {
        row["bundle_id"]: row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("bundle_id"), str)
    }


def _validate_compatibility_row(
    bundle_id: str,
    projected: dict[str, list[str]],
    compatibility_rows: dict[str, dict[str, Any]],
    issues: list[Any],
) -> None:
    row = compatibility_rows.get(bundle_id)
    if not isinstance(row, dict):
        _issue(
            issues,
            "bundle",
            bundle_id,
            "compatibility",
            "bundle_index_join",
            "matching compatibility row required",
        )
        return
    if (
        row.get("status") != "supported"
        or row.get("audience") != COMPATIBILITY_AUDIENCES[bundle_id]
        or row.get("manifest") != {"path": MANIFEST_PATH}
        or _path_refs(row.get("validation")) != {VALIDATOR_PATH}
    ):
        _issue(
            issues,
            "bundle",
            bundle_id,
            "compatibility",
            "compatibility_projection",
            "supported manifest audience and validator projection required",
        )
    expected_participant = (
        {f"profiles/{bundle_id}/participant/"}
        if projected["participant_entrypoints"]
        else set()
    )
    expected_operator = (
        {f"profiles/{bundle_id}/operator/"}
        if projected["operator_entrypoints"]
        else set()
    )
    if _path_refs(row.get("participant_paths")) != expected_participant:
        _issue(
            issues,
            "bundle",
            bundle_id,
            "participant_paths",
            "compatibility_projection",
            "participant compatibility path must match manifest exposure",
        )
    if _path_refs(row.get("operator_paths")) != expected_operator:
        _issue(
            issues,
            "bundle",
            bundle_id,
            "operator_paths",
            "compatibility_projection",
            "operator compatibility path must match manifest exposure",
        )


def _pack_bundle_ids(pack: dict[str, Any], issues: list[Any]) -> list[str]:
    index = pack.get("profile_bundles")
    if not isinstance(index, dict):
        _issue(
            issues,
            "pack",
            PACK_PATH,
            "profile_bundles",
            "bundle_index_join",
            "profile bundle index required",
        )
        return []
    if index.get("manifest") != MANIFEST_PATH:
        _issue(
            issues,
            "pack",
            PACK_PATH,
            "profile_bundles.manifest",
            "bundle_index_join",
            "canonical manifest pointer required",
        )
    rows = index.get("bundles")
    if not isinstance(rows, list):
        _issue(
            issues,
            "pack",
            PACK_PATH,
            "profile_bundles.bundles",
            "bundle_index_join",
            "bundle index rows required",
        )
        return []
    return [
        row.get("id")
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    ]


def _benchmark_projection(
    oracle: dict[str, Any],
    issues: list[Any],
) -> dict[str, dict[str, Any]]:
    try:
        rendered = SHARED_ORACLE.render_export(oracle, "agent_benchmark")
    except (ValueError, SHARED_ORACLE.OracleValidationError):
        _issue(
            issues,
            "benchmark",
            "agent-benchmark",
            "",
            "oracle_projection",
            "validated shared benchmark projection required",
        )
        return {}
    projection: dict[str, dict[str, Any]] = {}
    for row in rendered.get("outcomes", []) or []:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            continue
        native = next(
            (
                award
                for award in row.get("awards", []) or []
                if isinstance(award, dict)
                and award.get("consumer") == "native-verdict"
            ),
            None,
        )
        projection[row["id"]] = {
            "title": row.get("title"),
            "required": row.get("required"),
            "points": native.get("points") if native else None,
        }
    return projection


def _load_benchmark_documents(
    root: Path,
    row: dict[str, Any],
    issues: list[Any],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    objective_rel = row.get("objective_contract")
    scoring_rel = row.get("scoring_map")
    if objective_rel != BENCHMARK_OBJECTIVE_REL or scoring_rel != BENCHMARK_SCORING_REL:
        _issue(
            issues,
            "benchmark",
            BENCHMARK_ID,
            "paths",
            "benchmark_paths",
            "canonical participant and operator benchmark paths required",
        )
        return None
    objectives = _load_contract(root, f"profiles/{objective_rel}", issues)
    scoring = _load_contract(root, f"profiles/{scoring_rel}", issues)
    if objectives is None or scoring is None:
        return None
    return objectives, scoring


def _aces_objective_ids(
    root: Path,
    issues: list[Any],
) -> set[str] | None:
    try:
        return set(objective_projection(root))
    except (OSError, ValueError, KeyError, AttributeError):
        _issue(
            issues,
            "benchmark",
            BENCHMARK_ID,
            "objectives",
            "aces_objective_projection",
            "typed ACES objective projection required",
        )
        return None


def _objective_rows(
    objectives: dict[str, Any],
    issues: list[Any],
) -> list[Any]:
    rows = objectives.get("objectives")
    if isinstance(rows, list):
        return rows
    _issue(
        issues,
        "benchmark",
        OBJECTIVE_CONTRACT_FILENAME,
        "objectives",
        "benchmark_objective_shape",
        "objective mapping list required",
    )
    return []


def _validate_public_objective(
    objective: Any,
    private_projection: dict[str, dict[str, Any]],
    public_ids: list[str],
    issues: list[Any],
) -> None:
    if not isinstance(objective, dict):
        _issue(
            issues,
            "benchmark",
            OBJECTIVE_CONTRACT_FILENAME,
            "objectives",
            "benchmark_objective_shape",
            "objective mapping required",
        )
        return
    if set(objective) != {"id", "title", "description", "required"}:
        _issue(
            issues,
            "benchmark",
            str(objective.get("id")),
            "fields",
            "benchmark_objective_shape",
            "participant-safe objective fields required",
        )
    objective_id = objective.get("id")
    if isinstance(objective_id, str):
        public_ids.append(objective_id)
        source = private_projection.get(objective_id)
        if (
            source is None
            or objective.get("title") != source["title"]
            or objective.get("required") != source["required"]
        ):
            _issue(
                issues,
                "benchmark",
                objective_id,
                "projection",
                "benchmark_outcome_join",
                "public objective must project the existing safe id and title",
            )
    if (
        not isinstance(objective.get("description"), str)
        or not objective["description"].strip()
    ):
        _issue(
            issues,
            "benchmark",
            str(objective_id),
            "description",
            "benchmark_objective_shape",
            "participant-safe description required",
        )


def _validate_public_objectives(
    objectives: dict[str, Any],
    private_projection: dict[str, dict[str, Any]],
    aces_ids: set[str],
    issues: list[Any],
) -> list[str]:
    public_ids: list[str] = []
    for objective in _objective_rows(objectives, issues):
        _validate_public_objective(
            objective,
            private_projection,
            public_ids,
            issues,
        )
    if set(public_ids) != aces_ids or len(public_ids) != len(set(public_ids)):
        _issue(
            issues,
            "benchmark",
            OBJECTIVE_CONTRACT_FILENAME,
            "objectives",
            "benchmark_outcome_join",
            "public objective ids must exactly match ACES objectives",
        )
    return public_ids


def _scoring_rows(
    scoring: dict[str, Any],
    issues: list[Any],
) -> list[Any]:
    rows = scoring.get("maps")
    if isinstance(rows, list):
        return rows
    _issue(
        issues,
        "benchmark",
        SCORING_MAP_FILENAME,
        "maps",
        "benchmark_scoring_shape",
        "operator scoring map list required",
    )
    return []


def _validate_scoring_mapping(
    mapping: Any,
    public_ids: list[str],
    private_projection: dict[str, dict[str, Any]],
    mapped: set[str],
    issues: list[Any],
) -> None:
    if not isinstance(mapping, dict):
        _issue(
            issues,
            "benchmark",
            SCORING_MAP_FILENAME,
            "maps",
            "benchmark_scoring_shape",
            "operator scoring mapping required",
        )
        return
    if set(mapping) != {
        "objective",
        "outcome_id",
        "consumer",
        "points",
    }:
        _issue(
            issues,
            "benchmark",
            str(mapping.get("objective")),
            "fields",
            "benchmark_scoring_shape",
            "exact native-award join fields required",
        )
    objective_id = mapping.get("objective")
    outcome_id = mapping.get("outcome_id")
    if isinstance(objective_id, str):
        mapped.add(objective_id)
    source = private_projection.get(str(outcome_id))
    if (
        objective_id not in public_ids
        or outcome_id != objective_id
        or source is None
        or mapping.get("consumer") != "native-verdict"
        or mapping.get("points") != source["points"]
    ):
        _issue(
            issues,
            "benchmark",
            str(objective_id),
            "outcome_id",
            "benchmark_outcome_join",
            "operator mapping must project the existing native award",
        )


def _validate_scoring(
    scoring: dict[str, Any],
    public_ids: list[str],
    private_projection: dict[str, dict[str, Any]],
    issues: list[Any],
) -> None:
    mapped: set[str] = set()
    for mapping in _scoring_rows(scoring, issues):
        _validate_scoring_mapping(
            mapping,
            public_ids,
            private_projection,
            mapped,
            issues,
        )
    if mapped != set(public_ids):
        _issue(
            issues,
            "benchmark",
            SCORING_MAP_FILENAME,
            "maps",
            "benchmark_objective_coverage",
            "every public objective requires one native-award mapping",
        )


def _validate_benchmark(
    root: Path,
    row: dict[str, Any],
    oracle: dict[str, Any],
    issues: list[Any],
) -> None:
    documents = _load_benchmark_documents(root, row, issues)
    if documents is None:
        return
    objectives, scoring = documents
    aces_ids = _aces_objective_ids(root, issues)
    if aces_ids is None:
        return
    private_projection = _benchmark_projection(oracle, issues)
    if set(private_projection) != aces_ids:
        _issue(
            issues,
            "benchmark",
            BENCHMARK_ID,
            "objectives",
            "benchmark_outcome_join",
            "private benchmark outcomes must match ACES objectives",
        )
    public_ids = _validate_public_objectives(
        objectives,
        private_projection,
        aces_ids,
        issues,
    )
    _validate_scoring(scoring, public_ids, private_projection, issues)


def _expected_profile_roots(
    rows: list[dict[str, Any]],
) -> tuple[set[str], set[str]]:
    participant = {"profiles/_shared/"}
    operator: set[str] = set()
    for row in rows:
        bundle_id = row.get("id")
        if not isinstance(bundle_id, str):
            continue
        if row.get("participant_entrypoints"):
            participant.add(f"profiles/{bundle_id}/participant/")
        if row.get("operator_entrypoints"):
            operator.add(f"profiles/{bundle_id}/operator/")
    return participant, operator


def _nested_value(
    document: dict[str, Any],
    parent: str,
    field: str,
) -> Any:
    value = document.get(parent)
    return value.get(field) if isinstance(value, dict) else None


def _validate_bundle_index_metadata(
    pack: dict[str, Any],
    ids: list[str],
    compatibility_rows: dict[str, dict[str, Any]],
    issues: list[Any],
) -> None:
    contents = pack.get("contents")
    if not isinstance(contents, dict) or contents.get("profile_bundles") is not True:
        _issue(
            issues,
            "pack",
            PACK_PATH,
            "contents.profile_bundles",
            "bundle_index_join",
            "profile bundle content flag must be true",
        )
    pack_ids = _pack_bundle_ids(pack, issues)
    if (
        ids != list(REQUIRED_BUNDLE_IDS)
        or pack_ids != ids
        or set(compatibility_rows) != set(ids)
    ):
        _issue(
            issues,
            "manifest",
            MANIFEST_FILENAME,
            "joins",
            "bundle_index_join",
            "manifest pack and compatibility ids must agree",
        )


def _validate_release_metadata(
    pack: dict[str, Any],
    compatibility: dict[str, Any],
    provenance: dict[str, Any],
    issues: list[Any],
) -> None:
    versions = {
        pack.get("version"),
        _nested_value(compatibility, "pack", "version"),
        _nested_value(provenance, "pack", "version"),
    }
    if len(versions) != 1 or None in versions:
        _issue(
            issues,
            "pack",
            "polaris",
            "version",
            "pack_version_join",
            "pack compatibility and provenance versions must agree",
        )
    artifacts = provenance.get("artifacts")
    profile_artifacts = {
        row.get("path")
        for row in artifacts or []
        if isinstance(row, dict) and row.get("artifact_id") == "profiles"
    }
    if profile_artifacts != {"profiles/"}:
        _issue(
            issues,
            "provenance",
            PROVENANCE_PATH,
            "artifacts",
            "profile_provenance",
            "profile artifact classification required",
        )


def _validate_profile_boundaries(
    compatibility: dict[str, Any],
    oracle: dict[str, Any],
    rows: list[dict[str, Any]],
    issues: list[Any],
) -> None:
    expected_participant, expected_operator = _expected_profile_roots(rows)
    boundaries = compatibility.get("artifact_boundaries")
    boundary_participant = _path_refs(
        boundaries.get("participant_visible")
        if isinstance(boundaries, dict)
        else None
    )
    boundary_operator = _path_refs(
        boundaries.get("operator_only")
        if isinstance(boundaries, dict)
        else None
    )
    if not expected_participant.issubset(boundary_participant):
        _issue(
            issues,
            "compatibility",
            COMPATIBILITY_PATH,
            "artifact_boundaries.participant_visible",
            "participant_root_join",
            "every participant profile root must be classified",
        )
    if not expected_operator.issubset(boundary_operator):
        _issue(
            issues,
            "compatibility",
            COMPATIBILITY_PATH,
            "artifact_boundaries.operator_only",
            "operator_root_join",
            "every operator profile root must be classified",
        )
    visibility = oracle.get("visibility")
    oracle_participant = _path_refs(
        visibility.get("participant_roots")
        if isinstance(visibility, dict)
        else None
    )
    if not expected_participant.issubset(oracle_participant):
        _issue(
            issues,
            "oracle",
            ORACLE_PATH,
            "visibility.participant_roots",
            "participant_root_join",
            "private visibility must name every participant profile root",
        )


def _validate_metadata(
    pack: dict[str, Any],
    compatibility: dict[str, Any],
    provenance: dict[str, Any],
    oracle: dict[str, Any],
    ids: list[str],
    rows: list[dict[str, Any]],
    compatibility_rows: dict[str, dict[str, Any]],
    issues: list[Any],
) -> None:
    _validate_bundle_index_metadata(pack, ids, compatibility_rows, issues)
    _validate_release_metadata(pack, compatibility, provenance, issues)
    _validate_profile_boundaries(compatibility, oracle, rows, issues)


def _scan_profile_tree(
    root: Path,
    declared: set[str],
    hidden_ids: set[str],
    flag_values: set[str],
    issues: list[Any],
) -> None:
    profiles = root / "profiles"
    if not profiles.is_dir():
        return
    for path in profiles.rglob("*"):
        relative = path.relative_to(profiles).as_posix()
        parts = PurePosixPath(relative).parts
        if parts and parts[0] in {"tests", "__pycache__"}:
            continue
        if path.is_symlink():
            _issue(
                issues,
                "profile",
                relative,
                "",
                "symlink_profile_entry",
                "profile tree symlinks are forbidden",
            )
            continue
        if not path.is_file():
            continue
        if relative in STRUCTURAL_PROFILE_FILES or relative in declared:
            continue
        _issue(
            issues,
            "profile",
            relative,
            "",
            "undeclared_profile_content",
            "every profile content file must be declared",
        )
        if relative.startswith("_shared/") or "/participant/" in f"/{relative}":
            _scan_participant(
                root,
                relative,
                hidden_ids,
                flag_values,
                issues,
            )


def validate_pack(root: Path = PACK_ROOT) -> list[Any]:
    """Return accumulated, redacted validation issues for one Polaris pack."""

    root = Path(root)
    issues: list[Any] = []
    manifest = _load_contract(root, MANIFEST_PATH, issues)
    pack = _load_contract(root, PACK_PATH, issues)
    compatibility = _load_contract(root, COMPATIBILITY_PATH, issues)
    provenance = _load_contract(root, PROVENANCE_PATH, issues)
    oracle = _load_contract(root, ORACLE_PATH, issues)
    placement = _load_contract(root, PLACEMENT_PATH, issues)
    if not all(
        document is not None
        for document in (
            manifest,
            pack,
            compatibility,
            provenance,
            oracle,
            placement,
        )
    ):
        return issues
    assert manifest is not None
    assert pack is not None
    assert compatibility is not None
    assert provenance is not None
    assert oracle is not None
    assert placement is not None

    rows, ids = _manifest_rows(manifest, issues)
    compatibility_rows = _compatibility_rows(compatibility, issues)
    runtime_ids = _runtime_profile_ids(compatibility)
    hidden_ids = _hidden_identifiers(oracle)
    flag_values = _flag_values(placement)
    declared: set[str] = set()

    for row in rows:
        bundle_id = _validate_bundle_shape(row, runtime_ids, issues)
        if bundle_id is None:
            continue
        projected = _validate_entries(
            root,
            bundle_id,
            row,
            hidden_ids,
            flag_values,
            declared,
            issues,
        )
        _validate_compatibility_row(
            bundle_id,
            projected,
            compatibility_rows,
            issues,
        )
        if bundle_id == "agent-benchmark":
            _validate_benchmark(root, row, oracle, issues)

    _validate_metadata(
        pack,
        compatibility,
        provenance,
        oracle,
        ids,
        rows,
        compatibility_rows,
        issues,
    )
    _scan_profile_tree(
        root,
        declared,
        hidden_ids,
        flag_values,
        issues,
    )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        choices=("validate",),
        default="validate",
    )
    parser.parse_args()
    issues = validate_pack()
    if issues:
        print(f"Polaris delivery bundles: FAIL ({len(issues)} issue(s))")
        for issue in issues:
            print(f" - {issue}")
        return 1
    print("Polaris delivery bundles: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
