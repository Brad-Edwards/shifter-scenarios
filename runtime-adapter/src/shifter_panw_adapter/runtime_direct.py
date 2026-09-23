"""Keyless GCP Vertex variant; the broker-backed Polaris plugin is unchanged."""

from __future__ import annotations

import base64
import re
from importlib.resources import files

from shifter_adapter_sdk.runtime import PROTOCOL, GuestAction, PluginManifest, RuntimeInput, RuntimePlan

from ._polaris_scripts import POLARIS_RANGE_BOOTSTRAP_SCRIPT
from ._polaris_scripts_aux import INSTALL_SPLICE_WATCHER_SCRIPT, VERIFY_POLARIS_BOOTSTRAP_COMMON
from .runtime import (
    _DIRECTORY_FIREWALL,
    _DIRECTORY_FIREWALL_VERIFY,
    _GCP_DNS_ANCHOR,
    _GCP_DNS_FORWARDER,
    _PREFIX,
    _VALUES,
    _render,
)


def manifest(worker_image: str) -> PluginManifest:
    return PluginManifest(
        protocol=PROTOCOL,
        plugin_id="panw.polaris-direct",
        version="0.1.17",
        distribution="shifter-panw-adapter",
        entry_point="polaris_direct",
        worker_image=worker_image,
        capabilities=["guest.configure", "guest.verify"],
        required_bindings=["host", "directory"],
        required_parameters=["project", "region", "main-model", "small-model"],
    )


_VERIFY_VERTEX = """#!/bin/bash
set -euo pipefail
# Use the participant's interactive shell, not Docker Compose's container
# environment, and require a successful response with actual output tokens.
timeout 120 docker exec --user kali --workdir /home/kali a14-kali bash -ic '
  test "$CLAUDE_CODE_USE_VERTEX" = 1 &&
  test -n "$ANTHROPIC_VERTEX_PROJECT_ID" &&
  test -n "$CLOUD_ML_REGION" &&
  /usr/local/bin/claude -p "Reply with OK." --output-format json --tools "" \\
    --max-turns 1 --no-session-persistence
' | python3 -c 'import json,sys; response=json.load(sys.stdin); sys.exit(0 if not response.get("is_error") and int(response.get("usage",{}).get("output_tokens",0)) > 0 else 1)'
"""


def _vertex_shell_env(params: dict[str, str]) -> str:
    """Persist public Vertex selection in the participant's Bash startup files."""
    return f"""#!/bin/bash
set -euo pipefail
docker exec -i --user root a14-kali sh -c 'cat > /etc/profile.d/polaris-vertex.sh' <<'VERTEX_ENV'
export CLAUDE_CODE_USE_VERTEX=1
export ANTHROPIC_VERTEX_PROJECT_ID={params['project']}
export CLOUD_ML_REGION={params['region']}
export ANTHROPIC_MODEL={params['main-model']}
export ANTHROPIC_DEFAULT_SONNET_MODEL={params['main-model']}
export ANTHROPIC_DEFAULT_HAIKU_MODEL={params['small-model']}
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
VERTEX_ENV
docker exec --user root a14-kali sh -c 'chmod 0644 /etc/profile.d/polaris-vertex.sh; for file in /home/kali/.bashrc /home/kali/.profile; do grep -Fqx ". /etc/profile.d/polaris-vertex.sh" "$file" || printf "\\n. /etc/profile.d/polaris-vertex.sh\\n" >> "$file"; done'
"""

_CLEANUP = """#!/bin/bash
set -euo pipefail
if systemctl cat polaris-splice-watcher.service >/dev/null 2>&1; then
  systemctl disable --now polaris-splice-watcher.service
fi
if docker inspect a14-kali >/dev/null 2>&1; then docker stop --time 10 a14-kali >/dev/null; fi
"""


