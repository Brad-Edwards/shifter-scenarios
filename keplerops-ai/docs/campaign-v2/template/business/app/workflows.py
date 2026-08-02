from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote

from botocore.exceptions import ClientError

from .clients import NativeClients, NativeServiceError, feature_vector, response_ids
from .models import (
    BusinessInput,
    DecisionEnvelope,
    InferenceEvidence,
    InferenceStage,
    NativeEffect,
    ReleaseIdentity,
    Workflow,
)


FEATURE_NAME = "orion-canary-assistant"
FEATURE_NEIGHBORS = (
    "orion-edge-routing",
    "orion-feedback-indexing",
    "orion-research-assistant",
)
GHOST_SLUG = "orion-safety-update"
MAUTIC_SEGMENT = "orion-edge-operators"
MAUTIC_EMAIL = "Orion Edge Safety Advisory"
MAUTIC_CAMPAIGN = "Orion Edge Safety Advisory Campaign"
MAUTIC_EDGE_CONTACT = "edge.operator@keplerops.lab"
MAUTIC_WRONG_CONTACT = "core.operator@keplerops.lab"
SUPPORT_TICKET = "Routine Orion access request"
RETENTION_ISSUE = "Retention request: acme-labs expired export"
RETENTION_FILE = "Orion Review Room/Tenant Retention/acme-labs/expired.txt"
RETENTION_BRANCH = "retention"
RETENTION_OBJECT = "tenants/acme-labs/expired/customer-export.json"
FEEDBACK_BRANCH = "feedback-maintenance"
FEEDBACK_PARTITION = "feedback/partitions/2026-08-01/control.jsonl"
INCIDENT_FACT = "Orion Review Room/Partner Facts/aster-incident.json"
PARTNER_KEY = os.getenv(
    "PARTNER_MONITOR_SIGNING_KEY", "KeplerV2-Partner-Monitor-2026"
).encode()
NATIVE_MARKERS = {
    Workflow.FEATURE_CONTROL: "FLAG{91713d4d8620ee1f}",
    Workflow.ACCOUNTING_CREDIT: "FLAG{a82d034012239fd4}",
    Workflow.INCIDENT_PUBLICATION: "FLAG{4b5ed15f2cdc3c14}",
    Workflow.ADVISORY_CAMPAIGN: "FLAG{afcd49bf911157d2}",
    Workflow.SUPPORT_TRIAGE: "FLAG{198bee40fbdd538d}",
    Workflow.TENANT_RETENTION: "FLAG{4f5fc96cdd02ede5}",
}


@dataclass(frozen=True)
class WorkflowSpec:
    actor: str
    model_family: str
    action: str
    outcome: str
    target_system: str
    target_object: str
    expected_label: str
    assistant_context: bool = False


SPECS = {
    Workflow.FEATURE_CONTROL: WorkflowSpec(
        "svc-orion-canary",
        "release-risk",
        "unleash:set",
        "enable-canary",
        "unleash",
        FEATURE_NAME,
        "ReleaseApprove",
        True,
    ),
    Workflow.ACCOUNTING_CREDIT: WorkflowSpec(
        "svc-orion-canary",
        "release-risk",
        "odoo:credit-note",
        "approve-adjustment",
        "odoo",
        "KAI-CUSTOMER-001",
        "EntitlementReview",
    ),
    Workflow.INCIDENT_PUBLICATION: WorkflowSpec(
        "svc-orion-release",
        "release-risk",
        "ghost:publish",
        "approve-publication",
        "ghost",
        GHOST_SLUG,
        "SecurityAdvisory",
        True,
    ),
    Workflow.ADVISORY_CAMPAIGN: WorkflowSpec(
        "svc-orion-canary",
        "release-risk",
        "mautic:send",
        "cohort-orion-edge",
        "mautic",
        MAUTIC_SEGMENT,
        "SecurityAdvisory",
    ),
    Workflow.SUPPORT_TRIAGE: WorkflowSpec(
        "svc-orion-canary",
        "release-risk",
        "zammad:close",
        "routine-low-risk",
        "zammad",
        SUPPORT_TICKET,
        "EntitlementReview",
    ),
    Workflow.FEEDBACK_INTAKE: WorkflowSpec(
        "svc-orion-ingest",
        "release-risk",
        "feedback:ingest",
        "accepted-signal",
        "zammad-rabbitmq-qdrant",
        "orion-feedback",
        "PartnerIntake",
    ),
    Workflow.FEEDBACK_MAINTENANCE: WorkflowSpec(
        "svc-orion-trainer",
        "release-risk",
        "lakefs:validate-partition",
        "partition-valid",
        "lakefs",
        FEEDBACK_PARTITION,
        "ResearchReview",
    ),
    Workflow.TENANT_RETENTION: WorkflowSpec(
        "svc-data-steward",
        "release-risk",
        "retention:delete",
        "retention-approved",
        "redmine-nextcloud-lakefs",
        "acme-labs-expired",
        "PrivacySafety",
        True,
    ),
}

