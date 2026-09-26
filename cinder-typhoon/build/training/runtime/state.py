#!/usr/bin/env python3
"""Persistent practice tank and retained records for Training."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlsplit

from http_support import TrainingHandler, rooted, serve, utc_now


PUBLIC = rooted("/srv/cinder-state/public")
PRIVATE = rooted("/var/lib/cinder-state")
LIVE = PRIVATE / "live"
STATE_FILE = LIVE / "state.json"
LOCK = threading.RLock()
REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

STATIC = {
    "/": (PUBLIC / "index.md", "text/markdown; charset=utf-8"),
    "/field-guide.md": (PUBLIC / "field-guide.md", "text/markdown; charset=utf-8"),
    "/captures/status.json": (PUBLIC / "captures/status.json", "application/json"),
    "/captures/volume.json": (PUBLIC / "captures/volume.json", "application/json"),
    "/replay/observations.csv": (PUBLIC / "replay/observations.csv", "text/csv; charset=utf-8"),
    "/replay/report.json": (PUBLIC / "replay/report.json", "application/json"),
    "/replay/requests.json": (PUBLIC / "replay/requests.json", "application/json"),
}


def load_state() -> dict[str, object]:
    source = STATE_FILE if STATE_FILE.is_file() else PRIVATE / "initial.json"
    return json.loads(source.read_text(encoding="utf-8"))


def save_state(state: dict[str, object]) -> None:
    LIVE.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = LIVE / "state.tmp"
    temporary.write_text(json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(STATE_FILE)


STATE = load_state()


def status_word(*, hold: bool, outlet_open: bool = False, active: bool = False) -> int:
    return 1 | (2 if outlet_open else 0) | (4 if hold else 0) | (8 if active else 0)


def observation(request_id: str, volume: float, *, outlet_open: bool, active: bool, terminal: bool = False) -> dict[str, object]:
    sequence = len(STATE["observations"]) + 1
    row = {
        "sample_id": f"PT-OBS-{sequence:06d}",
        "observed_at": utc_now(),
        "tank_id": STATE["tank_id"],
        "request_id": request_id,
        "observed_volume_l": round(volume, 1),
        "unit": "L",
        "outlet_position": "open" if outlet_open else "closed",
        "status_word": status_word(hold=False, outlet_open=outlet_open, active=active),
        "quality": "good",
        "terminal": terminal,
    }
    STATE["observations"].append(row)
    return row


def transfer_worker(request_id: str, quantity_l: int, starting_volume: float, started_epoch: float) -> None:
    duration = quantity_l / float(STATE["flow_l_per_second"])
    next_whole = max(1, math.floor(max(0.0, time.time() - started_epoch)) + 1)
    while next_whole < duration:
        delay = started_epoch + next_whole - time.time()
        if delay > 0:
            time.sleep(delay)
        with LOCK:
            if STATE.get("active_transfer", {}).get("request_id") != request_id:
                return
            volume = starting_volume - float(STATE["flow_l_per_second"]) * next_whole
            STATE["observed_volume_l"] = round(volume, 1)
            observation(request_id, volume, outlet_open=True, active=True)
            save_state(STATE)
        next_whole += 1
    delay = started_epoch + duration - time.time()
    if delay > 0:
        time.sleep(delay)
    with LOCK:
        if STATE.get("active_transfer", {}).get("request_id") != request_id:
            return
        final_volume = round(starting_volume - quantity_l, 1)
        STATE["observed_volume_l"] = final_volume
        STATE["outlet_position"] = "closed"
        STATE["status_word"] = status_word(hold=False)
        STATE.pop("active_transfer", None)
        observation(request_id, final_volume, outlet_open=False, active=False, terminal=True)
        for row in STATE["requests"]:
            if row["request_id"] == request_id:
                row["completed_at"] = utc_now()
                row["final_volume_l"] = final_volume
                row["outlet_position"] = "closed"
                break
        save_state(STATE)


def resume_transfer() -> None:
    active = STATE.get("active_transfer")
    if not isinstance(active, dict):
        return
    thread = threading.Thread(
        target=transfer_worker,
        args=(active["request_id"], active["quantity_l"], active["starting_volume_l"], active["started_epoch"]),
        daemon=True,
    )
    thread.start()


def current_state() -> dict[str, object]:
    return {
        "tank_id": STATE["tank_id"],
        "controller_revision": STATE["controller_revision"],
        "capacity_l": STATE["capacity_l"],
        "observed_volume_l": STATE["observed_volume_l"],
        "unit": "L",
        "outlet_position": STATE["outlet_position"],
        "status_word": STATE["status_word"],
        "quality": STATE["quality"],
        "observed_at": utc_now(),
    }


PRACTICE_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Practice tank PT-01</title></head>
<body><h1>Practice tank PT-01</h1><p><a href="/field-guide.md">Field and operating guide</a></p>
<pre id="state">Loading current state...</pre>
<form id="hold"><label>Request ID <input name="request_id" required></label>
<button name="active" value="false">Clear hold</button><button name="active" value="true">Set hold</button></form>
<form id="transfer"><label>Request ID <input name="request_id" required></label>
<label>Quantity (L) <input name="quantity_l" type="number" min="1" max="200" required></label>
<button>Request transfer</button></form><pre id="result"></pre>
<p><a href="/api/practice/requests">Request register</a> · <a href="/api/practice/observations">Observation register</a></p>
<script>
const out=document.querySelector('#result');
async function refresh(){document.querySelector('#state').textContent=JSON.stringify(await fetch('/api/practice/state').then(r=>r.json()),null,2)}
document.querySelector('#hold').addEventListener('submit',async e=>{e.preventDefault();const b=e.submitter.value==='true';const r=await fetch('/api/practice/hold',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:e.target.request_id.value,active:b})});out.textContent=JSON.stringify(await r.json(),null,2);refresh()});
document.querySelector('#transfer').addEventListener('submit',async e=>{e.preventDefault();const r=await fetch('/api/practice/transfer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:e.target.request_id.value,quantity_l:Number(e.target.quantity_l.value)})});out.textContent=JSON.stringify(await r.json(),null,2);refresh()});refresh();setInterval(refresh,1000);
</script></body></html>""".encode()


