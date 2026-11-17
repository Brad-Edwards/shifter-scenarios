"""Legacy W34 reporting-handover schedule calculation.

W33 no longer owns a scheduler or rehearsal service. W34 still compares its
reporting handover with this fixed, non-operating calculation until W34 is
converted to native product evidence.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


DEMAND = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70,
          0.70, 0.65, 0.60, 0.55, 0.50, 0.45]


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def number_list(value: object) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 12 or any(
            not isinstance(item, (int, float)) or isinstance(item, bool) for item in value):
        return None
    return [float(item) for item in value]


def evaluate_schedule(releases_value: object, alternate_value: object,
                      demand_value: object = DEMAND, gain: float = 1.0) -> dict[str, Any] | None:
    releases = number_list(releases_value)
    alternate = number_list(alternate_value)
    demand = number_list(demand_value)
    if releases is None or alternate is None or demand is None:
        return None
    if any(not 0.0 <= value <= 0.8 for value in releases) or any(
            not 0.0 <= value <= 0.5 for value in alternate):
        return None
    if any(abs(values[index] - values[index - 1]) > 0.1000001
           for values in (releases, alternate) for index in range(1, 12)):
        return None
    buffers = [180.0]
    for release, supply, required in zip(releases, alternate, demand, strict=True):
        buffers.append(buffers[-1] + 300.0 * (gain * release + supply - required))
    volume = sum(300.0 * gain * value for value in releases) / 1000.0
    if (any(not 120.0 <= value <= 240.0 for value in buffers)
            or not 160.0 <= buffers[-1] <= 200.0 or not 0.78 <= volume <= 0.84):
        return None
    schedule = {"demand_m3s": demand, "reservoir_release_m3s": releases,
                "alternate_supply_m3s": alternate}
    return {
        "interval_seconds": 300, "interval_count": 12,
        "initial_buffer_m3": 180.0, "final_buffer_m3": round(buffers[-1], 6),
        "minimum_buffer_m3": round(min(buffers), 6),
        "maximum_buffer_m3": round(max(buffers), 6),
        "reservoir_volume_ml": round(volume, 6),
        "buffers_m3": [round(value, 6) for value in buffers],
        "schedule_sha256": hashlib.sha256(canonical(schedule)).hexdigest(), "feasible": True,
    }
