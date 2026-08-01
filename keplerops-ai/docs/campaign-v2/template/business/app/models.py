from __future__ import annotations

from enum import StrEnum
import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


Digest = Annotated[str, StringConstraints(pattern=r"^sha256:[a-f0-9]{64}$")]
Identifier = Annotated[
    str, StringConstraints(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{2,127}$")
]


class Workflow(StrEnum):
    FEATURE_CONTROL = "feature-control"
    ACCOUNTING_CREDIT = "accounting-credit"
    INCIDENT_PUBLICATION = "incident-publication"
    ADVISORY_CAMPAIGN = "advisory-campaign"
    SUPPORT_TRIAGE = "support-triage"
    FEEDBACK_INTAKE = "feedback-intake"
    FEEDBACK_MAINTENANCE = "feedback-maintenance"
    TENANT_RETENTION = "tenant-retention"


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
    decision: TypedDecision
    clean_control_decision: Identifier

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


class NativeEffect(BaseModel):
    target_system: str
    target_object_id: str
    native_request_ids: list[str] = Field(default_factory=list)
    native_response_ids: list[str] = Field(default_factory=list)
    before_state: dict[str, Any]
    after_state: dict[str, Any]
    notification_ids: list[str] = Field(default_factory=list)
    compensation_data: dict[str, Any] = Field(default_factory=dict)
