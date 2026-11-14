"""Check native Compose networking against the operating integration contract."""
import copy
import json
import os
import pathlib
import socket
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
IT = pathlib.Path("/opt/arwc-ot-compat/it/cinder-typhoon/build/arwc")


def validate(ot, it, contract, initial):
    for name in ("plc", "engineering"):
        assert ot["services"][name] == initial["services"][name]
    logging = contract["capacity"]["container_logging"]
    for document in (ot, it):
        for service in document["services"].values():
            assert service["logging"]["driver"] == logging["driver"]
            assert service["logging"]["options"] == {
                "max-size": logging["max_size"], "max-file": logging["max_file"]}
    exchange = contract["exchange"]
    network = ot["networks"]["history_exchange"]
    assert network["internal"]
    assert network["ipam"]["config"][0]["subnet"] == exchange["network"]
    assert it["networks"]["history_exchange"]["external"]
    assert it["networks"]["history_exchange"]["name"] == network["name"]
    for name, document in (("postgres", ot), ("a-data-bridge", it)):
        service = document["services"][name]
        assert str(service["sysctls"]["net.ipv4.ip_forward"]) == "0"
        assert service["networks"]["history_exchange"]["ipv4_address"] == exchange["members"][name]
    assert not ot["services"]["postgres"].get("ports")
    assert set(ot["services"]["postgres"]["networks"]) == {"supervisory", "history_exchange"}
    assert set(it["services"]["a-data-bridge"]["networks"]) == {"dmz", "engineering", "history_exchange"}
    assert all("history_exchange" not in service["networks"] for name, service in ot["services"].items() if name != "postgres")
    assert all("history_exchange" not in service["networks"] for name, service in it["services"].items() if name != "a-data-bridge")


def main():
    if socket.gethostname() != "cinder-arwc-ot-compat-363":
        raise SystemExit("Use the approved development VM")
    environment = dict(os.environ, ARWC_OT_OPERATOR_DIR=str(ROOT / ".operator"), ARWC_CARRIER_ADDRESS="10.77.59.6")

    def model(files, cwd):
        args = ["sudo", "--preserve-env=ARWC_OT_OPERATOR_DIR,ARWC_CARRIER_ADDRESS", "docker", "compose"]
        for path in files:
            args += ["-f", str(path)]
        result = subprocess.run(args+["config", "--format", "json"], cwd=cwd, env=environment,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return json.loads(result.stdout)

    ot = model(["compose.yaml", "site/compose.yaml", "historian/compose.yaml", "dispatch/compose.yaml",
                "workstation/compose.yaml", "integration/compose.yaml"], ROOT)
    it = model([IT / "compose.yaml", ROOT / "integration/it-compose.yaml"], IT)
    initial = model(["compose.yaml", "site/compose.yaml", "workstation/compose.yaml"], ROOT)
    contract = json.loads((ROOT / "integration/contract.json").read_text())
    validate(ot, it, contract, initial)
    mutations = [
        lambda o, i: o["services"]["engineering"].update(command=["unexpected-replacement"]),
        lambda o, i: o["services"]["plc"].pop("logging"),
        lambda o, i: i["services"]["a-data-bridge"]["logging"]["options"].update({"max-file": "0"}),
        lambda o, i: o["networks"]["history_exchange"].update(internal=False),
        lambda o, i: o["services"]["postgres"]["sysctls"].update({"net.ipv4.ip_forward": "1"}),
        lambda o, i: i["services"]["a-data-bridge"]["sysctls"].update({"net.ipv4.ip_forward": "1"}),
        lambda o, i: i["services"]["a-data-bridge"]["networks"].update(supervisory={}),
        lambda o, i: o["services"]["engineering"]["networks"].update(history_exchange={}),
        lambda o, i: o["services"]["postgres"].update(ports=[{"target": 5432, "published": "5432"}]),
    ]
    for mutate in mutations:
        changed_ot, changed_it = copy.deepcopy(ot), copy.deepcopy(it)
        mutate(changed_ot, changed_it)
        try:
            validate(changed_ot, changed_it, contract, initial)
        except (AssertionError, KeyError):
            continue
        raise RuntimeError("An integration networking mutation escaped the preflight")
    print(json.dumps({"native_compose_contract": "passed", "network_mutations_detected": len(mutations)-3,
                      "log_rotation_mutations_detected": 2, "lifecycle_mutations_detected": 1}))


if __name__ == "__main__":
    main()
