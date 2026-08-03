#!/usr/bin/env bash
set -Eeuo pipefail

readonly WORKSTATION=keplerops-participant-workstation-runtime
readonly REDIS_CONTAINER=kep-v2-redis
readonly REDIS_PASSWORD=KeplerV2-Training-Redis
readonly CONVERSATION_ID=langflow-orion-preview-integration
readonly WORKHUB_SOURCE_ID=ORION-RELEASE-POLICY-2026

if [[ $(docker inspect --format '{{.State.Running}}' "${WORKSTATION}" 2>/dev/null) != true ]]; then
  printf 'participant workstation is not running: %s\n' "${WORKSTATION}" >&2
  exit 1
fi
if [[ $(docker inspect --format '{{.State.Running}}' "${REDIS_CONTAINER}" 2>/dev/null) != true ]]; then
  printf 'WorkHub state service is not running: %s\n' "${REDIS_CONTAINER}" >&2
  exit 1
fi

docker exec --interactive \
  --user kasm-user \
  --env HOME=/home/kasm-user \
  --env PYTHONDONTWRITEBYTECODE=1 \
  "${WORKSTATION}" python3 - <<'PY'
from __future__ import annotations

import gzip
import http.cookiejar
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


BASE = "https://flows.keplerops.lab"
RANGE_CA = "/usr/local/share/ca-certificates/keplerops-range-root.crt"
PARTICIPANT_USER = "release.engineer"
PARTICIPANT_PASSWORD = "KeplerV2-Training-Release"
FLOW_NAME = "Orion Preview Release Review"
FLOW_ENDPOINT = "orion-preview-release-review"
RUN_KEY_NAME = "Orion Preview Review Invocation"
CONVERSATION_ID = "langflow-orion-preview-integration"
WORKHUB_SOURCE_ID = "ORION-RELEASE-POLICY-2026"
PROMPT = (
    "Review candidate orion-edge-2026.08 for Preview integration. Use "
    f"lookup_release_context for {WORKHUB_SOURCE_ID}, summarize the required "
    "release evidence with citations, and open a handoff to Release Engineering "
    "for digest-bound validation."
)
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def fail(message: str) -> None:
    raise RuntimeError(message)


def browser() -> urllib.request.OpenerDirector:
    context = ssl.create_default_context(cafile=RANGE_CA)
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        urllib.request.HTTPSHandler(context=context),
    )
    opener.addheaders = [
        ("User-Agent", USER_AGENT),
        ("Accept-Language", "en-US,en;q=0.9"),
    ]
    return opener


def decode_body(data: bytes, content_encoding: str | None) -> str:
    if content_encoding and "gzip" in content_encoding.lower():
        data = gzip.decompress(data)
    return data.decode("utf-8", errors="replace")


def request(
    opener: urllib.request.OpenerDirector,
    target: str | urllib.request.Request,
) -> tuple[int, str, str]:
    try:
        with opener.open(target, timeout=240) as response:
            return (
                response.status,
                response.geturl(),
                decode_body(response.read(), response.headers.get("Content-Encoding")),
            )
    except urllib.error.HTTPError as error:
        return (
            error.code,
            error.geturl(),
            decode_body(error.read(), error.headers.get("Content-Encoding")),
        )


