#!/usr/bin/env python3
"""Seed the corporate handover for a standalone ARWC run.

The real handoff is earned by a signed KeplerOps package activation or support
diagnostic (`fieldlink_consumer.earn_corporate`), which needs a paired carrier
running the real KeplerOps delivery. A single-stack local or CI run has no such
peer, so this calls the connector's own `earn_corporate` directly, inside its
container, exactly as a real activation or diagnostic would. This produces the
same handover files a real delivery produces; it does not replace the W26/K27.3
cross-segment delivery coverage, and it is a no-op once a real delivery has
already earned the handoff.
"""
from __future__ import annotations

import subprocess


CLIENT = "cinder-arwc-connector"

script = r'''
import sys
sys.path.insert(0, "/opt/fieldlink-connector")
import fieldlink_consumer
fieldlink_consumer.earn_corporate("package-activation", "RCP-SEED-STANDALONE", "7.4.3-cinder.standalone")
print("seeded" if fieldlink_consumer.TOKEN.exists() else "missing")
'''

completed = subprocess.run(
    ["docker", "exec", "-i", "--user", "arwc-connector", CLIENT, "python3", "-c", script],
    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
)
if completed.returncode or completed.stdout.strip() != "seeded":
    raise SystemExit(completed.stdout + completed.stderr)
