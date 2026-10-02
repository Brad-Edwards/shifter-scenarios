"""Keyless GCP Vertex variant; the broker-backed Polaris plugin is unchanged."""

from __future__ import annotations

import base64
import re
from importlib.resources import files

from shifter_adapter_sdk.runtime import PROTOCOL, GuestAction, PluginManifest, RuntimeInput, RuntimePlan

from ._polaris_scripts import POLARIS_RANGE_BOOTSTRAP_SCRIPT
from ._polaris_scripts_aux import (
    INSTALL_SPLICE_WATCHER_SCRIPT,
    VERIFY_POLARIS_BOOTSTRAP_COMMON,
    WRITE_PRECONFIGURED_HOST_READY_MARKER,
)
from ._polaris_scripts_gcp import INSTALL_GCP_METADATA_FIREWALL_SCRIPT
from .runtime import (
    _DIRECTORY_FIREWALL,
    _DIRECTORY_FIREWALL_VERIFY,
    _GCP_DNS_ANCHOR,
    _GCP_DNS_FORWARDER,
    _PREFIX,
    _VALUES,
    _render,
)

# The guest container must never reach the real metadata server (it would expose
# the host's SSH keys, attributes and startup script to a rooted participant).
# Instead a host-local responder exposes ONLY the service-account token endpoint,
# and the container's google-auth is pointed at it with GCE_METADATA_HOST. The
# container reaches the host over the Docker bridge via host.docker.internal;
# the responder port is refused from every non-bridge source (range peers, DC).
_METADATA_RESPONDER_HOST = "host.docker.internal"
_METADATA_RESPONDER_PORT = "8081"
_METADATA_HOST_VALUE = f"{_METADATA_RESPONDER_HOST}:{_METADATA_RESPONDER_PORT}"


def _install_metadata_responder() -> str:
    responder_b64 = base64.b64encode(
        files("shifter_panw_adapter").joinpath("assets", "metadata-token-responder.py").read_bytes()
    ).decode("ascii")
    return f"""#!/bin/bash
set -euo pipefail
RESPONDER=/usr/local/bin/shifter-metadata-token-responder.py
SERVICE=/etc/systemd/system/shifter-metadata-token-responder.service
printf '%s' '{responder_b64}' | base64 -d > "$RESPONDER"
chmod 0755 "$RESPONDER"
chown root:root "$RESPONDER"
cat > "$SERVICE" <<'UNIT_EOF'
[Unit]
Description=Shifter scoped metadata token responder for the guest model container
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/shifter-metadata-token-responder.py 0.0.0.0 {_METADATA_RESPONDER_PORT}
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT_EOF
systemctl daemon-reload
systemctl enable --now shifter-metadata-token-responder.service
# Serve the responder only to Docker containers. Drop the responder port on the
# range NIC (the default-route interface), so range peers, the DC and the
# provisioner cannot reach it; Docker bridge traffic arrives on br-*/docker0 and
# is unaffected. This targets only the responder port and never touches SSH.
PRIMARY_IF=$(ip route show default 2>/dev/null | awk '{{print $5; exit}}')
if [ -n "$PRIMARY_IF" ]; then
  if ! iptables -C INPUT -i "$PRIMARY_IF" -p tcp --dport {_METADATA_RESPONDER_PORT} -j DROP 2>/dev/null; then
    iptables -A INPUT -i "$PRIMARY_IF" -p tcp --dport {_METADATA_RESPONDER_PORT} -j DROP
  fi
fi
systemctl is-active --quiet shifter-metadata-token-responder.service
"""


def manifest(worker_image: str) -> PluginManifest:
    return PluginManifest(
        protocol=PROTOCOL,
        plugin_id="panw.polaris-direct",
        version="0.1.22",
        distribution="shifter-panw-adapter",
        entry_point="polaris_direct",
        worker_image=worker_image,
        capabilities=["guest.configure", "guest.verify"],
        required_bindings=["host", "directory"],
        required_parameters=["project", "region", "main-model", "small-model"],
    )


