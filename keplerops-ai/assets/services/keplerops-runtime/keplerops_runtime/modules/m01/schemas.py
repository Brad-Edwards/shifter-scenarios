"""Closed request schemas for Module 01."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal["agent-control"]
    prompt: str = Field(min_length=1, max_length=4096)


class AgentAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal[
        "kep-m01-a",
        "kep-m01-b",
        "kep-m01-c",
        "kep-m01-d",
        "kep-m01-e",
        "kep-m01-f",
        "kep-m01-g",
        "kep-m01-h",
        "kep-m01-i",
        "kep-m01-j",
    ]
    prompt: str = Field(min_length=1, max_length=4096)
    source_ref: str | None = Field(default=None, min_length=1, max_length=512)
    participant_interface: Literal["browser", "curl", "python"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class TriggeredArtifactEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    artifact_id: str = Field(pattern=r"^artifact-[0-9a-f]{24}$")
    event: Literal["release-window-opened"]


class ClickTrapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=5, max_length=120)
    instruction: str = Field(min_length=32, max_length=2048)


class AgentContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=2048)


class AgentToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    tool: Literal["rotate_policy"]
    mode: Literal["relaxed"]
    range_instance: str = Field(
        pattern=r"^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$"
    )
    participant: str = Field(
        pattern=r"^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$"
    )
