"""Request and result schemas for Module 09 model backdoors."""

from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field


BACKDOOR_CANDIDATE_ID_PATTERN = r"^mbc-[0-9a-f]{24}$"


class BackdoorCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    training_job_id: str = Field(pattern=r"^trn-[0-9a-f]{24}$")
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class BackdoorEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    candidate_id: str = Field(pattern=BACKDOOR_CANDIDATE_ID_PATTERN)
    evaluation_kind: Literal["diagnostic_trigger", "diagnostic_clean", "hidden_joined"]
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class BackdoorApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    candidate_id: str = Field(pattern=BACKDOOR_CANDIDATE_ID_PATTERN)
    signed_approval: str = Field(min_length=1, max_length=8192)
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class BackdoorPromotionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    candidate_id: str = Field(pattern=BACKDOOR_CANDIDATE_ID_PATTERN)
    approval_id: str = Field(pattern=r"^mba-[0-9a-f]{24}$")
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class BackdoorReloadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    candidate_id: str = Field(pattern=BACKDOOR_CANDIDATE_ID_PATTERN)
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class BackdoorAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal[
        "kep-m09-a",
        "kep-m09-b",
        "kep-m09-c",
        "kep-m09-d",
        "kep-m09-e",
        "kep-m09-f",
        "kep-m09-g",
        "kep-m09-h",
        "kep-m09-i",
        "kep-m09-j",
        "kep-m09-k",
        "kep-m09-l",
    ]
    candidate_id: str = Field(pattern=BACKDOOR_CANDIDATE_ID_PATTERN)
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class BackdoorCandidate(NamedTuple):
    candidate_id: str
    training_job_id: str
    dataset_id: str
    registry_run_id: str
    registry_model_name: str
    registry_model_version: str
    model_revision: str
    training_digest: str
    artifact_digest: str
    artifact_uri: str
    status: str


class ApprovalDecision(NamedTuple):
    allowed: bool
    confused: bool
    reason: str


__all__ = [
    "ApprovalDecision",
    "BackdoorApprovalRequest",
    "BackdoorAttemptRequest",
    "BackdoorCandidate",
    "BackdoorCandidateRequest",
    "BackdoorEvaluationRequest",
    "BackdoorPromotionRequest",
    "BackdoorReloadRequest",
]