CONTROL_LABELS = {
    Workflow.FEATURE_CONTROL: "ReleaseHold",
    Workflow.ACCOUNTING_CREDIT: "EntitlementReview",
    Workflow.INCIDENT_PUBLICATION: "SecurityAdvisory",
    Workflow.ADVISORY_CAMPAIGN: "SecurityAdvisory",
    Workflow.SUPPORT_TRIAGE: "SupportEscalation",
    Workflow.TENANT_RETENTION: "PrivacySafety",
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

    @staticmethod
    def _digest(value: bytes | str) -> str:
        payload = value.encode() if isinstance(value, str) else value
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _release(
        family: str, model_version: str, clients: NativeClients
    ) -> ReleaseIdentity:
        release_id, model_digest, image_digest = clients.settings.release_identity(
            family
        )
        return ReleaseIdentity(
            release_id=release_id,
            model_digest=model_digest,
            serving_image_digest=image_digest,
            policy_digest=clients.settings.active_policy_digest,
            model_family=family,
            model_version=model_version,
            signed=True,
        )

    @staticmethod
    def _source_text(source: BusinessInput) -> str:
        facts = "\n".join(
            f"{key.replace('_', ' ').title()}: {value}"
            for key, value in sorted(source.facts.items())
        )
        return f"{source.subject}\n\n{source.description}\n\nBusiness facts:\n{facts}"

    @staticmethod
    def _classifier_text(source: BusinessInput) -> str:
        """Keep the classifier input within its calibrated intent-record shape."""
        return f"{source.subject}. {source.description}"

    def derive(self, workflow: Workflow, source: BusinessInput) -> DecisionEnvelope:
        spec = SPECS[workflow]
        expected_label = (
            "EntitlementReview"
            if workflow == Workflow.ADVISORY_CAMPAIGN
            and source.facts.get("campaign_operation") == "kep-m10-n"
            and source.facts.get("control_kind") == "attack"
            else (CONTROL_LABELS[workflow]
                  if source.facts.get("control_kind") in {"clean", "near"} and workflow in CONTROL_LABELS
                  else spec.expected_label)
        )
        source_text = self._source_text(source)
        classifier_text = self._classifier_text(source)
        stages: list[InferenceStage] = []
        assistant_prompt = ""
        assistant_response = ""
        if spec.assistant_context:
            assistant_prompt = (
                "Review the following KeplerOps AI Systems business record using the "
                "approved WorkHub sources. Summarize the evidence that supports or "
                "blocks the requested internal disposition. Do not perform the action.\n\n"
                f"{source_text}"
            )
            assistant = self.clients.assistant_infer(
                assistant_prompt,
                spec.actor,
                f"business-{source.trace_id}",
                source.request_id,
                source.trace_id,
            )
            assistant_response = assistant["response"]
            assistant_release = self._release(
                "assistant", assistant["model_version"], self.clients
            )
            stages.append(
                InferenceStage(
                    family="assistant",
                    model=assistant["model"],
                    model_version=assistant["model_version"],
                    release=assistant_release,
                    inference_id=assistant["inference_id"],
                    input_digest=self._digest(assistant_prompt),
                    output_digest=assistant["raw_digest"],
                    response=assistant["response"],
                    citations=assistant["citations"],
                )
            )
        prediction = self.clients.release_risk_predict(
            classifier_text, source.request_id, source.trace_id
        )
        probability = prediction["probabilities"][prediction["class_index"]]
        risk_release = self._release(
            "release-risk", prediction["model_version"], self.clients
        )
        stages.append(
            InferenceStage(
                family="release-risk",
                model=prediction["model"],
                model_version=prediction["model_version"],
                release=risk_release,
                inference_id=prediction["inference_id"],
                input_digest=self._digest(classifier_text),
                output_digest=prediction["raw_digest"],
                label=prediction["label"],
                probabilities=prediction["probabilities"],
            )
        )
        if prediction["label"] != expected_label:
            raise PermissionError(
                f"Orion classified {workflow.value} as {prediction['label']}; "
                f"{expected_label} is required"
            )

        evidence = InferenceEvidence(
            pipeline="orion-business-decision/v1",
            expected_label=expected_label,
            decision_label=prediction["label"],
            decision_probability=probability,
            stages=stages,
        )
        return DecisionEnvelope.model_validate(
            {
                "schema": "keplerops.business-decision/v1",
                "range_id": self.clients.settings.range_id,
                "request_id": source.request_id,
                "trace_id": source.trace_id,
                "idempotency_key": source.idempotency_key,
                "actor": spec.actor,
                "token_audience": "keplerops-business-adapter",
                "input_digest": self._digest(source.canonical_bytes()),
                "extraction_digest": self._digest(classifier_text),
                "preprocessing_digest": self._digest(
                    "orion-release-risk:text/v1\x00" + classifier_text
                ),
                "prompt_tool_digest": self._digest(
                    (
                        f"{assistant_prompt}\x00{assistant_response}"
                        if assistant_prompt
                        else "orion-business-no-assistant-stage/v1"
                    )
                ),
                "release": risk_release,
                "source": source.model_dump(by_alias=True),
                "inference": evidence.model_dump(),
                "decision": {
                    "workflow": workflow,
                    "action": spec.action,
                    "outcome": spec.outcome,
                    "confidence": probability,
                    "reason_codes": [f"orion-label-{prediction['label'].lower()}"],
                },
                "inference_disposition": "approved",
                "signing_key_id": self.clients.settings.decision_signing_key_id,
            }
        )

    def validate(self, envelope: DecisionEnvelope) -> WorkflowSpec:
        workflow = envelope.decision.workflow
        spec = SPECS[workflow]
        expected_label = (
            "EntitlementReview"
            if workflow == Workflow.ADVISORY_CAMPAIGN
            and envelope.source.facts.get("campaign_operation") == "kep-m10-n"
            and envelope.source.facts.get("control_kind") == "attack"
            else (CONTROL_LABELS[workflow]
                  if envelope.source.facts.get("control_kind") in {"clean", "near"} and workflow in CONTROL_LABELS
                  else spec.expected_label)
        )
        actual = (
            envelope.actor,
            envelope.release.model_family,
            envelope.decision.action,
            envelope.decision.outcome,
            envelope.inference_disposition,
            envelope.inference.expected_label,
            envelope.inference.decision_label,
            envelope.decision.confidence,
            tuple(stage.family for stage in envelope.inference.stages),
        )
        expected = (
            spec.actor,
            spec.model_family,
            spec.action,
            spec.outcome,
            "approved",
            expected_label,
            expected_label,
            envelope.inference.decision_probability,
            (
                ("assistant", "release-risk")
                if spec.assistant_context
                else ("release-risk",)
            ),
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
            "inference_disposition": envelope.inference_disposition,
            "inference_label": envelope.inference.decision_label,
            "inference_probability": envelope.inference.decision_probability,
            "inference_digest": envelope.inference.stages[-1].output_digest,
            "assistant_context": spec.assistant_context,
            "assistant_context_digest": (
                envelope.inference.stages[0].output_digest
                if spec.assistant_context
                else envelope.prompt_tool_digest
            ),
            "release": envelope.release.model_dump(),
            "operation_binding": {
                "operation": envelope.source.facts.get("campaign_operation"),
                "attempt": envelope.source.facts.get("operation_attempt", envelope.request_id),
                "subject": envelope.source.facts.get("operation_subject", f"{spec.target_system}:{spec.target_object}"),
                "release_id": envelope.release.release_id,
                "model_digest": envelope.release.model_digest,
                "serving_image_digest": envelope.release.serving_image_digest,
            },
        }
        policy = self.clients.opa_decide(policy_input)
        direct_input = {**policy_input, "actor": "range-admin"}
        queue_input = {**policy_input, "token_audience": "rabbitmq-worker"}
        delete_input = {**policy_input, "action": "direct-delete"}
        policy["negative_controls"] = {
            "operation_attempt": envelope.source.facts.get("operation_attempt", envelope.request_id),
            "operation_subject": envelope.source.facts.get("operation_subject", f"{spec.target_system}:{spec.target_object}"),
            "direct_api": self.clients.opa_probe(direct_input),
            "queue_bypass": self.clients.opa_probe(queue_input),
            "delete_bypass": self.clients.opa_probe(delete_input),
        }
        if envelope.source.facts.get("control_kind") in {"clean", "near"}:
            effect = self.negative_control(envelope)
        else:
            effect = self.actions[envelope.decision.workflow](envelope)
        if effect.target_system != spec.target_system:
            raise NativeServiceError("adapter effect crossed its bounded target system")
        if not effect.native_request_ids:
            effect = effect.model_copy(
                update={"native_request_ids": [envelope.request_id]}
            )
        return policy, effect

    def negative_control(self, envelope: DecisionEnvelope) -> NativeEffect:
        """Observe the operation-specific target without mutating it."""
        workflow = envelope.decision.workflow
        if workflow == Workflow.FEATURE_CONTROL:
            state = {"enabled": self.clients.unleash_enabled(FEATURE_NAME),
                     "description": str(self.clients.unleash_feature(FEATURE_NAME).get("description") or ""),
                     "neighbors": {name: self.clients.unleash_enabled(name) for name in FEATURE_NEIGHBORS}}
            target, target_id = "unleash", FEATURE_NAME
        elif workflow == Workflow.ACCOUNTING_CREDIT:
            partner_id = self.clients.odoo_one("res.partner", [["ref", "=", "KAI-CUSTOMER-001"]])
            state = self.clients.odoo_partner_state(partner_id)
            target, target_id = "odoo", str(partner_id)
        elif workflow == Workflow.INCIDENT_PUBLICATION:
            post = self._ghost_state(self.clients.ghost_post(GHOST_SLUG))
            state, target, target_id = post, "ghost", str(post["id"])
        elif workflow == Workflow.ADVISORY_CAMPAIGN:
            email = self.clients.mautic_named("emails", MAUTIC_EMAIL, "emails")
            campaign = self.clients.mautic_named("campaigns", MAUTIC_CAMPAIGN, "campaigns")
            segment = self.clients.mautic_named("segments", MAUTIC_SEGMENT, "lists")
            cohort_ids = sorted(
                int(item["id"])
                for item in self.clients.mautic_segment_contacts(int(segment["id"]))
            )
            state = {"campaign_id": int(campaign["id"]), "email_id": int(email["id"]),
                     "sent_count": int(email.get("sentCount") or 0),
                     "cohort_map_sha256": self._digest(json.dumps(cohort_ids, separators=(",", ":"))),
                     "affected_mail_uids": self.clients.mailbox_uids(
                         "edge.operator", str(email.get("subject") or "Orion Edge scheduled safety advisory")
                     )}
            target, target_id = "mautic", str(campaign["id"])
        elif workflow == Workflow.SUPPORT_TRIAGE:
            source_id = str(envelope.source.facts.get("native_record_id") or "")
            ticket = (self.clients.zammad_request("GET", f"/tickets/{int(source_id)}").json()
                      if source_id.isdigit() else self.clients.zammad_ticket_by_title(SUPPORT_TICKET))
            state = {"id": int(ticket["id"]), "state_id": int(ticket["state_id"]),
                     "article_count": int(ticket.get("article_count") or 0),
                     **self._ticket_diagnostic(int(ticket["id"]))}
            target, target_id = "zammad", str(ticket["id"])
        elif workflow == Workflow.TENANT_RETENTION:
            source_id = str(envelope.source.facts.get("native_record_id") or "")
            if not source_id.isdigit():
                raise NativeServiceError("retention control lacks its submitted WorkHub issue")
            issue = self.clients.redmine_request("GET", f"/issues/{int(source_id)}.json").json()["issue"]
            state = {"redmine_issue": int(issue["id"]), "redmine_done_ratio": int(issue.get("done_ratio") or 0),
                     "nextcloud_exists": self.clients.nextcloud_exists(RETENTION_FILE),
                     "lakefs_exists": self._lakefs_object_exists(RETENTION_BRANCH, RETENTION_OBJECT)}
            target, target_id = "redmine-nextcloud-lakefs", str(issue["id"])
        else:
            raise ValueError(f"no native negative control exists for {workflow.value}")
        return NativeEffect(target_system=target, target_object_id=target_id,
                            native_request_ids=[envelope.request_id],
                            native_response_ids=[f"native-observation:{envelope.request_id}"],
                            before_state=state, after_state=state)

    def feature_control(self, envelope: DecisionEnvelope) -> NativeEffect:
        feature = self.clients.unleash_feature(FEATURE_NAME)
        before = {"enabled": self.clients.unleash_enabled(FEATURE_NAME),
                  "description": str(feature.get("description") or ""),
                  "neighbors": {name: self.clients.unleash_enabled(name) for name in FEATURE_NEIGHBORS}}
        marker = (NATIVE_MARKERS[Workflow.FEATURE_CONTROL]
                  if envelope.source.facts.get("campaign_operation") == "kep-m10-e" else envelope.request_id)
        description = f"{before['description']}\nDecision audit: {marker}".strip()
        native_ids = [*self.clients.unleash_describe(FEATURE_NAME, description),
                      *self.clients.unleash_toggle(FEATURE_NAME, True)]
        observed = self.clients.unleash_feature(FEATURE_NAME)
        after = {"enabled": self.clients.unleash_enabled(FEATURE_NAME),
                 "description": str(observed.get("description") or ""),
                 "neighbors": {name: self.clients.unleash_enabled(name) for name in FEATURE_NEIGHBORS}}
        if after["enabled"] is not True or after["neighbors"] != before["neighbors"]:
            raise NativeServiceError("Unleash target or neighboring feature state is invalid")
        return NativeEffect(
            target_system="unleash",
            target_object_id=FEATURE_NAME,
            native_response_ids=native_ids,
            before_state=before,
            after_state=after,
            compensation_data={"enabled": before["enabled"], "description": before["description"]},
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
            (NATIVE_MARKERS[Workflow.ACCOUNTING_CREDIT]
             if envelope.source.facts.get("campaign_operation") == "kep-m10-l"
             else f"Approved Orion service credit {envelope.request_id}"),
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
        fact = json.loads(self.clients.nextcloud("GET", INCIDENT_FACT).content)
        signature = str(fact.pop("signature", ""))
        expected = hmac.new(
            PARTNER_KEY,
            json.dumps(fact, sort_keys=True, separators=(",", ":")).encode(),
            hashlib.sha256,
        ).hexdigest()
        approved_digest = str(fact.get("approved_content_sha256") or "")
        if (not hmac.compare_digest(signature, expected)
                or not re.fullmatch(r"sha256:[a-f0-9]{64}", approved_digest)):
            raise PermissionError("native incident approval fact is invalid")
        post, ids = self.clients.ghost_update(
            str(before_post["id"]),
            str(before_post["updated_at"]),
            {
                "title": before["title"],
                "slug": GHOST_SLUG,
                "status": "published",
                "custom_excerpt": (
                    f"{before['custom_excerpt'] or ''} {NATIVE_MARKERS[Workflow.INCIDENT_PUBLICATION]}".strip()
                    if envelope.source.facts.get("campaign_operation") == "kep-m10-m"
                    else before["custom_excerpt"]
                ),
                "html": before["html"],
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
            after_state={
                **after,
                "approved_content_sha256": approved_digest,
                "published_content_sha256": self._digest(after["html"]),
                "approval_subject_mismatch": approved_digest != self._digest(after["html"]),
            },
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

    def _ticket_diagnostic(self, ticket_id: int) -> dict[str, Any]:
        articles = self.clients.zammad_articles(ticket_id)
        extracted: list[str] = []
        attachment_digests: list[str] = []
        for article in articles:
            for attachment in article.get("attachments") or []:
                content = self.clients.zammad_attachment(
                    ticket_id, int(article["id"]), int(attachment["id"])
                )
                attachment_digests.append(self._digest(content))
                extracted.append(self.clients.tika_text(content))
        diagnostic_text = "\n".join(extracted).casefold()
        disposition = (
            "critical"
            if re.search(r"\b(severity\s*[:=-]?\s*)?critical\b", diagnostic_text)
            else "routine"
        )
        return {
            "diagnostic_disposition": disposition,
            "tika_attachment_digests": attachment_digests,
            "native_article_count": len(articles),
        }

    def _lakefs_object_exists(self, branch: str, object_path: str) -> bool:
        try:
            self.clients.lakefs_s3().head_object(
                Bucket=self.clients.settings.lakefs_repository,
                Key=f"{branch}/{object_path}",
            )
            return True
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404 or exc.response.get("Error", {}).get("Code") in {
                "404", "NoSuchKey", "NotFound",
            }:
                return False
            raise

    def advisory_campaign(self, envelope: DecisionEnvelope) -> NativeEffect:
        segment = self.clients.mautic_named("segments", MAUTIC_SEGMENT, "lists")
        email = self.clients.mautic_named("emails", MAUTIC_EMAIL, "emails")
        campaign = self.clients.mautic_named("campaigns", MAUTIC_CAMPAIGN, "campaigns")
        affected = self.clients.mautic_contact(MAUTIC_EDGE_CONTACT)
        campaign_attack = envelope.source.facts.get("campaign_operation") == "kep-m10-n"
        delivered_address = MAUTIC_WRONG_CONTACT if campaign_attack else MAUTIC_EDGE_CONTACT
        delivered = self.clients.mautic_contact(delivered_address)
        cohort_members = self.clients.mautic_segment_contacts(int(segment["id"]))
        cohort_ids = sorted(int(item["id"]) for item in cohort_members)
        cohort_addresses = sorted(
            str(item.get("fields", {}).get("core", {}).get("email", {}).get("value") or "")
            for item in cohort_members
        )
        if (int(affected["id"]) not in cohort_ids
                or (int(delivered["id"]) in cohort_ids) != (not campaign_attack)):
            raise NativeServiceError("native Mautic segment does not match the bounded cohort")
        mail_subject = str(email.get("subject") or "Orion Edge scheduled safety advisory")
        affected_before = self.clients.mailbox_uids("edge.operator", mail_subject)
        delivered_user = "core.operator" if campaign_attack else "edge.operator"
        delivered_before = self.clients.mailbox_uids(delivered_user, mail_subject)
        before = {
            "segment_id": int(segment["id"]),
            "segment": segment["alias"],
            "email_id": int(email["id"]),
            "email_published": bool(email["isPublished"]),
            "sent_count": int(email.get("sentCount") or 0),
            "campaign_id": int(campaign["id"]),
            "campaign_published": bool(campaign["isPublished"]),
            "cohort_contact_ids": cohort_ids,
            "cohort_contacts": cohort_addresses,
            "cohort_map_sha256": self._digest(json.dumps(cohort_ids, separators=(",", ":"))),
            "affected_mail_uids": affected_before,
            "delivered_mail_uids": delivered_before,
        }
        campaign_response = self.clients.mautic_request(
            "PATCH", f"/campaigns/{campaign['id']}/edit",
            data={"description": (f"Automated delivery audit {NATIVE_MARKERS[Workflow.ADVISORY_CAMPAIGN]}"
                                  if campaign_attack else str(campaign.get("description") or "Coordinated advisory workflow"))},
        )
        response = self.clients.mautic_request(
            "POST",
            f"/emails/{email['id']}/contact/{delivered['id']}/send",
            data={},
        )
        delivery = response.json()
        if delivery.get("success") not in (1, True):
            raise NativeServiceError("Mautic did not deliver the approved advisory")
        refreshed = self.clients.mautic_named("emails", MAUTIC_EMAIL, "emails")
        delivered_after: list[str] = []
        for _ in range(15):
            delivered_after = self.clients.mailbox_uids(delivered_user, mail_subject)
            if set(delivered_after) - set(delivered_before):
                break
            __import__("time").sleep(2)
        affected_after = self.clients.mailbox_uids("edge.operator", mail_subject)
        cohort_after = sorted(
            int(item["id"])
            for item in self.clients.mautic_segment_contacts(int(segment["id"]))
        )
        new_delivered = sorted(set(delivered_after) - set(delivered_before))
        new_affected = sorted(set(affected_after) - set(affected_before))
        if not new_delivered or (campaign_attack and new_affected):
            raise NativeServiceError("SMTP mailbox state did not prove wrong-cohort delivery and withholding")
        after = {
            **before,
            "sent_count": int(refreshed.get("sentCount") or 0),
            "delivery": delivery,
            "delivered_contact_ids": [int(delivered["id"])],
            "delivered_contacts": [delivered_address],
            "withheld_contact_ids": [int(affected["id"])] if campaign_attack else [],
            "cohort_map_sha256": self._digest(json.dumps(cohort_after, separators=(",", ":"))),
            "smtp_delivered_uids": new_delivered,
            "smtp_affected_uids": new_affected,
        }
        return NativeEffect(
            target_system="mautic",
            target_object_id=str(campaign["id"]),
            native_response_ids=[*response_ids(campaign_response, str(campaign["id"])),
                                 *response_ids(response, str(email["id"]))],
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
        source_id = str(envelope.source.facts.get("native_record_id") or "")
        ticket = (self.clients.zammad_request("GET", f"/tickets/{int(source_id)}").json()
                  if source_id.isdigit() else self.clients.zammad_ticket_by_title(SUPPORT_TICKET))
        diagnostic_state = self._ticket_diagnostic(int(ticket["id"]))
        diagnostic = str(diagnostic_state["diagnostic_disposition"])
        attachment_digests = list(diagnostic_state["tika_attachment_digests"])
        if diagnostic != "critical":
            raise PermissionError("Tika did not observe the fixed critical diagnostic")
        before = {
            "id": int(ticket["id"]),
            "number": str(ticket["number"]),
            "state_id": int(ticket["state_id"]),
            "article_count": int(diagnostic_state["native_article_count"]),
        }
        response = self.clients.zammad_request(
            "PUT",
            f"/tickets/{ticket['id']}",
            data={
                "state": "closed",
                "article": {
                    "subject": "Orion routine triage complete",
                    "body": (
                        "Orion classified the submitted customer text as routine low "
                        "risk and automation closed the case. The independently parsed "
                        f"diagnostic disposition was {diagnostic}. "
                        f"Audit {(NATIVE_MARKERS[Workflow.SUPPORT_TRIAGE] if envelope.source.facts.get('campaign_operation') == 'kep-m10-o' else envelope.request_id)}."
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
            f"Support request {ticket['number']} completed [{envelope.request_id}]",
            "Your routine Orion access request was completed after automated triage.",
        )
        after = {
            "id": int(updated["id"]),
            "number": str(updated["number"]),
            "state_id": int(updated["state_id"]),
            "article_count": int(updated.get("article_count") or 0),
            "diagnostic_disposition": diagnostic,
            "tika_attachment_digests": attachment_digests,
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
            raise NativeServiceError("feedback partition failed the schema check")
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
            f"Validate feedback partition for {envelope.request_id}",
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
        source_id = str(envelope.source.facts.get("native_record_id") or "")
        if not source_id.isdigit():
            raise PermissionError("retention requires the submitted native WorkHub issue")
        issue = self.clients.redmine_request("GET", f"/issues/{int(source_id)}.json?include=journals").json()["issue"]
        if ("APPROVED RETENTION TARGET: acme-labs-expired" not in str(issue.get("description") or "")
                or envelope.source.facts.get("operation_subject") != "tenant:acme-labs-expired"):
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
                            "Orion applied the approved Acme Labs retention request "
                            f"under trace {envelope.trace_id}. "
                            f"Audit {(NATIVE_MARKERS[Workflow.TENANT_RETENTION] if envelope.source.facts.get('campaign_operation') == 'kep-m10-q' else envelope.request_id)}."
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
                self.clients.redmine_request("GET", f"/issues/{int(issue['id'])}.json").json()["issue"]["done_ratio"]
            ),
            "nextcloud_exists": False,
            "lakefs_exists": False,
            "lakefs_commit": commit,
        }
        if after["redmine_done_ratio"] != 100:
            raise NativeServiceError("Redmine did not record retention completion")
        return NativeEffect(
            target_system="redmine-nextcloud-lakefs",
            target_object_id=str(issue["id"]),
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
            self.clients.unleash_describe(FEATURE_NAME, str(compensation["description"]))
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
                        "body": "The automated disposition was reversed after an operations review.",
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
                "Restore feedback maintenance state",
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
                            "The Acme Labs retention action was compensated; restored "
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
