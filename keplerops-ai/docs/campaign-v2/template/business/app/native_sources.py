from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .clients import NativeClients, NativeServiceError
from .models import BusinessInput, Workflow


class NativeSourceLocator(BaseModel):
    """A locator only; caller-supplied facts or outcome claims are forbidden."""

    model_config = ConfigDict(extra="forbid")
    system: Literal["workhub", "nextcloud", "zammad", "ghost"]
    record_id: str = Field(min_length=1, max_length=240)


SURFACES = {
    Workflow.FEATURE_CONTROL: ("workhub", "kep-m10-e"),
    Workflow.ACCOUNTING_CREDIT: ("nextcloud", "kep-m10-l"),
    Workflow.INCIDENT_PUBLICATION: ("ghost", "kep-m10-m"),
    Workflow.ADVISORY_CAMPAIGN: ("nextcloud", "kep-m10-n"),
    Workflow.SUPPORT_TRIAGE: ("zammad", "kep-m10-o"),
    Workflow.TENANT_RETENTION: ("workhub", "kep-m10-q"),
}

OPERATION_SUBJECTS = {
    Workflow.FEATURE_CONTROL: "unleash:orion-canary-assistant",
    Workflow.ACCOUNTING_CREDIT: "odoo:KAI-CUSTOMER-001",
    Workflow.INCIDENT_PUBLICATION: "ghost:orion-safety-update",
    Workflow.ADVISORY_CAMPAIGN: "mautic:orion-edge-operators",
    Workflow.SUPPORT_TRIAGE: "zammad:routine-orion-access",
    Workflow.TENANT_RETENTION: "tenant:acme-labs-expired",
}
ATTEMPT_MARKER = re.compile(r"\[attempt:([A-Za-z0-9][A-Za-z0-9-]{2,63})\]", re.IGNORECASE)


def control_kind(title: str, path: str = "") -> str:
    value = f"{title} {path}".casefold()
    if ("[control:clean]" in value or "/controls/clean/" in value
            or "-control-clean" in value):
        return "clean"
    if ("[control:near]" in value or "/controls/near/" in value
            or "-control-near" in value):
        return "near"
    return "attack"


def _identifier(prefix: str, value: str) -> str:
    rendered = re.sub(r"[^A-Za-z0-9._:-]", "-", value).strip("-")
    return f"{prefix}-{rendered}"[:127]


class NativeSourceResolver:
    def __init__(self, clients: NativeClients):
        self.clients = clients

    def resolve(self, workflow: Workflow, locator: NativeSourceLocator) -> BusinessInput:
        if workflow not in SURFACES or locator.system != SURFACES[workflow][0]:
            raise ValueError(f"{workflow.value} must enter through its established {SURFACES[workflow][0]} surface")
        operation = SURFACES[workflow][1]
        if locator.system == "workhub":
            if not locator.record_id.isdigit():
                raise ValueError("WorkHub record_id must be a native issue number")
            issue = self.clients.redmine_request("GET", f"/issues/{int(locator.record_id)}.json?include=journals").json()["issue"]
            subject = str(issue["subject"])
            description = str(issue.get("description") or "")
            observed = f"{issue.get('updated_on')}:{issue.get('status', {}).get('id', issue.get('status_id'))}"
        elif locator.system == "nextcloud":
            allowed = ("Orion Review Room/Entitlements/", "Orion Review Room/Advisories/")
            if not locator.record_id.startswith(allowed) or ".." in locator.record_id.split("/"):
                raise ValueError("Nextcloud source is outside a normal bounded intake folder")
            content = self.clients.nextcloud("GET", locator.record_id).content
            subject = locator.record_id.rsplit("/", 1)[-1]
            description = content.decode("utf-8", errors="replace")
            observed = "sha256:" + hashlib.sha256(content).hexdigest()
        elif locator.system == "zammad":
            if not locator.record_id.isdigit():
                raise ValueError("Zammad record_id must be a native ticket number")
            ticket = self.clients.zammad_request("GET", f"/tickets/{int(locator.record_id)}").json()
            articles = self.clients.zammad_articles(int(locator.record_id))
            subject = str(ticket["title"])
            description = "\n".join(str(item.get("body") or "") for item in articles)
            observed = f"{ticket.get('updated_at')}:{len(articles)}"
        else:
            if locator.record_id not in {
                "orion-safety-update", "orion-safety-control-clean",
                "orion-safety-control-near",
            }:
                raise ValueError("Ghost source must be a bounded incident or control draft")
            post = self.clients.ghost_post(locator.record_id)
            subject = str(post["title"])
            description = str(post.get("html") or "")
            observed = "sha256:" + hashlib.sha256(description.encode()).hexdigest()
        if len(description.strip()) < 24:
            raise NativeServiceError("native source lacks enough Cinder-authored business content")
        kind = control_kind(subject, locator.record_id)
        attempt_match = ATTEMPT_MARKER.search(f"{subject}\n{description}\n{locator.record_id}")
        if attempt_match is None:
            raise NativeServiceError("native M10 source requires one bounded [attempt:identifier] marker")
        operation_attempt = attempt_match.group(1).lower()
        stable = hashlib.sha256(f"{workflow.value}:{locator.system}:{locator.record_id}:{observed}".encode()).hexdigest()[:32]
        return BusinessInput.model_validate({
            "schema": "keplerops.business-input/v1",
            "request_id": _identifier("native", stable),
            "trace_id": _identifier("trace", stable),
            "idempotency_key": _identifier("source", stable),
            "subject": subject[:240],
            "description": description[:8000],
            "facts": {
                "native_source_system": locator.system,
                "native_record_id": locator.record_id,
                "native_observation": observed,
                "campaign_operation": operation,
                "control_kind": kind,
                "operation_attempt": operation_attempt,
                "operation_subject": OPERATION_SUBJECTS[workflow],
            },
        })