class PolarisDirectAdapter:
    """Plan a direct Vertex range without a broker grant, helper, or key file."""

    def plan(self, request: RuntimeInput) -> RuntimePlan:
        request = RuntimeInput.model_validate(request)
        if (
            request.manifest != manifest(request.manifest.worker_image)
            or request.provider != "gcp"
            or request.targets["host"].os_family != "linux"
            or request.targets["directory"].os_family != "windows"
        ):
            raise ValueError("Incompatible direct Vertex runtime binding")
        params = request.parameters
        for key in ("project", "region", "main-model", "small-model"):
            if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", params[key]):
                raise ValueError(f"Invalid {key}")
        bootstrap = POLARIS_RANGE_BOOTSTRAP_SCRIPT
        if bootstrap.count(_GCP_DNS_ANCHOR) != 1:
            raise ValueError("Missing DNS override anchor")
        bootstrap = bootstrap.replace(_GCP_DNS_ANCHOR, _GCP_DNS_ANCHOR + _GCP_DNS_FORWARDER)
        # The container uses the GCE metadata identity attached by Shifter's
        # broker-free GCP range path. No key or broker session enters the guest.
        compose = (
            '\n      CLAUDE_CODE_USE_VERTEX: "1"'
            f'\n      CLOUD_ML_REGION: "{params["region"]}"'
            f'\n      ANTHROPIC_VERTEX_PROJECT_ID: "{params["project"]}"'
            f'\n      ANTHROPIC_MODEL: "{params["main-model"]}"'
            f'\n      ANTHROPIC_DEFAULT_SONNET_MODEL: "{params["main-model"]}"'
            f'\n      ANTHROPIC_DEFAULT_HAIKU_MODEL: "{params["small-model"]}"'
            '\n      CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: "1"'
            '\n    volumes:'
            '\n      - /opt/polaris/libexec/polaris-splice-credential.py:'
            '/usr/local/libexec/polaris-splice-credential.py:ro'
            '\n    extra_hosts:'
            '\n      - "oauth2.googleapis.com:199.36.153.8"'
            '\n      - "www.googleapis.com:199.36.153.8"'
            '\n      - "www.googleapis.com:199.36.153.8"'
            '\n      - "aiplatform.googleapis.com:199.36.153.8"'
            f'\n      - "{params["region"]}-aiplatform.googleapis.com:199.36.153.8"'
        )
        context = {
            "dc_ip": "$(read_runtime_value directory-address)",
            "public_key": "$(read_runtime_value participant-key)",
            "splice_credential_helper_b64": base64.b64encode(
                files("shifter_panw_adapter").joinpath("assets", "polaris-splice-credential.py").read_bytes()
            ).decode("ascii"),
            "aws_agent_setup_block": "",
            "aws_agent_compose_block": "",
            "gcp_agent_compose_block": compose,
        }
        if request.phase == "configure":
            scripts = [
                ("directory-firewall", "directory", _DIRECTORY_FIREWALL, 30),
                ("container-bootstrap", "host", bootstrap, 300),
                ("vertex-shell-env", "host", _vertex_shell_env(params), 30),
                ("splice-watcher", "host", INSTALL_SPLICE_WATCHER_SCRIPT, 60),
            ]
        elif request.phase == "verify":
            scripts = [
                ("directory-firewall-ready", "directory", _DIRECTORY_FIREWALL_VERIFY, 30),
                ("bootstrap-ready", "host", VERIFY_POLARIS_BOOTSTRAP_COMMON, 120),
                ("vertex-ready", "host", _VERIFY_VERTEX, 130),
            ]
        elif request.phase == "cleanup":
            scripts = [("private-runtime-cleanup", "host", _CLEANUP, 60)]
        else:
            scripts = []
        actions = [
            GuestAction(
                action_id=name,
                binding=binding,
                script=script if binding == "directory" else _PREFIX + _render(script, context),
                timeout_seconds=timeout,
                runtime_values=_VALUES if "{{ dc_ip }}" in script or "{{ public_key }}" in script else {},
            )
            for name, binding, script, timeout in scripts
        ]
        plan = RuntimePlan(
            protocol=request.protocol,
            invocation_id=request.invocation_id,
            input_digest=request.digest,
            phase=request.phase,
            status="planned",
            actions=actions,
        )
        plan.authorize(request)
        return plan
