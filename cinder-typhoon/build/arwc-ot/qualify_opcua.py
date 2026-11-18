"""Focused normal-operation checks against the real native OPC UA endpoint."""
import asyncio
import json
import pathlib
from datetime import datetime, timedelta, timezone

from asyncua import Client, ua
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

OPERATOR = pathlib.Path("/slice/.operator")
ENDPOINT = "opc.tcp://plc:4840/arwc"
APPLICATION_URI = "urn:arwc:compat:client"


def client_certificate() -> None:
    key_path = OPERATOR / "client-key.pem"
    cert_path = OPERATOR / "client-cert.pem"
    if key_path.exists() and cert_path.exists():
        return
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ARWC compatibility client")])
    certificate = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName([x509.UniformResourceIdentifier(APPLICATION_URI), x509.DNSName("tools")]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .sign(key, hashes.SHA256()))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    key_path.chmod(0o640)
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))


async def connect(user: str = "operator") -> Client:
    client_certificate()
    credentials = json.loads((OPERATOR / "credentials.json").read_text())
    client = Client(ENDPOINT, timeout=10)
    client.application_uri = APPLICATION_URI
    await client.set_security_string(
        "Basic256Sha256,SignAndEncrypt," + str(OPERATOR / "client-cert.pem") + "," +
        str(OPERATOR / "client-key.pem") + "," + str(OPERATOR / "server-cert.pem"))
    client.set_user(user)
    client.set_password(credentials[{"operator": "opcua", "dispatcher": "ua_dispatcher", "reader": "ua_reader"}[user]])
    await client.connect()
    return client


async def main() -> None:
    client = await connect()
    try:
        namespace = await client.get_namespace_index("urn:arwc:crr:tags")
        observations = {}
        for name in ("LevelM", "PositionPct", "FlowM3s", "IoHealthy", "RequestedTargetPct", "Owner"):
            value = await client.get_node(ua.NodeId("CRR." + name, namespace)).read_data_value()
            observations[name] = {"value": value.Value.Value, "status": value.StatusCode.name,
                                  "source_timestamp": str(value.SourceTimestamp)}
        endpoints = await client.get_endpoints()
        certificate = x509.load_pem_x509_certificate((OPERATOR / "server-cert.pem").read_bytes())
        uris = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.UniformResourceIdentifier)
        description = {"namespace": namespace, "application_uris": sorted(set(e.Server.ApplicationUri for e in endpoints)),
                       "certificate_uris": uris, "observations": observations}
        print(json.dumps(description, indent=2))
        assert observations["IoHealthy"]["value"] is True, "PLC has no current Modbus I/O"
        assert observations["LevelM"]["value"] == 8.0, "Scaled measurement did not reach native PLC state"
        assert all(e.Server.ApplicationUri in uris for e in endpoints), "Native endpoint/certificate application identity mismatch"
        (OPERATOR / "opcua-evidence.json").write_text(json.dumps(description, indent=2)+"\n")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
