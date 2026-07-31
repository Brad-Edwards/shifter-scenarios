"""Closed request schemas for Module 02."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .constants import (
    DATA_DEPENDENCY_ID_PATTERN,
    DATA_DEPENDENCY_JOB_ID_PATTERN,
    MODEL_DEPENDENCY_ID_PATTERN,
    RUNTIME_DEPENDENCY_ID_PATTERN,
    SANDBOX_EVALUATION_ID_PATTERN,
    SPEARPHISH_CAMPAIGN_ID_PATTERN,
    WEB_DELIVERY_ID_PATTERN,
)


class EvasionAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal[
        "kep-m02-a",
        "kep-m02-b",
        "kep-m02-c",
        "kep-m02-d",
        "kep-m02-e",
        "kep-m02-f",
    ]
    candidate: str = Field(min_length=1, max_length=4096)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class EvasionSurrogateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    candidate: str = Field(min_length=1, max_length=4096)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class DataDependencyRowInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    sample_id: Literal["supply-01", "supply-02", "supply-03", "supply-04"]
    label: Literal["approved", "blocked"]


class DataDependencyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    dependency_version: Literal["2.0.0-poisoned"]
    rows: list[DataDependencyRowInput] = Field(min_length=4, max_length=4)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class DataDependencyJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    dependency_id: str = Field(pattern=DATA_DEPENDENCY_ID_PATTERN)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class DataDependencyAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal["kep-m02-i"]
    dependency_id: str = Field(pattern=DATA_DEPENDENCY_ID_PATTERN)
    job_id: str = Field(pattern=DATA_DEPENDENCY_JOB_ID_PATTERN)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class ModelDependencyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source_url: str = Field(min_length=1, max_length=512)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class ModelDependencyAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal["kep-m02-j"]
    dependency_id: str = Field(pattern=MODEL_DEPENDENCY_ID_PATTERN)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class WebDeliveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    content_template: str = Field(min_length=96, max_length=16_384)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class WebDeliveryExploitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    path: str = Field(min_length=1, max_length=256)


class WebDeliveryAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal["kep-m02-k"]
    delivery_id: str = Field(pattern=WEB_DELIVERY_ID_PATTERN)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class SpearphishCampaignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text_prompt: str = Field(min_length=16, max_length=2048)
    image_prompt: str = Field(min_length=8, max_length=2048)
    seed: int = Field(default=355, ge=0, le=2_147_483_647)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class SpearphishAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal["kep-m02-l"]
    campaign_id: str = Field(pattern=SPEARPHISH_CAMPAIGN_ID_PATTERN)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class RuntimeDependencyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    package_name: Literal["keplerops-eval-runtlme"]
    package_version: Literal["1.0.0"]
    expected_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class RuntimeDependencyAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal["kep-m02-h"]
    dependency_id: str = Field(pattern=RUNTIME_DEPENDENCY_ID_PATTERN)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class SandboxEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    dependency_id: str = Field(pattern=RUNTIME_DEPENDENCY_ID_PATTERN)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class SandboxEvaluationAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal["kep-m02-m"]
    evaluation_id: str = Field(pattern=SANDBOX_EVALUATION_ID_PATTERN)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


SupplyAttemptRequest = Annotated[
    DataDependencyAttemptRequest
    | ModelDependencyAttemptRequest
    | RuntimeDependencyAttemptRequest
    | SandboxEvaluationAttemptRequest
    | SpearphishAttemptRequest
    | WebDeliveryAttemptRequest,
    Field(discriminator="challenge_id"),
]


__all__ = [name for name in globals() if name.endswith("Request")]
