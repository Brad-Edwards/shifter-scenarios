from __future__ import annotations

import hashlib
import itertools
import json
from typing import Any

CHECKPOINT = "REH-SCHED-33"
DEMAND = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70,
          0.70, 0.65, 0.60, 0.55, 0.50, 0.45]
REFERENCE_RELEASE = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35,
                     0.35, 0.30, 0.25, 0.20, 0.15, 0.10]
REFERENCE_ALTERNATE = [round(demand - release, 2)
                       for demand, release in zip(DEMAND, REFERENCE_RELEASE)]


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def number_list(value: object) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 12 or any(
            not isinstance(item, (int, float)) or isinstance(item, bool) for item in value):
        return None
    return [float(item) for item in value]


def evaluate_schedule(releases_value: object, alternate_value: object,
                      demand_value: object = DEMAND, gain: float = 1.0) -> dict[str, Any] | None:
    releases = number_list(releases_value); alternate = number_list(alternate_value)
    demand = number_list(demand_value)
    if releases is None or alternate is None or demand is None:
        return None
    if any(not 0.0 <= value <= 0.8 for value in releases) or \
            any(not 0.0 <= value <= 0.5 for value in alternate):
        return None
    if any(abs(values[index] - values[index - 1]) > 0.1000001
           for values in (releases, alternate) for index in range(1, 12)):
        return None
    buffers = [180.0]
    for release, supply, required in zip(releases, alternate, demand):
        buffers.append(buffers[-1] + 300.0 * (gain * release + supply - required))
    volume = sum(300.0 * gain * value for value in releases) / 1000.0
    if (any(not 120.0 <= value <= 240.0 for value in buffers) or
            not 160.0 <= buffers[-1] <= 200.0 or not 0.78 <= volume <= 0.84):
        return None
    schedule = {"demand_m3s": demand, "reservoir_release_m3s": releases,
                "alternate_supply_m3s": alternate}
    return {
        "checkpoint": CHECKPOINT, "interval_seconds": 300, "interval_count": 12,
        "initial_buffer_m3": 180.0, "final_buffer_m3": round(buffers[-1], 6),
        "minimum_buffer_m3": round(min(buffers), 6),
        "maximum_buffer_m3": round(max(buffers), 6),
        "reservoir_volume_ml": round(volume, 6), "buffers_m3": [round(value, 6) for value in buffers],
        "schedule_sha256": hashlib.sha256(canonical(schedule)).hexdigest(), "feasible": True,
    }


def evaluate_policy(policy: object) -> dict[str, Any] | None:
    if not isinstance(policy, dict) or set(policy) != {
            "format", "checkpoint", "base_release_m3s", "buffer_gain", "demand_gain"}:
        return None
    base = number_list(policy.get("base_release_m3s"))
    buffer_gain = policy.get("buffer_gain"); demand_gain = policy.get("demand_gain")
    if (policy.get("format") != "ARWC-POL1" or policy.get("checkpoint") != CHECKPOINT or
            base is None or not isinstance(buffer_gain, (int, float)) or isinstance(buffer_gain, bool) or
            not isinstance(demand_gain, (int, float)) or isinstance(demand_gain, bool) or
            not -1.0 <= float(buffer_gain) <= 1.0 or not -1.0 <= float(demand_gain) <= 1.0):
        return None
    results: list[dict[str, Any]] = []
    for offset, outlet_gain, delay in itertools.product(
            (-0.05, 0.0, 0.05), (0.98, 1.0, 1.02), (20, 40, 60)):
        demands = [round(value + offset, 6) for value in DEMAND]
        buffer = 180.0; buffers = [buffer]; supplies: list[float] = []
        previous_release = previous_supply = previous_demand = 0.0
        for index, (release, demand) in enumerate(zip(base, demands)):
            delayed = 180.0 if index == 0 else buffer - delay * (
                outlet_gain * previous_release + previous_supply - previous_demand)
            supply = float(demand_gain) * demand - release + float(buffer_gain) * (180.0 - delayed) / 300.0
            supply = min(0.5, max(0.0, supply)); supplies.append(round(supply, 9))
            buffer += 300.0 * (outlet_gain * release + supply - demand)
            buffers.append(buffer)
            previous_release, previous_supply, previous_demand = release, supply, demand
        evaluated = evaluate_schedule(base, supplies, demands, outlet_gain)
        if evaluated is None:
            return None
        results.append({"demand_offset_m3s": offset, "outlet_gain": outlet_gain,
                        "observation_delay_seconds": delay,
                        "reservoir_volume_ml": evaluated["reservoir_volume_ml"],
                        "final_buffer_m3": evaluated["final_buffer_m3"],
                        "minimum_buffer_m3": evaluated["minimum_buffer_m3"],
                        "maximum_buffer_m3": evaluated["maximum_buffer_m3"],
                        "steps": 12})
    return {
        "checkpoint": CHECKPOINT, "format": "ARWC-POL1", "case_count": len(results),
        "scenario_steps": sum(int(item["steps"]) for item in results),
        "demand_offsets_m3s": [-0.05, 0.0, 0.05], "outlet_gains": [0.98, 1.0, 1.02],
        "observation_delays_seconds": [20, 40, 60],
        "minimum_reservoir_volume_ml": min(item["reservoir_volume_ml"] for item in results),
        "maximum_reservoir_volume_ml": max(item["reservoir_volume_ml"] for item in results),
        "minimum_buffer_m3": min(item["minimum_buffer_m3"] for item in results),
        "maximum_buffer_m3": max(item["maximum_buffer_m3"] for item in results),
        "policy_sha256": hashlib.sha256(canonical(policy)).hexdigest(),
        "all_cases_feasible": True, "cases": results,
    }
