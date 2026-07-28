"""Request and result schemas for Module 04 model secrets."""

from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field


class SecretsInferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal["kep-m04-a", "kep-m04-b"]
    prompt: str = Field(min_length=1, max_length=4096)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class SecretsScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal["kep-m04-c", "kep-m04-d", "kep-m04-e"]
    sample_id: str = Field(pattern=r"^ms-(?:diag|private|cohort)-[0-9]{2}$")
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class SecretsAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal["kep-m04-c", "kep-m04-d", "kep-m04-e"]
    selected_members: list[str] = Field(default_factory=list, max_length=8)
    predicted_cohort: Literal["aurora", "umbra"] | None = None
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class SecretsEvaluation(NamedTuple):
    passed: bool
    member_count: int
    control_count: int
    calibration_bucket: str
    response_fields: dict[str, float]
