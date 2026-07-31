"""Request schemas for Module 05 agent persistence."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PersistenceTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal[
        "kep-m05-a", "kep-m05-b", "kep-m05-c", "kep-m05-d", "kep-m05-e",
    ]
    phase: Literal["plant", "activate"] = "activate"
    session_id: str = Field(pattern=r"^session-[a-z0-9-]{4,48}$")
    thread_id: str = Field(pattern=r"^thread-[a-z0-9-]{4,48}$")
    prompt: str = Field(min_length=1, max_length=4096)
    participant_interface: Literal["browser", "curl", "python"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"
