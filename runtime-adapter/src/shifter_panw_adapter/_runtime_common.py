"""Guest-action building blocks shared by the runtime plugin's plans."""

from __future__ import annotations

import re

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
_GCP_DNS_ANCHOR = '      DC01_IP: "$DC_IP"\n'
_GCP_DNS_FORWARDER = '      DNS_FORWARDER: "169.254.169.254"\n'
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


def _render(script: str, context: dict[str, str]) -> str:
    return re.sub(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}", lambda match: context[match[1]], script)
