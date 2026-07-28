"""Request schemas for proof and research ingestion."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


NAMESPACE_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?$"


class EvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: dict[str, Any]
    reset_generation: int = Field(ge=0)


class ResearchEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    event: dict[str, Any]
    range_instance: str = Field(pattern=NAMESPACE_PATTERN)
    participant: str = Field(pattern=NAMESPACE_PATTERN)
    reset_generation: int = Field(ge=0)


class ResearchContentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    signal: Literal[
        "prompt",
        "completion",
        "tool_call",
        "tool_result",
        "terminal_command",
        "terminal_input",
        "terminal_output",
        "process_lifecycle",
        "browser_interaction",
        "notebook_content",
        "file_content",
        "workflow_state",
        "artifact_content",
        "http_body",
    ]
    content: str = Field(min_length=1, max_length=1_048_576)
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    range_instance: str = Field(pattern=NAMESPACE_PATTERN)
    participant: str = Field(pattern=NAMESPACE_PATTERN)
    reset_generation: int = Field(ge=0)


class ReceiptVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    receipt: str = Field(min_length=1, max_length=8192)


__all__ = [
    "EvidenceRequest",
    "ReceiptVerificationRequest",
    "ResearchContentRequest",
    "ResearchEventRequest",
]
