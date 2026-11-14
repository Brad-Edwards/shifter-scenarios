"""Prepare a locked offline desktop bundle manually on the development VM."""
import hashlib
import json
import pathlib
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
import zipfile
from email.parser import Parser

ROOT = pathlib.Path(__file__).resolve().parents[1]
HERE = ROOT / "workstation"
CONTRACT = json.loads((HERE / "contract.json").read_text())
ASSETS = ROOT / ".operator/workstation-assets"
PACKAGES = ["xfce4", "xfce4-terminal", "xrdp", "xorgxrdp", "dbus", "dbus-x11", "firefox-esr", "git", "postgresql-client",
            "mosquitto-clients", "g++", "ca-certificates", "openssl", "libgtk-3-0", "libnss3", "libasound2",
            "libgbm1", "libxss1", "libx11-xcb1", "libdrm2", "libxcb-cursor0", "fonts-dejavu-core",
            "libxkbcommon-x11-0", "libxcb-icccm4", "libxcb-keysyms1", "libxcb-shape0", "libxcb-xkb1"]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    if socket.gethostname() not in ("cinder-arwc-ot-compat-363", "cinder-arwc-dev") or str(ROOT) != "/opt/arwc-ot-compat/slice":
        raise SystemExit("Prepare desktop dependencies only on the approved persistent VM")
    refresh = "--refresh" in sys.argv
    if refresh and ASSETS.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        ASSETS.rename(ASSETS.with_name("workstation-assets.previous-" + stamp))
    ASSETS.mkdir(parents=True, exist_ok=True)
    sums = ASSETS / "SHA256SUMS"
    expected = HERE / "locks/SHA256SUMS"
    if sums.exists():
        subprocess.run(["sha256sum", "--check", "SHA256SUMS"], cwd=ASSETS, check=True, stdout=subprocess.DEVNULL)
        if expected.exists() and not refresh and sums.read_bytes() != expected.read_bytes():
            raise RuntimeError("Offline dependency bundle differs from the reviewed lock")
        print("Existing pinned offline desktop bundle verified.")
        return
    script = '''set -eu
rm -f /etc/apt/apt.conf.d/docker-clean
apt-get update
apt-get install --download-only --no-install-recommends -y ''' + " ".join(PACKAGES) + '''
mkdir -p /bundle/debs /bundle/wheels
cp /var/cache/apt/archives/*.deb /bundle/debs/
python -m pip download --only-binary=:all: --dest /bundle/wheels opcua-client==1.0.2
'''
    log = ROOT / ".operator/workstation-download.log"
    with log.open("w") as output:
        subprocess.run(["sudo", "docker", "run", "--rm", "--cpus=1", "--memory=2g", "--platform=linux/amd64",
            "--mount", f"type=bind,src={ASSETS},dst=/bundle", CONTRACT["base"], "bash", "-euc", script],
            check=True, stdout=output, stderr=subprocess.STDOUT)
    editor = pathlib.Path("/opt/arwc-ot-compat/upstream/OpenPLC.Editor-4.3.4.AppImage")
    if digest(editor) != CONTRACT["editor"]["sha256"]:
        raise RuntimeError("Official Editor archive digest mismatch")
    shutil.copyfile(editor, ASSETS / "editor.AppImage")
    lock = []
    for wheel in sorted((ASSETS / "wheels").glob("*.whl")):
        with zipfile.ZipFile(wheel) as archive:
            metadata = [p for p in archive.namelist() if p.endswith(".dist-info/METADATA")]
            if len(metadata) != 1:
                raise RuntimeError("Unexpected wheel metadata layout")
            info = Parser().parsestr(archive.read(metadata[0]).decode())
        lock.append(f"{info['Name']}=={info['Version']} --hash=sha256:{digest(wheel)}")
    (ASSETS / "requirements.lock").write_text("\n".join(lock)+"\n")
    files = sorted(p for p in ASSETS.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    sums.write_text("".join(f"{digest(p)}  {p.relative_to(ASSETS)}\n" for p in files))
    if expected.exists() and not refresh and sums.read_bytes() != expected.read_bytes():
        raise RuntimeError("Resolved dependencies differ from the reviewed lock; use the pinned offline bundle")
    print(f"Prepared {len(list((ASSETS/'debs').glob('*.deb')))} Debian packages and {len(lock)} pinned Python wheels.")


if __name__ == "__main__":
    main()
