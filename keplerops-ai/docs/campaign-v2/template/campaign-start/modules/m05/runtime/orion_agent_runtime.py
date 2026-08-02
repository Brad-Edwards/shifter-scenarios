from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, TypedDict

import yaml
from langgraph.graph import END, START, StateGraph


STATE = pathlib.Path(os.getenv("ORION_AGENT_STATE", "/var/lib/orion-dataset-worker/orion-agent"))
POLL_SECONDS = int(os.getenv("ORION_AGENT_POLL_SECONDS", "5"))
WORKER_URL = os.getenv("ORION_WORKER_URL", "http://127.0.0.1:8088")
TRAINER_TOKEN = os.getenv("ORION_TRAINER_TOKEN", "")


class AgentState(TypedDict, total=False):
    attempt_id: str
    registration: dict[str, Any]
    endpoint: str
    credential: str
    transport: str
    task: dict[str, Any]
    result: dict[str, Any]
    previous: dict[str, Any]
    librechat_url: str
    librechat_session: str
    conversation_id: str
    configuration_binding: dict[str, str]


def request_json(
    url: str,
    *,
    token: str,
    body: dict[str, object] | None = None,
    basic_user: str | None = None,
) -> dict[str, Any]:
    authorization = f"Bearer {token}"
    if basic_user is not None:
        authorization = "Basic " + base64.b64encode(f"{basic_user}:{token}".encode()).decode()
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": authorization, "Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(request, timeout=30))


def register_node(state: AgentState) -> AgentState:
    registration = request_json(
        f"{WORKER_URL}/v1/agents/register",
        token=TRAINER_TOKEN,
        body={"pid": os.getpid(), "attempt_id": state["attempt_id"]},
    )
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "registration.json").write_text(json.dumps(registration, indent=2) + "\n")
    return {**state, "registration": registration}


def tool_node(state: AgentState) -> AgentState:
    registration = state["registration"]
    response = request_json(
        f"{WORKER_URL}/v1/tools/training-contribution-status",
        token=str(registration["agent_token"]),
    )
    (STATE / "tool-response.json").write_text(json.dumps(response, indent=2) + "\n")
    return {**state, "result": response}


def heartbeat_node(state: AgentState) -> AgentState:
    registration = state["registration"]
    heartbeat = request_json(
        f"{WORKER_URL}/v1/agents/{registration['registration_id']}/heartbeat",
        token=str(registration["agent_token"]),
        body={"pid": os.getpid()},
    )
    (STATE / "heartbeat.json").write_text(json.dumps(heartbeat, indent=2) + "\n")
    return state


registration_graph_builder = StateGraph(AgentState)
registration_graph_builder.add_node("register", register_node)
registration_graph_builder.add_node("tool", tool_node)
registration_graph_builder.add_node("heartbeat", heartbeat_node)
registration_graph_builder.add_edge(START, "register")
registration_graph_builder.add_edge("register", "tool")
registration_graph_builder.add_edge("tool", "heartbeat")
registration_graph_builder.add_edge("heartbeat", END)
registration_graph = registration_graph_builder.compile()


