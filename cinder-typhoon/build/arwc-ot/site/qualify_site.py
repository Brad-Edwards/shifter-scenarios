"""Normal site operations through native OPC UA, checked against real Modbus I/O."""
import argparse
import asyncio
import json
import pathlib
import sys
import time

from asyncua import ua
from pymodbus.client import AsyncModbusTcpClient

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from qualify_opcua import connect

REGISTER = json.loads((ROOT / "tags.json").read_text())
TYPES = {tag["variable"]: getattr(ua.VariantType,{"BOOL":"Boolean","UINT":"UInt16","REAL":"Float"}[tag["type"]]) for tag in REGISTER["tags"]}
OBSERVE = ("ProjectRevision","LevelM","UsableVolumeML","PositionPct","PositionBPct","FlowM3s","FlowBM3s",
           "TotalFlowM3s","IoHealthy","Owner","Armed","AutoMode","HmiRemoteEnabled","HmiAccepted",
           "RemoteAccepted","HmiSeen","RemoteSeen","HmiRejected","RemoteRejected","HmiRejectReason",
           "RemoteRejectReason","RequestedTargetPct","RequestedTargetBPct","RequestedFlowM3s",
           "MotorEnableA","MotorEnableB","TravelFaultA","TravelFaultB","MotionStateA","MotionStateB")


class Operator:
    def __init__(self, client, namespace):
        self.client = client
        self.namespace = namespace

    def node(self, name):
        return self.client.get_node(ua.NodeId("CRR."+name,self.namespace))

    async def read(self, names=OBSERVE):
        values = await self.client.read_attributes([self.node(name) for name in names],ua.AttributeIds.Value)
        for value in values:
            value.StatusCode.check()
        return {name:value.Value.Value for name,value in zip(names,values)}

    async def write(self, values):
        for name,value in values.items():
            await self.node(name).write_value(ua.Variant(value,TYPES[name]))

    async def wait(self, predicate, message, timeout=45):
        deadline = time.monotonic()+timeout
        latest = {}
        while time.monotonic() < deadline:
            latest = await self.read()
            if predicate(latest):
                return latest
            await asyncio.sleep(0.25)
        raise AssertionError(message+": "+json.dumps(latest))

    async def command(self, a, b, auto=False, flow=0.2, remote=None):
        prefix = "Remote" if remote else "Hmi"
        seen = (await self.read((prefix+"Seen",)))[prefix+"Seen"]
        sequence = seen % 65535+1
        writer = remote or self
        await writer.write({prefix+"TargetPct":float(a),prefix+"TargetBPct":float(b),
                            prefix+"AutoMode":auto,prefix+"FlowM3s":float(flow),prefix+"Sequence":sequence})
        await self.wait(lambda v:v[prefix+"Accepted"] == sequence,"PLC did not accept the complete request")
        return sequence


async def physical():
    client = AsyncModbusTcpClient(REGISTER["modbus"]["host"],port=502)
    await client.connect()
    try:
        inputs = await client.read_input_registers(0,6,slave=1)
        targets = await client.read_holding_registers(0,2,slave=1)
        enables = await client.read_coils(0,2,slave=1)
        assert not any(response.isError() for response in (inputs,targets,enables)), "Physical Modbus read failed"
        return {"input_registers":inputs.registers,"target_registers":targets.registers,"motor_coils":enables.bits[:2]}
    finally:
        client.close()


async def flow_stable(operator):
    stable = 0
    def predicate(v):
        nonlocal stable
        assert not v["TravelFaultA"] and not v["TravelFaultB"], "Automatic operation caused a travel fault"
        good = v["Armed"] and v["AutoMode"] and not v["MotorEnableA"] and not v["MotorEnableB"] and abs(v["FlowM3s"]-0.2)<0.01 and abs(v["FlowBM3s"]-0.2)<0.01
        stable = stable+1 if good else 0
        return stable >= 8
    return await operator.wait(predicate,"Measured automatic flow did not settle",90)


