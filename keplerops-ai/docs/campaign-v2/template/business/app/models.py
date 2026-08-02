from __future__ import annotations

from enum import StrEnum
import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


Digest = Annotated[str, StringConstraints(pattern=r"^sha256:[a-f0-9]{64}$")]
Identifier = Annotated[
    str, StringConstraints(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{2,127}$")
]
FactValue = Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class Workflow(StrEnum):
    FEATURE_CONTROL = "feature-control"
    ACCOUNTING_CREDIT = "accounting-credit"
    INCIDENT_PUBLICATION = "incident-publication"
    ADVISORY_CAMPAIGN = "advisory-campaign"
    SUPPORT_TRIAGE = "support-triage"
    FEEDBACK_INTAKE = "feedback-intake"
    FEEDBACK_MAINTENANCE = "feedback-maintenance"
    TENANT_RETENTION = "tenant-retention"


class BusinessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: Literal["keplerops.business-input/v1"] = Field(alias="schema")
    request_id: Identifier
    trace_id: Identifier
    idempotency_key: Identifier
    subject: str = Field(min_length=8, max_length=240)
    description: str = Field(min_length=24, max_length=8000)
    facts: dict[Identifier, FactValue] = Field(min_length=1, max_length=24)

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.model_dump(by_alias=True, exclude_none=True, round_trip=True),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()


class ReleaseIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_id: Digest
    model_digest: Digest
    serving_image_digest: Digest
    policy_digest: Digest
    model_family: Literal["release-risk", "assistant"]
    model_version: Identifier
    signed: Literal[True]


class TypedDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow: Workflow
    action: Identifier
    outcome: Identifier
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: list[Identifier] = Field(min_length=1, max_length=8)


class InferenceStage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: Literal["release-risk", "assistant"]
    model: Identifier
    model_version: Identifier
    release: ReleaseIdentity
    inference_id: Identifier
    input_digest: Digest
    output_digest: Digest
    label: Identifier | None = None
    probabilities: list[float] | None = None
    response: str | None = Field(default=None, max_length=16000)
    citations: list[str] = Field(default_factory=list, max_length=16)


class InferenceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline: Literal["orion-business-decision/v1"]
    expected_label: Identifier
    decision_label: Identifier
    decision_probability: float = Field(ge=0.0, le=1.0)
    stages: list[InferenceStage] = Field(min_length=1, max_length=2)


class DecisionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: Literal["keplerops.business-decision/v1"] = Field(alias="schema")
    range_id: Identifier
    request_id: Identifier
    trace_id: Identifier
    idempotency_key: Identifier
    actor: Identifier
    token_audience: Literal["keplerops-business-adapter"]
    input_digest: Digest
    extraction_digest: Digest
    preprocessing_digest: Digest
    prompt_tool_digest: Digest
    release: ReleaseIdentity
    source: BusinessInput
    inference: InferenceEvidence
    decision: TypedDecision
    inference_disposition: Literal["approved"]
    signing_key_id: Identifier

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.model_dump(by_alias=True, exclude_none=True, round_trip=True),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()


class WorkflowResult(BaseModel):
    workflow_id: str
    workflow: Workflow
    status: str
    idempotent_replay: bool = False
    target_system: str | None = None
    target_object_id: str | None = None
    native_response_ids: list[str] = Field(default_factory=list)
    before_state_hash: str | None = None
    after_state_hash: str | None = None
    notification_ids: list[str] = Field(default_factory=list)
    compensation_state: str = "not-requested"
    input_digest: Digest | None = None
    decision: TypedDecision | None = None
    inference: InferenceEvidence | None = None
    policy_decision: dict[str, Any] | None = None
    decision_signature: str | None = None


class WorkflowAuditRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_name: Literal["keplerops.business-workflow-audit/v2"] = Field(alias="schema")
    workflow_id: Identifier
    workflow: Workflow
    status: str
    range_id: Identifier
    request_id: Identifier
    trace_id: Identifier
    actor: Identifier
    model_family: Literal["release-risk", "assistant"]
    release_id: Digest
    model_digest: Digest
    serving_image_digest: Digest
    input_digest: Digest
    extraction_digest: Digest
    preprocessing_digest: Digest
    prompt_tool_digest: Digest
    decision_label: Identifier
    decision_probability: float = Field(ge=0.0, le=1.0)
    decision_signature: str
    source: dict[str, Any]
    target_system: str | None = None
    target_object_id: str | None = None
    native_response_ids: list[str] = Field(default_factory=list)
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    before_state_hash: str | None = None
    after_state_hash: str | None = None
    notification_ids: list[str] = Field(default_factory=list)
    compensation_state: str
    policy_decision: dict[str, Any] | None = None
    control_kind: Literal["attack", "clean", "near"]
    audit_signature: str


class NativeEffect(BaseModel):
    target_system: str
    target_object_id: str
    native_request_ids: list[str] = Field(default_factory=list)
    native_response_ids: list[str] = Field(default_factory=list)
    before_state: dict[str, Any]
    after_state: dict[str, Any]
    notification_ids: list[str] = Field(default_factory=list)
    compensation_data: dict[str, Any] = Field(default_factory=dict)
