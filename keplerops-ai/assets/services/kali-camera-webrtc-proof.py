#!/usr/bin/env python3
"""Drive a live browser/WebRTC camera capture for Module 08 physical proof."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from typing import Any


DATA_CHANNEL_LABEL = "keplerops-live-capture-v1"


class DevToolsSocket:
    """Small RFC 6455 client sufficient for local Chrome DevTools messages."""

    def __init__(self, url: str) -> None:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "ws" or parsed.hostname is None or parsed.port is None:
            raise ValueError("expected a local ws:// DevTools URL")
        self.connection = socket.create_connection((parsed.hostname, parsed.port), 5)
        self.connection.settimeout(20)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        self.connection.sendall(request)
        response = self._until(b"\r\n\r\n")
        if not response.startswith(b"HTTP/1.1 101"):
            raise RuntimeError("Chromium rejected the DevTools WebSocket handshake")
        expected = base64.b64encode(
            hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii"),
                usedforsecurity=False,
            ).digest()
        )
        if b"sec-websocket-accept: " + expected.lower() not in response.lower():
            raise RuntimeError("Chromium returned an invalid WebSocket accept digest")
        self.next_id = 1

    def command(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        command_id = self.next_id
        self.next_id += 1
        self._send(1, json.dumps({"id": command_id, "method": method, "params": params}))
        while True:
            opcode, payload = self._receive()
            if opcode == 9:
                self._send(10, payload)
                continue
            if opcode != 1:
                continue
            message = json.loads(payload)
            if message.get("id") == command_id:
                if "error" in message:
                    raise RuntimeError(str(message["error"]))
                return message.get("result", {})

    def close(self) -> None:
        try:
            self._send(8, b"")
        finally:
            self.connection.close()

    def _send(self, opcode: int, value: str | bytes) -> None:
        payload = value.encode("utf-8") if isinstance(value, str) else value
        mask = os.urandom(4)
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65_536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        header.extend(mask)
        masked = bytes(item ^ mask[index % 4] for index, item in enumerate(payload))
        self.connection.sendall(header + masked)

    def _receive(self) -> tuple[int, bytes]:
        first, second = self._exact(2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._exact(8))[0]
        mask = self._exact(4) if second & 0x80 else None
        payload = self._exact(length)
        if mask is not None:
            payload = bytes(item ^ mask[index % 4] for index, item in enumerate(payload))
        return opcode, payload

    def _until(self, marker: bytes) -> bytes:
        captured = bytearray()
        while marker not in captured:
            captured.extend(self.connection.recv(4096))
        return bytes(captured)

    def _exact(self, size: int) -> bytes:
        captured = bytearray()
        while len(captured) < size:
            block = self.connection.recv(size - len(captured))
            if not block:
                raise ConnectionError("Chromium closed the DevTools connection")
            captured.extend(block)
        return bytes(captured)


def _chromium() -> str:
    for name in (
        "chromium-headless-shell",
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
    ):
        found = shutil.which(name)
        if found is not None:
            return found
    raise RuntimeError("Chromium is not installed")


def _evaluate(channel: DevToolsSocket, expression: str) -> Any:
    result = channel.command(
        "Runtime.evaluate",
        {
            "expression": expression,
            "awaitPromise": True,
            "returnByValue": True,
            "userGesture": True,
        },
    )
    if "exceptionDetails" in result:
        raise RuntimeError(str(result["exceptionDetails"]))
    return result.get("result", {}).get("value")


def _devtools_target(debug_port: int, url: str) -> dict[str, Any]:
    version_url = f"http://127.0.0.1:{debug_port}/json/version"
    deadline = time.monotonic() + 12
    while True:
        try:
            with urllib.request.urlopen(version_url, timeout=1):
                break
        except OSError:
            if time.monotonic() >= deadline:
                raise RuntimeError("Chromium DevTools did not start")
            time.sleep(0.1)
    request = urllib.request.Request(
        f"http://127.0.0.1:{debug_port}/json/new?"
        + urllib.parse.quote(url, safe=""),
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


def _browser_proof(base_url: str, session: dict[str, Any]) -> dict[str, Any]:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        debug_port = reservation.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="keplerops-camera-chrome-") as profile:
        process = subprocess.Popen(
            [
                _chromium(),
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-features=WebRtcHideLocalIpsWithMdns",
                "--ignore-certificate-errors",
                "--autoplay-policy=no-user-gesture-required",
                f"--remote-debugging-port={debug_port}",
                f"--user-data-dir={profile}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        channel: DevToolsSocket | None = None
        try:
            target = _devtools_target(debug_port, base_url.rstrip("/") + "/")
            channel = DevToolsSocket(target["webSocketDebuggerUrl"])
            channel.command("Page.enable", {})
            channel.command("Runtime.enable", {})
            channel.command("Page.navigate", {"url": base_url.rstrip("/") + "/"})
            _evaluate(
                channel,
                "new Promise((resolve,reject)=>{const end=Date.now()+12000;"
                "const wait=setInterval(()=>{if(document.readyState==='complete'){"
                "clearInterval(wait);resolve(true);}else if(Date.now()>end){"
                "clearInterval(wait);reject(new Error('page timeout'));}},50);})",
            )
            return _evaluate(channel, _proof_expression(base_url, session))
        finally:
            if channel is not None:
                channel.close()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def _proof_expression(base_url: str, session: dict[str, Any]) -> str:
    return (
        "(async()=>{"
        f"const baseUrl={json.dumps(base_url.rstrip('/') + '/')};"
        f"const session={json.dumps(session, separators=(',', ':'))};"
        f"const fallbackLabel={json.dumps(DATA_CHANNEL_LABEL)};"
        "const delay=(ms)=>new Promise((resolve)=>setTimeout(resolve,ms));"
        "const canvas=document.createElement('canvas');canvas.width=320;canvas.height=240;"
        "document.body.appendChild(canvas);const ctx=canvas.getContext('2d');let tick=0;"
        "function draw(role){tick++;ctx.fillStyle=tick%2?'#111':'#171717';"
        "ctx.fillRect(0,0,320,240);ctx.fillStyle='#f7f7f7';"
        "if(role==='control'){for(let x=120;x<200;x+=20){ctx.fillRect(x,0,16,240);}}"
        "else{for(let y=90;y<150;y+=20){ctx.fillRect(0,y,320,16);}}"
        "ctx.fillStyle='#444';ctx.fillRect(tick%320,0,8,8);}"
        "let role='control';draw(role);const interval=setInterval(()=>draw(role),120);"
        "const stream=canvas.captureStream(5);const pc=new RTCPeerConnection({iceServers:[]});"
        "const messages=[];const channel=pc.createDataChannel("
        "(session.data_channel_label||fallbackLabel),{ordered:true});"
        "channel.onmessage=(event)=>{try{messages.push(JSON.parse(event.data));}"
        "catch(error){messages.push({type:'parse-error',reason:String(error)});}};"
        "stream.getVideoTracks().forEach((track)=>pc.addTrack(track,stream));"
        "const opened=new Promise((resolve,reject)=>{const timer=setTimeout(()=>"
        "reject(new Error('data channel open timeout')),15000);channel.onopen=()=>{"
        "clearTimeout(timer);resolve(true);};});"
        "const offer=await pc.createOffer();await pc.setLocalDescription(offer);"
        "await new Promise((resolve,reject)=>{if(pc.iceGatheringState==='complete')"
        "{resolve(true);return;}const timer=setTimeout(()=>reject(new Error("
        "'ICE gathering timeout')),10000);pc.onicegatheringstatechange=()=>{"
        "if(pc.iceGatheringState==='complete'){clearTimeout(timer);resolve(true);}};});"
        "const offerUrl=new URL(session.offer_url,baseUrl).pathname;"
        "const response=await fetch(offerUrl,{method:'POST',headers:{Authorization:"
        "'Bearer '+session.session_token,'Content-Type':'application/json'},"
        "body:JSON.stringify(pc.localDescription)});const answer=await response.json();"
        "if(!response.ok){throw new Error(answer.detail||'WebRTC signaling failed');}"
        "await pc.setRemoteDescription(answer);await opened;"
        "const pairId='pair-'+session.session_id.slice(0,12)+'-'+"
        "crypto.randomUUID().replaceAll('-','').slice(0,8);"
        "async function capture(nextRole){role=nextRole;draw(role);await delay(800);"
        "const command={type:'capture',pair_id:pairId,role:nextRole,"
        "client_timestamp_ms:Date.now(),nonce:crypto.randomUUID().replaceAll('-','')};"
        "channel.send(JSON.stringify(command));const end=Date.now()+15000;"
        "while(Date.now()<end){const index=messages.findIndex((msg)=>"
        "msg.type==='capture-result'&&msg.role===nextRole);if(index>=0){"
        "const [msg]=messages.splice(index,1);if(!msg.ok){throw new Error("
        "msg.reason||('capture failed '+nextRole));}return msg;}await delay(100);}"
        "throw new Error('capture timeout '+nextRole);}"
        "const control=await capture('control');await delay(800);"
        "const attack=await capture('attack');clearInterval(interval);"
        "try{await fetch('/v1/sessions/'+session.session_id+'/close',{method:'POST',"
        "headers:{Authorization:'Bearer '+session.session_token}});}catch(_error){}"
        "pc.close();stream.getTracks().forEach((track)=>track.stop());"
        "const labels=(msg)=>(msg.ml_response?.predictions||[]).map((row)=>row.label);"
        "return {session_id:session.session_id,pair_id:pairId,control_ok:!!control.ok,"
        "attack_ok:!!attack.ok,control_labels:labels(control),attack_labels:labels(attack)};"
        "})()"
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = _browser_proof(str(payload["base_url"]), payload["session"])
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps({"error": str(error)[:500]}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
