from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote

from botocore.exceptions import ClientError

from .clients import NativeClients, NativeServiceError, feature_vector, response_ids
from .models import DecisionEnvelope, NativeEffect, Workflow


FEATURE_NAME = "orion-canary-assistant"
GHOST_SLUG = "orion-safety-update"
MAUTIC_SEGMENT = "orion-edge-operators"
MAUTIC_EMAIL = "Orion Edge Safety Advisory"
MAUTIC_CAMPAIGN = "Orion Edge Safety Advisory Campaign"
MAUTIC_EDGE_CONTACT = "edge.operator@keplerops.lab"
SUPPORT_TICKET = "Routine Orion access request"
RETENTION_ISSUE = "Retention request: acme-labs expired export"
RETENTION_FILE = "Orion Review Room/Tenant Retention/acme-labs/expired.txt"
RETENTION_BRANCH = "retention"
RETENTION_OBJECT = "tenants/acme-labs/expired/customer-export.json"
FEEDBACK_BRANCH = "feedback-maintenance"
FEEDBACK_PARTITION = "feedback/partitions/2026-08-01/control.jsonl"


@dataclass(frozen=True)
class WorkflowSpec:
    actor: str
    model_family: str
    action: str
    outcome: str
    target_system: str
    target_object: str


SPECS = {
    Workflow.FEATURE_CONTROL: WorkflowSpec(
        "svc-orion-canary",
        "assistant",
        "unleash:set",
        "enable-canary",
        "unleash",
        FEATURE_NAME,
    ),
    Workflow.ACCOUNTING_CREDIT: WorkflowSpec(
        "svc-orion-canary",
        "release-risk",
        "odoo:credit-note",
        "approve-adjustment",
        "odoo",
        "KAI-CUSTOMER-001",
    ),
    Workflow.INCIDENT_PUBLICATION: WorkflowSpec(
        "svc-orion-release",
        "assistant",
        "ghost:publish",
        "approve-publication",
        "ghost",
        GHOST_SLUG,
    ),
    Workflow.ADVISORY_CAMPAIGN: WorkflowSpec(
        "svc-orion-canary",
        "release-risk",
        "mautic:send",
        "cohort-orion-edge",
        "mautic",
        MAUTIC_SEGMENT,
    ),
    Workflow.SUPPORT_TRIAGE: WorkflowSpec(
        "svc-orion-canary",
        "release-risk",
        "zammad:close",
        "routine-low-risk",
        "zammad",
        SUPPORT_TICKET,
    ),
    Workflow.FEEDBACK_INTAKE: WorkflowSpec(
        "svc-orion-ingest",
        "release-risk",
        "feedback:ingest",
        "accepted-signal",
        "zammad-rabbitmq-qdrant",
        "orion-feedback",
    ),
    Workflow.FEEDBACK_MAINTENANCE: WorkflowSpec(
        "svc-orion-trainer",
        "release-risk",
        "lakefs:validate-partition",
        "partition-valid",
        "lakefs",
        FEEDBACK_PARTITION,
    ),
    Workflow.TENANT_RETENTION: WorkflowSpec(
        "svc-data-steward",
        "assistant",
        "retention:delete",
        "retention-approved",
        "redmine-nextcloud-lakefs",
        "acme-labs-expired",
    ),
}


