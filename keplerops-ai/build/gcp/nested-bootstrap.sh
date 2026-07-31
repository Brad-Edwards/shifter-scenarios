#!/bin/bash
set -euo pipefail
umask 077
trap 'printf "nested bootstrap failed at line %s: %s\n" "$LINENO" "$BASH_COMMAND" >&2' ERR

readonly METADATA_ROOT='http://metadata.google.internal/computeMetadata/v1'
readonly METADATA_HEADER='Metadata-Flavor: Google'
readonly STATE_ROOT='/var/lib/keplerops-nested'
readonly NVRAM_ROOT='/var/lib/libvirt/qemu/nvram'
readonly NETWORK_NAME='keplerops-windows'
readonly BRIDGE_NAME='virbr-kep'
readonly BRIDGE_URL='http://192.168.77.1:8080'

metadata() {
  curl --fail --silent --show-error \
    -H "$METADATA_HEADER" "$METADATA_ROOT/instance/attributes/$1"
}

readonly PROJECT_ID=$(metadata keplerops-project-id)
readonly SECRET_SUFFIX=$(metadata keplerops-secret-suffix)
readonly LOCAL_ADMIN_SECRET='ad-domain-admin-password'

install -d -m 0700 \
  "$STATE_ROOT" "$STATE_ROOT/bin" "$STATE_ROOT/windows" \
  "$STATE_ROOT/guest-attributes"
install -d -m 0755 "$NVRAM_ROOT"
metadata keplerops-nested-metadata >"$STATE_ROOT/bin/nested-metadata.py"
chmod 0500 "$STATE_ROOT/bin/nested-metadata.py"
metadata keplerops-nested-secret-access >"$STATE_ROOT/secret-access.json"
chmod 0600 "$STATE_ROOT/secret-access.json"

if ! virsh net-info "$NETWORK_NAME" >/dev/null 2>&1; then
  cat >"$STATE_ROOT/network.xml" <<EOF
<network>
  <name>$NETWORK_NAME</name>
  <forward mode="nat"/>
  <bridge name="$BRIDGE_NAME" stp="on" delay="0"/>
  <ip address="192.168.77.1" netmask="255.255.255.0">
    <dhcp>
      <range start="192.168.77.100" end="192.168.77.199"/>
      <host mac="52:54:00:77:00:10" name="ad-dc-01" ip="192.168.77.10"/>
      <host mac="52:54:00:77:00:11" name="workforce-workstation-01" ip="192.168.77.11"/>
      <host mac="52:54:00:77:00:12" name="ml-workstation-01" ip="192.168.77.12"/>
    </dhcp>
  </ip>
</network>
EOF
  virsh net-define "$STATE_ROOT/network.xml"
fi
virsh net-autostart "$NETWORK_NAME"
if [[ $(virsh net-info "$NETWORK_NAME" | awk '/^Active:/ {print $2}') != yes ]]; then
  virsh net-start "$NETWORK_NAME"
fi
for attempt in $(seq 1 30); do
  if ip -4 address show dev "$BRIDGE_NAME" |
    grep -Fq 'inet 192.168.77.1/24'; then
    break
  fi
  [[ $attempt -lt 30 ]] || exit 1
  sleep 2
done
sysctl -w "net.ipv4.conf.$BRIDGE_NAME.proxy_arp=1" >/dev/null
ip neighbor replace proxy 169.254.169.254 dev "$BRIDGE_NAME"
iptables -t nat -C PREROUTING -i "$BRIDGE_NAME" \
  -d 169.254.169.254/32 -p tcp --dport 80 \
  -j DNAT --to-destination 192.168.77.1:8080 2>/dev/null ||
  iptables -t nat -I PREROUTING 1 -i "$BRIDGE_NAME" \
    -d 169.254.169.254/32 -p tcp --dport 80 \
    -j DNAT --to-destination 192.168.77.1:8080

cat >"/etc/systemd/system/keplerops-nested-metadata.service" <<EOF
[Unit]
Description=KeplerOps nested guest metadata bridge
After=network-online.target libvirtd.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $STATE_ROOT/bin/nested-metadata.py --project $PROJECT_ID --suffix $SECRET_SUFFIX --state-root $STATE_ROOT --secret-access $STATE_ROOT/secret-access.json
Restart=always
RestartSec=2
User=root
Group=root
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable keplerops-nested-metadata.service
systemctl restart keplerops-nested-metadata.service
for attempt in $(seq 1 30); do
  curl --fail --silent "$BRIDGE_URL/health" >/dev/null && break
  [[ $attempt -lt 30 ]] || exit 1
  sleep 2
done

