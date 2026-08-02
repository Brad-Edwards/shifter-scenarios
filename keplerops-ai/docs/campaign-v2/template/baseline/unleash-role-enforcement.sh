#!/usr/bin/env bash
set -Eeuo pipefail

readonly WORKLOAD=kep-v2-business-adapter

if [[ $(docker inspect --format '{{.State.Running}}' "${WORKLOAD}" 2>/dev/null) != true ]]; then
  printf 'business workload is not running: %s\n' "${WORKLOAD}" >&2
  exit 1
fi

docker exec --interactive \
  --env PYTHONDONTWRITEBYTECODE=1 \
  "${WORKLOAD}" python3 - <<'PY'
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


BASE = "http://unleash:4242"
CLIENT_TOKEN = "default:development.KeplerV2-Training-Orion-Canary-Read"
CONTROL_TOKEN = "user:KeplerV2-Training-Orion-Unleash-Control"
CANARY_FEATURE = "orion-canary-assistant"


def get(path: str, token: str) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(
        f"{BASE}{path}", headers={"Authorization": token, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
            raw = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        raw = error.read()
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        body = {"raw": raw.decode("utf-8", errors="replace")[:500]}
    return status, body


def feature_names(body: dict[str, object]) -> set[str]:
    features = body.get("features")
    if not isinstance(features, list):
        raise RuntimeError(f"Unleash Client API response has no feature list: {body}")
    return {
        str(feature["name"])
        for feature in features
        if isinstance(feature, dict) and "name" in feature
    }


status, body = get("/api/client/features", CLIENT_TOKEN)
if status != 200:
    raise RuntimeError(f"scoped canary read failed: HTTP {status}: {body}")
names = feature_names(body)
if CANARY_FEATURE not in names:
    raise RuntimeError(f"scoped canary read omitted its feature: {sorted(names)}")
canonical_names = names
for feature in body["features"]:
    if isinstance(feature, dict) and feature.get("project") != "default":
        raise RuntimeError(f"dedicated OSS service returned an unexpected project: {feature}")
print("PASS Orion workload read its native environment-scoped feature set")

status, body = get(
    "/api/admin/projects/default/features/orion-canary-assistant", CLIENT_TOKEN
)
if status != 403:
    raise RuntimeError(f"backend token reached the Admin API: HTTP {status}: {body}")
print("PASS Orion workload backend token was denied Admin API access")

query = urllib.parse.urlencode({"project": "unrelated", "environment": "production"})
status, body = get(f"/api/client/features?{query}", CLIENT_TOKEN)
if status != 200:
    raise RuntimeError(f"cross-project override request failed: HTTP {status}: {body}")
names = feature_names(body)
if names != canonical_names:
    raise RuntimeError(f"client query overrode server token scope: {sorted(names)}")
print("PASS client-supplied project/environment overrides could not escape token scope")

status, body = get(
    "/api/admin/projects/default/features/orion-canary-assistant",
    CONTROL_TOKEN,
)
if status != 200 or body.get("name") != CANARY_FEATURE:
    raise RuntimeError(f"separate control identity failed its read boundary: HTTP {status}: {body}")
print("PASS separate native control identity retained the administrative boundary")
PY

printf 'Unleash role enforcement passed from the business workload network\n'
