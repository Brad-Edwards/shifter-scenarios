"""Image-owned ARWC application initialization; BigRAE owns participant access."""
import argparse
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".operator"
STATE = pathlib.Path("/var/lib/cinder-typhoon/arwc-ot.initialized")
READY = pathlib.Path("/run/shifter/preconfigured-range-host.ready")
DESKTOP = "cinder-arwc-ot-engineering"
BASE = ["compose.yaml", "site/compose.yaml", "workstation/compose.yaml"]
JOINED = BASE + ["historian/compose.yaml", "dispatch/compose.yaml", "integration/compose.yaml"]
sys.path.insert(0, str(ROOT))
from project_config import operator_credentials


def run(*args, environment=None):
    with (PRIVATE / "first-boot.log").open("a") as log:
        return subprocess.run(list(args), cwd=ROOT, env=environment,
            stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)


def compose(*args, joined=False):
    files = JOINED if joined else BASE
    command = ["docker", "compose"]
    for file in files:
        command += ["-f", str(ROOT / file)]
    if args[0] in ("up", "run"):
        args = (args[0], "--pull", "never", *args[1:])
    return run(*command, *args)


def tools(script, *args):
    compose("run", "--rm", "-T", "tools", "python", "/slice/" + script, *args)


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wait_for(*command, seconds=60):
    deadline = time.monotonic() + seconds
    while True:
        try:
            run(*command)
            return
        except subprocess.CalledProcessError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)


def verify_images():
    inventory = json.loads((ROOT / "image/runtime-inventory.json").read_text())
    if inventory["schema"] != "arwc.cached-images/v1" or not inventory["images"]:
        raise ValueError("Missing qualified image inventory")
    for tag, expected in inventory["images"].items():
        actual = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", tag], text=True).strip()
        if actual != expected:
            raise ValueError("Cached image differs from the qualified inventory: " + tag)


def start_desktop():
    operator_credentials(ROOT)
    verify_images()
    run("bash", str(ROOT / "workstation/prepare-handover.sh"))
    compose("up", "-d", "--no-build", "engineering")