def execute(command: str, registration: dict[str, Any]) -> dict[str, object]:
    command = command.replace("{AGENT_TOKEN}", str(registration["agent_token"]))
    completed = subprocess.run(
        ["/bin/sh", "-lc", command],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    return {
        "command_sha256": __import__("hashlib").sha256(command.encode()).hexdigest(),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def openai_turn(endpoint: str, credential: str, content: str, transport: str) -> dict[str, Any]:
    return request_json(
        endpoint.rstrip("/") + "/v1/chat/completions",
        token=credential,
        body={
            "model": "orion-worker-relay",
            "messages": [{"role": "user", "content": content}],
            "metadata": {"transport": transport},
        },
    )


def librechat_turn(state: AgentState, content: str) -> dict[str, Any]:
    envelope = {
        "kind": "orion-worker-message/v1",
        "registration_id": str(state["registration"]["registration_id"]),
        "issued_at": int(time.time()),
        "nonce": secrets.token_hex(16),
        "payload": content,
    }
    canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
    envelope["signature"] = hmac.new(
        str(state["registration"]["route_grants"]["web_worker"]).encode(),
        canonical,
        hashlib.sha256,
    ).hexdigest()
    body = {
        "text": json.dumps(envelope, separators=(",", ":")),
        "sender": "User",
        "isCreatedByUser": True,
        "endpoint": "custom",
        "endpointOption": {"name": "Orion Worker Review Relay"},
        "conversationId": state["conversation_id"],
    }
    request = urllib.request.Request(
        state["librechat_url"].rstrip("/") + "/api/ask/orion-worker-relay",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {state['librechat_session']}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
    )
    events: list[dict[str, Any]] = []
    with urllib.request.urlopen(request, timeout=60) as response:
        for raw in response:
            line = raw.decode(errors="replace").strip()
            if line.startswith("data:") and line[5:].strip() != "[DONE]":
                value = json.loads(line[5:].strip())
                if isinstance(value, dict):
                    events.append(value)
    message = next(
        (
            str(item.get("text") or item.get("final") or "")
            for item in reversed(events)
            if item.get("text") or item.get("final")
        ),
        "",
    )
    return {"choices": [{"message": {"content": message}}]}


def poll_node(state: AgentState) -> AgentState:
    content = json.dumps(state.get("previous"), separators=(",", ":")) if state.get("previous") else "poll"
    body = (
        librechat_turn(state, content)
        if state["transport"] == "librechat-web"
        else openai_turn(state["endpoint"], state["credential"], content, state["transport"])
    )
    task = json.loads(str(body["choices"][0]["message"]["content"]))
    return {**state, "task": task}


def execute_node(state: AgentState) -> AgentState:
    task = state["task"]
    if task.get("status") == "idle":
        return {**state, "previous": {}}
    task_id = str(task["task_id"])
    command = str(task["command"]).replace("{TASK_ID}", task_id).replace(
        "{NONCE}", str(task.get("nonce") or "")
    )
    result = execute(command, state["registration"])
    result.update({"task_id": task_id, "transport": state["transport"]})
    if task.get("worker_registration_id") or task.get("worker_proof"):
        result.update(
            {
                "worker_registration_id": task.get("worker_registration_id"),
                "worker_proof": task.get("worker_proof"),
            }
        )
    return {**state, "result": result, "previous": result}


def record_node(state: AgentState) -> AgentState:
    result = state.get("result")
    if result and result.get("task_id"):
        (STATE / f"{state['transport']}-{result['task_id']}.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
    return state


transport_graph_builder = StateGraph(AgentState)
transport_graph_builder.add_node("poll", poll_node)
transport_graph_builder.add_node("execute", execute_node)
transport_graph_builder.add_node("record", record_node)
transport_graph_builder.add_edge(START, "poll")
transport_graph_builder.add_edge("poll", "execute")
transport_graph_builder.add_edge("execute", "record")
transport_graph_builder.add_edge("record", END)
transport_graph = transport_graph_builder.compile()


def load_registration() -> dict[str, Any]:
    path = STATE / "registration.json"
    if not path.is_file():
        raise RuntimeError("run --register before starting a transport")
    return json.loads(path.read_text())


def provider_from_config(url: str, username: str, credential: str) -> tuple[str, dict[str, str]]:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    commit = str(query.get("ref", [""])[0])
    if (
        parsed.hostname != "git.keplerops.lab"
        or parsed.path != "/keplerops/orion-agent-config/raw/agent.yaml"
        or len(commit) < 40
        or any(character not in "0123456789abcdef" for character in commit.lower())
    ):
        raise ValueError("immutable Orion configuration URL and commit are required")
    authorization = "Basic " + base64.b64encode(f"{username}:{credential}".encode()).decode()
    request = urllib.request.Request(
        url,
        headers={"Authorization": authorization},
    )
    config_bytes = urllib.request.urlopen(request, timeout=20).read()
    config = yaml.safe_load(config_bytes)
    report_url = urllib.parse.urlunparse(
        parsed._replace(path="/keplerops/orion-agent-config/raw/reports/latest-status.json", query="ref=main")
    )
    report_request = urllib.request.Request(report_url, headers={"Authorization": authorization})
    report_bytes = urllib.request.urlopen(report_request, timeout=20).read()
    report = json.loads(report_bytes)
    config_digest = f"sha256:{hashlib.sha256(config_bytes).hexdigest()}"
    if (
        report.get("commit") != commit
        or report.get("config_digest") != config_digest
        or report.get("signature_verified") is not True
        or not str(report.get("image_digest") or "").startswith("sha256:")
    ):
        raise ValueError("configuration bytes are not the admitted signed deployment source")
    binding = {
        "source_commit": commit,
        "config_digest": config_digest,
        "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "image_digest": str(report["image_digest"]),
    }
    (STATE / "provider-binding.json").write_text(json.dumps(binding, indent=2) + "\n")
    return str(config["spec"]["provider"]["baseURL"]), binding


def main() -> None:
    parser = argparse.ArgumentParser(description="Orion LangGraph worker agent runtime")
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--transport", choices=("openai-api", "librechat-web"))
    parser.add_argument("--config-url")
    parser.add_argument("--config-user", default="external-contributor")
    parser.add_argument("--config-credential")
    parser.add_argument("--librechat-url", default="http://librechat:3080")
    parser.add_argument("--conversation-id")
    parser.add_argument("--attempt-id")
    args = parser.parse_args()
    if args.register:
        if not args.attempt_id:
            parser.error("--register requires the server-issued shell attempt ID")
        state = registration_graph.invoke({"attempt_id": args.attempt_id})
        print(json.dumps({
            "registration_id": state["registration"]["registration_id"],
            "tool_response": state["registration"].get("tool_response"),
            "route_grants": state["registration"]["route_grants"],
        }), flush=True)
        while True:
            heartbeat_node(state)
            time.sleep(POLL_SECONDS)
    if not args.transport:
        parser.error("choose --register or --transport")
    registration = load_registration()
    grants = registration["route_grants"]
    state: AgentState = {"registration": registration, "transport": args.transport}
    if args.transport == "openai-api":
        if not args.config_url or not args.config_credential:
            parser.error("openai-api requires signed configuration URL and earned repository credential")
        endpoint, binding = provider_from_config(args.config_url, args.config_user, args.config_credential)
        state.update(
            {
                "endpoint": endpoint,
                "credential": str(grants["openai_worker"]),
                "configuration_binding": binding,
            }
        )
    else:
        if not args.conversation_id:
            parser.error("librechat-web requires an existing normal conversation ID")
        state.update(
            {
                "librechat_url": args.librechat_url,
                "librechat_session": str(grants["librechat_session"]),
                "conversation_id": args.conversation_id,
            }
        )
    while True:
        try:
            state = transport_graph.invoke(state)
        except (KeyError, ValueError, json.JSONDecodeError, urllib.error.URLError):
            state["previous"] = {}
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