local_admin_password=$(
  curl --fail --silent --show-error --connect-timeout 5 --max-time 30 \
    "$BRIDGE_URL/secret/$LOCAL_ADMIN_SECRET"
)
local_admin_b64=$(printf '%s' "$local_admin_password" | base64 -w 0)
unset local_admin_password

prepare_windows_disk() {
  local host_id=$1 device="/dev/disk/by-id/google-kep-${host_id}"
  local partition mountpoint="$STATE_ROOT/mnt-$host_id"
  [[ -b $device ]] || return 1
  if virsh dominfo "$host_id" >/dev/null 2>&1; then
    if [[ $(virsh domstate "$host_id") == running ]]; then
      virsh shutdown "$host_id"
      for _ in $(seq 1 30); do
        [[ $(virsh domstate "$host_id") == "shut off" ]] && break
        sleep 2
      done
    fi
    if [[ $(virsh domstate "$host_id") != "shut off" ]]; then
      virsh destroy "$host_id"
    fi
  fi
  install -d -m 0700 "$mountpoint"
  for attempt in $(seq 1 30); do
    [[ -b ${device}-part3 ]] && break
    [[ $attempt -lt 30 ]] || return 1
    sleep 2
  done
  partition=$(readlink -f "${device}-part3")
  [[ -b $partition ]]
  mountpoint -q "$mountpoint" && umount "$mountpoint"
  mount -t ntfs-3g "$partition" "$mountpoint" || true
  if ! mountpoint -q "$mountpoint" ||
    findmnt -no OPTIONS "$mountpoint" | tr ',' '\n' | grep -qx ro; then
    mountpoint -q "$mountpoint" && umount "$mountpoint"
    ntfsfix -d "$partition"
    mount -t ntfs-3g -o remove_hiberfile "$partition" "$mountpoint"
  fi
  test -w "$mountpoint"
  install -d "$mountpoint/Windows/Setup/Scripts"
  cat >"$mountpoint/Windows/Setup/Scripts/SetupComplete.cmd" <<EOF
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "\$p=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('$local_admin_b64')); & net.exe user Administrator \$p; & net.exe user Administrator /active:yes; Enable-PSRemoting -Force; Set-Item WSMan:\\localhost\\Service\\Auth\\Basic -Value true"
EOF

  local credential_root="$mountpoint/ProgramData/KeplerOps"
  local system_hive="$mountpoint/Windows/System32/config/SYSTEM"
  local current_control_set registry_commands
  install -d "$credential_root"
  cat >"$credential_root/credential-bootstrap.ps1" <<EOF
\$ErrorActionPreference = "Stop"
\$password = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String("$local_admin_b64")
)
& net.exe user Administrator \$password
& net.exe user Administrator /active:yes
& sc.exe delete KeplerOpsCredential
Remove-Item -LiteralPath \$PSCommandPath -Force
EOF
  current_control_set=$(hivexget "$system_hive" '\Select' Current)
  [[ $current_control_set =~ ^[0-9]+$ ]]
  printf -v current_control_set 'ControlSet%03d' "$current_control_set"
  registry_commands="$STATE_ROOT/windows/$host_id-credential.hivex"
  if printf 'cd \\%s\\Services\\KeplerOpsCredential\n' "$current_control_set" |
    hivexsh "$system_hive" >/dev/null 2>&1; then
    cat >"$registry_commands" <<EOF
cd \\$current_control_set\\Services\\KeplerOpsCredential
del
commit
EOF
    hivexsh -w -f "$registry_commands" "$system_hive" >/dev/null
  fi
  cat >"$registry_commands" <<EOF
cd \\$current_control_set\\Services
add KeplerOpsCredential
cd KeplerOpsCredential
setval 7
Type
dword:0x10
Start
dword:0x2
ErrorControl
dword:0x1
ImagePath
expandstring:%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File C:\\ProgramData\\KeplerOps\\credential-bootstrap.ps1
DisplayName
string:KeplerOps credential bootstrap
ObjectName
string:LocalSystem
DelayedAutoStart
dword:0x1
commit
EOF
  hivexsh -w -f "$registry_commands" "$system_hive" >/dev/null
  rm -f "$registry_commands"
  sync
  umount "$mountpoint"
}

