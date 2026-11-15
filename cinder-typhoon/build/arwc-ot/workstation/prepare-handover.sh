#!/bin/bash
# Prepare only an empty shared directory before the first desktop mount.
set -euo pipefail
docker volume create cinder-arwc-connector-fieldlink >/dev/null
docker run --rm --pull never --network none --read-only --user 0:0 \
  --cap-drop ALL --cap-add CHOWN --security-opt no-new-privileges:true \
  --entrypoint python \
  --mount type=volume,src=cinder-arwc-connector-fieldlink,dst=/customer \
  arwc-ot-engineering:368 -c '
import os
from pathlib import Path
path = Path("/customer/handover")
try:
    path.mkdir(mode=0o770)
except FileExistsError:
    if not path.is_dir():
        raise
else:
    os.chmod(path, 0o770)
    os.chown(path, 999, 999)
'
