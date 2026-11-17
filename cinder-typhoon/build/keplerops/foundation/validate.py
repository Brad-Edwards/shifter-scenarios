#!/usr/bin/env python3
"""Validate the code-checkable FieldLink foundation contract."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(pack_root: Path, compose_path: Path, named_conf_path: Path) -> None:
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = compose["services"]
    required = {"fieldlink-dns", "fieldlink-edge", "fieldlink-postgres"}
    require(required <= services.keys(), "foundation services are incomplete")

    for name in required:
        require("ports" not in services[name], f"{name} publishes a host port")
        require(services[name].get("restart") == "unless-stopped", f"{name} restart policy")

    for name in ("fieldlink-dns", "fieldlink-edge"):
        require(
            services[name].get("sysctls", {}).get("net.ipv4.ip_forward") == 0,
            f"{name} can forward between networks",
        )

    for name in ("fieldlink-edge", "fieldlink-postgres"):
        image = services[name].get("image", "")
        require("@sha256:" in image, f"{name} image is not digest pinned")

    dns_networks = services["fieldlink-dns"]["networks"]
    require(
        set(dns_networks) == {"corporate", "delivery", "cloud", "jobs"},
        "DNS network ownership changed",
    )
    require(
        services["fieldlink-postgres"]["networks"]
        == {"foundation_data": {"ipv4_address": "10.77.56.10"}},
        "PostgreSQL left its private data network",
    )
    require(compose["networks"]["foundation_data"].get("internal") is True, "data network is not internal")
    require("native-postgres-data" in compose["volumes"], "PostgreSQL volume is absent")

    named_conf = named_conf_path.read_text(encoding="utf-8")
    require("recursion no;" in named_conf, "DNS recursion is not disabled")
    require("allow-transfer { none; };" in named_conf, "DNS zone transfer is not disabled")
    require("forwarders" not in named_conf, "DNS has an external forwarder")
    require("recursion yes;" not in named_conf, "DNS recursion is enabled")

    dns_dockerfile = (pack_root / "build/keplerops/foundation/dns.Dockerfile").read_text(encoding="utf-8")
    require("@sha256:" in dns_dockerfile, "DNS base image is not digest pinned")
    require("bind=9.18.44-r0" in dns_dockerfile, "BIND package is not version pinned")

    edge_volumes = services['fieldlink-edge']['volumes']
    require('${KEPLEROPS_OPERATOR_DIR:-./.operator}/tls:/etc/nginx/tls:ro' not in edge_volumes,
            'edge can read infrastructure CA signing material')
    require('./native-workplace/nginx.conf:/etc/nginx/conf.d/default.conf:ro' in edge_volumes,
            'native edge configuration is not mounted')
    enrollment_mounts = [value for value in edge_volumes if '/native-workplace/ca' in value]
    require(set(enrollment_mounts) == {
        '${KEPLEROPS_OPERATOR_DIR:-./.operator}/native-workplace/ca/tls:/etc/nginx/enrollment/tls:ro',
        '${KEPLEROPS_OPERATOR_DIR:-./.operator}/native-workplace/ca/certs/root_ca.crt:/etc/nginx/enrollment/root_ca.crt:ro',
    }, 'edge can read enrollment CA signing material')
    nginx = (pack_root / "build/keplerops/native-workplace/nginx.conf").read_text(encoding="utf-8")
    require("ssl_certificate " in nginx, "Nginx TLS is absent")
    require("location = /health" in nginx, "Nginx health route is absent")
    require('set $identity http://fieldlink-keycloak:8080;' in nginx,
            'native identity upstream is absent')
    require('set $authority https://k-cert:9000;' in nginx,
            'native enrollment upstream is absent')
    require('proxy_ssl_verify on;' in nginx, 'enrollment upstream TLS is not verified')

    relative = "build/keplerops/restore-pristine.sh"
    text = (pack_root / relative).read_text(encoding="utf-8")
    for name in required:
        require(name in text, f"{relative} does not start {name}")
    retired = (pack_root / "build/keplerops/gcp/deploy.sh").read_text(encoding="utf-8")
    require('exit 1' in retired and 'terraform ' not in retired and 'gcloud ' not in retired,
            'retired golden deployment entrypoint can mutate infrastructure')

    operator = (pack_root / "build/keplerops/generate-operator-material.sh").read_text(encoding="utf-8")
    require("native-foundation.env" in operator, "foundation operator seed is absent")
    require("DNS:edge.keplerops.test" in operator, "edge TLS name is absent")

    design = (pack_root / "docs/design/fieldlink-native-foundation.md").read_text(encoding="utf-8")
    for product in ("BIND", "Nginx", "PostgreSQL", "Gitea", "Jenkins", "Keycloak", "K3s"):
        require(product in design, f"product ownership omits {product}")


def main() -> int:
    script = Path(__file__).resolve()
    pack_root = script.parents[3]
    parser = argparse.ArgumentParser()
    parser.add_argument("--compose", type=Path, default=pack_root / "build/keplerops/compose.yaml")
    parser.add_argument("--named-conf", type=Path, default=script.parent / "named.conf")
    args = parser.parse_args()
    try:
        validate(pack_root, args.compose, args.named_conf)
    except (KeyError, OSError, TypeError, ValueError, yaml.YAMLError) as error:
        print(f"FieldLink foundation validation failed: {error}")
        return 1
    print("FieldLink foundation contract is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
