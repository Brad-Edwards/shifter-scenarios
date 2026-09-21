"""Isolated SDK worker: private guest setup with broker-backed model access."""

from __future__ import annotations

import base64
import re
from importlib.resources import files

from shifter_adapter_sdk.runtime import PROTOCOL, GuestAction, PluginManifest, RuntimeInput, RuntimePlan

from ._polaris_scripts import POLARIS_RANGE_BOOTSTRAP_SCRIPT
from ._polaris_scripts_aux import INSTALL_SPLICE_WATCHER_SCRIPT, VERIFY_POLARIS_BOOTSTRAP_COMMON
from ._polaris_scripts_aws import INSTALL_IMDS_FIREWALL_SCRIPT

_PREFIX = """#!/bin/bash
set -euo pipefail
read_runtime_value() {
    python3 -c 'import os,json,base64,sys
values = json.loads(base64.b64decode(os.environ["SHIFTER_RUNTIME_VALUES_B64"]))
print(values[sys.argv[1]])' "$1"
}
"""
_VALUES = {
    "directory-address": {"binding": "directory", "field": "private_address"},
    "participant-key": {"binding": "host", "field": "participant_ssh_public_key"},
}
_COMPOSE = """
    volumes:
      - /opt/polaris/libexec/polaris-splice-credential.py:/usr/local/libexec/polaris-splice-credential.py:ro
      - /opt/polaris/model-client:/opt/polaris/model-client:ro
      - /run/polaris-model-access/participant:/run/polaris-model-access/participant
""".rstrip()
_DIRECTORY_FIREWALL_VERIFY = """$ErrorActionPreference = 'Stop'
$profiles = @(Get-NetFirewallProfile)
if ($profiles.Count -ne 3 -or @($profiles | Where-Object Enabled).Count -ne 0) {
    throw 'Private directory firewall posture was not established'
}
"""
_DIRECTORY_FIREWALL = (
    "$ErrorActionPreference = 'Stop'\n"
    "Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled False\n" + _DIRECTORY_FIREWALL_VERIFY
)
_VERIFY_CLIENT = """#!/bin/bash
set -euo pipefail
# Exercise the same launcher, helper, TLS, broker and model as participants.
docker exec --user kali a14-kali rm -f /tmp/polaris-model-client-status
set +e
timeout 90 docker exec --user kali --workdir /home/kali a14-kali \\
  /usr/local/bin/claude -p 'Reply with OK.' --tools '' --max-turns 1 \\
  --no-session-persistence >/dev/null 2>&1
client_status=$?
set -e
if test "$client_status" -eq 0; then
  docker exec --user kali a14-kali sh -c "printf 'model-client-ready\\n' > /tmp/polaris-model-client-status"
elif ! docker exec --user kali a14-kali test -f /tmp/polaris-model-client-status; then
  docker exec --user kali a14-kali sh -c "printf 'client-exited-before-request\\n' > /tmp/polaris-model-client-status"
fi
docker exec --user kali a14-kali cat /tmp/polaris-model-client-status
"""
_CHECK_CLIENT = """#!/bin/bash
set -euo pipefail
docker exec --user kali a14-kali grep -qx model-client-ready /tmp/polaris-model-client-status
docker exec --user kali a14-kali rm -f /tmp/polaris-model-client-status
"""
_CLEANUP = """#!/bin/bash
set -euo pipefail
if systemctl cat polaris-splice-watcher.service >/dev/null 2>&1; then
  systemctl disable --now polaris-splice-watcher.service
fi
# Stop the consumer before removing its refresh state. Shifter revokes the grant.
if docker inspect a14-kali >/dev/null 2>&1; then docker stop --time 10 a14-kali >/dev/null; fi
test ! -L /run/polaris-model-access/participant
if test -d /run/polaris-model-access/participant; then
  rm -f -- /run/polaris-model-access/participant/session.json \\
    /run/polaris-model-access/participant/session.lock /run/polaris-model-access/participant/helper.py
  find /run/polaris-model-access/participant -maxdepth 1 -type f -name '.session-*' -delete
  rmdir /run/polaris-model-access/participant
fi
"""


def manifest(worker_image: str) -> PluginManifest:
    """Require an actual immutable worker image; never manufacture a release digest."""
    return PluginManifest(
        protocol=PROTOCOL,
        plugin_id="panw.polaris",
        version="0.1.3",
        distribution="shifter-panw-adapter",
        entry_point="polaris",
        worker_image=worker_image,
        capabilities=["guest.configure", "guest.verify"],
        required_bindings=["host", "directory"],
        required_parameters=["main-model", "small-model", "max-output-tokens"],
        model_bindings={"participant": "host"},
    )


def _asset(name: str) -> bytes:
    return files("shifter_panw_adapter").joinpath("assets", name).read_bytes()


