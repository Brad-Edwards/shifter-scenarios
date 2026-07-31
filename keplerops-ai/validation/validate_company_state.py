"""Validate the coherent synthetic company-state content graph."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

PACK_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = PACK_ROOT / "assets/content/company-state/company-state.yaml"
SECTIONS = (
    "teams",
    "people",
    "service_identities",
    "endpoints",
    "projects",
    "repositories",
    "datasets",
    "tickets",
    "commits",
    "experiments",
    "artifacts",
    "models",
    "approvals",
    "releases",
    "messages",
    "files",
    "operations",
)
ROOT_KEYS = {
    "schema_version",
    "organization",
    "represented_window",
    *SECTIONS,
}
IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
CHALLENGE_ID = re.compile(r"\bkep-m\d{2}-[a-z]\b", re.IGNORECASE)
PROHIBITED_TEXT = (
    re.compile(r"flag\s*\{", re.IGNORECASE),
    re.compile(r"kep\s*\{", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
PROHIBITED_KEYS = re.compile(r"(password|passwd|secret|credential|private_key|token)", re.IGNORECASE)
REFERENCE_TARGETS = {
    "lead_ref": {"people"},
    "team_ref": {"teams"},
    "owner_team_ref": {"teams"},
    "owner_ref": {"people", "service_identities"},
    "assignee_ref": {"people"},
    "author_ref": {"people"},
    "actor_ref": {"people", "service_identities"},
    "sender_ref": {"people", "service_identities"},
    "recipient_refs": {"people", "service_identities"},
    "endpoint_ref": {"endpoints"},
    "project_ref": {"projects"},
    "repository_ref": {"repositories"},
    "dataset_ref": {"datasets"},
    "dataset_refs": {"datasets"},
    "ticket_refs": {"tickets"},
    "commit_ref": {"commits"},
    "commit_refs": {"commits"},
    "experiment_ref": {"experiments"},
    "artifact_ref": {"artifacts"},
    "model_ref": {"models"},
    "model_refs": {"models"},
    "approver_ref": {"people"},
    "approval_ref": {"approvals"},
    "object_refs": set(SECTIONS),
}


class CompanyStateError(ValueError):
    """Raised when the authored company-state corpus is invalid."""


def load_corpus(path: Path = DEFAULT_CORPUS) -> dict[str, Any]:
    # Validator callers intentionally select the pack corpus under test.
    raw = path.read_text(encoding="utf-8")  # NOSONAR
    if len(raw.encode("utf-8")) > 1_048_576:
        raise CompanyStateError("company-state corpus exceeds 1 MiB")
    value = yaml.safe_load(raw)
    if not isinstance(value, dict):
        raise CompanyStateError("company-state corpus must be a mapping")
    return value


def canonical_corpus(corpus: dict[str, Any]) -> bytes:
    return json.dumps(
        corpus,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _timestamp(value: object, label: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        errors.append(f"{label} must be an RFC3339 UTC timestamp")
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{label} must be an RFC3339 UTC timestamp")
        return None


def _index(  # NOSONAR - one cohesive global-identity validation pass.
    corpus: dict[str, Any], errors: list[str]
) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    section_by_id: dict[str, str] = {}
    row_by_id: dict[str, dict[str, Any]] = {}
    for section in SECTIONS:
        rows = corpus.get(section)
        if not isinstance(rows, list) or not rows:
            errors.append(f"{section} must be a non-empty list")
            continue
        for offset, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"{section}[{offset}] must be a mapping")
                continue
            object_id = row.get("id")
            if not isinstance(object_id, str) or not IDENTIFIER.fullmatch(object_id):
                errors.append(f"{section}[{offset}].id is invalid")
                continue
            if object_id in section_by_id:
                errors.append(f"duplicate object id {object_id}")
                continue
            section_by_id[object_id] = section
            row_by_id[object_id] = row
    return section_by_id, row_by_id


def _references(  # NOSONAR - relation validation is clearer as one matrix pass.
    row_by_id: dict[str, dict[str, Any]],
    section_by_id: dict[str, str],
    errors: list[str],
) -> None:
    for object_id, row in row_by_id.items():
        for field, allowed_sections in REFERENCE_TARGETS.items():
            if field not in row:
                continue
            raw = row[field]
            values = raw if isinstance(raw, list) else [raw]
            if not values and field.endswith("_ref"):
                errors.append(f"{object_id}.{field} must not be empty")
            for reference in values:
                if not isinstance(reference, str):
                    errors.append(f"{object_id}.{field} contains a non-string reference")
                elif reference not in section_by_id:
                    errors.append(f"{object_id}.{field} references missing {reference}")
                elif section_by_id[reference] not in allowed_sections:
                    errors.append(f"{object_id}.{field} references wrong-kind {reference}")


def _timeline(  # NOSONAR - one cohesive represented-time invariant pass.
    corpus: dict[str, Any],
    row_by_id: dict[str, dict[str, Any]],
    errors: list[str],
) -> int:
    window = corpus.get("represented_window")
    if not isinstance(window, dict) or set(window) != {"start", "end", "participant_start"}:
        errors.append("represented_window has an invalid shape")
        return 0
    start = _timestamp(window.get("start"), "represented_window.start", errors)
    end = _timestamp(window.get("end"), "represented_window.end", errors)
    participant_start = _timestamp(
        window.get("participant_start"),
        "represented_window.participant_start",
        errors,
    )
    if start is None or end is None or participant_start is None:
        return 0
    if not start < end < participant_start:
        errors.append("represented window must end before participant start")
    for object_id, row in row_by_id.items():
        for field, value in row.items():
            if field.endswith("_at"):
                parsed = _timestamp(value, f"{object_id}.{field}", errors)
                if parsed is not None and not start <= parsed <= end:
                    errors.append(f"{object_id}.{field} falls outside represented window")
    for experiment in corpus.get("experiments", []):
        started = _timestamp(experiment.get("started_at"), f"{experiment.get('id')}.started_at", errors)
        completed = _timestamp(
            experiment.get("completed_at"),
            f"{experiment.get('id')}.completed_at",
            errors,
        )
        if started is not None and completed is not None and completed < started:
            errors.append(f"{experiment.get('id')} completes before it starts")
    for ticket in corpus.get("tickets", []):
        created = _timestamp(ticket.get("created_at"), f"{ticket.get('id')}.created_at", errors)
        updated = _timestamp(ticket.get("updated_at"), f"{ticket.get('id')}.updated_at", errors)
        if created is not None and updated is not None and updated < created:
            errors.append(f"{ticket.get('id')} updates before creation")
    return max(0, (end - start).days)


def _causal(  # NOSONAR - causal ordering is evaluated as one graph pass.
    corpus: dict[str, Any],
    row_by_id: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    def parsed(row: dict[str, Any], field: str) -> datetime:
        return datetime.fromisoformat(row[field].replace("Z", "+00:00"))

    represented_at = {
        "projects": "started_at",
        "datasets": "created_at",
        "tickets": "updated_at",
        "commits": "authored_at",
        "experiments": "completed_at",
        "artifacts": "created_at",
        "models": "created_at",
        "approvals": "decided_at",
        "releases": "released_at",
        "messages": "sent_at",
        "files": "updated_at",
        "operations": "occurred_at",
    }
    reference_available_at = {
        **represented_at,
        "tickets": "created_at",
    }
    event_time_by_id = {
        row["id"]: parsed(row, represented_at[section])
        for section in represented_at
        for row in corpus.get(section, [])
    }
    reference_time_by_id = {
        row["id"]: parsed(row, reference_available_at[section])
        for section in reference_available_at
        for row in corpus.get(section, [])
    }
    for object_id, row in row_by_id.items():
        object_time = event_time_by_id.get(object_id)
        if object_time is None:
            continue
        for field in REFERENCE_TARGETS:
            raw = row.get(field)
            references = raw if isinstance(raw, list) else [raw]
            for reference in references:
                reference_time = reference_time_by_id.get(reference)
                if reference_time is not None and reference_time > object_time:
                    errors.append(f"{object_id}.{field} references future {reference}")

    for model in corpus.get("models", []):
        experiment = row_by_id.get(model.get("experiment_ref"))
        artifact = row_by_id.get(model.get("artifact_ref"))
        if experiment and parsed(model, "created_at") < parsed(experiment, "completed_at"):
            errors.append(f"{model['id']} predates its experiment")
        if artifact and parsed(model, "created_at") < parsed(artifact, "created_at"):
            errors.append(f"{model['id']} predates its artifact")
    for approval in corpus.get("approvals", []):
        model = row_by_id.get(approval.get("model_ref"))
        if model and parsed(approval, "decided_at") < parsed(model, "created_at"):
            errors.append(f"{approval['id']} predates its model")
    for release in corpus.get("releases", []):
        model = row_by_id.get(release.get("model_ref"))
        approval = row_by_id.get(release.get("approval_ref"))
        commit = row_by_id.get(release.get("commit_ref"))
        released = parsed(release, "released_at")
        if model and released < parsed(model, "created_at"):
            errors.append(f"{release['id']} predates its model")
        if approval and released < parsed(approval, "decided_at"):
            errors.append(f"{release['id']} predates its approval")
        if commit and released < parsed(commit, "authored_at"):
            errors.append(f"{release['id']} predates its commit")


def _safety(  # NOSONAR - recursive content-policy validation is intentionally cohesive.
    corpus: dict[str, Any], errors: list[str]
) -> None:
    encoded = canonical_corpus(corpus).decode("ascii")
    for pattern in PROHIBITED_TEXT:
        if pattern.search(encoded):
            errors.append(f"corpus contains prohibited pattern {pattern.pattern}")
    if CHALLENGE_ID.search(encoded):
        errors.append("corpus must not contain evaluated challenge identifiers")

    def visit(value: object, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if PROHIBITED_KEYS.search(str(key)):
                    errors.append(f"{path}.{key} is a prohibited sensitive field")
                visit(item, f"{path}.{key}")
        elif isinstance(value, list):
            for offset, item in enumerate(value):
                visit(item, f"{path}[{offset}]")

    visit(corpus, "company_state")


def _source_digests(  # NOSONAR - path and digest checks form one invariant.
    row_by_id: dict[str, dict[str, Any]],
    object_root: Path,
    errors: list[str],
) -> None:
    for object_id, row in row_by_id.items():
        digest = row.get("digest")
        if digest is None:
            continue
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            errors.append(f"{object_id}.digest is invalid")
            continue
        source_path = row.get("source_path")
        if (
            not isinstance(source_path, str)
            or not source_path
            or Path(source_path).is_absolute()
            or ".." in Path(source_path).parts
        ):
            errors.append(f"{object_id}.source_path is invalid")
            continue
        source = object_root / source_path
        if source.is_symlink() or not source.is_file():
            errors.append(f"{object_id}.source_path is not a regular file")
            continue
        payload = source.read_bytes()
        if len(payload) > 1_048_576:
            errors.append(f"{object_id}.source_path exceeds 1 MiB")
            continue
        encoded = payload.decode("utf-8", errors="replace")
        for pattern in PROHIBITED_TEXT:
            if pattern.search(encoded):
                errors.append(
                    f"{object_id}.source_path contains prohibited pattern {pattern.pattern}"
                )
        if CHALLENGE_ID.search(encoded):
            errors.append(
                f"{object_id}.source_path contains an evaluated challenge identifier"
            )
        actual = "sha256:" + hashlib.sha256(payload).hexdigest()
        if actual != digest:
            errors.append(f"{object_id}.digest does not match source bytes")


def validate_corpus(
    corpus: dict[str, Any],
    object_root: Path = DEFAULT_CORPUS.parent,
) -> dict[str, Any]:
    errors: list[str] = []
    if set(corpus) != ROOT_KEYS:
        errors.append("company-state root keys do not match schema v1")
    if corpus.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    organization = corpus.get("organization")
    if (
        not isinstance(organization, dict)
        or organization.get("id") != "org-keplerops"
        or organization.get("synthetic") is not True
    ):
        errors.append("organization must declare the synthetic KeplerOps identity")
    section_by_id, row_by_id = _index(corpus, errors)
    _references(row_by_id, section_by_id, errors)
    represented_days = _timeline(corpus, row_by_id, errors)
    if not errors:
        _causal(corpus, row_by_id, errors)
    _safety(corpus, errors)
    _source_digests(row_by_id, object_root, errors)
    usernames = [
        row["username"]
        for section in ("people", "service_identities")
        for row in corpus.get(section, [])
        if isinstance(row, dict) and isinstance(row.get("username"), str)
    ]
    if len(usernames) != len(set(usernames)):
        errors.append("directory usernames must be unique")
    canonical = canonical_corpus(corpus)
    return {
        "schema_version": corpus.get("schema_version"),
        "object_count": len(row_by_id),
        "represented_days": represented_days,
        "canonical_digest": "sha256:" + hashlib.sha256(canonical).hexdigest(),
        "errors": sorted(set(errors)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("validate",), nargs="?", default="validate")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = validate_corpus(load_corpus(args.corpus), args.corpus.parent)
    except (OSError, CompanyStateError, yaml.YAMLError) as error:
        report = {"errors": [str(error)]}
    if args.json:
        print(json.dumps(report, separators=(",", ":"), sort_keys=True))
    elif report["errors"]:
        for error in report["errors"]:
            print(f"[error] {error}")
    else:
        print(
            "[ok] company state "
            f"({report['object_count']} objects; {report['represented_days']} represented days; "
            f"{report['canonical_digest']})"
        )
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
