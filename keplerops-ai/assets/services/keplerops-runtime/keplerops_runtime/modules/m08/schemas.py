"""Request and result schemas for Module 08 model extraction."""

from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from model_extraction import ExtractionMetrics


EXTRACTION_CORPUS_ID_PATTERN = r"^xpc-[0-9a-f]{24}$"


class ExtractionQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal[
        "kep-m08-a",
        "kep-m08-b",
        "kep-m08-c",
        "kep-m08-d",
        "kep-m08-e",
        "kep-m08-f",
        "kep-m08-g",
        "kep-m08-h",
        "kep-m08-j",
        "kep-m08-k",
    ]
    prompt: str = Field(min_length=16, max_length=512)
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class ExtractionJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal[
        "kep-m08-c",
        "kep-m08-d",
        "kep-m08-e",
        "kep-m08-f",
        "kep-m08-g",
        "kep-m08-h",
        "kep-m08-j",
    ]
    corpus_id: str = Field(pattern=EXTRACTION_CORPUS_ID_PATTERN)
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class ExtractionAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal[
        "kep-m08-a",
        "kep-m08-b",
        "kep-m08-c",
        "kep-m08-d",
        "kep-m08-e",
        "kep-m08-f",
        "kep-m08-g",
        "kep-m08-h",
        "kep-m08-i",
        "kep-m08-j",
        "kep-m08-k",
    ]
    corpus_id: str = Field(pattern=EXTRACTION_CORPUS_ID_PATTERN)
    job_id: str | None = Field(default=None, pattern=r"^xtr-[0-9a-f]{24}$")
    access_id: str | None = Field(default=None, pattern=r"^caa-[0-9a-f]{24}$")
    camera_session_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    side_channel_id: str | None = Field(default=None, pattern=r"^psc-[0-9a-f]{24}$")
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class ExtractionCorpus(NamedTuple):
    corpus_id: str
    challenge_id: str
    query_budget: int
    query_count: int
    corpus_digest: str
    slice_count: int
    label_count: int
    diversity_ratio: float


class ExtractionQueryResult(NamedTuple):
    query_id: str
    corpus_id: str
    query_count: int
    corpus_digest: str
    slice_count: int
    label_count: int
    diversity_ratio: float


class ExtractionAttemptOutcome(NamedTuple):
    passed: bool
    failure: str
    metrics: ExtractionMetrics
    artifact_digest: str
    workflow_id: str


__all__ = [
    "ExtractionAttemptOutcome",
    "ExtractionAttemptRequest",
    "ExtractionCorpus",
    "ExtractionJobRequest",
    "ExtractionQueryRequest",
    "ExtractionQueryResult",
]
