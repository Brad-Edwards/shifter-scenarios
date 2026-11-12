"""Physical I/O response for the compatibility fixture; no controller logic."""
import asyncio
import logging

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
from pymodbus.server import StartAsyncTcpServer


async def main() -> None:
    slave = ModbusSlaveContext(
        hr=ModbusSequentialDataBlock(0, [0] * 16),
        ir=ModbusSequentialDataBlock(0, [8000, 0, 0, 1] + [0] * 12),
        zero_mode=True,
    )
    context = ModbusServerContext(slaves={1: slave}, single=False)

    async def equipment() -> None:
        position = 0.0
        heartbeat = 1
        while True:
            target = min(10000, max(0, slave.getValues(3, 0, 1)[0]))
            position += max(-50.0, min(50.0, target - position))
            heartbeat = heartbeat % 65534 + 1
            # 0..10000 position counts; 10000 flow counts per m3/s.
            slave.setValues(4, 0, [8000, round(position), round(position * 0.5), heartbeat])
            await asyncio.sleep(0.1)

    task = asyncio.create_task(equipment())
    try:
        await StartAsyncTcpServer(context=context, address=("0.0.0.0", 502))
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
