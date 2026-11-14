#!/usr/bin/env python3
"""Create private bootstrap material for the native IT products."""
import json
import hashlib
import hmac
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parent
OPERATOR = ROOT / ".operator"


def write_private(path: Path, value: str, *, mode: int = 0o600) -> None:
    path.write_text(value, encoding="utf-8")
    path.chmod(mode)


def prepare() -> None:
    os.umask(0o077)
    OPERATOR.mkdir(mode=0o700, exist_ok=True)
    seed_path = OPERATOR / "bootstrap.json"
    if seed_path.exists():
        seed = json.loads(seed_path.read_text(encoding="utf-8"))
    else:
        seed = {}
    for name in (
        "identity_db", "identity_admin", "mariadb_root", "erp_admin", "workforce", "ca", "kerberos",
        "corporate_db", "metabase_db", "planning_reader", "documents_db_root",
        "documents_db", "documents_admin", "metabase_admin", "engineering_admin",
        "postgrest",
    ):
        seed.setdefault(name, secrets.token_hex(24))
    write_private(seed_path, json.dumps(seed))
    write_private(OPERATOR / "identity_db_password", seed["identity_db"])
    write_private(OPERATOR / "mariadb_root_password", seed["mariadb_root"])
    write_private(OPERATOR / "kerberos_master", seed["kerberos"])
    write_private(OPERATOR / "workforce_password", seed["workforce"])
    write_private(OPERATOR / "postgrest_password", seed["postgrest"])
    write_private(OPERATOR / "postgrest.env", (
        f'PGRST_DB_URI=postgresql://pgrst_authenticator:{seed["postgrest"]}@172.29.70.2:5432/planning\n'
    ))
    for name in ("corporate_db", "metabase_db", "planning_reader", "documents_db_root",
                 "documents_db", "documents_admin"):
        write_private(OPERATOR / f"{name}_password", seed[name])
    for name in ("metabase_db", "planning_reader", "postgrest"):
        path = OPERATOR / f"{name}_password"
        os.chown(path, 999, 999)
        path.chmod(0o400)
    write_private(OPERATOR / "metabase.env", f'MB_DB_PASS={seed["metabase_db"]}\n')
    write_private(OPERATOR / "documents-seed.env", (
        f'DOCUMENTS_ADMIN_PASSWORD={seed["documents_admin"]}\n'
        f'STAFF_SEED={seed["workforce"]}\n'
    ))
    write_private(OPERATOR / "reports-seed.env", (
        f'METABASE_ADMIN_PASSWORD={seed["metabase_admin"]}\n'
        f'PLANNING_READER_PASSWORD={seed["planning_reader"]}\n'
        f'STAFF_SEED={seed["workforce"]}\n'
    ))
    write_private(OPERATOR / "engineering-seed.env", (
        f'GITEA_ADMIN_PASSWORD={seed["engineering_admin"]}\n'
        'CLARA_PASSWORD=' + hmac.new(seed["workforce"].encode(), b"clara.morivelle@alterrawaterco.com", hashlib.sha256).hexdigest() + '\n'
        'THEO_PASSWORD=' + hmac.new(seed["workforce"].encode(), b"theo.marrivel@alterrawaterco.com", hashlib.sha256).hexdigest() + '\n'
    ))
    write_private(OPERATOR / "keycloak.env", (
        f'KC_DB_PASSWORD={seed["identity_db"]}\n'
        'KC_BOOTSTRAP_ADMIN_USERNAME=platform-admin\n'
        f'KC_BOOTSTRAP_ADMIN_PASSWORD={seed["identity_admin"]}\n'
    ))
    write_private(OPERATOR / "erp-init.env", (
        f'MARIADB_ROOT_PASSWORD={seed["mariadb_root"]}\n'
        f'ERP_ADMIN_PASSWORD={seed["erp_admin"]}\n'
    ))
    write_private(OPERATOR / "erp-seed.env", (
        f'ERP_ADMIN_PASSWORD={seed["erp_admin"]}\n'
        f'ERP_STAFF_SEED={seed["workforce"]}\n'
    ))
    realm = {
        "realm": "arwc", "enabled": True, "displayName": "ARWC Workforce",
        "registrationAllowed": False, "resetPasswordAllowed": False,
        "roles": {"realm": [{"name": name} for name in ("staff", "planning", "maintenance")]},
        "users": [{
            "username": "morgan.reid", "enabled": True,
            "firstName": "Morgan", "lastName": "Reid",
            "email": "morgan.reid@arwc.test", "emailVerified": True,
            "realmRoles": ["staff"],
            "credentials": [{"type": "password", "value": seed["workforce"], "temporary": False}],
        }],
    }
    write_private(OPERATOR / "realm.json", json.dumps(realm), mode=0o644)
    ca = OPERATOR / "ca"
    ca.mkdir(mode=0o755, exist_ok=True)
    (ca / "secrets").mkdir(mode=0o700, exist_ok=True)
    write_private(ca / "secrets/password", seed["ca"])


if __name__ == "__main__":
    prepare()
