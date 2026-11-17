#!/usr/bin/env python3
"""Completion script: reads the assigned HANDOVER-COMP-2841 from the internal handover store.

Runs as svc-assistant-completion with the handover read grant.
Outputs the handover record as JSON to stdout.
"""

import json
import os
import sys
from pathlib import Path

handover_path = Path(os.environ.get(
    "FIELDKEST_HANDOVER_PATH",
    "/var/lib/fieldkest-assistant-api/completion/handover",
))
handover_id = os.environ.get("FIELDKEST_HANDOVER_ID", "HANDOVER-COMP-2841")

target = handover_path / f"{handover_id}.json"
if not target.is_file():
    print(json.dumps({"error": f"handover {handover_id} not found"}))
    sys.exit(1)

data = json.loads(target.read_text())
print(json.dumps(data))
