"""Phase-E reset: delete exact tracked jobs, then clear local evidence state."""

from __future__ import annotations

import json
import os
from pathlib import Path

from cloud_boundary import WorkspaceBroker
from policy import load_policy
from store import StateStore


def main() -> None:
    root = Path(os.environ.get("PLATFORM_DEPLOYMENT_STATE_ROOT", "/var/lib/keplerops-platform-deployment"))
    policy_path = Path(os.environ.get("PLATFORM_DEPLOYMENT_POLICY", "/run/keplerops/deployment-policy.json"))
    policy = load_policy(policy_path)
    result = WorkspaceBroker(policy, StateStore(root, policy.tenant_id)).reset()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
