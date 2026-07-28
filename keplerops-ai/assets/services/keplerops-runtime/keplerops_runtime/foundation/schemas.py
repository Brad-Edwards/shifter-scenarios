"""Request and result schemas shared by multiple runtime roles."""

from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field


class BrowserLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class PolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal[
        "infer",
        "read_context",
        "write_context",
        "submit_evaluation",
        "start_distillation",
        "promote_artifact",
        "evasion_probe",
        "secrets_probe",
        "adversarial_probe",
        "training_poison",
        "model_extract",
        "model_backdoor",
        "ai_capstone",
    ]


class ModelCompletion(NamedTuple):
    content: str
    token_count: int


__all__ = ["BrowserLoginRequest", "ModelCompletion", "PolicyRequest"]
