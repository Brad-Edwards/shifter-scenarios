#!/usr/bin/env python3
"""Check product ownership and network boundaries in the native IT design."""
from pathlib import Path
import re
import yaml

ROOT = Path(__file__).resolve().parent


def load_compose() -> dict:
    document = yaml.safe_load((ROOT / "compose.yaml").read_text())
    corporate = yaml.safe_load((ROOT / "corporate.compose.yaml").read_text())
    assert not (document["services"].keys() & corporate["services"].keys())
    document["services"].update(corporate["services"])
    return document


def validate(document: dict) -> None:
    services = document["services"]
    assert document["name"] == "cinder-arwc-native"
    assert document["networks"]["data"]["internal"] is True
    for name, service in services.items():
        assert not service.get("ports"), f"{name}: unexpected host port"
        assert "control" not in service.get("networks", {}), name
        assert "field" not in service.get("networks", {}), name
        if name not in ("dns", "edge"):
            assert "supervisory" not in service.get("networks", {}), name
        assert str(service["sysctls"]["net.ipv4.ip_forward"]) == "0", name
    assert services["keycloak"]["image"].startswith("${KEYCLOAK_IMAGE")
    assert services["backend"]["image"].startswith("${ERPNEXT_IMAGE")
    assert "recursion no;" in (ROOT / "named.conf").read_text()
    assert "proxy_pass $identity;" in (ROOT / "nginx.conf").read_text()
    assert "proxy_pass $erp;" in (ROOT / "nginx.conf").read_text()
    pins = (ROOT / "images.env").read_text().splitlines()
    assert len(pins) >= 7
    assert all(re.fullmatch(r"[A-Z_]+=[^\s]+@sha256:[a-f0-9]{64}", line) for line in pins)


def validate_dmz(document: dict) -> None:
    services = document["services"]
    legacy = yaml.safe_load((ROOT.parent / "compose.yaml").read_text())
    legacy_addresses = {
        settings["ipv4_address"]
        for service in legacy["services"].values()
        for settings in (service.get("networks", {}) or {}).values()
        if isinstance(settings, dict) and "ipv4_address" in settings
    }
    for name, service in services.items():
        for settings in (service.get("networks", {}) or {}).values():
            if isinstance(settings, dict) and "ipv4_address" in settings:
                assert settings["ipv4_address"] not in legacy_addresses, f"{name}: legacy address collision"
    expected = {
        "dmz-edge": {"dmz", "portal_exchange", "render_exchange", "api_exchange"},
        "renderer": {"render_exchange"},
        "postgrest": {"api_exchange", "api_database"},
    }
    for name, networks in expected.items():
        service = services[name]
        assert set(service["networks"]) == networks, name
        assert str(service["sysctls"]["net.ipv4.ip_forward"]) == "0", name
        assert not service.get("ports"), name
        assert not service.get("privileged"), name
    assert set(services["frontend"]["networks"]) == {"portal_exchange"}
    assert set(services["corporate-db"]["networks"]) == {"api_database"}
    assert services["postgrest"]["environment"]["PGRST_DB_SCHEMAS"] == "dmz_api"
    assert services["postgrest"]["environment"]["PGRST_DB_ANON_ROLE"] == "dmz_reader"
    for name in ("portal_exchange", "render_exchange", "api_exchange", "api_database"):
        assert document["networks"][name]["internal"] is True
    allowed = {"@", "IN", "ns", "suppliers", "render", "read-data"}
    for line in (ROOT / "db.arwc-dmz.test").read_text().splitlines():
        if line and not line.startswith("$"):
            assert line.split()[0] in allowed, "Unapproved DMZ DNS host"


if __name__ == "__main__":
    validate(load_compose())
    validate_dmz(yaml.safe_load((ROOT / "dmz.compose.yaml").read_text()))
    print("ARWC native IT foundation contract passes")
