#!/usr/bin/env python3
"""Check product ownership and network boundaries in the native IT design."""
from pathlib import Path
import re
import yaml

ROOT = Path(__file__).resolve().parent


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
    assert len(pins) == 7
    assert all(re.fullmatch(r"[A-Z_]+=[^\s]+@sha256:[a-f0-9]{64}", line) for line in pins)


if __name__ == "__main__":
    validate(yaml.safe_load((ROOT / "compose.yaml").read_text()))
    print("ARWC native IT foundation contract passes")
