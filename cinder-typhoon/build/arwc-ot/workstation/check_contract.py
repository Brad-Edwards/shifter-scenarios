"""Check the native Compose model against the desktop's isolation contract."""
import copy
import hashlib
import json
import pathlib
import socket
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
HERE = ROOT / "workstation"


def validate(document, contract):
    service = document["services"]["engineering"]
    assert service["image"] == contract["image"]
    assert set(service["networks"]) == set(contract["networks"])
    assert not service.get("privileged", False)
    assert service.get("network_mode") != "host"
    assert service.get("ipc") != "host"
    assert not service.get("cap_add")
    assert "NET_RAW" in service["cap_drop"]
    assert any(option.startswith("no-new-privileges") for option in service["security_opt"])
    assert all(volume["type"] == "volume" and volume["target"] == "/home/fieldlink" for volume in service["volumes"])
    assert any(int(port["target"]) == contract["rdp_port"] for port in service["ports"])
    assert (HERE / "Dockerfile").read_text().splitlines()[0] == "FROM " + contract["base"]
    assert "--no-sandbox" not in (HERE / "launch-editor.sh").read_text()
    assert "--disable-setuid-sandbox" in (HERE / "launch-editor.sh").read_text()
    assert hashlib.sha256((HERE / "participant-readiness.json").read_bytes()).hexdigest() == contract["participant_readiness"]["manifest_sha256"]
    assert hashlib.sha256((HERE / "browser-seccomp.json").read_bytes()).hexdigest() == contract["browser_sandbox_profile"]["sha256"]


def main():
    if socket.gethostname() != "cinder-arwc-ot-compat-363":
        raise SystemExit("Check the native model on the approved development VM")
    result = subprocess.run(["sudo", "docker", "compose", "-f", "compose.yaml", "-f", "site/compose.yaml",
        "-f", "workstation/compose.yaml", "config", "--format", "json", "engineering"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    document = json.loads(result.stdout)
    contract = json.loads((HERE / "contract.json").read_text())
    validate(document, contract)
    mutations = [
        lambda s: s.update(privileged=True),
        lambda s: s.update(network_mode="host"),
        lambda s: s.update(ipc="host"),
        lambda s: s["networks"].update(field={}),
        lambda s: s.update(cap_add=["SYS_ADMIN"]),
        lambda s: s["volumes"].append({"type": "bind", "source": "/var/run/docker.sock", "target": "/var/run/docker.sock"}),
    ]
    for mutate in mutations:
        changed = copy.deepcopy(document)
        mutate(changed["services"]["engineering"])
        try:
            validate(changed, contract)
        except AssertionError:
            continue
        raise RuntimeError("A desktop isolation mutation escaped the preflight")
    print(json.dumps({"native_compose_contract": "passed", "isolation_mutations_detected": len(mutations),
        "sandbox_profile": contract["browser_sandbox_profile"]["sha256"]}))


if __name__ == "__main__":
    main()
