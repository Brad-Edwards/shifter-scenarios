#!/usr/bin/env python3
"""Generate operational secrets and per-asset TLS bundles outside Terraform."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import secrets
import subprocess
import tarfile
import tempfile
from pathlib import Path


PROJECT = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
SUFFIX = re.compile(r"^[0-9a-f]{6}$")


class SecretSeedError(ValueError):
    """A bounded secret-seeding failure."""


def run(argv: list[str], *, quiet: bool = False) -> None:
    result = subprocess.run(
        argv,
        check=False,
        stdout=subprocess.DEVNULL if quiet else None,
        stderr=subprocess.DEVNULL if quiet else None,
    )
    if result.returncode:
        raise SecretSeedError("secret seed command failed")


def add_version(project: str, secret_id: str, source: Path, *, force: bool = False) -> None:
    existing = subprocess.run(
        ["gcloud", "secrets", "versions", "list", secret_id, "--project", project,
         "--filter=state:ENABLED", "--limit=1", "--format=value(name)"],
        check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    if existing.returncode:
        raise SecretSeedError("unable to inspect secret version")
    if existing.stdout.strip() and not force:
        return
    run(
        ["gcloud", "secrets", "versions", "add", secret_id, "--project", project,
         f"--data-file={source}", "--quiet"],
        quiet=True,
    )


def write_secret(path: Path, size: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(secrets.token_urlsafe(size).encode())
        handle.write(b"\n")


def write_binary_secret(path: Path, size: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(secrets.token_bytes(size))


def certificate_sans(asset: str, participant_ip: str) -> tuple[str, ...]:
    sans = [f"DNS:{asset}.keplerops.lab", "IP:127.0.0.1"]
    if asset == "ad-dc-01":
        sans.extend(("DNS:ad-dc-01.keplerops.test", "DNS:keplerops.test"))
    if asset == "participant-workstation":
        sans.append(f"IP:{participant_ip}")
    return tuple(sans)


def load_inventory(path: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Read asset and evidence-producer identities from the SDL realization."""

    try:
        realization = json.loads(path.read_text(encoding="utf-8"))
        workloads = realization["workloads"]
        evidence_producers = realization["evidence_producers"]
        runtime_secret_ids = realization["runtime_secret_ids"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise SecretSeedError("SDL realization inventory invalid") from error
    if (
        not isinstance(workloads, dict)
        or not workloads
        or not isinstance(evidence_producers, list)
        or not isinstance(runtime_secret_ids, list)
        or any(not isinstance(asset, str) or not asset for asset in workloads)
        or any(
            not isinstance(asset, str) or asset not in workloads
            for asset in evidence_producers
        )
        or any(not isinstance(secret_id, str) for secret_id in runtime_secret_ids)
    ):
        raise SecretSeedError("SDL realization inventory invalid")
    tls_assets = {
        secret_id.removeprefix("tls-")
        for secret_id in runtime_secret_ids
        if secret_id.startswith("tls-")
    }
    if not tls_assets or any(
        not asset or (asset != "ad-dc-01" and asset not in workloads)
        for asset in tls_assets
    ):
        raise SecretSeedError("SDL realization inventory invalid")
    return tuple(sorted(tls_assets)), tuple(sorted(set(evidence_producers)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--suffix", required=True)
    parser.add_argument("--participant-ip", required=True)
    parser.add_argument("--realization", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not PROJECT.fullmatch(args.project) or not SUFFIX.fullmatch(args.suffix):
        raise SecretSeedError("invalid GCP namespace")
    try:
        participant_ip = ipaddress.ip_address(args.participant_ip)
    except ValueError as error:
        raise SecretSeedError("invalid participant address") from error
    if not isinstance(participant_ip, ipaddress.IPv4Address) or not participant_ip.is_global:
        raise SecretSeedError("invalid participant address")
    assets, evidence_producers = load_inventory(args.realization)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)

    simple = {
        "service-token": 48,
        "receipt-signing-key": 64,
        "minio-root-user": 18,
        "minio-root-password": 48,
        "postgres-password": 48,
        "platform-context-token": 48,
        "platform-agent-admin-token": 48,
        "platform-agent-seed-token": 48,
        "platform-isolation-admin-token": 48,
        "edge-registry-admin-token": 48,
        "platform-deployment-token": 48,
        "research-pseudonym-key": 64,
        **{f"producer-token-{asset}": 48 for asset in evidence_producers},
    }
    for name, size in simple.items():
        path = args.output / name
        if not path.exists():
            write_secret(path, size)
        add_version(args.project, f"kep-{name.replace('-', '')}-{args.suffix}", path)

    content_key = args.output / "research-content-key"
    if not content_key.exists():
        write_binary_secret(content_key, 32)
    add_version(
        args.project,
        f"kep-researchcontentkey-{args.suffix}",
        content_key,
    )

    reputation_key = args.output / "reputation-signing-key"
    if not reputation_key.exists():
        run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "ED25519",
                "-out",
                str(reputation_key),
            ],
            quiet=True,
        )
        reputation_key.chmod(0o600)
    add_version(
        args.project,
        f"kep-reputationsigningkey-{args.suffix}",
        reputation_key,
    )

    committed_credentials = {
        "ad-domain-admin-password": "assets/content/credentials/ad-domain-admin-password.txt",
        "ad-federation-bind-password": "assets/content/credentials/ad-federation-bind-password.txt",
        "ad-guardrail-admin-password": "assets/content/credentials/ad-guardrail-admin-password.txt",
        "ad-ml-engineer-password": "assets/content/credentials/ad-ml-engineer-password.txt",
        "ad-qa-password": "assets/content/credentials/ad-qa-password.txt",
        "ad-release-manager-password": "assets/content/credentials/ad-release-manager-password.txt",
        "participant-password": "assets/content/credentials/participant-password.txt",
        "jupyter-token": "assets/content/credentials/notebook-token.txt",
        "keycloak-platform-context-secret": "assets/content/credentials/platform-context-keycloak-secret.txt",
        "gitea-registry-credential": "assets/content/credentials/gitea-registry-credential.txt",
    }
    pack_root = Path(__file__).resolve().parents[2]
    for name, relative in committed_credentials.items():
        destination = args.output / name
        if not destination.exists():
            descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write((pack_root / relative).read_bytes())
        add_version(args.project, f"kep-{name.replace('-', '')}-{args.suffix}", destination)

    tls_schema = "rsa-2048-v4-mtls"
    tls_marker = args.output / "tls-schema"
    tls_rotated = not tls_marker.exists() or tls_marker.read_text(encoding="utf-8").strip() != tls_schema
    if tls_rotated:
        for path in (
            args.output / "ca.key",
            args.output / "ca.crt",
            args.output / "ca.srl",
            *args.output.glob("tls-*.tar"),
        ):
            path.unlink(missing_ok=True)
        tls_marker.write_text(tls_schema + "\n", encoding="utf-8")
        tls_marker.chmod(0o600)

    ca_key = args.output / "ca.key"
    ca_cert = args.output / "ca.crt"
    if not ca_key.exists():
        run([
            "openssl", "genpkey", "-algorithm", "RSA",
            "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(ca_key),
        ], quiet=True)
        ca_key.chmod(0o600)
        run([
            "openssl", "req", "-new", "-x509", "-key", str(ca_key),
            "-out", str(ca_cert), "-days", "7", "-subj", "/CN=KeplerOps range CA",
            "-addext", "basicConstraints=critical,CA:TRUE",
            "-addext", "keyUsage=critical,keyCertSign,cRLSign",
        ], quiet=True)
        ca_cert.chmod(0o600)

    for asset in assets:
        bundle = args.output / f"tls-{asset}.tar"
        if not bundle.exists():
            with tempfile.TemporaryDirectory(prefix="tls-", dir=args.output) as temp_dir:
                temp = Path(temp_dir)
                key = temp / "tls.key"
                csr = temp / "tls.csr"
                cert = temp / "tls.crt"
                config = temp / "san.cnf"
                config.write_text(
                    "[req]\ndistinguished_name=dn\n[dn]\n[ext]\n"
                    "basicConstraints=critical,CA:FALSE\n"
                    "keyUsage=critical,digitalSignature,keyEncipherment\n"
                    "extendedKeyUsage=serverAuth,clientAuth\n"
                    f"subjectAltName={','.join(certificate_sans(asset, args.participant_ip))}\n",
                    encoding="utf-8",
                )
                run([
                    "openssl", "genpkey", "-algorithm", "RSA",
                    "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(key),
                ], quiet=True)
                run(["openssl", "req", "-new", "-key", str(key), "-out", str(csr), "-subj", f"/CN={asset}.keplerops.lab"], quiet=True)
                run([
                    "openssl", "x509", "-req", "-in", str(csr), "-CA", str(ca_cert),
                    "-CAkey", str(ca_key), "-CAcreateserial", "-out", str(cert),
                    "-days", "7", "-extfile", str(config), "-extensions", "ext",
                ], quiet=True)
                pfx = temp / "tls.pfx"
                if asset == "ad-dc-01":
                    run([
                        "openssl", "pkcs12", "-export",
                        "-inkey", str(key),
                        "-in", str(cert),
                        "-certfile", str(ca_cert),
                        "-out", str(pfx),
                        "-passout", f"file:{args.output / 'ad-domain-admin-password'}",
                    ], quiet=True)
                with tarfile.open(bundle, "w") as archive:
                    archive.add(key, arcname="tls.key")
                    archive.add(cert, arcname="tls.crt")
                    # MinIO follows the public.crt/private.key naming convention.
                    archive.add(key, arcname="private.key")
                    archive.add(cert, arcname="public.crt")
                    archive.add(ca_cert, arcname="ca.crt")
                    if asset == "ad-dc-01":
                        archive.add(pfx, arcname="tls.pfx")
                bundle.chmod(0o600)
        add_version(
            args.project,
            f"kep-tls{asset.replace('-', '')}-{args.suffix}",
            bundle,
            force=tls_rotated,
        )
    print(f"seeded {len(simple) + len(assets) + len(committed_credentials)} secret bindings")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SecretSeedError as error:
        print(f"error: {error}")
        raise SystemExit(2) from None
