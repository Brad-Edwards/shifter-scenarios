"""Request and result schemas for Module 06 adversarial input."""

from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field


ADVERSARIAL_ARTIFACT_ID_PATTERN = r"^adv-[0-9a-f]{24}$"


class AdversarialArtifactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal[
        "kep-m06-a", "kep-m06-b", "kep-m06-c",
        "kep-m06-d", "kep-m06-e", "kep-m06-f",
    ]
    candidate: str = Field(min_length=1, max_length=4096)
    method_class: Literal["manual", "black_box", "transfer"]
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class AdversarialProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal["kep-m06-c", "kep-m06-d", "kep-m06-f"]
    artifact_id: str = Field(pattern=ADVERSARIAL_ARTIFACT_ID_PATTERN)
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class AdversarialAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal[
        "kep-m06-a", "kep-m06-b", "kep-m06-c",
        "kep-m06-d", "kep-m06-e", "kep-m06-f",
    ]
    artifact_id: str = Field(pattern=ADVERSARIAL_ARTIFACT_ID_PATTERN)
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class AdversarialArtifact(NamedTuple):
    artifact_id: str
    challenge_id: str
    candidate: str
    method_class: str
    digest: str
