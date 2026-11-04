#!/bin/sh
set -eu

run_dir=${ARWC_CONNECTOR_RUN_DIR:-/run/arwc-connector}
customer_root=${ARWC_CONNECTOR_CUSTOMER_ROOT:-/var/lib/arwc-connector}
fieldlink_root=${ARWC_CONNECTOR_FIELDLINK_ROOT:-/var/lib/fieldlink-connector}

for child in customer-handover fieldlink-consumer; do
  pid_file="$run_dir/$child.pid"
  test -s "$pid_file"
  read -r pid < "$pid_file"
  case "$pid" in
    ''|*[!0-9]*) exit 1 ;;
  esac
  kill -0 "$pid" 2>/dev/null
done

test -e "$customer_root/audit/events.jsonl"
test -e "$customer_root/audit/fieldlink-consumer.jsonl"
test -d "$fieldlink_root/consumer/candidates"
