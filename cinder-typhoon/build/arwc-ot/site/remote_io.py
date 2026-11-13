"""Modbus remote I/O and physical response. No process or permission decisions."""
import argparse
import asyncio
import json
import logging
import math
import os
import pathlib
import time
from dataclasses import dataclass, field

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
from pymodbus.server import StartAsyncTcpServer

MODEL = json.loads(pathlib.Path(__file__).with_name("tags.json").read_text())["physical"]


@dataclass
class Equipment:
    level_m: float = MODEL["initial_level_m"]
    positions: list[float] = field(default_factory=lambda: [0.0, 0.0])
    overflow_m3: float = 0.0

    def advance(self, seconds: float, targets: list[int], enabled: list[bool], jammed: list[bool]) -> list[float]:
        travel = 100.0 * seconds / MODEL["full_travel_seconds"]
        for index in range(2):
            if enabled[index] and not jammed[index]:
                target = min(100.0, max(0.0, targets[index] / 100.0))
                self.positions[index] += max(-travel, min(travel, target-self.positions[index]))
        flows = [position * MODEL["outlet_capacity_m3s"] / 100.0 for position in self.positions]
        available = self.level_m * MODEL["surface_area_m2"] + MODEL["inflow_m3s"] * seconds
        requested = sum(flows) * seconds
        if requested > available and requested > 0:
            flows = [flow * available / requested for flow in flows]
        volume = available - sum(flows) * seconds
        maximum = 10.0 * MODEL["surface_area_m2"]
        self.overflow_m3 += max(0.0, volume-maximum)
        self.level_m = min(maximum, max(0.0, volume)) / MODEL["surface_area_m2"]
        return flows

    def save(self, path: pathlib.Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"level_m": self.level_m, "positions": self.positions, "overflow_m3": self.overflow_m3})+"\n")
        os.replace(temporary, path)

    @classmethod
    def load(cls, path: pathlib.Path):
        if not path.exists():
            return cls()
        value = json.loads(path.read_text())
        state = cls(**value)
        if not (math.isfinite(state.level_m) and 0 <= state.level_m <= 10 and len(state.positions) == 2
                and all(math.isfinite(p) and 0 <= p <= 100 for p in state.positions)
                and math.isfinite(state.overflow_m3) and state.overflow_m3 >= 0):
            raise ValueError("Invalid physical state; restore or explicitly reset the development fixture")
        return state


class WatchedOutput(ModbusSequentialDataBlock):
    def __init__(self, clock):
        super().__init__(0, [0]*16)
        self.clock = clock

    def setValues(self, address, values):
        super().setValues(address, values)
        self.clock[0] = time.monotonic()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=pathlib.Path, default=pathlib.Path("/state/equipment.json"))
    parser.add_argument("--initial-level", type=float, default=MODEL["initial_level_m"])
    parser.add_argument("--reset", action="store_true", help="Explicit development/range physical reset")
    parser.add_argument("--local-a", action="store_true", help="Physical field selector at local")
    parser.add_argument("--jam-a", action="store_true", help="Mechanical actuator fault fixture")
    args = parser.parse_args()
    if not math.isfinite(args.initial_level) or not 0 <= args.initial_level <= 10:
        raise ValueError("Initial level must be between 0 and 10 m")
    state = Equipment(level_m=args.initial_level) if args.reset else Equipment.load(args.state)
    writes = [0.0]
    slave = ModbusSlaveContext(hr=WatchedOutput(writes), co=WatchedOutput(writes),
        ir=ModbusSequentialDataBlock(0, [0]*16),
        di=ModbusSequentialDataBlock(0, [1, 1, int(not args.local_a), 1]+[0]*12), zero_mode=True)
    context = ModbusServerContext(slaves={1: slave}, single=False)

    async def equipment() -> None:
        heartbeat = 1
        previous = time.monotonic()
        saved = previous
        while True:
            current = time.monotonic()
            seconds = min(0.5, max(0.0, current-previous))
            previous = current
            fresh = current-writes[0] <= MODEL["write_watchdog_seconds"]
            enabled = [bool(coil) and fresh for coil in slave.getValues(1, 0, 2)]
            flows = state.advance(seconds, slave.getValues(3, 0, 2), enabled, [args.jam_a, False])
            heartbeat = heartbeat % 65534+1
            slave.setValues(4, 0, [round(state.level_m*1000), round(state.positions[0]*100),
                round(flows[0]*10000), heartbeat, round(state.positions[1]*100), round(flows[1]*10000)])
            if current-saved >= 1:
                state.save(args.state)
                saved = current
            await asyncio.sleep(0.1)

    task = asyncio.create_task(equipment())
    try:
        await StartAsyncTcpServer(context=context, address=("0.0.0.0", 502))
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        state.save(args.state)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
