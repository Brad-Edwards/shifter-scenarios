#!/usr/bin/env python3
"""K18.2 seed: create the OIDC-FIELDKEST-SUPPORT Keycloak client and store its
registration access token as staff_preview_service in runtime-credentials.json.

This runs during range setup (restore-pristine) after Keycloak is healthy.
The staff service reads staff_preview_service as its initial Keycloak DCR token,
enabling the K18.2 note-preview SSRF path to traverse to the identity registration.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
from pathlib import Path
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operator-dir", type=Path, required=True)
    args = parser.parse_args()

    creds_path = args.operator_dir / "range-seed/runtime-credentials.json"
    ca_cert = args.operator_dir / "tls/ca.crt"

    # Load bootstrap values for Keycloak admin credentials (operator material).
    bootstrap = json.loads((args.operator_dir / "native-platform/bootstrap.json").read_text())
    admin_pass = bootstrap["assistant_admin"]  # platform-admin password

    ctx = ssl.create_default_context(cafile=str(ca_cert))
    base = "https://identity.keplerops.test"

    # Get admin token.
    token_req = Request(
        f"{base}/realms/master/protocol/openid-connect/token",
        data=f"client_id=admin-cli&username=platform-admin&password={admin_pass}&grant_type=password".encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(token_req, context=ctx, timeout=15) as r:
        admin_token = json.load(r)["access_token"]

    # Create or find the OIDC-FIELDKEST-SUPPORT client.
    find_req = Request(
        f"{base}/admin/realms/keplerops/clients?clientId=OIDC-FIELDKEST-SUPPORT",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    with urlopen(find_req, context=ctx, timeout=10) as r:
        existing = json.load(r)

    if not existing:
        create_body = json.dumps({
            "clientId": "OIDC-FIELDKEST-SUPPORT",
            "name": "FieldKest Support Registration",
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": False,
            "standardFlowEnabled": True,
            "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": False,
            "redirectUris": ["https://support.keplerops.test/federation/callback"],
            "registrationAccessTokenLifespan": 0,
        }).encode()
        create_req = Request(
            f"{base}/admin/realms/keplerops/clients",
            data=create_body,
            headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
        )
        with urlopen(create_req, context=ctx, timeout=10) as r:
            r.read()

        with urlopen(find_req, context=ctx, timeout=10) as r:
            existing = json.load(r)

    client_id = existing[0]["id"]

    # Generate a fresh registration access token with no expiry.
    rat_req = Request(
        f"{base}/admin/realms/keplerops/clients/{client_id}/registration-access-token",
        data=b"",
        method="POST",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    with urlopen(rat_req, context=ctx, timeout=10) as r:
        rat = json.load(r)["registrationAccessToken"]

    # Write to runtime-credentials.json (operator material updated during setup).
    creds = json.loads(creds_path.read_text())
    creds["credentials"]["staff_preview_service"] = rat
    descriptor = os.open(str(creds_path), os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as f:
        f.write(json.dumps(creds, sort_keys=True, separators=(",", ":")) + "\n")

    print(f"K18.2 seed: OIDC-FIELDKEST-SUPPORT client ready, RAT stored as staff_preview_service.")


if __name__ == "__main__":
    main()