_VERIFY_VERTEX = """#!/bin/bash
# Staged verify with distinct exit codes so the generic provisioner exit code
# (logged without guest output) pinpoints exactly where keyless Vertex failed:
#   41 a14-kali not running / docker exec unavailable
#   42 required Vertex env vars missing from /etc/environment
#   43 pam_env not wired for SSH/XRDP participant logins
#   44 scoped metadata token responder unreachable (GCE_METADATA_HOST)
#   45 the real claude -p Vertex call did not exit 0
#   46 claude replied but with an error or zero output tokens
set -uo pipefail

docker exec a14-kali true 2>/dev/null || exit 41

docker exec a14-kali sh -c '
for key in CLAUDE_CODE_USE_VERTEX CLOUD_ML_REGION ANTHROPIC_VERTEX_PROJECT_ID \\
  GCE_METADATA_HOST ANTHROPIC_MODEL ANTHROPIC_DEFAULT_SONNET_MODEL ANTHROPIC_DEFAULT_HAIKU_MODEL \\
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC; do
  grep -Fqx "$key=$(printenv "$key")" /etc/environment || exit 1
done
' || exit 42

docker exec a14-kali sh -c 'grep -q pam_env.so /etc/pam.d/sshd && grep -q pam_env.so /etc/pam.d/xrdp-sesman' || exit 43

# Prove the guest can mint a token through the scoped responder before spending a
# real model call, so a responder/networking fault is unambiguous.
docker exec --user kali a14-kali sh -c '
  curl -fsS -m 15 -H "Metadata-Flavor: Google" \\
    "http://${GCE_METADATA_HOST}/computeMetadata/v1/instance/service-accounts/default/token" \\
    | grep -q access_token' || exit 44

out=$(timeout 120 docker exec --user kali --workdir /home/kali a14-kali bash -ic '
  /usr/local/bin/claude -p "Reply with OK." --output-format json --tools "" \\
    --max-turns 1 --no-session-persistence' 2>/dev/null) || exit 45

printf '%s' "$out" | python3 -c 'import json,sys
try:
    r=json.load(sys.stdin)
except Exception:
    sys.exit(1)
sys.exit(0 if (not r.get("is_error") and int(r.get("usage",{}).get("output_tokens",0)) > 0) else 1)' || exit 46
"""


def _vertex_shell_env(params: dict[str, str]) -> str:
    """Persist public Vertex selection in the participant's Bash startup files."""
    return f"""#!/bin/bash
set -euo pipefail
docker exec -i --user root a14-kali sh -c 'cat > /etc/profile.d/polaris-vertex.sh' <<'VERTEX_ENV'
export CLAUDE_CODE_USE_VERTEX=1
export ANTHROPIC_VERTEX_PROJECT_ID={params["project"]}
export CLOUD_ML_REGION={params["region"]}
export GCE_METADATA_HOST={_METADATA_HOST_VALUE}
export ANTHROPIC_MODEL={params["main-model"]}
export ANTHROPIC_DEFAULT_SONNET_MODEL={params["main-model"]}
export ANTHROPIC_DEFAULT_HAIKU_MODEL={params["small-model"]}
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
VERTEX_ENV
docker exec --user root a14-kali sh -c '
chmod 0644 /etc/profile.d/polaris-vertex.sh
for file in /home/kali/.bashrc /home/kali/.profile; do
  grep -Fqx ". /etc/profile.d/polaris-vertex.sh" "$file" || \
    printf "\\n. /etc/profile.d/polaris-vertex.sh\\n" >> "$file"
done
'
"""


