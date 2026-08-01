#!/usr/bin/env python3
"""Capture and verify product-owned state across disposable-worker replacement."""

from __future__ import annotations

import argparse
import base64
import email
import hashlib
import imaplib
import json
import os
import ssl
import sys
import urllib.parse
import urllib.error
import urllib.request
from email import policy
from pathlib import Path
from typing import Any


SCHEMA = "keplerops.clean-enterprise.worker-replacement/v1"


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def basic_auth(value: str) -> str:
    return "Basic " + base64.b64encode(value.encode()).decode()


def request_bytes(
    url: str,
    *,
    authorization: str | None = None,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> bytes:
    request_headers = dict(headers or {})
    if authorization:
        request_headers["Authorization"] = authorization
    request = urllib.request.Request(
        url, data=data, headers=request_headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read(1000).decode(errors="replace")
        raise RuntimeError(
            f"{method} {url} returned HTTP {exc.code}: {body}"
        ) from exc


def request_json(url: str, **kwargs: Any) -> Any:
    return json.loads(request_bytes(url, **kwargs))


def post_json(url: str, payload: dict[str, Any]) -> Any:
    return request_json(
        url,
        method="POST",
        data=json.dumps(payload, separators=(",", ":")).encode(),
        headers={"Content-Type": "application/json"},
    )


def mail_message(user: str, password: str, correlation: str) -> dict[str, Any]:
    context = ssl.create_default_context()
    if not os.getenv("MAIL_CA_FILE"):
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    else:
        context.load_verify_locations(os.environ["MAIL_CA_FILE"])

    host = env("IMAP_HOST", "10.61.10.20")
    port = int(env("IMAP_PORT", "993"))
    with imaplib.IMAP4_SSL(host, port, ssl_context=context, timeout=20) as mailbox:
        mailbox.login(user, password)
        status, _ = mailbox.select("INBOX", readonly=True)
        if status != "OK":
            raise RuntimeError(f"cannot select mailbox for {user}")
        status, matches = mailbox.search(None, "SUBJECT", f'"{correlation}"')
        if status != "OK" or not matches[0]:
            raise RuntimeError(f"mail correlation is absent for {user}: {correlation}")
        message_number = matches[0].split()[-1]
        status, payload = mailbox.fetch(message_number, "(RFC822)")
        if status != "OK" or not payload or not isinstance(payload[0], tuple):
            raise RuntimeError(f"cannot fetch mail correlation for {user}")
        raw = payload[0][1]

    parsed = email.message_from_bytes(raw, policy=policy.default)
    attachments = []
    for part in parsed.iter_attachments():
        body = part.get_payload(decode=True) or b""
        attachments.append(
            {"filename": part.get_filename() or "", "sha256": sha256(body)}
        )
    return {
        "message_id": parsed.get("Message-ID", ""),
        "in_reply_to": parsed.get("In-Reply-To", ""),
        "subject": parsed.get("Subject", ""),
        "workflow": parsed.get("X-KeplerOps-Workflow", ""),
        "attachments": attachments,
        "rfc822_sha256": sha256(raw),
    }


def collect_mail(correlation: str) -> dict[str, Any]:
    original = mail_message(
        env("REVIEWER_MAIL_USER", "reviewer"),
        env("REVIEWER_MAIL_PASSWORD", "KeplerV2-Training-Reviewer"),
        correlation,
    )
    reply = mail_message(
        env("CINDER_MAIL_USER", "cinder.operator"),
        env("CINDER_MAIL_PASSWORD", "KeplerV2-Training-Cinder"),
        correlation,
    )
    if original["workflow"] != correlation or reply["workflow"] != correlation:
        raise RuntimeError("mail workflow correlation changed")
    if reply["in_reply_to"] != original["message_id"]:
        raise RuntimeError("mail reply no longer references the original message")
    return {"correlation": correlation, "original": original, "reply": reply}


def collect_intake(anchors: dict[str, str]) -> dict[str, Any]:
    zammad_url = env("ZAMMAD_URL", "http://10.61.50.43:8080")
    zammad_auth = basic_auth(env("ZAMMAD_AUTH", "range-admin:KeplerV2-Training-Zammad-Admin"))
    redmine_url = env("REDMINE_URL", "http://10.61.50.41:3000")
    redmine_auth = basic_auth(env("REDMINE_AUTH", "range-admin:KeplerV2-Training-Redmine-Admin"))
    nextcloud_url = env("NEXTCLOUD_URL", "http://10.61.50.42")
    nextcloud_auth = basic_auth(env("NEXTCLOUD_AUTH", "range-admin:KeplerV2-Training-Nextcloud"))
    qdrant_url = env("QDRANT_URL", "http://10.61.50.62:6333")

    ticket = request_json(
        f"{zammad_url}/api/v1/tickets/{anchors['ticket_id']}",
        authorization=zammad_auth,
    )
    if str(ticket["number"]) != anchors["ticket_number"]:
        raise RuntimeError("Zammad ticket number changed")
    articles = request_json(
        f"{zammad_url}/api/v1/ticket_articles/by_ticket/{anchors['ticket_id']}",
        authorization=zammad_auth,
    )
    completion = [
        item for item in articles if item.get("subject") == "Orion intake processing complete"
    ]
    if not completion:
        raise RuntimeError("Zammad intake completion article is absent")

    issue = request_json(
        f"{redmine_url}/issues/{anchors['issue_id']}.json",
        authorization=redmine_auth,
    )["issue"]
    point = request_json(
        f"{qdrant_url}/collections/orion_partner_intake/points/{anchors['point_id']}"
    )["result"]
    document_path = urllib.parse.quote(
        f"Orion Review Room/Partner Intake/{anchors['ticket_number']}-partner-note.txt"
    )
    document = request_bytes(
        f"{nextcloud_url}/remote.php/dav/files/range-admin/{document_path}",
        authorization=nextcloud_auth,
        headers={"Host": env("NEXTCLOUD_HOST", "files.keplerops.lab")},
    )

    document_sha = sha256(document)
    if document_sha != anchors["document_sha256"]:
        raise RuntimeError("Nextcloud intake document digest changed")
    if point.get("payload", {}).get("sha256") != anchors["document_sha256"]:
        raise RuntimeError("Qdrant payload no longer references the intake document")
    if anchors["document_sha256"] not in issue.get("description", ""):
        raise RuntimeError("WorkHub issue no longer references the intake document")

    return {
        **anchors,
        "zammad": {
            "title": ticket.get("title", ""),
            "group_id": ticket.get("group_id"),
            "completion_sha256": canonical_sha(completion[-1].get("body", "")),
        },
        "workhub": {
            "subject": issue.get("subject", ""),
            "description_sha256": canonical_sha(issue.get("description", "")),
            "project_id": issue.get("project", {}).get("id"),
        },
        "qdrant_payload_sha256": canonical_sha(point.get("payload", {})),
    }


def collect_source() -> dict[str, Any]:
    forgejo = env("FORGEJO_URL", "http://10.61.40.20:3000")
    forgejo_auth = basic_auth(env("FORGEJO_AUTH", "range-admin:KeplerV2-Training-Forgejo-Admin"))
    repository = env("FORGEJO_REPOSITORY", "keplerops/orion-build")
    branch = request_json(
        f"{forgejo}/api/v1/repos/{repository}/branches/main",
        authorization=forgejo_auth,
    )
    revision = branch["commit"]["id"]
    runs = request_json(
        f"{forgejo}/api/v1/repos/{repository}/actions/tasks?limit=1",
        authorization=forgejo_auth,
    )
    run = max(runs["workflow_runs"], key=lambda item: int(item["id"]))
    if run.get("status") != "success" or run.get("head_sha") != revision:
        raise RuntimeError("latest Forgejo publication does not match main")

    harbor = env("HARBOR_URL", "http://10.61.40.32:8080")
    harbor_auth = basic_auth(env("HARBOR_AUTH", "admin:KeplerV2-Training-Harbor"))
    artifacts = request_json(
        f"{harbor}/api/v2.0/projects/orion-build/repositories/orion-release-metadata/artifacts?with_tag=true",
        authorization=harbor_auth,
    )
    short = revision[:12]
    matches = []
    for artifact in artifacts:
        tags = {tag["name"] for tag in artifact.get("tags") or []}
        image_env = artifact.get("extra_attrs", {}).get("config", {}).get("Env", [])
        if short in tags and f"ORION_BUILD_REVISION={revision}" in image_env:
            matches.append(artifact)
    if len(matches) != 1:
        raise RuntimeError("cannot identify the revision-bound Harbor artifact")
    return {
        "repository": repository,
        "revision": revision,
        "workflow_run_id": str(run["id"]),
        "workflow_run_number": str(run["run_number"]),
        "harbor_digest": matches[0]["digest"],
    }


def collect_gitops() -> dict[str, str]:
    forgejo = env("FORGEJO_URL", "http://10.61.40.20:3000")
    forgejo_auth = basic_auth(env("FORGEJO_AUTH", "range-admin:KeplerV2-Training-Forgejo-Admin"))
    repository = env("FORGEJO_GITOPS_REPOSITORY", "keplerops/orion-platform")
    branch = request_json(
        f"{forgejo}/api/v1/repos/{repository}/branches/main",
        authorization=forgejo_auth,
    )
    return {"repository": repository, "revision": branch["commit"]["id"]}


def mlflow_run(
    run_id: str | None = None, export_sha: str | None = None
) -> dict[str, Any]:
    mlflow = env("MLFLOW_URL", "http://10.61.40.36:5000")
    if run_id:
        return request_json(
            f"{mlflow}/api/2.0/mlflow/runs/get?{urllib.parse.urlencode({'run_id': run_id})}"
        )["run"]

    experiments = post_json(
        f"{mlflow}/api/2.0/mlflow/experiments/search", {"max_results": 100}
    )
    name = env("MLFLOW_EXPERIMENT", "Orion Clean Intent Training")
    experiment_id = next(
        item["experiment_id"] for item in experiments["experiments"] if item["name"] == name
    )
    runs = post_json(
        f"{mlflow}/api/2.0/mlflow/runs/search",
        {
            "experiment_ids": [experiment_id],
            "max_results": 100,
            "order_by": ["attributes.start_time DESC"],
        },
    )
    for run in runs.get("runs", []):
        tags = {item["key"]: item["value"] for item in run["data"].get("tags", [])}
        if run["info"]["status"] != "FINISHED" or tags.get("stage") != "clean-baseline":
            continue
        if export_sha is None:
            return run
        if tags.get("source.export_sha256") != export_sha:
            continue
        commit_id = tags.get("data.lakefs_commit")
        if not commit_id:
            continue
        lakefs = env("LAKEFS_URL", "http://10.61.40.51:8000")
        lakefs_auth = basic_auth(
            env(
                "LAKEFS_AUTH",
                "KeplerLakeFSAccess:KeplerV2-Training-LakeFS-Object-Key",
            )
        )
        commit = request_json(
            f"{lakefs}/api/v1/repositories/orion/commits/{commit_id}",
            authorization=lakefs_auth,
        )
        if commit.get("metadata", {}).get("export_sha256") == export_sha:
            return run
    raise RuntimeError("no finished clean-baseline MLflow run exists")


def collect_training(run_id: str | None = None) -> dict[str, Any]:
    label_url = env("LABEL_STUDIO_URL", "http://10.61.40.34:8080")
    label_token = env("LABEL_STUDIO_TOKEN", "31a5a4b4ab3cdbaf110644eed06853b2b418daf6")
    project_name = env("LABEL_STUDIO_PROJECT", "Orion Intent Annotation Baseline")
    projects = request_json(
        f"{label_url}/api/projects?page_size=100",
        authorization=f"Token {label_token}",
    )
    project = next(item for item in projects["results"] if item["title"] == project_name)
    exported = request_json(
        f"{label_url}/api/projects/{project['id']}/export?exportType=JSON",
        authorization=f"Token {label_token}",
    )
    export_sha = canonical_sha(exported)

    run = mlflow_run(run_id, export_sha)
    tags = {item["key"]: item["value"] for item in run["data"].get("tags", [])}
    params = {item["key"]: item["value"] for item in run["data"].get("params", [])}
    metrics = {item["key"]: item["value"] for item in run["data"].get("metrics", [])}
    if tags.get("source.export_sha256") != export_sha:
        raise RuntimeError("MLflow run no longer matches the Label Studio export")
    lakefs_commit = tags["data.lakefs_commit"]
    lakefs = env("LAKEFS_URL", "http://10.61.40.51:8000")
    lakefs_auth = basic_auth(env("LAKEFS_AUTH", "KeplerLakeFSAccess:KeplerV2-Training-LakeFS-Object-Key"))
    repository = env("LAKEFS_REPOSITORY", "orion")
    commit = request_json(
        f"{lakefs}/api/v1/repositories/{repository}/commits/{lakefs_commit}",
        authorization=lakefs_auth,
    )
    if commit.get("metadata", {}).get("export_sha256") != export_sha:
        raise RuntimeError("lakeFS commit no longer matches the Label Studio export")

    run_id_value = run["info"]["run_id"]
    weights = request_bytes(
        f"{env('MLFLOW_URL', 'http://10.61.40.36:5000')}/get-artifact?"
        + urllib.parse.urlencode(
            {"run_id": run_id_value, "path": "model/adapter_model.safetensors"}
        )
    )
    weights_sha = sha256(weights)
    if tags.get("model.weights_sha256") != weights_sha:
        raise RuntimeError("MLflow weights digest changed")
    return {
        "label_studio_project_id": str(project["id"]),
        "label_export_sha256": export_sha,
        "lakefs_repository": repository,
        "lakefs_commit": lakefs_commit,
        "dvc_md5": tags.get("data.dvc_md5", ""),
        "mlflow_run_id": run_id_value,
        "records": params.get("records", ""),
        "training_accuracy": metrics.get("training_accuracy"),
        "weights_sha256": weights_sha,
    }


def collect(args: argparse.Namespace, expected: dict[str, Any] | None = None) -> dict[str, Any]:
    if expected:
        intake_anchors = {
            key: expected["intake"][key]
            for key in (
                "ticket_number",
                "ticket_id",
                "issue_id",
                "point_id",
                "document_sha256",
            )
        }
        correlation = expected["mail"]["correlation"]
        run_id = expected["training"]["mlflow_run_id"]
    else:
        intake_anchors = {
            "ticket_number": args.ticket_number,
            "ticket_id": args.ticket_id,
            "issue_id": args.issue_id,
            "point_id": args.point_id,
            "document_sha256": args.document_sha256,
        }
        correlation = args.mail_correlation
        run_id = None

    host_state = json.loads(Path(args.host_state).read_text(encoding="utf-8"))
    return {
        "schema": SCHEMA,
        "mail": collect_mail(correlation),
        "intake": collect_intake(intake_anchors),
        "source": collect_source(),
        "training": collect_training(run_id),
        "gitops": collect_gitops(),
        "host_state": host_state,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("capture", "verify"))
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--host-state", required=True)
    parser.add_argument("--mail-correlation")
    parser.add_argument("--ticket-number")
    parser.add_argument("--ticket-id")
    parser.add_argument("--issue-id")
    parser.add_argument("--point-id")
    parser.add_argument("--document-sha256")
    args = parser.parse_args()
    if args.mode == "capture":
        for name in (
            "mail_correlation",
            "ticket_number",
            "ticket_id",
            "issue_id",
            "point_id",
            "document_sha256",
        ):
            if not getattr(args, name):
                parser.error(f"--{name.replace('_', '-')} is required for capture")
    return args


def main() -> int:
    args = parse_args()
    manifest = Path(args.manifest)
    if args.mode == "capture":
        state = collect(args)
        manifest.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"durable state captured: {canonical_sha(state)}")
        return 0

    expected = json.loads(manifest.read_text(encoding="utf-8"))
    if expected.get("schema") != SCHEMA:
        raise RuntimeError("durable-state manifest schema is unsupported")
    actual = collect(args, expected)
    if actual != expected:
        print("durable enterprise state changed during worker replacement", file=sys.stderr)
        for section in sorted(expected):
            if actual.get(section) != expected.get(section):
                print(f"changed section: {section}", file=sys.stderr)
        return 1
    print(f"durable state preserved: {canonical_sha(actual)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        KeyError,
        StopIteration,
        ValueError,
        RuntimeError,
        urllib.error.URLError,
        imaplib.IMAP4.error,
    ) as exc:
        print(f"durable state verification failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
