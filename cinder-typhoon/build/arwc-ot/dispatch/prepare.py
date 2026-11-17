"""Prepare the fixed dispatcher role, native client identity, and broker policy."""
import datetime as dt
import json
import os
import pathlib
import shutil
import sys

import psycopg
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from prepare_services import write

ROOT = pathlib.Path("/slice")
PRIVATE = ROOT / ".operator"


def client_identity():
    pki = PRIVATE / "dispatcher-pki"
    pki.mkdir(exist_ok=True)
    if not ((pki / "client-key.pem").exists() and (pki / "client-cert.pem").exists()):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = dt.datetime.now(dt.timezone.utc)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Cairn Reach dispatcher")])
        certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now-dt.timedelta(minutes=1))
            .not_valid_after(now+dt.timedelta(days=30))
            .add_extension(x509.SubjectAlternativeName([x509.UniformResourceIdentifier("urn:arwc:dispatcher"), x509.DNSName("dispatcher")]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
            .sign(key, hashes.SHA256()))
        (pki / "client-key.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        (pki / "client-cert.pem").write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    shutil.copyfile(PRIVATE / "server-cert.pem", pki / "server-cert.pem")
    shutil.copyfile(PRIVATE / "mosquitto/ca.pem", pki / "ca.pem")
    os.chown(pki, 65532, 65532)
    pki.chmod(0o700)
    for path in pki.iterdir():
        os.chown(path, 65532, 65532)
        path.chmod(0o600)


def main():
    credentials = json.loads((PRIVATE / "credentials.json").read_text())
    with psycopg.connect(host="postgres", dbname="historian", user="historian", password=credentials["postgres"], autocommit=True) as db:
        db.execute((ROOT / "dispatch/schema.sql").read_text())
    client_identity()
    write(PRIVATE / "dispatcher.env", "PGUSER=dispatcher\nPGPASSWORD=" + credentials["pg_dispatcher"]
          + "\nUA_PASSWORD=" + credentials["ua_dispatcher"] + "\nMQTT_PASSWORD=" + credentials["mqtt_dispatcher"] + "\n")
    broker = PRIVATE / "mosquitto/mosquitto.conf"
    text = broker.read_text()
    setting = "retain_available false"
    if setting not in text.splitlines():
        if any(line.strip().startswith("retain_available ") for line in text.splitlines()):
            raise ValueError("Existing retained-message policy needs explicit reconciliation")
        write(broker, text.rstrip() + "\n" + setting + "\n", 0o644)
    print("Prepared the fixed dispatcher journal, private client identity, and native no-retain broker setting.")


if __name__ == "__main__":
    main()