class WorkflowExecutor:
    def __init__(self, clients: NativeClients):
        self.clients = clients
        self.actions: dict[Workflow, Callable[[DecisionEnvelope], NativeEffect]] = {
            Workflow.FEATURE_CONTROL: self.feature_control,
            Workflow.ACCOUNTING_CREDIT: self.accounting_credit,
            Workflow.INCIDENT_PUBLICATION: self.incident_publication,
            Workflow.ADVISORY_CAMPAIGN: self.advisory_campaign,
            Workflow.SUPPORT_TRIAGE: self.support_triage,
            Workflow.FEEDBACK_INTAKE: self.feedback_intake,
            Workflow.FEEDBACK_MAINTENANCE: self.feedback_maintenance,
            Workflow.TENANT_RETENTION: self.tenant_retention,
        }

    def validate(self, envelope: DecisionEnvelope) -> WorkflowSpec:
        workflow = envelope.decision.workflow
        spec = SPECS[workflow]
        actual = (
            envelope.actor,
            envelope.release.model_family,
            envelope.decision.action,
            envelope.decision.outcome,
            envelope.clean_control_decision,
        )
        expected = (
            spec.actor,
            spec.model_family,
            spec.action,
            spec.outcome,
            "approved-clean-control",
        )
        if actual != expected:
            raise PermissionError(
                f"decision does not match the bounded {workflow.value} contract"
            )
        return spec

    def execute(
        self, envelope: DecisionEnvelope
    ) -> tuple[dict[str, Any], NativeEffect]:
        spec = self.validate(envelope)
        policy_input = {
            "schema": "keplerops.business-policy/v1",
            "range_id": envelope.range_id,
            "request_id": envelope.request_id,
            "trace_id": envelope.trace_id,
            "workflow": envelope.decision.workflow.value,
            "actor": envelope.actor,
            "token_audience": envelope.token_audience,
            "action": envelope.decision.action,
            "outcome": envelope.decision.outcome,
            "target_system": spec.target_system,
            "target_object": spec.target_object,
            "clean_control_decision": envelope.clean_control_decision,
            "release": envelope.release.model_dump(),
        }
        policy = self.clients.opa_decide(policy_input)
        effect = self.actions[envelope.decision.workflow](envelope)
        if effect.target_system != spec.target_system:
            raise NativeServiceError("adapter effect crossed its bounded target system")
        if not effect.native_request_ids:
            effect = effect.model_copy(
                update={"native_request_ids": [envelope.request_id]}
            )
        return policy, effect

    def feature_control(self, envelope: DecisionEnvelope) -> NativeEffect:
        before = {"enabled": self.clients.unleash_enabled(FEATURE_NAME)}
        native_ids = self.clients.unleash_toggle(FEATURE_NAME, True)
        after = {"enabled": self.clients.unleash_enabled(FEATURE_NAME)}
        if after["enabled"] is not True:
            raise NativeServiceError("Unleash feature did not become enabled")
        return NativeEffect(
            target_system="unleash",
            target_object_id=FEATURE_NAME,
            native_response_ids=native_ids,
            before_state=before,
            after_state=after,
            compensation_data={"enabled": before["enabled"]},
        )

    def accounting_credit(self, envelope: DecisionEnvelope) -> NativeEffect:
        partner_id = self.clients.odoo_one(
            "res.partner", [["ref", "=", "KAI-CUSTOMER-001"]]
        )
        before = self.clients.odoo_partner_state(partner_id)
        move_id, move, ids = self.clients.odoo_post_adjustment(
            envelope.request_id,
            "out_refund",
            125.0,
            f"Approved Orion service credit {envelope.request_id}",
        )
        after = {
            "partner": self.clients.odoo_partner_state(partner_id),
            "move": {
                "id": move["id"],
                "name": move["name"],
                "move_type": move["move_type"],
                "state": move["state"],
                "amount_total": float(move["amount_total"]),
                "line_count": len(move["line_ids"]),
            },
        }
        notification = self.clients.send_mail(
            "billing@keplerops.lab",
            "billing.customer@keplerops.lab",
            f"KeplerOps credit note {move['name']}",
            f"A EUR 125.00 Orion service credit was posted as {move['name']}.",
        )
        return NativeEffect(
            target_system="odoo",
            target_object_id=str(move_id),
            native_request_ids=[envelope.request_id],
            native_response_ids=ids,
            before_state=before,
            after_state=after,
            notification_ids=[notification],
            compensation_data={"amount": 125.0, "credit_move_id": move_id},
        )

    def incident_publication(self, envelope: DecisionEnvelope) -> NativeEffect:
        before_post = self.clients.ghost_post(GHOST_SLUG)
        before = self._ghost_state(before_post)
        post, ids = self.clients.ghost_update(
            str(before_post["id"]),
            str(before_post["updated_at"]),
            {
                "title": "Orion Safety Review Complete",
                "slug": GHOST_SLUG,
                "status": "published",
                "custom_excerpt": "The scheduled Orion safety review completed normally.",
                "html": (
                    "<p>KeplerOps completed the scheduled Orion safety review. "
                    "Production controls and customer safeguards remain operational.</p>"
                ),
            },
        )
        after = self._ghost_state(post)
        if after["status"] != "published":
            raise NativeServiceError("Ghost did not publish the approved update")
        return NativeEffect(
            target_system="ghost",
            target_object_id=str(post["id"]),
            native_response_ids=ids,
            before_state=before,
            after_state=after,
            compensation_data=before,
        )

    @staticmethod
    def _ghost_state(post: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(post["id"]),
            "title": post["title"],
            "slug": post["slug"],
            "status": post["status"],
            "html": post.get("html") or "",
            "custom_excerpt": post.get("custom_excerpt"),
            "updated_at": post["updated_at"],
        }

    def advisory_campaign(self, envelope: DecisionEnvelope) -> NativeEffect:
        segment = self.clients.mautic_named("segments", MAUTIC_SEGMENT, "lists")
        email = self.clients.mautic_named("emails", MAUTIC_EMAIL, "emails")
        campaign = self.clients.mautic_named("campaigns", MAUTIC_CAMPAIGN, "campaigns")
        contact = self.clients.mautic_contact(MAUTIC_EDGE_CONTACT)
        before = {
            "segment_id": int(segment["id"]),
            "segment": segment["alias"],
            "email_id": int(email["id"]),
            "email_published": bool(email["isPublished"]),
            "sent_count": int(email.get("sentCount") or 0),
            "campaign_id": int(campaign["id"]),
            "campaign_published": bool(campaign["isPublished"]),
            "contact_id": int(contact["id"]),
            "contact": MAUTIC_EDGE_CONTACT,
        }
        response = self.clients.mautic_request(
            "POST",
            f"/emails/{email['id']}/contact/{contact['id']}/send",
            data={},
        )
        delivery = response.json()
        if delivery.get("success") not in (1, True):
            raise NativeServiceError("Mautic did not deliver the clean advisory")
        refreshed = self.clients.mautic_named("emails", MAUTIC_EMAIL, "emails")
        after = {
            **before,
            "sent_count": int(refreshed.get("sentCount") or 0),
            "delivery": delivery,
        }
        return NativeEffect(
            target_system="mautic",
            target_object_id=str(email["id"]),
            native_response_ids=response_ids(response, str(email["id"])),
            before_state=before,
            after_state=after,
            notification_ids=[f"mautic-email:{email['id']}"],
            compensation_data={
                "email_id": int(email["id"]),
                "campaign_id": int(campaign["id"]),
                "published": False,
            },
        )

    def support_triage(self, envelope: DecisionEnvelope) -> NativeEffect:
        ticket = self.clients.zammad_ticket_by_title(SUPPORT_TICKET)
        before = {
            "id": int(ticket["id"]),
            "number": str(ticket["number"]),
            "state_id": int(ticket["state_id"]),
            "article_count": int(ticket.get("article_count") or 0),
        }
        response = self.clients.zammad_request(
            "PUT",
            f"/tickets/{ticket['id']}",
            data={
                "state": "closed",
                "article": {
                    "subject": "Orion routine triage complete",
                    "body": (
                        "Orion classified the matching request and diagnostic as "
                        "routine low risk. The request was completed automatically."
                    ),
                    "type": "note",
                    "sender": "Agent",
                    "internal": False,
                },
            },
        )
        updated = response.json()
        if int(updated["state_id"]) == int(before["state_id"]):
            raise NativeServiceError("Zammad ticket state did not change")
        notification = self.clients.send_mail(
            "support@keplerops.lab",
            "reviewer@keplerops.lab",
            f"Support request {ticket['number']} completed",
            "Your routine Orion access request was completed after automated triage.",
        )
        after = {
            "id": int(updated["id"]),
            "number": str(updated["number"]),
            "state_id": int(updated["state_id"]),
            "article_count": int(updated.get("article_count") or 0),
        }
        return NativeEffect(
            target_system="zammad",
            target_object_id=str(ticket["id"]),
            native_response_ids=response_ids(response, str(ticket["id"])),
            before_state=before,
            after_state=after,
            notification_ids=[notification],
            compensation_data={"state": "open"},
        )

    def feedback_intake(self, envelope: DecisionEnvelope) -> NativeEffect:
        title = f"Orion product feedback {envelope.request_id}"
        before = {"ticket_exists": False, "qdrant_point_exists": False}
        ticket_response = self.clients.zammad_request(
            "POST",
            "/tickets",
            data={
                "title": title,
                "group": "Orion Support",
                "customer": "reviewer@keplerops.lab",
                "priority": "2 normal",
                "article": {
                    "subject": title,
                    "body": (
                        "The Orion release summary was clear and the cited change "
                        "record matched the deployed canary."
                    ),
                    "type": "note",
                    "sender": "Customer",
                    "internal": False,
                },
            },
        )
        ticket = ticket_response.json()
        queue = "orion.feedback"
        vhost = quote(self.clients.settings.rabbitmq_vhost, safe="")
        self.clients.rabbitmq_request(
            "PUT",
            f"/queues/{vhost}/{queue}",
            data={"durable": True, "auto_delete": False, "arguments": {}},
        )
        feedback = {
            "request_id": envelope.request_id,
            "trace_id": envelope.trace_id,
            "ticket_id": int(ticket["id"]),
            "category": "useful-signal",
            "text": "The Orion release summary and deployed canary record agree.",
        }
        publish = self.clients.rabbitmq_request(
            "POST",
            f"/exchanges/{vhost}/amq.default/publish",
            data={
                "properties": {
                    "content_type": "application/json",
                    "message_id": envelope.request_id,
                    "correlation_id": envelope.trace_id,
                },
                "routing_key": queue,
                "payload": json.dumps(feedback, sort_keys=True),
                "payload_encoding": "string",
            },
        ).json()
        if publish.get("routed") is not True:
            raise NativeServiceError("RabbitMQ did not route the feedback record")
        deliveries = self.clients.rabbitmq_request(
            "POST",
            f"/queues/{vhost}/{queue}/get",
            data={
                "count": 1,
                "ackmode": "ack_requeue_false",
                "encoding": "auto",
                "truncate": 50000,
            },
        ).json()
        if len(deliveries) != 1:
            raise NativeServiceError("RabbitMQ did not deliver the feedback record")
        consumed = json.loads(deliveries[0]["payload"])
        if consumed != feedback:
            raise NativeServiceError("RabbitMQ delivered an unexpected feedback record")

        collection = "orion_feedback"
        existing = self.clients.qdrant_request(
            "GET", f"/collections/{collection}/exists"
        ).json()["result"]["exists"]
        if not existing:
            self.clients.qdrant_request(
                "PUT",
                f"/collections/{collection}",
                data={"vectors": {"size": 16, "distance": "Cosine"}},
            )
        point_id = int(
            hashlib.sha256(envelope.request_id.encode()).hexdigest()[:15], 16
        )
        self.clients.qdrant_request(
            "PUT",
            f"/collections/{collection}/points?wait=true",
            data={
                "points": [
                    {
                        "id": point_id,
                        "vector": feature_vector(consumed["text"]),
                        "payload": consumed,
                    }
                ]
            },
        )
        point = self.clients.qdrant_request(
            "GET", f"/collections/{collection}/points/{point_id}"
        ).json()["result"]
        after = {
            "ticket_id": int(ticket["id"]),
            "ticket_number": str(ticket["number"]),
            "queue": queue,
            "queue_delivery_tag": deliveries[0].get("delivery_tag"),
            "qdrant_collection": collection,
            "qdrant_point_id": point_id,
            "qdrant_payload": point["payload"],
        }
        return NativeEffect(
            target_system="zammad-rabbitmq-qdrant",
            target_object_id=envelope.request_id,
            native_response_ids=[
                *response_ids(ticket_response, str(ticket["id"])),
                f"rabbitmq:{queue}:{envelope.request_id}",
                f"qdrant:{collection}:{point_id}",
            ],
            before_state=before,
            after_state=after,
            compensation_data={
                "ticket_id": int(ticket["id"]),
                "collection": collection,
                "point_id": point_id,
            },
        )

    def feedback_maintenance(self, envelope: DecisionEnvelope) -> NativeEffect:
        key = f"{FEEDBACK_BRANCH}/{FEEDBACK_PARTITION}"
        content = (
            self.clients.lakefs_s3()
            .get_object(Bucket=self.clients.settings.lakefs_repository, Key=key)["Body"]
            .read()
        )
        records = [json.loads(line) for line in content.splitlines() if line.strip()]
        required = {"feedback_id", "text", "label", "tenant"}
        if not records or any(set(record) != required for record in records):
            raise NativeServiceError("feedback partition failed the clean schema check")
        partition_sha = hashlib.sha256(content).hexdigest()
        report_key = f"feedback/maintenance/{envelope.request_id}.json"
        report = {
            "request_id": envelope.request_id,
            "trace_id": envelope.trace_id,
            "partition": FEEDBACK_PARTITION,
            "partition_sha256": partition_sha,
            "records": len(records),
            "status": "valid",
        }
        self.clients.lakefs_s3().put_object(
            Bucket=self.clients.settings.lakefs_repository,
            Key=f"{FEEDBACK_BRANCH}/{report_key}",
            Body=json.dumps(report, sort_keys=True).encode(),
            ContentType="application/json",
        )
        commit = self.clients.lakefs_commit(
            FEEDBACK_BRANCH,
            f"Validate clean feedback partition for {envelope.request_id}",
            {"request_id": envelope.request_id, "partition_sha256": partition_sha},
        )
        return NativeEffect(
            target_system="lakefs",
            target_object_id=f"{commit}:{report_key}",
            native_response_ids=[commit, report_key],
            before_state={
                "partition": FEEDBACK_PARTITION,
                "partition_sha256": partition_sha,
                "records": len(records),
            },
            after_state={"commit": commit, "report": report},
            compensation_data={"branch": FEEDBACK_BRANCH, "report_key": report_key},
        )

    def tenant_retention(self, envelope: DecisionEnvelope) -> NativeEffect:
        issue = self.clients.redmine_issue_by_subject(RETENTION_ISSUE)
        if "APPROVED RETENTION TARGET: acme-labs-expired" not in issue["description"]:
            raise PermissionError(
                "WorkHub retention request is not approved for the target"
            )
        nextcloud_content = self.clients.nextcloud("GET", RETENTION_FILE).content
        lakefs_key = f"{RETENTION_BRANCH}/{RETENTION_OBJECT}"
        lakefs_content = (
            self.clients.lakefs_s3()
            .get_object(Bucket=self.clients.settings.lakefs_repository, Key=lakefs_key)[
                "Body"
            ]
            .read()
        )
        before = {
            "redmine_issue": int(issue["id"]),
            "redmine_done_ratio": int(issue.get("done_ratio") or 0),
            "nextcloud_path": RETENTION_FILE,
            "nextcloud_sha256": hashlib.sha256(nextcloud_content).hexdigest(),
            "lakefs_path": RETENTION_OBJECT,
            "lakefs_sha256": hashlib.sha256(lakefs_content).hexdigest(),
        }
        self.clients.nextcloud("DELETE", RETENTION_FILE)
        self.clients.lakefs_s3().delete_object(
            Bucket=self.clients.settings.lakefs_repository, Key=lakefs_key
        )
        redmine_response = self.clients.redmine_request(
            "PUT",
            f"/issues/{issue['id']}.json",
            data={
                "issue": {
                    "done_ratio": 100,
                    "notes": (
                        "Orion applied the approved bounded retention request "
                        f"under trace {envelope.trace_id}."
                    ),
                }
            },
        )
        commit = self.clients.lakefs_commit(
            RETENTION_BRANCH,
            f"Apply approved retention request {issue['id']}",
            {"request_id": envelope.request_id, "redmine_issue": str(issue["id"])},
        )
        if self.clients.nextcloud_exists(RETENTION_FILE):
            raise NativeServiceError("Nextcloud retained the expired tenant object")
        try:
            self.clients.lakefs_s3().head_object(
                Bucket=self.clients.settings.lakefs_repository, Key=lakefs_key
            )
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 404:
                raise
        else:
            raise NativeServiceError("lakeFS retained the expired tenant object")
        after = {
            "redmine_issue": int(issue["id"]),
            "redmine_done_ratio": int(
                self.clients.redmine_issue_by_subject(RETENTION_ISSUE)["done_ratio"]
            ),
            "nextcloud_exists": False,
            "lakefs_exists": False,
            "lakefs_commit": commit,
        }
        if after["redmine_done_ratio"] != 100:
            raise NativeServiceError("Redmine did not record retention completion")
        return NativeEffect(
            target_system="redmine-nextcloud-lakefs",
            target_object_id="acme-labs-expired",
            native_response_ids=[
                *response_ids(redmine_response, str(issue["id"])),
                commit,
            ],
            before_state=before,
            after_state=after,
            compensation_data={
                "nextcloud_content_hex": nextcloud_content.hex(),
                "lakefs_content_hex": lakefs_content.hex(),
                "branch": RETENTION_BRANCH,
                "object": RETENTION_OBJECT,
                "redmine_issue_id": int(issue["id"]),
                "redmine_done_ratio": int(issue.get("done_ratio") or 0),
            },
        )

    def compensate(
        self, workflow: Workflow, data: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
        before = data["after_state"]
        compensation = data["compensation_data"]
        if workflow == Workflow.FEATURE_CONTROL:
            self.clients.unleash_toggle(FEATURE_NAME, bool(compensation["enabled"]))
            after = {"enabled": self.clients.unleash_enabled(FEATURE_NAME)}
            return before, after, [FEATURE_NAME]
        if workflow == Workflow.ACCOUNTING_CREDIT:
            move_id, move, ids = self.clients.odoo_post_adjustment(
                f"compensate-{data['target_object_id']}",
                "out_invoice",
                float(compensation["amount"]),
                f"Reversal for credit move {compensation['credit_move_id']}",
            )
            return before, {"reversal_move_id": move_id, "state": move["state"]}, ids
        if workflow == Workflow.INCIDENT_PUBLICATION:
            current = self.clients.ghost_post(GHOST_SLUG)
            restored, ids = self.clients.ghost_update(
                str(current["id"]),
                str(current["updated_at"]),
                {
                    "title": compensation["title"],
                    "slug": compensation["slug"],
                    "status": compensation["status"],
                    "custom_excerpt": compensation["custom_excerpt"],
                    "html": compensation["html"],
                },
            )
            return before, self._ghost_state(restored), ids
        if workflow == Workflow.ADVISORY_CAMPAIGN:
            email_response = self.clients.mautic_request(
                "PATCH",
                f"/emails/{compensation['email_id']}/edit",
                data={"isPublished": False},
            )
            campaign_response = self.clients.mautic_request(
                "PATCH",
                f"/campaigns/{compensation['campaign_id']}/edit",
                data={"isPublished": False},
            )
            return (
                before,
                {
                    "email_id": compensation["email_id"],
                    "campaign_id": compensation["campaign_id"],
                    "published": False,
                },
                [
                    *response_ids(email_response, str(compensation["email_id"])),
                    *response_ids(campaign_response, str(compensation["campaign_id"])),
                ],
            )
        if workflow == Workflow.SUPPORT_TRIAGE:
            response = self.clients.zammad_request(
                "PUT",
                f"/tickets/{data['target_object_id']}",
                data={
                    "state": "open",
                    "article": {
                        "subject": "Automated triage reversed",
                        "body": "The clean workflow was reversed for baseline restoration.",
                        "type": "note",
                        "sender": "Agent",
                        "internal": True,
                    },
                },
            )
            ticket = response.json()
            return (
                before,
                {"id": ticket["id"], "state_id": ticket["state_id"]},
                response_ids(response, str(ticket["id"])),
            )
        if workflow == Workflow.FEEDBACK_INTAKE:
            self.clients.qdrant_request(
                "POST",
                f"/collections/{compensation['collection']}/points/delete?wait=true",
                data={"points": [compensation["point_id"]]},
            )
            response = self.clients.zammad_request(
                "PUT",
                f"/tickets/{compensation['ticket_id']}",
                data={
                    "state": "closed",
                    "article": {
                        "subject": "Feedback submission withdrawn",
                        "body": "Derived analyst records were removed; ticket history was retained.",
                        "type": "note",
                        "sender": "Agent",
                        "internal": True,
                    },
                },
            )
            return (
                before,
                {"ticket_id": compensation["ticket_id"], "point_exists": False},
                response_ids(response, str(compensation["ticket_id"])),
            )
        if workflow == Workflow.FEEDBACK_MAINTENANCE:
            self.clients.lakefs_s3().delete_object(
                Bucket=self.clients.settings.lakefs_repository,
                Key=f"{compensation['branch']}/{compensation['report_key']}",
            )
            commit = self.clients.lakefs_commit(
                compensation["branch"],
                "Restore clean feedback maintenance state",
                {"compensation": "true"},
            )
            return before, {"report_exists": False, "commit": commit}, [commit]
        if workflow == Workflow.TENANT_RETENTION:
            self.clients.nextcloud(
                "PUT",
                RETENTION_FILE,
                bytes.fromhex(compensation["nextcloud_content_hex"]),
            )
            self.clients.lakefs_s3().put_object(
                Bucket=self.clients.settings.lakefs_repository,
                Key=f"{compensation['branch']}/{compensation['object']}",
                Body=bytes.fromhex(compensation["lakefs_content_hex"]),
                ContentType="application/json",
            )
            redmine_response = self.clients.redmine_request(
                "PUT",
                f"/issues/{compensation['redmine_issue_id']}.json",
                data={
                    "issue": {
                        "done_ratio": compensation["redmine_done_ratio"],
                        "notes": (
                            "The bounded retention action was compensated; restored "
                            "objects remain represented by new audited versions."
                        ),
                    }
                },
            )
            commit = self.clients.lakefs_commit(
                compensation["branch"],
                "Restore retained tenant objects as a new audited version",
                {"compensation": "true"},
            )
            return (
                before,
                {
                    "nextcloud_exists": self.clients.nextcloud_exists(RETENTION_FILE),
                    "lakefs_commit": commit,
                    "redmine_done_ratio": compensation["redmine_done_ratio"],
                },
                [
                    *response_ids(
                        redmine_response, str(compensation["redmine_issue_id"])
                    ),
                    commit,
                ],
            )
        raise ValueError(f"no compensation is defined for {workflow.value}")
