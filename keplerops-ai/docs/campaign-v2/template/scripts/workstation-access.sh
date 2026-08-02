#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly CONTAINER=keplerops-participant-workstation-runtime
readonly PASSWORD_FILE="$ROOT/state/workstation/participant-password"
readonly RDP_BIND_ADDRESS=${PARTICIPANT_RDP_BIND_ADDRESS:-0.0.0.0}
readonly WEB_BIND_ADDRESS=${PARTICIPANT_WEB_BIND_ADDRESS:-127.0.0.1}
readonly RDP_PORT=${PARTICIPANT_RDP_PORT:-3389}
readonly WEB_PORT=${PARTICIPANT_WEB_PORT:-8443}
readonly ACTION=${1:-show}

die() {
  printf 'workstation access error: %s\n' "$*" >&2
  exit 1
}

published_binding() {
  local container_port=$1
  docker inspect --format \
    "{{with (index .NetworkSettings.Ports \"${container_port}/tcp\")}}{{(index . 0).HostIp}}:{{(index . 0).HostPort}}{{end}}" \
    "$CONTAINER"
}

check() {
  local rdp_binding web_binding password probe_address

  [[ $(docker inspect --format '{{.State.Running}}' "$CONTAINER" 2>/dev/null) == true ]] ||
    die "participant workstation is not running"
  [[ -s $PASSWORD_FILE ]] || die "participant password file is unavailable"

  rdp_binding="$(published_binding 3389)"
  web_binding="$(published_binding 6901)"
  [[ -n $rdp_binding ]] || die "XRDP port 3389 is not published"
  [[ -n $web_binding ]] || die "Kasm port 6901 is not published"
  [[ ${rdp_binding##*:} == "$RDP_PORT" ]] ||
    die "XRDP is published on unexpected host port: ${rdp_binding}"
  [[ ${web_binding##*:} == "$WEB_PORT" ]] ||
    die "Kasm is published on unexpected host port: ${web_binding}"
  [[ ${rdp_binding%:*} == "$RDP_BIND_ADDRESS" ]] ||
    die "XRDP is published on unexpected host address: ${rdp_binding}"
  [[ ${web_binding%:*} == "$WEB_BIND_ADDRESS" ]] ||
    die "Kasm is published on unexpected host address: ${web_binding}"

  probe_address=$RDP_BIND_ADDRESS
  [[ $probe_address != 0.0.0.0 ]] || probe_address=127.0.0.1
  timeout 5 bash -c "</dev/tcp/${probe_address}/${RDP_PORT}" 2>/dev/null ||
    die "XRDP host port is not accepting connections"
  probe_address=$WEB_BIND_ADDRESS
  [[ $probe_address != 0.0.0.0 ]] || probe_address=127.0.0.1
  password="$(<"$PASSWORD_FILE")"
  curl --fail --silent --show-error --insecure \
    --user "kasm_user:${password}" \
    --max-time 10 "https://${probe_address}:${WEB_PORT}/" >/dev/null ||
    die "Kasm browser endpoint rejected the participant credential"
  unset password

  printf 'workstation access passed: rdp=%s web=%s\n' \
    "$rdp_binding" "$web_binding"
}

show() {
  cat <<EOF
XRDP: ${RDP_BIND_ADDRESS}:${RDP_PORT} (user: kasm-user)
Browser: https://${WEB_BIND_ADDRESS}:${WEB_PORT}/ (user: kasm_user)
Password file: ${PASSWORD_FILE}
EOF
}

case "$ACTION" in
  check)
    check
    ;;
  show)
    show
    ;;
  *)
    die "usage: $0 {check|show}"
    ;;
esac