define_windows_guest() {
  local host_id=$1 ip_last=$2 memory_mib=$3 vcpus=$4
  local mac
  printf -v mac '52:54:00:77:00:%02d' "$ip_last"
  if [[ ! -f $NVRAM_ROOT/$host_id-VARS.fd ]]; then
    install -m 0600 /usr/share/OVMF/OVMF_VARS_4M.ms.fd \
      "$NVRAM_ROOT/$host_id-VARS.fd"
  fi
  cat >"$STATE_ROOT/windows/$host_id.xml" <<EOF
<domain type="kvm">
  <name>$host_id</name>
  <memory unit="MiB">$memory_mib</memory>
  <vcpu placement="static">$vcpus</vcpu>
  <os>
    <type arch="x86_64" machine="pc-q35-8.2">hvm</type>
    <loader readonly="yes" secure="yes" type="pflash">/usr/share/OVMF/OVMF_CODE_4M.secboot.fd</loader>
    <nvram template="/usr/share/OVMF/OVMF_VARS_4M.ms.fd">$NVRAM_ROOT/$host_id-VARS.fd</nvram>
  </os>
  <features><acpi/><apic/><smm state="on"/></features>
  <cpu mode="host-passthrough" check="none" migratable="off"/>
  <clock offset="localtime">
    <timer name="rtc" tickpolicy="catchup"/>
    <timer name="pit" tickpolicy="delay"/>
    <timer name="hpet" present="no"/>
    <timer name="hypervclock" present="yes"/>
  </clock>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>restart</on_crash>
  <devices>
    <emulator>/usr/bin/qemu-system-x86_64</emulator>
    <disk type="block" device="disk">
      <driver name="qemu" type="raw" cache="none" io="native"/>
      <source dev="/dev/disk/by-id/google-kep-$host_id"/>
      <target dev="sda" bus="sata"/>
      <boot order="1"/>
    </disk>
    <controller type="sata" index="0"/>
    <interface type="network">
      <mac address="$mac"/>
      <source network="$NETWORK_NAME"/>
      <model type="e1000e"/>
    </interface>
    <serial type="pty"><target type="isa-serial" port="0"/></serial>
    <console type="pty"><target type="serial" port="0"/></console>
    <graphics type="vnc" port="-1" autoport="yes" listen="127.0.0.1">
      <listen type="address" address="127.0.0.1"/>
    </graphics>
    <video><model type="vga" vram="16384" heads="1" primary="yes"/></video>
    <memballoon model="virtio"/>
  </devices>
</domain>
EOF
  if virsh dominfo "$host_id" >/dev/null 2>&1; then
    if ! grep -Fq "$NVRAM_ROOT/$host_id-VARS.fd" \
      < <(virsh dumpxml "$host_id"); then
      [[ $(virsh domstate "$host_id") != running ]]
      virsh undefine "$host_id" --nvram
      install -m 0600 /usr/share/OVMF/OVMF_VARS_4M.ms.fd \
        "$NVRAM_ROOT/$host_id-VARS.fd"
      virsh define "$STATE_ROOT/windows/$host_id.xml"
    fi
  else
    virsh define "$STATE_ROOT/windows/$host_id.xml"
  fi
  virsh autostart "$host_id" --disable
  [[ $(virsh domstate "$host_id") == running ]] || virsh start "$host_id"
}

for host_id in ad-dc-01 workforce-workstation-01 ml-workstation-01; do
  metadata "keplerops-windows-bootstrap-$host_id" \
    >"$STATE_ROOT/windows/$host_id-bootstrap.ps1"
  chmod 0600 "$STATE_ROOT/windows/$host_id-bootstrap.ps1"
  prepare_windows_disk "$host_id"
done
unset local_admin_b64

define_windows_guest ad-dc-01 10 8192 2
define_windows_guest workforce-workstation-01 11 8192 2
define_windows_guest ml-workstation-01 12 12288 4

