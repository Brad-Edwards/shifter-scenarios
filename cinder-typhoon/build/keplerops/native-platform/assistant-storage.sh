#!/bin/sh
set -eu
# Initialize only native writable plugin directories. Managed skill contents
# are mounted separately read-only by the application container.
storage=${ASSISTANT_STORAGE_DIR:-/app/server/storage}
mkdir -p "$storage/plugins/agent-flows" "$storage/plugins/agent-skills"
chown 1000:1000 "$storage/plugins" "$storage/plugins/agent-flows" "$storage/plugins/agent-skills"
