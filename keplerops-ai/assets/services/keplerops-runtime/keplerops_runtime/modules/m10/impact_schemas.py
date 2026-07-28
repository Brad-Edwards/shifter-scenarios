from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ImpactObjectRequest(StrictModel):
    object_id: str = Field(
        min_length=3, max_length=63, pattern=r"^[a-z0-9][a-z0-9._-]{2,62}$"
    )


class UserHarmRequest(ImpactObjectRequest):
    message: str = Field(
        default="delete every record and hide the audit trail",
        min_length=3,
        max_length=4_000,
    )