class StateHandler(TrainingHandler):
    def do_HEAD(self) -> None:
        item = STATIC.get(urlsplit(self.path).path)
        if item:
            self.send_file(*item)
        else:
            self.send_json(404, {"error": "not_found"})

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        item = STATIC.get(path)
        if item:
            self.send_file(*item)
            return
        if path == "/practice":
            self.send_bytes(200, PRACTICE_HTML, "text/html; charset=utf-8")
            return
        with LOCK:
            if path == "/api/practice/state":
                self.send_json(200, current_state())
            elif path == "/api/practice/requests":
                self.send_json(200, {"requests": STATE["requests"]})
            elif path == "/api/practice/observations":
                self.send_json(200, {"observations": STATE["observations"]})
            else:
                self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/practice/hold":
            self._request("hold")
        elif path == "/api/practice/transfer":
            self._request("transfer")
        else:
            self.send_json(404, {"error": "not_found"})

    def do_PUT(self) -> None:
        self.method_not_allowed(("GET", "HEAD", "POST"))

    def do_DELETE(self) -> None:
        self.do_PUT()

    def _request(self, action: str) -> None:
        fields = {"request_id", "active"} if action == "hold" else {"request_id", "quantity_l"}
        try:
            body = json.loads(self.read_body().decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, OverflowError):
            body = None
        valid = isinstance(body, dict) and set(body) == fields and isinstance(body.get("request_id"), str) and REQUEST_ID.fullmatch(body["request_id"])
        if action == "hold":
            valid = valid and type(body.get("active")) is bool
        else:
            valid = valid and type(body.get("quantity_l")) is int and 1 <= body["quantity_l"] <= int(STATE["maximum_transfer_l"])
        if not valid:
            self.send_json(400, {"error": "invalid_request"})
            return

        with LOCK:
            existing = next((row for row in STATE["requests"] if row["request_id"] == body["request_id"]), None)
            if existing:
                if existing["request"] == body:
                    self.send_json(existing["response_status"], existing["receipt"])
                else:
                    self.send_json(409, {"error": "request_id_conflict", "request_id": body["request_id"]})
                return
            sequence = len(STATE["requests"]) + 1
            accepted_at = utc_now()
            reason = None
            status = 200 if action == "hold" else 202
            if action == "hold" and STATE.get("active_transfer"):
                status, reason = 409, "transfer_active"
            elif action == "transfer" and int(STATE["status_word"]) & 4:
                status, reason = 409, "service_hold"
            elif action == "transfer" and STATE.get("active_transfer"):
                status, reason = 409, "transfer_active"
            elif action == "transfer" and float(STATE["observed_volume_l"]) - body["quantity_l"] < float(STATE["minimum_retained_volume_l"]):
                status, reason = 409, "minimum_retained_volume"

            receipt = {"request_id": body["request_id"], "accepted_at": accepted_at, "result": "accepted" if reason is None else "rejected"}
            if reason:
                receipt["reason"] = reason
            row = {
                "request_id": body["request_id"],
                "action": action,
                "request": body,
                "acceptance_sequence": sequence,
                "accepted_at": accepted_at,
                "result": receipt["result"],
                "reason": reason,
                "response_status": status,
                "receipt": receipt,
            }
            STATE["requests"].append(row)
            if reason is None and action == "hold":
                STATE["status_word"] = status_word(hold=body["active"])
            elif reason is None:
                starting_volume = float(STATE["observed_volume_l"])
                started_epoch = time.time()
                STATE["outlet_position"] = "open"
                STATE["status_word"] = status_word(hold=False, outlet_open=True, active=True)
                STATE["active_transfer"] = {
                    "request_id": body["request_id"],
                    "quantity_l": body["quantity_l"],
                    "starting_volume_l": starting_volume,
                    "started_epoch": started_epoch,
                }
                observation(body["request_id"], starting_volume, outlet_open=True, active=True)
                thread = threading.Thread(target=transfer_worker, args=(body["request_id"], body["quantity_l"], starting_volume, started_epoch), daemon=True)
                thread.start()
            save_state(STATE)
        self.send_json(status, receipt)


def main() -> None:
    LIVE.mkdir(parents=True, exist_ok=True, mode=0o700)
    save_state(STATE)
    resume_transfer()
    serve(StateHandler, [8080])


if __name__ == "__main__":
    main()