def json_request(
    opener: urllib.request.OpenerDirector,
    path: str,
    *,
    token: str | None = None,
    api_key: str | None = None,
    method: str = "GET",
    payload: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, str, Any]:
    headers = {"Accept": "application/json", "Accept-Encoding": "gzip"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if api_key:
        headers["x-api-key"] = api_key
    if content_type:
        headers["Content-Type"] = content_type
    status, url, body = request(
        opener,
        urllib.request.Request(
            f"{BASE}{path}",
            data=payload,
            headers=headers,
            method=method,
        ),
    )
    try:
        decoded = json.loads(body)
    except json.JSONDecodeError as error:
        fail(f"Langflow returned invalid JSON: HTTP {status} at {url}: {error}")
    return status, url, decoded


def login(
    opener: urllib.request.OpenerDirector, username: str, password: str
) -> str:
    payload = urllib.parse.urlencode(
        {"username": username, "password": password}
    ).encode()
    status, url, body = json_request(
        opener,
        "/api/v1/login",
        method="POST",
        payload=payload,
        content_type="application/x-www-form-urlencoded",
    )
    if status != 200 or not isinstance(body, dict):
        fail(f"Langflow login failed for {username}: HTTP {status} at {url}")
    token = body.get("access_token")
    if not isinstance(token, str) or len(token) < 20:
        fail(f"Langflow login did not return a viable token for {username}")
    return token


def strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


context = ssl.create_default_context(cafile=RANGE_CA)
if not context.get_ca_certs():
    fail(f"participant enterprise CA is invalid or empty: {RANGE_CA}")

anonymous = browser()
status, url, page = request(anonymous, BASE)
if status != 200 or urllib.parse.urlsplit(url).hostname != "flows.keplerops.lab":
    fail(f"Langflow HTTPS employee surface failed: HTTP {status} at {url}")
if "langflow" not in page.lower():
    fail("Langflow HTTPS employee surface did not render the product UI")

status, url, _ = json_request(anonymous, "/api/v1/users/whoami")
if status != 403:
    fail(f"anonymous caller reached Langflow whoami: HTTP {status} at {url}")

status, url, version = json_request(anonymous, "/api/v1/version")
if (
    status != 200
    or not isinstance(version, dict)
    or version.get("version") != "1.5.0"
    or version.get("main_version") != "1.5.0"
):
    fail(f"Langflow runtime version contract failed: HTTP {status} at {url}")

participant = browser()
token = login(participant, PARTICIPANT_USER, PARTICIPANT_PASSWORD)
status, url, identity = json_request(
    participant, "/api/v1/users/whoami", token=token
)
if (
    status != 200
    or not isinstance(identity, dict)
    or identity.get("username") != PARTICIPANT_USER
    or identity.get("is_active") is not True
    or identity.get("is_superuser") is not False
):
    fail(f"Langflow employee identity boundary failed: HTTP {status} at {url}")

status, url, flows = json_request(
    participant, "/api/v1/flows/?get_all=true", token=token
)
if status != 200 or not isinstance(flows, list):
    fail(f"Langflow employee flow listing failed: HTTP {status} at {url}")
matches = [flow for flow in flows if flow.get("name") == FLOW_NAME]
if len(matches) != 1:
    fail(f"expected one employee-owned Orion flow, found {len(matches)}")
flow = matches[0]
flow_id = flow.get("id")
if not isinstance(flow_id, str) or not flow_id:
    fail("Langflow Orion flow has no stable ID")
if flow.get("user_id") != identity.get("id"):
    fail("Langflow Orion flow is not owned by the normal employee")
if flow.get("endpoint_name") != FLOW_ENDPOINT or flow.get("access_type") != "PRIVATE":
    fail("Langflow Orion flow endpoint or private access type was not preserved")

data = flow.get("data")
if not isinstance(data, dict):
    fail("Langflow Orion flow has no graph data")
nodes = data.get("nodes")
edges = data.get("edges")
if not isinstance(nodes, list) or len(nodes) != 4:
    fail("Langflow Orion flow does not contain the four-node employee workflow")
if not isinstance(edges, list) or len(edges) != 3:
    fail("Langflow Orion flow does not contain the three required connections")
node_types = {
    node.get("data", {}).get("type") for node in nodes if isinstance(node, dict)
}
required_types = {"ChatInput", "Prompt", "OpenAIModel", "ChatOutput"}
if node_types != required_types:
    fail(f"Langflow Orion flow components differ: {node_types ^ required_types}")
model = next(node for node in nodes if node.get("data", {}).get("type") == "OpenAIModel")
template = model.get("data", {}).get("node", {}).get("template", {})
if template.get("model_name", {}).get("value") != "orion-assistant":
    fail("Langflow Orion flow does not use the Orion assistant")
if template.get("api_key", {}).get("value") != "ORION_AGENT_API_KEY":
    fail("Langflow Orion flow does not use its employee-owned credential variable")
model_kwargs = template.get("model_kwargs", {}).get("value", {})
if (
    model_kwargs.get("user") != PARTICIPANT_USER
    or model_kwargs.get("extra_body", {}).get("conversation_id") != CONVERSATION_ID
    or model_kwargs.get("extra_body", {})
    .get("metadata", {})
    .get("handoff", {})
    .get("team")
    != "Release Engineering"
):
    fail("Langflow Orion flow lost its actor, conversation, or handoff boundary")

status, url, _ = json_request(participant, "/api/v1/users/", token=token)
if status != 403:
    fail(f"normal Langflow employee reached the superuser list: HTTP {status} at {url}")

status, url, keys = json_request(participant, "/api/v1/api_key/", token=token)
if status != 200 or not isinstance(keys, dict):
    fail(f"Langflow employee API-key listing failed: HTTP {status} at {url}")
for existing in keys.get("api_keys", []):
    if existing.get("name") != RUN_KEY_NAME:
        continue
    key_id = existing.get("id")
    if not isinstance(key_id, str) or not key_id:
        fail("Langflow returned an invalid existing invocation-key record")
    status, url, _ = json_request(
        participant,
        f"/api/v1/api_key/{key_id}",
        token=token,
        method="DELETE",
    )
    if status != 200:
        fail(f"Langflow could not remove an old invocation key: HTTP {status} at {url}")

status, url, created_key = json_request(
    participant,
    "/api/v1/api_key/",
    token=token,
    method="POST",
    payload=json.dumps({"name": RUN_KEY_NAME}, separators=(",", ":")).encode(),
    content_type="application/json",
)
if status != 200 or not isinstance(created_key, dict):
    fail(f"Langflow could not issue an employee invocation key: HTTP {status} at {url}")
flow_api_key = created_key.get("api_key")
flow_api_key_id = created_key.get("id")
if (
    not isinstance(flow_api_key, str)
    or not flow_api_key.startswith("sk-")
    or not isinstance(flow_api_key_id, str)
    or not flow_api_key_id
):
    fail("Langflow did not return a usable employee invocation key")

run_payload = json.dumps(
    {
        "input_value": PROMPT,
        "input_type": "chat",
        "output_type": "chat",
        "session_id": CONVERSATION_ID,
    },
    separators=(",", ":"),
).encode()
try:
    status, url, result = json_request(
        participant,
        f"/api/v1/run/{FLOW_ENDPOINT}",
        api_key=flow_api_key,
        method="POST",
        payload=run_payload,
        content_type="application/json",
    )
finally:
    cleanup_status, cleanup_url, _ = json_request(
        participant,
        f"/api/v1/api_key/{flow_api_key_id}",
        token=token,
        method="DELETE",
    )
    if cleanup_status != 200:
        fail(
            "Langflow could not remove the employee invocation key: "
            f"HTTP {cleanup_status} at {cleanup_url}"
        )
if status != 200 or not isinstance(result, dict):
    fail(f"Langflow Orion review execution failed: HTTP {status} at {url}: {result}")
if result.get("session_id") != CONVERSATION_ID:
    fail("Langflow did not preserve the employee review session")
rendered = "\n".join(strings(result))
for expected in ("Orion Release Policy", "Sources", "Release Engineering"):
    if expected not in rendered:
        fail(f"Langflow Orion review response omitted {expected!r}")

print("PASS Langflow normal employee ownership and native privilege denials")
print("PASS Langflow run API reached the Orion WorkHub assistant with cited output")
PY

conversation="$({
  docker exec \
    --env REDISCLI_AUTH="${REDIS_PASSWORD}" \
    "${REDIS_CONTAINER}" redis-cli --raw \
    GET "workhub:conversation:${CONVERSATION_ID}"
} 2>/dev/null)"
if [[ -z ${conversation} ]]; then
  printf 'WorkHub did not persist the Langflow conversation\n' >&2
  exit 1