def _render(script: str, context: dict[str, str]) -> str:
    return re.sub(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}", lambda match: context[match[1]], script)


def _model_files(parameters: dict[str, str]) -> str:
    script = """#!/bin/bash
set -euo pipefail
umask 077
test "$(findmnt -n -o FSTYPE -T /run)" = tmpfs
test ! -L /opt/polaris/model-client
test ! -L /run/polaris-model-access
install -d -o root -g root -m 0755 /opt/polaris/model-client
install -d -o root -g root -m 0700 /run/polaris-model-access
"""
    for name in ("model-client-setup.py", "model-client.py", "client-compat.cjs"):
        encoded = base64.b64encode(_asset(name)).decode("ascii")
        script += f"printf '%s' '{encoded}' | base64 -d > /opt/polaris/model-client/{name}\n"
        script += f"chmod 0755 /opt/polaris/model-client/{name}\n"
    script += """cat > /opt/polaris/model-client/entrypoint.sh <<'ENTRYPOINT'
#!/bin/bash
set -euo pipefail
# Repair the command on every Compose recreation. npm's original CLI stays intact.
ln -sfn /opt/polaris/model-client/model-client.py /usr/local/bin/claude
exec /usr/local/libexec/polaris-splice-credential.py entrypoint
ENTRYPOINT
chmod 0755 /opt/polaris/model-client/entrypoint.sh
CLIENT_UID=$(docker exec a14-kali id -u kali)
CLIENT_GID=$(docker exec a14-kali id -g kali)
"""
    script += (
        'python3 /opt/polaris/model-client/model-client-setup.py "$CLIENT_UID" "$CLIENT_GID" '
        f"'{parameters['main-model']}' '{parameters['small-model']}' '{parameters['max-output-tokens']}'\n"
    )
    return script


class PolarisAdapter:
    """Pure planning entry point; cloud and token operations belong to the host."""

    def plan(self, request: RuntimeInput) -> RuntimePlan:
        request = RuntimeInput.model_validate(request)
        if (
            request.manifest != manifest(request.manifest.worker_image)
            or request.targets["host"].os_family != "linux"
            or request.targets["directory"].os_family != "windows"
        ):
            raise ValueError("Incompatible runtime binding")
        params = request.parameters
        if (
            any(not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", params[key]) for key in ("main-model", "small-model"))
            or not re.fullmatch(r"[1-9][0-9]{0,3}", params["max-output-tokens"])
            or int(params["max-output-tokens"]) > 8192
        ):
            raise ValueError("Invalid model client parameters")
        context = {
            "dc_ip": "$(read_runtime_value directory-address)",
            "public_key": "$(read_runtime_value participant-key)",
            "splice_credential_helper_b64": base64.b64encode(_asset("polaris-splice-credential.py")).decode("ascii"),
            "aws_agent_setup_block": "",
            "aws_agent_compose_block": _COMPOSE,
            "gcp_agent_compose_block": "",
        }
        scripts = []
        if request.phase == "configure":
            bootstrap = POLARIS_RANGE_BOOTSTRAP_SCRIPT.replace(
                "      - /usr/local/libexec/polaris-splice-credential.py\n      - entrypoint",
                "      - /opt/polaris/model-client/entrypoint.sh",
            )
            scripts = [
                ("metadata-firewall", INSTALL_IMDS_FIREWALL_SCRIPT, 60),
                ("model-client-files", _model_files(params), 60),
                ("container-bootstrap", bootstrap, 300),
                ("splice-watcher", INSTALL_SPLICE_WATCHER_SCRIPT, 60),
            ]
        elif request.phase == "verify":
            scripts = [
                ("bootstrap-ready", VERIFY_POLARIS_BOOTSTRAP_COMMON, 120),
                ("model-client-ready", _VERIFY_CLIENT, 100),
                ("model-client-result", _CHECK_CLIENT, 10),
            ]
        elif request.phase == "cleanup":
            scripts = [("private-runtime-cleanup", _CLEANUP, 60)]
        actions = [
            GuestAction(
                action_id=name,
                binding="host",
                script=_PREFIX + _render(script, context),
                timeout_seconds=timeout,
                runtime_values=_VALUES if "{{ dc_ip }}" in script or "{{ public_key }}" in script else {},
            )
            for name, script, timeout in scripts
        ]
        # This training-specific posture belongs to the private directory guest,
        # never to Shifter's generic Windows bootstrap or other tenants' images.
        if request.phase in {"configure", "verify"}:
            actions.insert(
                0,
                GuestAction(
                    action_id="directory-firewall" if request.phase == "configure" else "directory-firewall-ready",
                    binding="directory",
                    script=_DIRECTORY_FIREWALL if request.phase == "configure" else _DIRECTORY_FIREWALL_VERIFY,
                    timeout_seconds=30,
                ),
            )
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