run_windows_bootstrap() {
  local host_id=$1 ip=$2
  local script="$STATE_ROOT/windows/$host_id-bootstrap.ps1"
  local applied="$STATE_ROOT/windows/$host_id-bootstrap.applied.sha256"
  local ready="$STATE_ROOT/guest-attributes/$host_id/ready"
  if [[ -s $ready ]] &&
    grep -qx ready "$ready" &&
    [[ -s $applied ]] &&
    sha256sum --check --status "$applied"; then
    return 0
  fi
  rm -f "$ready"
  for attempt in $(seq 1 180); do
    timeout --signal=TERM --kill-after=10s 1800s \
      python3 - "$ip" "$script" "$BRIDGE_URL/secret/$LOCAL_ADMIN_SECRET" <<'PY' &
import base64
import hashlib
import sys
import urllib.request

import winrm

ip, script_path, password_url = sys.argv[1:]
try:
    with urllib.request.urlopen(password_url, timeout=20) as response:
        password = response.read().decode().strip()
    script = open(script_path, "rb").read()
    session = None
    principal_failures = []
    for principal, username in (
        ("domain", r"KEPLEROPS\Administrator"),
        ("local", "Administrator"),
    ):
        candidate = winrm.Session(
            f"https://{ip}:5986/wsman",
            auth=(username, password),
            transport="ntlm",
            server_cert_validation="ignore",
            read_timeout_sec=70,
            operation_timeout_sec=60,
        )
        try:
            probe = candidate.run_ps("$null")
        except Exception as exc:
            principal_failures.append(f"{principal}={type(exc).__name__}")
            continue
        if probe.status_code == 0:
            session = candidate
            break
        principal_failures.append(f"{principal}=status-{probe.status_code}")
    if session is None:
        raise RuntimeError(
            "no valid Windows bootstrap principal: " + ",".join(principal_failures)
        )
    remote_root = r"C:\ProgramData\KeplerOps"
    remote_script = rf"{remote_root}\nested-bootstrap.ps1"
    remote_encoded = rf"{remote_script}.b64"
    digest = hashlib.sha256(script).hexdigest().upper()
    check = session.run_ps(
        f"if (Test-Path '{remote_script}') {{ "
        f"(Get-FileHash -Algorithm SHA256 '{remote_script}').Hash }}"
    )
    remote_digest = check.std_out.decode(errors="replace").strip()
    if check.status_code or remote_digest != digest:
        encoded = base64.b64encode(script).decode()
        initialize = session.run_ps(
            f"New-Item -ItemType Directory -Force '{remote_root}' | Out-Null; "
            f"foreach ($path in @('{remote_encoded}','{remote_script}')) {{ "
            f"if (Test-Path $path) {{ Remove-Item -Force $path }} }}"
        )
        if initialize.status_code:
            raise RuntimeError("unable to initialize Windows bootstrap transfer")
        for offset in range(0, len(encoded), 1024):
            chunk = encoded[offset : offset + 1024]
            append = session.run_ps(
                f"Add-Content -LiteralPath '{remote_encoded}' "
                f"-Value '{chunk}' -NoNewline -Encoding Ascii"
            )
            if append.status_code:
                raise RuntimeError("unable to transfer Windows bootstrap")
        decode = session.run_ps(
            f"[IO.File]::WriteAllBytes('{remote_script}',"
            f"[Convert]::FromBase64String("
            f"[IO.File]::ReadAllText('{remote_encoded}'))); "
            f"Remove-Item -Force '{remote_encoded}'"
        )
        if decode.status_code:
            raise RuntimeError("unable to decode Windows bootstrap")
    result = session.run_ps(
        f"& powershell.exe -NoProfile -NonInteractive "
        f"-ExecutionPolicy Bypass -File '{remote_script}'"
    )
    if result.status_code:
        stderr = result.std_err.decode(errors="replace").replace(password, "[redacted]")
        stderr = " ".join(stderr.split())[-500:]
        raise RuntimeError(
            f"nested Windows bootstrap returned status {result.status_code}: {stderr}"
        )
except Exception as exc:
    message = str(exc).replace(password, "[redacted]")
    print(
        f"{ip}: Windows bootstrap attempt failed "
        f"({type(exc).__name__}: {message[:300]})",
        file=sys.stderr,
    )
    raise SystemExit(1)
PY
    bootstrap_pid=$!
    while kill -0 "$bootstrap_pid" 2>/dev/null; do
      if [[ -s $ready ]] && grep -qx ready "$ready"; then
        kill "$bootstrap_pid" 2>/dev/null || true
        wait "$bootstrap_pid" 2>/dev/null || true
        sha256sum "$script" >"$applied"
        return 0
      fi
      sleep 2
    done
    if wait "$bootstrap_pid" &&
      [[ -s $ready ]] &&
      grep -qx ready "$ready"; then
      sha256sum "$script" >"$applied"
      return 0
    fi
    sleep 10
  done
  return 1
}

run_windows_bootstrap ad-dc-01 192.168.77.10
run_windows_bootstrap workforce-workstation-01 192.168.77.11 &
workforce_pid=$!
run_windows_bootstrap ml-workstation-01 192.168.77.12 &
ml_pid=$!
wait "$workforce_pid"
wait "$ml_pid"

iptables -C FORWARD -i "$BRIDGE_NAME" -j ACCEPT 2>/dev/null ||
  iptables -I FORWARD 1 -i "$BRIDGE_NAME" -j ACCEPT
iptables -C FORWARD -o "$BRIDGE_NAME" -m conntrack --ctstate RELATED,ESTABLISHED \
  -j ACCEPT 2>/dev/null ||
  iptables -I FORWARD 1 -o "$BRIDGE_NAME" -m conntrack \
    --ctstate RELATED,ESTABLISHED -j ACCEPT
touch "$STATE_ROOT/ready"
