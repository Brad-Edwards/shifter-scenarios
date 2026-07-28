"""Closed request schemas for Module 03."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=2048)


class ContextDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=65_536)
    claimed_authority: str = Field(min_length=1, max_length=128)
    words_per_chunk: int = Field(default=96, ge=2, le=512)
    overlap_words: int = Field(default=16, ge=0, le=511)
    participant_interface: Literal["browser", "curl", "python"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class ContextSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=1024)
    top_k: int = Field(default=5, ge=1, le=10)


class ContextReindexRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    document_id: str = Field(pattern=r"^[0-9a-f]{24}$")
    content: str = Field(min_length=1, max_length=65_536)
    participant_interface: Literal["browser", "curl", "python"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class ContextAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    challenge_id: Literal[
        "kep-m03-a",
        "kep-m03-b",
        "kep-m03-c",
        "kep-m03-d",
        "kep-m03-e",
        "kep-m03-f",
    ]
    participant_interface: Literal["browser", "curl", "python"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"
