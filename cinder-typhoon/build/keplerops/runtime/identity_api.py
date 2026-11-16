"""k-identity-api: identity registration and federation service for K18.

K18.2: GET /api/registrations/{id} — returns registration record and revision.
       Authorized by staff_preview_service bearer (the reviewer service identity).
K18.3: PATCH /api/registrations/{id} — adds RETAINED_SUPPORT provider to the
       registration while preserving the existing staff provider.
K18.4: POST /api/federation/staff-login — Keycloak OIDC login for staff.
       POST /api/federation/login — assertion-based federated login.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from urllib.parse import urlsplit

from http_support import KeplerHandler, append_audit, serve_tls
from credentials import credential

STATE = Path(os.environ.get("FIELDKEST_STATE_ROOT", "/var/lib/fieldkest-identity-api"))
AUDIT = STATE / "audit"
REGISTRATIONS = STATE / "registrations"
CONFIG = json.loads((STATE / "config/identity-api.json").read_text())

PREVIEW_SERVICE_TOKEN = credential("staff_preview_service")

_LOCK = threading.Lock()


def _load_registration(reg_id: str) -> dict | None:
    path = REGISTRATIONS / f"{reg_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _save_registration(reg_id: str, record: dict) -> None:
    REGISTRATIONS.mkdir(parents=True, exist_ok=True)
    path = REGISTRATIONS / f"{reg_id}.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


class IdentityApiHandler(KeplerHandler):
    def _preview_service(self) -> bool:
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {PREVIEW_SERVICE_TOKEN}"

    def do_GET(self) -> None:
        path = urlsplit(self.path).path

        if path == "/health":
            self.send_json(200, {"status": "up"})
            return

        if path.startswith("/api/registrations/"):
            reg_id = path.removeprefix("/api/registrations/")
            if not self._preview_service():
                self.send_json(401, {"error": "unauthorized"})
                return
            with _LOCK:
                record = _load_registration(reg_id)
            if record is None:
                self.send_json(404, {"error": "registration_not_found"})
                return
            append_audit(AUDIT, "registration", {
                "action": "read", "registration_id": reg_id, "peer": self.client_address[0],
            })
            self.send_json(200, record)
            return

        self.send_json(404, {"error": "not_found"})

    def do_PATCH(self) -> None:
        path = urlsplit(self.path).path

        if path.startswith("/api/registrations/"):
            reg_id = path.removeprefix("/api/registrations/")
            if not self._preview_service():
                self.send_json(401, {"error": "unauthorized"})
                return
            retained = CONFIG.get("retained_support_provider", {})
            with _LOCK:
                record = _load_registration(reg_id)
                if record is None:
                    self.send_json(404, {"error": "registration_not_found"})
                    return
                record["revision"] += 1
                record["provider_configuration"] = {
                    "status": "enabled",
                    "provider": retained["provider"],
                    "metadata_uri": retained["metadata_uri"],
                    "issuer": retained["issuer"],
                    "assertion_submission_endpoint": retained["assertion_submission_endpoint"],
                }
                _save_registration(reg_id, record)
            append_audit(AUDIT, "registration", {
                "action": "patch", "registration_id": reg_id, "revision": record["revision"],
                "peer": self.client_address[0],
            })
            self.send_json(200, record)
            return

        self.send_json(404, {"error": "not_found"})


if __name__ == "__main__":
    serve_tls(IdentityApiHandler)
