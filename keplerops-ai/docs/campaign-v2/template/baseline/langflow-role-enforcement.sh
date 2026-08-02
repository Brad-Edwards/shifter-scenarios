#!/usr/bin/env bash
set -Eeuo pipefail

readonly WORKSTATION=keplerops-participant-workstation-runtime

if [[ $(docker inspect --format '{{.State.Running}}' "${WORKSTATION}" 2>/dev/null) != true ]]; then
  printf 'participant workstation is not running: %s\n' "${WORKSTATION}" >&2
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
PARTICIPANT_USER = "cinder.operator"
PARTICIPANT_PASSWORD = "KeplerV2-Training-Cinder"
FLOW_NAME = "Orion Preview Integration Flow"
FLOW_ENDPOINT = "orion-preview-integration"
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
        with opener.open(target, timeout=60) as response:
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
    method: str = "GET",
    payload: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, str, Any]:
    headers = {"Accept": "application/json", "Accept-Encoding": "gzip"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
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


context = ssl.create_default_context(cafile=RANGE_CA)
if not context.get_ca_certs():
    fail(f"participant range CA is invalid or empty: {RANGE_CA}")

anonymous = browser()
status, url, page = request(anonymous, BASE)
if status != 200 or urllib.parse.urlsplit(url).hostname != "flows.keplerops.lab":
    fail(f"Langflow HTTPS participant surface failed: HTTP {status} at {url}")
if "langflow" not in page.lower():
    fail("Langflow HTTPS participant surface did not render the product UI")

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
    fail(f"Langflow participant identity boundary failed: HTTP {status} at {url}")

status, url, flows = json_request(
    participant, "/api/v1/flows/?get_all=true", token=token
)
if status != 200 or not isinstance(flows, list):
    fail(f"Langflow participant flow listing failed: HTTP {status} at {url}")
matches = [flow for flow in flows if flow.get("name") == FLOW_NAME]
if len(matches) != 1:
    fail(f"expected one participant-owned Orion flow, found {len(matches)}")
flow = matches[0]
flow_id = flow.get("id")
if not isinstance(flow_id, str) or not flow_id:
    fail("Langflow Orion flow has no stable ID")
if flow.get("user_id") != identity.get("id"):
    fail("Langflow Orion flow is not owned by the normal participant")
if flow.get("endpoint_name") != FLOW_ENDPOINT or flow.get("access_type") != "PUBLIC":
    fail("Langflow Orion flow endpoint or public access type was not preserved")

data = flow.get("data")
if not isinstance(data, dict):
    fail("Langflow Orion flow has no graph data")
nodes = data.get("nodes")
edges = data.get("edges")
if not isinstance(nodes, list) or len(nodes) != 9:
    fail("Langflow Orion flow does not contain the pinned nine-node graph")
if not isinstance(edges, list) or len(edges) != 7:
    fail("Langflow Orion flow does not contain the pinned seven-edge graph")
node_types = {
    node.get("data", {}).get("type") for node in nodes if isinstance(node, dict)
}
required_types = {"ChatInput", "Prompt", "LanguageModelComponent", "ChatOutput"}
if not required_types.issubset(node_types):
    fail(f"Langflow Orion flow is missing native components: {required_types - node_types}")
prompt_values = [
    node.get("data", {})
    .get("node", {})
    .get("template", {})
    .get("template", {})
    .get("value", "")
    for node in nodes
    if node.get("data", {}).get("type") == "Prompt"
]
if len(prompt_values) != 3 or not all("Orion" in value for value in prompt_values):
    fail("Langflow Orion flow does not contain the three seeded review stages")

status, url, owned = json_request(
    participant, f"/api/v1/flows/{flow_id}", token=token
)
if status != 200 or not isinstance(owned, dict) or owned.get("id") != flow_id:
    fail(f"participant could not read the owned Langflow flow: HTTP {status} at {url}")

status, url, _ = json_request(participant, "/api/v1/users/", token=token)
if status != 403:
    fail(f"normal Langflow participant reached the superuser list: HTTP {status} at {url}")

status, url, _ = json_request(anonymous, f"/api/v1/flows/{flow_id}")
if status != 403:
    fail(f"anonymous caller reached the authenticated flow route: HTTP {status} at {url}")

status, url, public_flow = json_request(
    anonymous, f"/api/v1/flows/public_flow/{flow_id}"
)
if (
    status != 200
    or not isinstance(public_flow, dict)
    or public_flow.get("id") != flow_id
    or public_flow.get("access_type") != "PUBLIC"
):
    fail(f"public Langflow flow route failed: HTTP {status} at {url}")

print(
    "PASS Langflow HTTPS, normal participant ownership, public flow access, "
    "and native privilege denials"
)
PY

printf 'Langflow participant role-enforcement acceptance passed\n'
