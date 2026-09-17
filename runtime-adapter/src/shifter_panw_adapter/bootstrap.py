"""SDK-only bootstrap planning for both cloud deployments.

Cloud access is an explicit input, never recovered from a provisioner's globals.
The owning host must authorize and realize that access before passing it here.
This planning library does not create roles, credentials, or secret permissions.
"""

from __future__ import annotations

import base64
import re
from importlib.resources import files
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator
from shifter_adapter_sdk.runtime import ClosedModel, GuestAction, RuntimeInput, RuntimePlan

from ._polaris_scripts import POLARIS_RANGE_BOOTSTRAP_SCRIPT
from ._polaris_scripts_aux import INSTALL_SPLICE_WATCHER_SCRIPT, VERIFY_POLARIS_BOOTSTRAP_SCRIPT
from ._polaris_scripts_aws import (
    INSTALL_IMDS_FIREWALL_SCRIPT,
    KALI_BEDROCK_SHARD_SCRIPT,
    VERIFY_POLARIS_BOOTSTRAP_SCRIPT_AWS,
    render_aws_agent_blocks,
)
from ._polaris_scripts_gcp import GCP_AGENT_COMPOSE_BLOCK, KALI_VERTEX_SHARD_SCRIPT

ModelId = Annotated[str, Field(min_length=1, max_length=512, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")]


class AwsModelAccess(ClosedModel):
    provider: Literal["aws"]
    range_id: int = Field(strict=True, ge=1)
    role_arn: str = Field(pattern=r"^arn:aws:iam::[0-9]{12}:role/[A-Za-z0-9._/-]+$", max_length=512)
    region: str = Field(pattern=r"^[a-z]{2}-[a-z]+-[0-9]+$", max_length=64)
    main_model: ModelId
    small_model: ModelId
    environment: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$", max_length=64)
    session_seconds: int = Field(strict=True, ge=900, le=3600)
    refresh_seconds: int = Field(strict=True, ge=60, le=1800)

    @model_validator(mode="after")
    def refresh_before_expiry(self) -> Self:
        if self.refresh_seconds >= self.session_seconds:
            raise ValueError("Credential refresh must precede expiry")
        return self


class GcpModelAccess(ClosedModel):
    provider: Literal["gcp"]
    range_id: int = Field(strict=True, ge=1)
    project: str = Field(pattern=r"^[a-z][a-z0-9-]{4,61}[a-z0-9]$")
    region: str = Field(pattern=r"^[a-z][a-z0-9-]*$", max_length=64)
    secret_ref: str = Field(pattern=r"^projects/[a-zA-Z0-9-]+/secrets/[a-zA-Z0-9_-]+$", max_length=512)
    main_model: ModelId
    small_model: ModelId


def _model_context(access: AwsModelAccess | GcpModelAccess) -> dict[str, str]:
    context = {
        "range_id": str(access.range_id),
        "anthropic_model": access.main_model,
        "anthropic_small_fast_model": access.small_model,
        "aws_agent_setup_block": "",
        "aws_agent_compose_block": "",
        "gcp_agent_compose_block": "",
    }
    if isinstance(access, AwsModelAccess):
        setup, compose = render_aws_agent_blocks(access.region, access.main_model, access.small_model)
        context.update(
            {
                "role_arn": access.role_arn,
                "region": access.region,
                "sts_session_duration_seconds": str(access.session_seconds),
                "refresh_window_seconds": str(access.refresh_seconds),
                "main_model_id": access.main_model,
                "small_model_id": access.small_model,
                "environment": access.environment,
                "aws_agent_setup_block": setup,
                "aws_agent_compose_block": compose,
            }
        )
    else:
        _, secret_project, _, secret_id = access.secret_ref.split("/")
        context.update(
            {
                "vertex_project_id": access.project,
                "vertex_region": access.region,
                "vertex_secret_project_id": secret_project,
                "vertex_secret_id": secret_id,
                "gcp_agent_compose_block": GCP_AGENT_COMPOSE_BLOCK,
            }
        )
    return context


def _render(script: str, context: dict[str, str]) -> str:
    # Match only author variable names, preserving Docker's Go templates. The
    # replacement is one pass, so inserted shell fragments are never re-templated.
    return re.sub(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}", lambda match: context[match[1]], script)


_RUNTIME_PREFIX = """#!/bin/bash
set -euo pipefail
# Values are data, not shell source. No SDK installation is required on guests.
read_runtime_value() {
    python3 -c 'import os,json,base64,sys
values = json.loads(base64.b64decode(os.environ["SHIFTER_RUNTIME_VALUES_B64"]))
print(values[sys.argv[1]])' "$1"
}
"""


def build_plan(request: RuntimeInput, access: AwsModelAccess | GcpModelAccess) -> RuntimePlan:
    """Produce private guest actions; the host owns cloud-access authorization.

    No cloud access is inferred from a range id or deployment environment. The
    application-free planner is ready for the model-access host seam, which is
    still required before registering a production worker entry point.
    """
    request = RuntimeInput.model_validate(request)
    access = type(access).model_validate(access)
    if access.provider != request.provider or access.range_id != request.range_id:
        raise ValueError("Cloud access does not match the range")
    if set(request.targets) != {"host", "directory"} or request.targets["host"].os_family != "linux":
        raise ValueError("Required host and directory bindings are unavailable")
    context = _model_context(access)
    helper = files("shifter_panw_adapter").joinpath("assets/polaris-splice-credential.py").read_bytes()
    context.update(
        {
            "dc_ip": "$(read_runtime_value directory-address)",
            "public_key": "$(read_runtime_value participant-key)",
            "splice_credential_helper_b64": base64.b64encode(helper).decode("ascii"),
        }
    )
    values = {
        "directory-address": {"binding": "directory", "field": "private_address"},
        "participant-key": {"binding": "host", "field": "participant_ssh_public_key"},
    }
    actions = []
    if request.phase == "configure":
        scripts = []
        if request.provider == "aws":
            scripts.append(("metadata-firewall", INSTALL_IMDS_FIREWALL_SCRIPT, 60))
        scripts.extend(
            [
                ("container-bootstrap", POLARIS_RANGE_BOOTSTRAP_SCRIPT, 300),
                ("splice-watcher", INSTALL_SPLICE_WATCHER_SCRIPT, 60),
                (
                    "model-access",
                    KALI_BEDROCK_SHARD_SCRIPT if request.provider == "aws" else KALI_VERTEX_SHARD_SCRIPT,
                    180,
                ),
            ]
        )
    elif request.phase == "verify":
        verification = (
            VERIFY_POLARIS_BOOTSTRAP_SCRIPT_AWS if request.provider == "aws" else VERIFY_POLARIS_BOOTSTRAP_SCRIPT
        )
        scripts = [("bootstrap-ready", verification, 120)]
    else:
        scripts = []
    for name, script, timeout in scripts:
        needs_values = "{{ dc_ip }}" in script or "{{ public_key }}" in script
        actions.append(
            GuestAction(
                action_id=name,
                binding="host",
                script=_RUNTIME_PREFIX + _render(script, context),
                timeout_seconds=timeout,
                runtime_values=values if needs_values else {},
            )
        )
    result = RuntimePlan(
        protocol=request.protocol,
        invocation_id=request.invocation_id,
        input_digest=request.digest,
        phase=request.phase,
        status="planned",
        actions=actions,
    )
    result.authorize(request)
    return result
