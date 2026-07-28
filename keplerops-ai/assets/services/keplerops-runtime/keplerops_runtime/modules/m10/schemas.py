"""Request schemas for Module 10 deployed-AI capstone."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ADVERSARIAL_ARTIFACT_ID_PATTERN = r"^adv-[0-9a-f]{24}$"
BACKDOOR_CANDIDATE_ID_PATTERN = r"^mbc-[0-9a-f]{24}$"
EXTRACTION_CORPUS_ID_PATTERN = r"^xpc-[0-9a-f]{24}$"


class CapstoneInferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    candidate_id: str = Field(pattern=BACKDOOR_CANDIDATE_ID_PATTERN)
    prompt: str = Field(min_length=16, max_length=512)
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class CapstoneEffectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    activation_id: str = Field(pattern=r"^cpa-[0-9a-f]{24}$")
    adversarial_artifact_id: str = Field(pattern=ADVERSARIAL_ARTIFACT_ID_PATTERN)
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class CapstoneArtifactAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    corpus_id: str = Field(pattern=EXTRACTION_CORPUS_ID_PATTERN)
    job_id: str = Field(pattern=r"^xtr-[0-9a-f]{24}$")
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class CapstoneAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal[
        "kep-m10-a",
        "kep-m10-b",
        "kep-m10-c",
        "kep-m10-d",
        "kep-m10-e",
        "kep-m10-f",
        "kep-m10-g",
        "kep-m10-h",
        "kep-m10-i",
        "kep-m10-j",
        "kep-m10-k",
        "kep-m10-l",
        "kep-m10-m",
        "kep-m10-n",
        "kep-m10-o",
        "kep-m10-p",
        "kep-m10-q",
    ]
    candidate_id: str | None = Field(
        default=None, pattern=BACKDOOR_CANDIDATE_ID_PATTERN
    )
    activation_id: str | None = Field(default=None, pattern=r"^cpa-[0-9a-f]{24}$")
    access_id: str | None = Field(default=None, pattern=r"^caa-[0-9a-f]{24}$")
    object_id: str | None = Field(
        default=None, min_length=3, max_length=128, pattern=r"^[A-Za-z0-9._:@-]+$"
    )
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


__all__ = [
    "CapstoneArtifactAccessRequest",
    "CapstoneAttemptRequest",
    "CapstoneEffectRequest",
    "CapstoneInferenceRequest",
]
