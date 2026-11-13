"""Author the native FBD project from the declared I/O and real block interfaces.

The Editor performs parsing and compilation. This module only creates its
documented on-disk project shape and checks our wiring before emitting it.
"""
import json
import os
import pathlib
import re
import shutil
import socket
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from project_config import operator_credentials, opcua_server, write_json


def interface(name):
    source = (ROOT / f"{name}.st").read_text()
    ports = []
    for qualifier, direction in (("INPUT", "input"), ("OUTPUT", "output")):
        section = re.search(r"VAR_"+qualifier+r"\s+(.*?)END_VAR", source, re.S)
        if not section:
            raise ValueError(f"Missing primitive {qualifier} interface in {name}")
        for variable, datatype in re.findall(r"^\s*(\w+)\s*:\s*(\w+)\s*;", section[1], re.M):
            ports.append({"name": variable, "class": direction,
                          "type": {"definition": "base-type", "value": datatype}})
    return {"name": name, "type": "function-block", "extensible": False, "variables": ports, "documentation": "Cairn Reach " + name}


def standard(name, datatype, count):
    variables = [{"name": f"IN{i+1}", "class": "input", "type": {"definition": "base-type", "value": datatype}} for i in range(count)]
    variables.append({"name": "OUT", "class": "output", "type": {"definition": "base-type", "value": datatype}})
    return {"name": name, "type": "function", "extensible": True, "variables": variables, "documentation": "Native IEC function"}


class Diagram:
    def __init__(self, variables):
        self.variables = variables
        self.nodes = []
        self.edges = []
        self.blocks = {}

    def handle(self, name, source, x, y, width, offset):
        return {"id": name, "type": "source" if source else "target", "position": "right" if source else "left",
                "glbPosition": {"x": x+width if source else x, "y": y+offset},
                "relPosition": {"x": width if source else 0, "y": offset},
                "style": {"top": offset, "right" if source else "left": 0}, "isConnectable": True}

    def block(self, name, variant, instance, x, y, order):
        inputs = [p for p in variant["variables"] if p["class"] == "input"]
        outputs = [p for p in variant["variables"] if p["class"] == "output"]
        width = 400
        height = 72 + (max(len(inputs),len(outputs))-1)*48
        left = [self.handle(p["name"], False, x,y,width,48+i*48) for i,p in enumerate(inputs)]
        right = [self.handle(p["name"], True, x,y,width,48+i*48) for i,p in enumerate(outputs)]
        node = {"id": name, "type": "block", "position": {"x":x,"y":y}, "width":width,"height":height,
                "measured": {"width":width,"height":height}, "draggable":True,"selectable":True,"selected":False,
                "data": {"numericId": str(len(self.nodes)+1), "executionOrder":order,"executionControl":False,
                         "variant": variant,"variable":{"name":instance},"handles":left+right,
                         "inputHandles":left,"outputHandles":right,"inputConnector":left[0],"outputConnector":right[0],
                         "draggable":True,"selectable":True,"deletable":True}}
        self.nodes.append(node)
        self.blocks[name] = node

    def port(self, name, port, direction):
        return next(p for p in self.blocks[name]["data"]["variant"]["variables"] if p["name"] == port and p["class"] == direction)

    def wire(self, source, output, target, input_name):
        if self.port(source,output,"output")["type"] != self.port(target,input_name,"input")["type"]:
            raise ValueError(f"FBD type mismatch: {source}.{output} -> {target}.{input_name}")
        self.edge(source,output,target,input_name)

    def edge(self, source, output, target, input_name):
        self.edges.append({"id":f"edge-{len(self.edges)+1}","source":source,"sourceHandle":output,
                           "target":target,"targetHandle":input_name,"type":"step"})

    def variable(self, block, port, expression, output=False):
        datatype = self.port(block,port,"output" if output else "input")["type"]["value"]
        if expression in self.variables:
            if self.variables[expression]["type"] != datatype:
                raise ValueError(f"Wrong variable type for {expression}")
        elif expression != "2.0":
            raise ValueError(f"Undeclared graphical variable: {expression}")
        anchor = self.blocks[block]
        peers = [p for p in anchor["data"]["variant"]["variables"] if p["class"] == ("output" if output else "input")]
        index = next(i for i,p in enumerate(peers) if p["name"] == port)
        x = anchor["position"]["x"] + (500 if output else -340)
        y = anchor["position"]["y"] + 32 + index*48
        node_id = f"{block}-{port}-{'out' if output else 'in'}"
        kind = "output-variable" if output else "input-variable"
        connector = self.handle(kind,not output,x,y,256,16)
        self.nodes.append({"id":node_id,"type":kind,"position":{"x":x,"y":y},"width":256,"height":32,
            "measured":{"width":256,"height":32},"draggable":True,"selectable":True,"selected":False,
            "data":{"numericId":str(len(self.nodes)+1),"executionOrder":anchor["data"]["executionOrder"],
                    "variable":{"id":"","name":expression},"variant":kind,"handles":[connector],
                    "inputHandles":[connector] if output else [],"outputHandles":[] if output else [connector],
                    "inputConnector":connector if output else None,"outputConnector":None if output else connector,
                    "draggable":True,"selectable":True,"deletable":True}})
        if output:
            self.edge(block,port,node_id,kind)
        else:
            self.edge(node_id,kind,block,port)

    def check(self):
        for name, node in self.blocks.items():
            for port in node["data"]["variant"]["variables"]:
                if port["class"] == "input":
                    edges = [e for e in self.edges if e["target"] == name and e["targetHandle"] == port["name"]]
                    if len(edges) != 1:
                        raise ValueError(f"{name}.{port['name']} must have exactly one input")


