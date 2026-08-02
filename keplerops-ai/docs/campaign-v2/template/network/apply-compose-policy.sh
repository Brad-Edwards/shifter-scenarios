#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FLOW_FILE=${FLOW_FILE:-$ROOT/compose-flows.tsv}
CAMPAIGN_FLOW_FILE=${CAMPAIGN_FLOW_FILE:-$ROOT/campaign-flows.tsv}
CHAIN=${KEPLEROPS_NETWORK_CHAIN:-KEP-V2-SEGMENT}
GUEST_CIDR=${KEPLEROPS_GUEST_CIDR:-192.168.78.0/24}
ACTION=${1:-apply}

fail() {
  printf 'ERROR %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

validate_flows() {
  local flow_file=$1
  [[ -r $flow_file ]] || fail "flow manifest not readable: $flow_file"
  awk -F '\t' '
    /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
    NF != 5 { printf "invalid field count at line %d\n", NR > "/dev/stderr"; bad=1; next }
    $1 !~ /^([a-zA-Z0-9_.-]+|label:[a-zA-Z0-9_.\/-]+=[*a-zA-Z0-9_.-]+|cidr:[0-9.]+\/[0-9]+)$/ {
      printf "invalid source at line %d\n", NR > "/dev/stderr"; bad=1
    }
    $2 !~ /^([a-zA-Z0-9_.-]+|cidr:[0-9.]+\/[0-9]+)$/ {
      printf "invalid destination at line %d\n", NR > "/dev/stderr"; bad=1
    }
    $3 != "tcp" && $3 != "udp" {
      printf "invalid protocol at line %d\n", NR > "/dev/stderr"; bad=1
    }
    $4 !~ /^[0-9]+(,[0-9]+)*$/ {
      printf "invalid port list at line %d\n", NR > "/dev/stderr"; bad=1
    }
    END { exit bad }
  ' "$flow_file"
}

container_ips() {
  local container=$1
  docker inspect "$container" --format '{{json .NetworkSettings.Networks}}' 2>/dev/null |
    jq -r 'to_entries[] | select(.key | startswith("kep-v2-")) | .value.IPAddress | select(length > 0)'
}

source_ips() {
  local source=$1 selector container
  if [[ $source == cidr:* ]]; then
    printf '%s\n' "${source#cidr:}"
  elif [[ $source == label:* ]]; then
    selector=${source#label:}
    selector=${selector%=*}
    while IFS= read -r container; do
      [[ -n $container ]] && container_ips "$container"
    done < <(docker ps --filter "label=$selector" --format '{{.Names}}')
  else
    container_ips "$source"
  fi
}

managed_subnets() {
  local network
  while IFS= read -r network; do
    [[ $network == kep-v2-* ]] || continue
    docker network inspect "$network" --format '{{json .IPAM.Config}}' 2>/dev/null |
      jq -r '.[]?.Subnet // empty'
  done < <(docker network ls --format '{{.Name}}') | sort -u
}

add_rule() {
  iptables -w -A "$CHAIN" "$@"
}

add_flow() {
  local source=$1 destination=$2 protocol=$3 ports=$4 purpose=$5
  local source_ip destination_ip comment
  local -a source_addresses=() destination_addresses=()
  comment=$(printf 'kep-v2:%s' "$purpose" | cut -c1-120)
  mapfile -t source_addresses < <(source_ips "$source" | sort -u)
  ((${#source_addresses[@]} > 0)) || {
    [[ ${REQUIRE_ALL_CONTAINERS:-0} == 1 ]] && fail "flow source is not running: $source"
    printf 'SKIP  source not running: %s\n' "$source" >&2
    return
  }

  if [[ $destination == cidr:* ]]; then
    destination_addresses=("${destination#cidr:}")
  else
    mapfile -t destination_addresses < <(container_ips "$destination" | sort -u)
    ((${#destination_addresses[@]} > 0)) || {
      [[ ${REQUIRE_ALL_CONTAINERS:-0} == 1 ]] && fail "flow destination is not running: $destination"
      printf 'SKIP  destination not running: %s\n' "$destination" >&2
      return
    }
  fi

  for source_ip in "${source_addresses[@]}"; do
    [[ $source_ip == */* ]] || source_ip="$source_ip/32"
    for destination_ip in "${destination_addresses[@]}"; do
      add_rule -s "$source_ip" -d "$destination_ip" -p "$protocol" \
        -m multiport --dports "$ports" -m comment --comment "$comment" -j RETURN
    done
  done
}

remove_policy() {
  if iptables -w -C DOCKER-USER -j "$CHAIN" >/dev/null 2>&1; then
    iptables -w -D DOCKER-USER -j "$CHAIN"
  fi
  iptables -w -F "$CHAIN" >/dev/null 2>&1 || true
  iptables -w -X "$CHAIN" >/dev/null 2>&1 || true
}

apply_policy() {
  local source destination protocol ports purpose source_subnet destination_subnet
  local -a subnets=()

  [[ $EUID -eq 0 ]] || fail "apply requires root"
  require_command docker
  require_command iptables
  require_command jq
  require_command modprobe
  require_command sysctl
  docker info >/dev/null 2>&1 || fail "Docker is not available"
  iptables -w -nL DOCKER-USER >/dev/null 2>&1 || fail "Docker DOCKER-USER chain is unavailable"

  modprobe br_netfilter
  sysctl -q -w net.bridge.bridge-nf-call-iptables=1
  sysctl -q -w net.ipv4.ip_forward=1

  mapfile -t subnets < <(managed_subnets)
  ((${#subnets[@]} > 0)) || fail "no kep-v2 Docker networks are present"

  iptables -w -N "$CHAIN" >/dev/null 2>&1 || true
  iptables -w -F "$CHAIN"
  add_rule -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN

  # Named service and bounded host flows are admitted before lateral denial.
  while IFS=$'\t' read -r source destination protocol ports purpose; do
    [[ -n $source && $source != \#* ]] || continue
    [[ $destination == cidr:0.0.0.0/0 ]] && continue
    add_flow "$source" "$destination" "$protocol" "$ports" "$purpose"
  done < <(cat "$FLOW_FILE" "$CAMPAIGN_FLOW_FILE")

  # Every nested guest is untrusted. Exact post-DNAT flows above are the only
  # paths from the libvirt subnet into a managed Docker network.
  for destination_subnet in "${subnets[@]}"; do
    add_rule -s "$GUEST_CIDR" -d "$destination_subnet" \
      -m comment --comment 'kep-v2:deny-undeclared-guest-ingress' -j DROP
  done

  # Deny every managed bridge pair, including traffic switched on one bridge.
  for source_subnet in "${subnets[@]}"; do
    for destination_subnet in "${subnets[@]}"; do
      add_rule -s "$source_subnet" -d "$destination_subnet" \
        -m comment --comment 'kep-v2:deny-undeclared-lateral' -j DROP
    done
  done

  # Public egress is exceptional and cannot override the managed-network deny.
  while IFS=$'\t' read -r source destination protocol ports purpose; do
    [[ -n $source && $source != \#* ]] || continue
    [[ $destination == cidr:0.0.0.0/0 ]] || continue
    add_flow "$source" "$destination" "$protocol" "$ports" "$purpose"
  done < <(cat "$FLOW_FILE" "$CAMPAIGN_FLOW_FILE")

  for source_subnet in "${subnets[@]}"; do
    add_rule -s "$source_subnet" -m comment --comment 'kep-v2:deny-undeclared-egress' -j DROP
  done
  add_rule -j RETURN

  iptables -w -C DOCKER-USER -j "$CHAIN" >/dev/null 2>&1 || \
    iptables -w -I DOCKER-USER 1 -j "$CHAIN"
  printf 'Applied %s from %s and %s\n' "$CHAIN" "$FLOW_FILE" "$CAMPAIGN_FLOW_FILE"
}

status_policy() {
  iptables -w -C DOCKER-USER -j "$CHAIN" >/dev/null 2>&1 || exit 1
  iptables -w -nL "$CHAIN" --line-numbers
}

validate_flows "$FLOW_FILE"
validate_flows "$CAMPAIGN_FLOW_FILE"
case "$ACTION" in
  apply) apply_policy ;;
  remove)
    [[ $EUID -eq 0 ]] || fail "remove requires root"
    require_command iptables
    remove_policy
    ;;
  status)
    require_command iptables
    status_policy
    ;;
  validate) printf 'Flow manifests are valid: %s %s\n' "$FLOW_FILE" "$CAMPAIGN_FLOW_FILE" ;;
  *) fail "usage: $0 {apply|remove|status|validate}" ;;
esac
