"""Read online site variables through the official Editor engineering tools."""
import json
import os
import pathlib
import socket
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
EDITOR = pathlib.Path("/opt/arwc-ot-compat/upstream/squashfs-root")
PROJECT = "/opt/arwc-ot-compat/work/arwc-site"


def main():
    if socket.gethostname() != "cinder-arwc-ot-compat-363":
        raise RuntimeError("Run engineering checks on the dedicated VM")
    directory = ROOT / ".operator/site-engineering"
    directory.mkdir(parents=True,exist_ok=True)
    credentials = json.loads((ROOT / ".operator/credentials.json").read_text())
    environment = dict(os.environ,APPDIR=str(EDITOR),OPENPLC_USER="engineer",OPENPLC_PASSWORD=credentials["plc"])
    counter = 0
    def cli(*args):
        nonlocal counter
        counter += 1
        result = subprocess.run([str(EDITOR / "AppRun"),"--cli","debug",*args,"--json"],env=environment,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90)
        (directory / f"step-{counter}.log").write_text(result.stdout)
        if result.returncode:
            raise RuntimeError(f"Editor debug command failed: {args[0]}; inspect VM step-{counter}.log")
        replies = []
        for line in result.stdout.splitlines():
            if line.startswith("{"):
                try:
                    replies.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        if not replies or not replies[-1].get("ok"):
            raise RuntimeError("Editor did not return a successful structured result")
        return replies[-1]
    opened = cli("open",PROJECT,"--host","172.29.63.20","--target","OpenPLC Runtime v4")
    session_id = opened["sessionId"]
    try:
        variables = cli("list-vars","--session",session_id)
        available = variables["variables"]
        names = [v["name"] for v in available]
        wanted = []
        for suffix in ("LevelM","PositionPct","PositionBPct","OutletA.FlowM3s","OutletB.FlowM3s"):
            matches = [n for n in names if n.casefold() == suffix.casefold() or n.casefold().endswith("."+suffix.casefold())]
            if not matches:
                raise AssertionError("Online variable missing: "+suffix)
            wanted.append(min(matches,key=lambda name:name.count(".")))
        values = cli("read",*wanted,"--session",session_id)
        result = {"product":"OpenPLC Editor 4.3.4","project":"arwc-site","online_variables":len(available),"selected":wanted,"read_result":values}
        (directory / "evidence.json").write_text(json.dumps(result,indent=2)+"\n")
        print(json.dumps(result,indent=2))
    finally:
        cli("close","--session",session_id)


if __name__ == "__main__":
    main()