def generate(project):
    register = json.loads((ROOT / "tags.json").read_text())
    variables = {tag["variable"]: tag for tag in register["tags"]}
    for group in ("inputs","outputs","discrete_inputs","coils"):
        for point in register["modbus"][group]:
            variables[point["variable"]] = dict(variables.get(point["variable"],{}),**point)
    graph = Diagram(variables)
    graph.block("measurements",interface("SiteInputs"),"Inputs",400,100,1)
    graph.block("permit-a",standard("AND","BOOL",3),"",1300,100,2)
    graph.block("permit-b",standard("AND","BOOL",3),"",1300,500,3)
    graph.block("requests",interface("SiteRequests"),"Requests",2300,100,4)
    graph.block("flow-split",standard("DIV","REAL",2),"",3300,100,5)
    graph.block("outlet-a",interface("OutletControl"),"OutletA",4300,100,6)
    graph.block("outlet-b",interface("OutletControl"),"OutletB",4300,1100,7)
    graph.block("flow-total",standard("ADD","REAL",2),"",5300,100,8)
    for name in ("LevelRaw","Heartbeat"):
        graph.variable("measurements",name,name)
    for name in ("LevelM","UsableVolumeML","IoHealthy","LowLevelAlarm"):
        graph.variable("measurements",name,name,True)
    for suffix, upper in (("a","A"),("b","B")):
        graph.wire("measurements","IoHealthy",f"permit-{suffix}","IN1")
        graph.variable(f"permit-{suffix}","IN2",f"Available{upper}Raw")
        graph.variable(f"permit-{suffix}","IN3",f"Remote{upper}Raw")
        graph.wire(f"permit-{suffix}","OUT","requests",f"Available{upper}")
        graph.wire(f"permit-{suffix}","OUT",f"outlet-{suffix}","BasePermit")
    graph.wire("measurements","IoHealthy","requests","IoHealthy")
    graph.wire("measurements","LowLevelAlarm","requests","LowLevel")
    for port, variable in {"FaultA":"TravelFaultA","FaultB":"TravelFaultB","HmiStop":"HmiStop",
        "RemoteEnableInput":"HmiRemoteEnabled","HmiTargetA":"HmiTargetPct","HmiTargetB":"HmiTargetBPct",
        "HmiAutoMode":"HmiAutoMode","HmiFlow":"HmiFlowM3s","HmiSequence":"HmiSequence",
        "RemoteTargetA":"RemoteTargetPct","RemoteTargetB":"RemoteTargetBPct","RemoteAutoMode":"RemoteAutoMode",
        "RemoteFlow":"RemoteFlowM3s","RemoteSequence":"RemoteSequence"}.items():
        graph.variable("requests",port,variable)
    request_outputs = {"TargetA":"RequestedTargetPct","TargetB":"RequestedTargetBPct","FlowSetting":"RequestedFlowM3s",
        "RemoteEnabled":"HmiRemoteEnabled"}
    for name in ("AutoMode","Armed","Owner","HmiAccepted","RemoteAccepted","HmiRejected","RemoteRejected",
                 "HmiSeen","RemoteSeen","RejectReason","HmiRejectReason","RemoteRejectReason"):
        request_outputs[name] = name
    for port, variable in request_outputs.items():
        graph.variable("requests",port,variable,True)
    graph.wire("requests","FlowSetting","flow-split","IN1")
    graph.variable("flow-split","IN2","2.0")
    for suffix, upper in (("a","A"),("b","B")):
        block = f"outlet-{suffix}"
        graph.variable(block,"PositionRaw","PositionRaw" if upper == "A" else "PositionBRaw")
        graph.variable(block,"FlowRaw","FlowRaw" if upper == "A" else "FlowBRaw")
        graph.variable(block,"ResetFault","HmiResetFaults")
        graph.wire("measurements","LowLevelAlarm",block,"LowLevel")
        graph.wire("requests","Armed",block,"Armed")
        graph.wire("requests","AutoMode",block,"AutoMode")
        graph.wire("requests","Target"+upper,block,"ManualTarget")
        graph.wire("flow-split","OUT",block,"FlowSetting")
        for port, variable in {"PositionPct":"PositionPct" if upper == "A" else "PositionBPct",
            "FlowM3s":"FlowM3s" if upper == "A" else "FlowBM3s",
            "TargetRaw":"TargetRaw" if upper == "A" else "TargetBRaw","EnableCoil":"MotorEnable"+upper,
            "Permissive":"Permissive"+upper,"Moving":"Moving"+upper,"AtTarget":"AtTarget"+upper,
            "TravelFault":"TravelFault"+upper,"MotionState":"MotionState"+upper}.items():
            graph.variable(block,port,variable,True)
        graph.wire(block,"FlowM3s","flow-total","IN1" if upper == "A" else "IN2")
    graph.variable("flow-total","OUT","TotalFlowM3s",True)
    graph.check()
    declarations = []
    for name, info in variables.items():
        address = " AT "+info["iec"] if info.get("iec") else ""
        initial = " := 364" if name == "ProjectRevision" else " := 0.2" if name in ("HmiFlowM3s","RemoteFlowM3s") else ""
        declarations.append(f"  {name}{address} : {info['type']}{initial};")
    for name, datatype in (("Inputs","SiteInputs"),("Requests","SiteRequests"),("OutletA","OutletControl"),("OutletB","OutletControl")):
        declarations.append(f"  {name} : {datatype};")
    body = {"name":"main","rung":{"comment":"Cairn Reach: live I/O, PLC request arbitration, field permissives, and two outlet controls. Travel-fault feedback uses the preceding scan.","nodes":graph.nodes,"edges":graph.edges}}
    content = "PROGRAM main\nVAR\n"+"\n".join(declarations)+"\nEND_VAR\n\n"+json.dumps(body,indent=2)+"\nEND_PROGRAM\n"
    program = project / "pous/programs/main.fbd"
    program.write_text(content)
    for name in ("SiteInputs","SiteRequests","OutletControl"):
        shutil.copyfile(ROOT / f"{name}.st",project / f"pous/function-blocks/{name}.st")
    metadata = json.loads((project / "project.json").read_text())
    metadata["data"]["configuration"]["resource"]["tasks"][0]["interval"] = "T#100ms"
    write_json(project / "project.json",metadata)
    credentials = operator_credentials(ROOT.parent)
    configuration = json.loads((project / "devices/configuration.json").read_text())
    configuration.update(deviceBoard="OpenPLC Runtime v4",runtimeIpAddress="172.29.63.20",
        persistentStorage={"enabled":True,"path":"/var/run/runtime/site-retain.bin","flushSeconds":1})
    write_json(project / "devices/configuration.json",configuration)
    write_json(project / "devices/servers/CairnReachUA.json",opcua_server(register,credentials))
    groups = []
    for key, points in ((key,register["modbus"][key]) for key in ("inputs","outputs","discrete_inputs","coils")):
        groups.append({"id":key,"name":key,"functionCode":str(register["modbus"]["functions"][key]),"cycleTime":100,
            "offset":"0","length":len(points),"errorHandling":"keep-last-value",
            "ioPoints":[{"id":p["variable"],"name":p["variable"],"type":p["type"],"iecLocation":p["iec"]} for p in points]})
    write_json(project / "devices/remote/CairnReachIO.json",{"name":"CairnReachIO","protocol":"modbus-tcp",
        "modbusTcpConfig":{"transport":"tcp","host":register["modbus"]["host"],"port":502,"timeout":1000,"slaveId":1,"ioGroups":groups}})
    write_json(project / "tag-register.json",register)
    print(f"Generated native FBD project: {len(graph.blocks)} blocks, {len(graph.edges)} connections, {len(register['tags'])} public tags.")


if __name__ == "__main__":
    if socket.gethostname() != "cinder-arwc-ot-compat-363":
        raise SystemExit("Generate and compile the site project on the dedicated VM")
    os.umask(0o077)
    project = pathlib.Path(sys.argv[1]).resolve()
    if project.name != "arwc-site" or not (project / "pous/programs/main.fbd").exists():
        raise SystemExit("First create arwc-site with the official Editor's FBD scaffold")
    generate(project)
