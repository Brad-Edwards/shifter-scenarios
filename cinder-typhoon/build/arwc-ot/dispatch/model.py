"""Fixed normal-operation request contract and measured completion criteria."""
import hashlib
import json
import math
import pathlib
import uuid

CONTRACT = json.loads((pathlib.Path(__file__).parent / "contract.json").read_text())


def parse_request(payload: bytes) -> dict:
    if len(payload) > CONTRACT["maximum_payload_bytes"]:
        raise ValueError("Request exceeds the fixed payload limit")
    request = json.loads(payload)
    if not isinstance(request, dict) or set(request) != set(CONTRACT["request_fields"]):
        raise ValueError("Request fields do not match the site contract")
    if type(request["id"]) is not str:
        raise ValueError("Request ID must be a UUID string")
    request["id"] = str(uuid.UUID(request["id"]))
    if request["asset"] != CONTRACT["asset"] or request["mode"] not in ("manual", "automatic"):
        raise ValueError("Request is outside the fixed site scope")
    for name in ("position_a_pct", "position_b_pct", "total_flow_m3s", "expires_at"):
        value = request[name]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Request contains an invalid number")
        request[name] = float(value)
    if not 0 <= request["position_a_pct"] <= 100 or not 0 <= request["position_b_pct"] <= 100:
        raise ValueError("Manual position is outside equipment range")
    if not 0 <= request["total_flow_m3s"] <= 1:
        raise ValueError("Total flow is outside site range")
    return request


def fingerprint(request: dict) -> str:
    return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def next_sequence(seen: int) -> int:
    if type(seen) is not int or not 0 <= seen <= 65535:
        raise ValueError("PLC consumed sequence is unavailable or invalid")
    return (seen % 65535) + 1


def dispatchable(request, now):
    return 0 < request["expires_at"]-now <= CONTRACT["maximum_expiry_seconds"]


def completion(request: dict, state: dict) -> bool:
    if not state["IoHealthy"] or state["Owner"] != 2 or state["AutoMode"] != (request["mode"] == "automatic"):
        return False
    if not state["PermissiveA"] or not state["PermissiveB"] or state["MovingA"] or state["MovingB"]:
        return False
    limits = CONTRACT["feedback"]
    if request["mode"] == "manual":
        return (abs(state["RequestedTargetPct"]-request["position_a_pct"]) <= 0.0001
                and abs(state["RequestedTargetBPct"]-request["position_b_pct"]) <= 0.0001
                and abs(state["PositionPct"]-request["position_a_pct"]) <= limits["position_tolerance_pct"]
                and abs(state["PositionBPct"]-request["position_b_pct"]) <= limits["position_tolerance_pct"])
    if abs(state["RequestedFlowM3s"]-request["total_flow_m3s"]) > 0.0001:
        return False
    if request["total_flow_m3s"] == 0:
        return state["PositionPct"] <= 0.05 and state["PositionBPct"] <= 0.05 and state["FlowM3s"] == 0 and state["FlowBM3s"] == 0
    half = request["total_flow_m3s"] / 2
    return (abs(state["FlowM3s"]-half) <= limits["flow_tolerance_m3s_per_outlet"]
            and abs(state["FlowBM3s"]-half) <= limits["flow_tolerance_m3s_per_outlet"])
