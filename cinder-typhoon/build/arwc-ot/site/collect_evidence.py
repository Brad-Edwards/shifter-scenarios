"""Publish explicit non-secret controller results after the VM restart check."""
import hashlib
import json
import pathlib
import re
import socket
import subprocess
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent
SLICE = ROOT.parent
OPERATOR = SLICE / ".operator"


def main():
    if socket.gethostname() != "cinder-arwc-ot-compat-363":
        raise RuntimeError("Collect controller evidence on the dedicated VM")
    unit = json.loads((OPERATOR / "controller-tests/evidence.json").read_text())
    summary = re.search(r"(\d+) tests, (\d+) passed, 0 failed",(OPERATOR / "controller-tests/baseline/result.log").read_text())
    assert summary and summary[1] == summary[2]
    unit["tests_passed"] = int(summary[2])
    live = {name:json.loads((OPERATOR / f"site-evidence/{name}.json").read_text())
            for name in ("operating","field-down","field-up","prepare-restart","restart")}
    engineering = json.loads((OPERATOR / "site-engineering/evidence.json").read_text())
    before = (OPERATOR / "vm-boot-before.txt").read_text().strip()
    after = pathlib.Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    assert before != after, "Evidence must follow a real VM stop/start"
    forwarding = subprocess.check_output(["sudo","docker","compose","exec","-T","plc","cat","/proc/sys/net/ipv4/ip_forward"],cwd=SLICE,text=True).strip()
    assert forwarding == "0", "The controller must not route between its two networks"
    program = pathlib.Path("/opt/arwc-ot-compat/work/arwc-site/pous/programs/main.fbd").read_text()
    graph = json.loads(program[program.index("\n{")+1:program.rindex("\nEND_PROGRAM")])
    graph_info = {"blocks":len([n for n in graph["rung"]["nodes"] if n["type"] == "block"]),
                  "connections":len(graph["rung"]["edges"]),"sha256":hashlib.sha256(program.encode()).hexdigest()}
    result = {"scope":"issue-364 two-outlet controller and physical I/O; normal operations", "status":"passed",
        "collected_at":datetime.now(timezone.utc).isoformat(),"project":"prod-mgau4w","vm":socket.gethostname(),
        "graphical_program":graph_info,"native_iec":unit,"physical_response_tests":4,
        "live":live,"official_editor":engineering,
        "vm_restart":{"before_boot_id":before,"after_boot_id":after,"persistent_directory":str(SLICE)},
        "controller_ip_forwarding":False,
        "limits":["virtual physical response","no hard real-time guarantee","participant and integrated utility acceptance remain downstream"]}
    destination = ROOT / "evidence/qualification.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(result,indent=2)+"\n")
    print("Collected non-secret controller qualification: "+str(destination))


if __name__ == "__main__":
    main()
