#!/bin/sh
set -eu

customer_root=${ARWC_CONNECTOR_CUSTOMER_ROOT:-/var/lib/arwc-connector}
fieldlink_root=${ARWC_CONNECTOR_FIELDLINK_ROOT:-/var/lib/fieldlink-connector}
proc_root=${ARWC_CONNECTOR_PROC_ROOT:-/proc}
supervisor_pid=${ARWC_CONNECTOR_SUPERVISOR_PID:-1}
connector_uid=${ARWC_CONNECTOR_UID:-$(id -u arwc-connector)}

child_running() {
  expected=$1
  for process_dir in "$proc_root"/[0-9]*; do
    test -d "$process_dir" || continue
    ppid=$(sed -n 's/^PPid:[[:space:]]*//p' "$process_dir/status" 2>/dev/null) \
      || continue
    uid=$(sed -n 's/^Uid:[[:space:]]*\([0-9][0-9]*\).*/\1/p' \
      "$process_dir/status" 2>/dev/null) || continue
    test "$ppid" = "$supervisor_pid" || continue
    test "$uid" = "$connector_uid" || continue
    command=$(tr '\000' '\n' < "$process_dir/cmdline" 2>/dev/null) || continue
    test "$command" = "python3
$expected" || continue
    return 0
  done
  return 1
}

child_running /opt/customer-handover/customer_handover.py
child_running /opt/fieldlink-connector/fieldlink_consumer.py

test -e "$customer_root/audit/events.jsonl"
test -e "$customer_root/audit/fieldlink-consumer.jsonl"
test -d "$fieldlink_root/consumer/candidates"
