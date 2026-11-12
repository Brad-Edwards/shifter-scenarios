"""Compile and open the official Editor with networking disabled on the VM."""
import json
import os
import pathlib
import pwd
import signal
import socket
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
EDITOR = pathlib.Path("/opt/arwc-ot-compat/upstream/squashfs-root")
PROJECT = "/opt/arwc-ot-compat/work/arwc-compat"


def gui() -> None:
    with open("/tmp/arwc-ot-editor-ui.log", "w") as log:
        process = subprocess.Popen([str(EDITOR / "AppRun"), "--disable-gpu", PROJECT], env=dict(os.environ, APPDIR=str(EDITOR)), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 35
            while time.monotonic() < deadline:
                tree = subprocess.check_output(["xwininfo", "-root", "-tree"], text=True)
                if '"OpenPLC Editor"' in tree:
                    print("Official OpenPLC Editor window opened with networking disabled.")
                    return
                if process.poll() is not None:
                    raise RuntimeError("Editor exited before its window opened; inspect VM UI log")
                time.sleep(1)
            raise TimeoutError("Editor window did not open")
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)


def main() -> None:
    if socket.gethostname() != "cinder-arwc-ot-compat-363":
        raise RuntimeError("Run only on the dedicated compatibility VM")
    if "--gui" in sys.argv:
        gui()
        return
    user = pwd.getpwuid(os.getuid()).pw_name
    prefix = ["sudo", "unshare", "--net", "runuser", "-u", user, "--"]
    with open("/tmp/arwc-ot-offline-compile.log", "w") as log:
        subprocess.run(prefix + ["env", "APPDIR="+str(EDITOR), str(EDITOR / "AppRun"), "--cli", "compile", PROJECT, "--target", "OpenPLC Runtime v4"], stdout=log, stderr=subprocess.STDOUT, check=True)
    subprocess.run(prefix + ["xvfb-run", "-a", sys.executable, str(ROOT / "qualify_editor.py"), "--gui"], check=True)
    result = {"product": "OpenPLC Editor", "version": "4.3.4", "network": "separate namespace without interfaces/routes", "compile": "passed", "gui_window": "opened", "external_account": "not required"}
    (ROOT / ".operator/editor-evidence.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
