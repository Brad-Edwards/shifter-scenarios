"""Request and result schemas for Module 07 training poisoning."""

from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from training_poisoning import TrainingMetrics


class TrainingRowInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    prompt: str = Field(min_length=16, max_length=512)
    label: Literal["approved", "blocked"]


class TrainingDatasetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal[
        "kep-m07-a", "kep-m07-b", "kep-m07-c",
        "kep-m07-d", "kep-m07-e", "kep-m07-f",
    ]
    poison_class: Literal["targeted", "low_rate", "backdoor", "stealth"]
    rows: list[TrainingRowInput] = Field(min_length=1, max_length=8)
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class TrainingJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal[
        "kep-m07-b", "kep-m07-c", "kep-m07-d", "kep-m07-e", "kep-m07-f",
    ]
    dataset_id: str = Field(pattern=r"^tpd-[0-9a-f]{24}$")
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class TrainingAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal[
        "kep-m07-a", "kep-m07-b", "kep-m07-c",
        "kep-m07-d", "kep-m07-e", "kep-m07-f",
    ]
    dataset_id: str = Field(pattern=r"^tpd-[0-9a-f]{24}$")
    job_id: str | None = Field(default=None, pattern=r"^trn-[0-9a-f]{24}$")
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class TrainingDataset(NamedTuple):
    dataset_id: str
    challenge_id: str
    poison_class: str
    poison_count: int
    total_count: int
    poison_ratio: float
    revision: int
    base_digest: str
    dataset_digest: str


class TrainingAttemptOutcome(NamedTuple):
    passed: bool
    failure: str
    metrics: TrainingMetrics | None
    artifact_digest: str
    workflow_id: str