async def operating(operator):
    await operator.wait(lambda v:v["IoHealthy"],"Field I/O did not become healthy")
    assert (await operator.read())["ProjectRevision"] == 364
    await operator.write({"HmiStop":True})
    await operator.wait(lambda v:not v["Armed"],"Operator stop did not disarm motion")
    await operator.write({"HmiStop":False})
    await operator.command(0,0,auto=True,flow=0.0)
    closed = await operator.wait(lambda v:v["PositionPct"] == 0 and v["PositionBPct"] == 0 and not v["MotorEnableA"] and not v["MotorEnableB"],"Zero-flow operation did not close both outlets completely")
    sequence = await operator.command(25,15)
    manual = await operator.wait(lambda v:abs(v["PositionPct"]-25)<0.6 and abs(v["PositionBPct"]-15)<0.6,"Manual command lacks measured position feedback")
    await asyncio.sleep(0.3)
    wire = await physical()
    assert wire["target_registers"] == [2500,1500], wire
    assert abs(wire["input_registers"][1]/100-manual["PositionPct"])<0.6
    assert abs(wire["input_registers"][4]/100-manual["PositionBPct"])<0.6
    assert abs(manual["UsableVolumeML"]-max(0,(manual["LevelM"]-1)*2))<0.003
    assert abs(manual["TotalFlowM3s"]-manual["FlowM3s"]-manual["FlowBM3s"])<0.001
    invalid = sequence%65535+1
    await operator.write({"HmiTargetPct":101.0,"HmiSequence":invalid})
    rejected = await operator.wait(lambda v:v["HmiRejected"] == invalid,"Invalid request lacks rejection feedback")
    assert rejected["HmiAccepted"] == sequence and rejected["HmiRejectReason"] == 4
    assert rejected["RequestedTargetPct"] == 25 and rejected["RequestedTargetBPct"] == 15
    await operator.write({"HmiRemoteEnabled":True})
    remote_client = await connect("dispatcher")
    try:
        remote = Operator(remote_client,operator.namespace)
        remote_sequence = await operator.command(30,20,remote=remote)
        await operator.wait(lambda v:v["Owner"] == 2 and abs(v["PositionPct"]-30)<0.6 and abs(v["PositionBPct"]-20)<0.6,"Remote request lacks controller/equipment feedback")
    finally:
        await remote_client.disconnect()
    await operator.command(35,20)
    takeover = await operator.wait(lambda v:v["Owner"] == 1 and not v["HmiRemoteEnabled"],"Local takeover did not remove remote authority")
    assert takeover["RemoteAccepted"] == remote_sequence
    await operator.command(35,20,auto=True,flow=0.4)
    automatic = await flow_stable(operator)
    await operator.command(35,20,flow=0.4)
    await operator.wait(lambda v:abs(v["PositionPct"]-35)<0.6 and abs(v["PositionBPct"]-20)<0.6,"Manual recovery did not reach retained settings")
    return {"zero_flow_closed":closed,"manual":manual,"modbus_feedback":wire,"invalid_request":rejected,
            "local_takeover":takeover,"automatic":automatic,"final":await operator.read()}


async def phase(operator, name):
    directory = ROOT.parent / ".operator/site-evidence"
    directory.mkdir(parents=True,exist_ok=True)
    if name == "operating":
        result = await operating(operator)
    elif name == "field-down":
        before = await operator.wait(lambda v:not v["IoHealthy"] and not v["Armed"],"Field loss did not disarm motion",20)
        assert not before["MotorEnableA"] and not before["MotorEnableB"]
        next_sequence = before["HmiSeen"]%65535+1
        await operator.write({"HmiTargetPct":45.0,"HmiSequence":next_sequence})
        result = await operator.wait(lambda v:v["HmiRejected"] == next_sequence,"Unavailable field request was not consumed")
        assert result["HmiRejectReason"] == 1
    elif name == "field-up":
        down = json.loads((directory / "field-down.json").read_text())
        result = await operator.wait(lambda v:v["IoHealthy"],"Field I/O failed to recover")
        assert not result["Armed"] and result["HmiAccepted"] == down["HmiAccepted"], "Recovery replayed an inactive request"
        assert result["HmiSeen"] == down["HmiSeen"]
    elif name == "prepare-restart":
        await operator.command(35,20,auto=True,flow=0.4)
        result = await flow_stable(operator)
        await operator.write({"HmiRemoteEnabled":True})
        result = await operator.wait(lambda v:v["HmiRemoteEnabled"],"Remote selection did not enable")
        assert result["Armed"] and result["AutoMode"]
        await asyncio.sleep(1.5)
        result = await operator.read()
    else:
        before = json.loads((directory / "prepare-restart.json").read_text())
        result = await operator.wait(lambda v:v["IoHealthy"],"Controller did not reconnect after restart",90)
        assert not result["Armed"] and not result["AutoMode"] and not result["HmiRemoteEnabled"]
        assert result["Owner"] == 0 and not result["MotorEnableA"] and not result["MotorEnableB"]
        for tag in ("RequestedTargetPct","RequestedTargetBPct","RequestedFlowM3s"):
            assert abs(result[tag]-before[tag])<0.001, f"Retained setting lost: {tag}"
        for tag in ("PositionPct","PositionBPct"):
            assert abs(result[tag]-before[tag])<1.5, f"Physical position lost: {tag}"
        await asyncio.sleep(2)
        after = await operator.read()
        assert abs(after["PositionPct"]-result["PositionPct"])<0.02 and abs(after["PositionBPct"]-result["PositionBPct"])<0.02, "Restart moved an unarmed outlet"
    (directory / f"{name}.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"phase":name,"result":"passed","observations":result},indent=2))


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase",choices=("operating","field-down","field-up","prepare-restart","restart"))
    args = parser.parse_args()
    deadline = time.monotonic()+90
    while True:
        try:
            client = await connect("operator")
            break
        except (OSError,asyncio.TimeoutError):
            if time.monotonic() >= deadline:
                raise
            await asyncio.sleep(1)
    try:
        namespace = await client.get_namespace_index(REGISTER["namespace_uri"])
        await phase(Operator(client,namespace),args.phase)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