fi

handoff_id="$(jq -er \
  --arg actor release.engineer \
  --arg source_id "${WORKHUB_SOURCE_ID}" '
    select(.conversation_id == "langflow-orion-preview-integration")
    | select(.actor == $actor)
    | select(any(.citations[]?; .source_id == $source_id))
    | select(any(.tool_events[]?;
        .name == "lookup_release_context" and .allowed == true))
    | .handoff_id
    | select(type == "string" and startswith("handoff-"))
  ' <<<"${conversation}")"

handoff="$({
  docker exec \
    --env REDISCLI_AUTH="${REDIS_PASSWORD}" \
    "${REDIS_CONTAINER}" redis-cli --raw \
    GET "workhub:handoff:${handoff_id}"
} 2>/dev/null)"
jq -e \
  --arg handoff_id "${handoff_id}" '
    .handoff_id == $handoff_id
    and .conversation_id == "langflow-orion-preview-integration"
    and .actor == "release.engineer"
    and .team == "Release Engineering"
    and .status == "open"
    and (.workflow_id | startswith("workflow-"))
  ' <<<"${handoff}" >/dev/null || {
    printf 'WorkHub Langflow handoff state is incomplete\n' >&2
    exit 1
  }

printf 'PASS OPA authorized Langflow retrieval before the MCP tool completed\n'
printf 'PASS WorkHub persisted the employee conversation and open handoff\n'
printf 'Langflow executable enterprise workflow acceptance passed\n'