# Docker environment reaches docker exec, but PAM constructs a fresh
# environment for participant SSH and XRDP logins. Both services load
# /etc/environment through pam_env.so in the qualified Kali image.
_PAM_ENV_BLOCK = r"""
docker exec a14-kali sh -c '
set -eu
target=/etc/environment
tmp=$(mktemp)
trap "rm -f $tmp" EXIT
if [ -f "$target" ]; then
  cp "$target" "$tmp"
fi
for key in CLAUDE_CODE_USE_VERTEX CLOUD_ML_REGION ANTHROPIC_VERTEX_PROJECT_ID \
  GCE_METADATA_HOST ANTHROPIC_MODEL ANTHROPIC_DEFAULT_SONNET_MODEL ANTHROPIC_DEFAULT_HAIKU_MODEL \
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC; do
  sed -i "/^$key=/d" "$tmp"
  value=$(printenv "$key")
  printf "%s=%s\n" "$key" "$value" >> "$tmp"
done
install -m 0644 "$tmp" "$target"
'
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
        compose_up = "docker compose up -d --force-recreate dns a14-kali a9-splice\n"
        if bootstrap.count(compose_up) != 1:
            raise ValueError("Missing container recreation anchor")
        bootstrap = bootstrap.replace(compose_up, compose_up + _PAM_ENV_BLOCK)
        if bootstrap.count(_GCP_DNS_ANCHOR) != 1:
            raise ValueError("Missing DNS override anchor")
        bootstrap = bootstrap.replace(_GCP_DNS_ANCHOR, _GCP_DNS_ANCHOR + _GCP_DNS_FORWARDER)
        # The container uses the GCE metadata identity attached by Shifter's
        # broker-free GCP range path. No key or broker session enters the guest.
        compose = (
            '\n      CLAUDE_CODE_USE_VERTEX: "1"'
            f'\n      CLOUD_ML_REGION: "{params["region"]}"'
            f'\n      ANTHROPIC_VERTEX_PROJECT_ID: "{params["project"]}"'
            f'\n      GCE_METADATA_HOST: "{_METADATA_HOST_VALUE}"'
            f'\n      ANTHROPIC_MODEL: "{params["main-model"]}"'
            f'\n      ANTHROPIC_DEFAULT_SONNET_MODEL: "{params["main-model"]}"'
            f'\n      ANTHROPIC_DEFAULT_HAIKU_MODEL: "{params["small-model"]}"'
            '\n      CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: "1"'
            "\n    volumes:"
            "\n      - /opt/polaris/libexec/polaris-splice-credential.py:"
            "/usr/local/libexec/polaris-splice-credential.py:ro"
            "\n    extra_hosts:"
            f'\n      - "{_METADATA_RESPONDER_HOST}:host-gateway"'
            '\n      - "oauth2.googleapis.com:199.36.153.8"'
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
                # Stand up the scoped token responder and block the container from the
                # real metadata server before the guest container starts, so the guest
                # only ever reaches the token endpoint (host.docker.internal), never the
                # host's metadata surface.
                ("metadata-token-responder", "host", _install_metadata_responder(), 60),
                ("metadata-firewall", "host", INSTALL_GCP_METADATA_FIREWALL_SCRIPT, 60),
                ("container-bootstrap", "host", bootstrap, 300),
                ("vertex-shell-env", "host", _vertex_shell_env(params), 30),
                ("splice-watcher", "host", INSTALL_SPLICE_WATCHER_SCRIPT, 60),
            ]
        elif request.phase == "verify":
            scripts = [
                ("directory-firewall-ready", "directory", _DIRECTORY_FIREWALL_VERIFY, 30),
                ("bootstrap-ready", "host", VERIFY_POLARIS_BOOTSTRAP_COMMON, 120),
                # Assert preconfigured-machine-host readiness to the platform
                # canary once the container and services are up (bootstrap-ready
                # above). Model access (vertex-ready) is a separate concern and
                # must not gate participant-host readiness, so write the marker
                # before it.
                ("preconfigured-host-ready", "host", WRITE_PRECONFIGURED_HOST_READY_MARKER, 300),
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
