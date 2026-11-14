"""Prepare native TLS, SQL permissions, and isolated bridge connection files."""
import datetime as dt
import json
import os
import pathlib
import secrets
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


def prepare_files(password: str) -> None:
    bridge = PRIVATE / "integration-bridge"
    pki = PRIVATE / "integration-pg"
    bridge.mkdir(exist_ok=True, mode=0o700)
    pki.mkdir(exist_ok=True, mode=0o755)
    identity = bridge / "operating-reader.json"
    if not identity.exists():
        write(identity, json.dumps({"username": "operating-reader", "password": secrets.token_urlsafe(24)})+"\n")
    if not (pki / "server-key.pem").exists():
        now = dt.datetime.now(dt.timezone.utc)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "historian-exchange")])
        certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-dt.timedelta(minutes=1)).not_valid_after(now+dt.timedelta(days=30))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("historian-exchange")]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(key, hashes.SHA256()))
        write(pki / "server-key.pem", key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode())
        write(pki / "server.pem", certificate.public_bytes(serialization.Encoding.PEM).decode(), 0o644)
    os.chown(pki / "server-key.pem", 999, 999)
    write(bridge / "history-ca.pem", (pki / "server.pem").read_text(), 0o644)
    write(pki / "pg_hba.conf", """local all all trust
hostssl historian dmz_reader 172.29.62.3/32 scram-sha-256
host all all 172.29.62.0/29 reject
host all all 172.29.63.0/24 scram-sha-256
host all all 0.0.0.0/0 reject
host all all ::/0 reject
""", 0o644)
    write(bridge / "pg-service.conf", """[arwc-operating-history]
host=historian-exchange
port=5432
dbname=historian
user=dmz_reader
sslmode=verify-full
sslrootcert=/tmp/ot-history-ca.pem
""")
    escaped = password.replace("\\", "\\\\").replace(":", "\\:")
    write(bridge / "pgpass", "historian-exchange:5432:historian:dmz_reader:" + escaped + "\n")


def main():
    credentials = json.loads((PRIVATE / "credentials.json").read_text())
    history = json.loads((PRIVATE / "history-credentials.json").read_text())
    with psycopg.connect(host="postgres", dbname="historian", user="historian",
                         password=credentials["postgres"], autocommit=True) as db:
        db.execute((ROOT / "integration/views.sql").read_text())
    prepare_files(history["dmz_reader"])
    print("Prepared the selected historian view, native TLS, and private read-only bridge identity.")


if __name__ == "__main__":
    main()