def install_project(credentials):
    project = PRIVATE / "projects/arwc-site"
    if not (project / "project.json").exists():
        project.parent.mkdir(mode=0o700, exist_ok=True)
        cache = "/home/fieldlink/.cache/arwc-scaffold"
        run("docker", "exec", "--user", "fieldlink", DESKTOP, "mkdir", "-p", cache)
        scaffold = subprocess.run(["docker", "exec", DESKTOP, "test", "-f", cache + "/arwc-site/project.json"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if scaffold.returncode:
            run("docker", "exec", "--user", "fieldlink", "--env", "HOME=/home/fieldlink", DESKTOP, "openplc-editor", "--cli",
                "create", "arwc-site", "--path", cache, "--language", "fbd", "--time", "T#100ms")
        run("docker", "cp", DESKTOP + ":" + cache + "/arwc-site", str(project))
    load_module("arwc_site_project", "site/generate_project.py").generate(project)
    # This path is image-owned and first initialization has no participant edits.
    run("docker", "exec", DESKTOP, "rm", "-rf", "--", "/home/fieldlink/CairnReach/controller")
    run("docker", "cp", str(project), DESKTOP + ":/home/fieldlink/CairnReach/controller")
    run("docker", "exec", DESKTOP, "chown", "-R", "2500:2500", "/home/fieldlink/CairnReach")
    environment = dict(os.environ, OPENPLC_USER="engineer", OPENPLC_PASSWORD=credentials["plc"])
    wait_for("docker", "exec", "arwc-ot-compat-postgres-1", "pg_isready", "-U", "historian", "-d", "historian")
    wait_for("docker", "exec", "--user", "fieldlink", DESKTOP, "python", "-c",
        "import socket; socket.create_connection(('plc',8443),2).close()")
    # Pass environment names, never password values, in the Docker command line.
    run("docker", "exec", "--user", "fieldlink", "--env", "HOME=/home/fieldlink", "--env", "OPENPLC_USER", "--env", "OPENPLC_PASSWORD",
        DESKTOP, "openplc-editor", "--cli", "upload", "/home/fieldlink/CairnReach/controller",
        "--target", "OpenPLC Runtime v4", "--host", "172.29.63.20", "--create-user", "--yes",
        environment=environment)
    certificate = "/workdir/core/src/drivers/plugins/python/opcua/certs/server_cert.pem"
    wait_for("docker", "exec", "arwc-ot-compat-plc-1", "test", "-s", certificate)
    run("docker", "cp", "arwc-ot-compat-plc-1:" + certificate, str(PRIVATE / "server-cert.pem"))
    return project


def initialize():
    credentials = operator_credentials(ROOT)
    (PRIVATE / "site-io").mkdir(exist_ok=True)
    compose("up", "-d", "--no-build", "plc", "io", "postgres", "fuxa")
    project = install_project(credentials)
    tools("prepare_services.py")
    tools("configure_fuxa.py")
    compose("restart", "fuxa")
    tools("hmi/import_project.py")
    compose("restart", "fuxa")
    compose("up", "-d", "--no-build", "grafana")
    # Use the native public health endpoint, with a bounded startup retry.
    tools("image/wait_grafana.py")
    tools("historian/prepare.py")
    tools("dispatch/prepare.py")
    tools("integration/prepare.py")
    compose("run", "--rm", "-T", "history-maintenance", "python", "/slice/historian/maintain.py", "--once", joined=True)
    password_file = PRIVATE / "mosquitto/passwords"
    if not password_file.read_text().startswith("operator:$7$"):
        broker = "eclipse-mosquitto:2.0.22@sha256:81a6193ae693942a3231cd3ac52875b02b7e3a19da671b2fb4b55cc874c5b279"
        run("docker", "run", "--rm", "--entrypoint", "mosquitto_passwd", "--mount",
            "type=bind,src=" + str(PRIVATE / "mosquitto") + ",dst=/mosquitto/config",
            broker, "-U", "/mosquitto/config/passwords")
    compose("up", "-d", "--no-build", joined=True)
    compose("restart", "grafana", joined=True)
    load_module("arwc_workstation", "workstation/provision.py").seed_connections(project)


def start_it():
    it = ROOT.parent / "arwc"
    environment = dict(os.environ, ARWC_OT_OPERATOR_DIR=str(PRIVATE), ARWC_CARRIER_ADDRESS="0.0.0.0")
    run("docker", "compose", "-f", str(it / "compose.yaml"), "-f", str(ROOT / "integration/it-compose.yaml"),
        "up", "--pull", "never", "-d", "--no-build", environment=environment)


def readiness():
    contract = json.loads((ROOT / "workstation/contract.json").read_text())["participant_readiness"]
    wait_for("docker", "exec", "--user", "fieldlink", DESKTOP,
        "/usr/local/libexec/shifter-participant-readiness", "--contract", contract["contract"],
        "--manifest-sha256", contract["manifest_sha256"])


def complete():
    run("bash", str(ROOT / "workstation/prepare-handover.sh"))
    if STATE.exists():
        compose("up", "-d", "--no-build", joined=True)
    else:
        initialize()
    start_it()
    readiness()
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.touch()
    READY.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    READY.parent.chmod(0o755)
    READY.touch(mode=0o644)
    READY.chmod(0o644)
    print("ARWC applications initialized; native participant readiness passed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["desktop", "complete", "verify"])
    args = parser.parse_args()
    if os.geteuid() != 0 or ROOT != pathlib.Path("/opt/cinder-typhoon/build/arwc-ot"):
        raise SystemExit("Use only the installed private image")
    if pathlib.Path("/etc/cinder-arwc-ot-image").read_text().strip() != "arwc.private-ot-image/v1":
        raise SystemExit("Missing private image installation contract")
    os.umask(0o077)
    if args.phase == "verify":
        if not STATE.exists():
            raise SystemExit("ARWC application initialization is incomplete")
        verify_images()
        readiness()
        return
    start_desktop()
    if args.phase == "complete":
        complete()


if __name__ == "__main__":
    main()
