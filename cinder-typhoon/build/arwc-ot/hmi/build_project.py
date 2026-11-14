"""Author a native FUXA project, with no custom browser or control service."""
import copy
import json
import pathlib
import re
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
SHOW = (1 | 2 | 4) << 8
DISPLAY = SHOW | 7
OPERATE = SHOW | 2
SVG = "http://www.w3.org/2000/svg"
XHTML = "http://www.w3.org/1999/xhtml"
ET.register_namespace("", SVG)
ET.register_namespace("html", XHTML)


class View:
    def __init__(self, spec):
        self.spec = spec
        self.items = {}
        self.svg = ET.Element("{" + SVG + "}svg", {
            "width": "1200", "height": "840", "viewBox": "0 0 1200 840",
            "style": "font-family:Arial,sans-serif;background:#f5f7f9",
        })
        self.text(30, 38, spec["name"], 26)
        self.text(30, 66, "Cairn Reach Reservoir | AST-CRR-017 | ARWC", 14)
        self.status(30, 92, "Field data", "IoHealthy", {0: "UNAVAILABLE", 1: "Healthy"}, abnormal={0})
        self.status(430, 92, "Control owner", "Owner", {0: "Unowned / disarmed", 1: "HMI", 2: "Dispatcher"})
        self.status(830, 92, "Actual mode", "AutoMode", {0: "Manual", 1: "Automatic flow"})

    def text(self, x, y, text, size=16):
        node = ET.SubElement(self.svg, "{" + SVG + "}text", {
            "x": str(x), "y": str(y), "fill": "#263645", "font-size": str(size),
        })
        node.text = text

    def shape(self, kind, **attrs):
        return ET.SubElement(self.svg, "{" + SVG + "}" + kind, {k: str(v) for k, v in attrs.items()})

    def widget(self, kind, label, x, y, tag=None, readonly=True, width=250):
        prefixes = {"value": "VAL", "html_input": "HXI", "html_select": "HXS", "html_button": "HXB"}
        labels = {"value": "Value", "html_input": "HtmlInput", "html_select": "HtmlSelect", "html_button": "HtmlButton"}
        ident = f"{prefixes[kind]}_{self.spec['id']}_{len(self.items)}"
        prop = {"permission": DISPLAY if readonly else OPERATE, "events": [], "actions": [],
                "ranges": [], "options": {}, "readonly": readonly}
        if tag:
            prop.update(variableId=tag, variable=tag, variableSrc="crr-plc")
        self.items[ident] = {"id": ident, "type": "svg-ext-" + kind, "label": labels[kind],
                             "name": label, "property": prop}
        self.text(x, y, label, 14)
        group = ET.SubElement(self.svg, "{" + SVG + "}g", {"id": ident, "type": "svg-ext-" + kind})
        if kind == "value":
            text = ET.SubElement(group, "{" + SVG + "}text", {
                "id": ident + "_text", "x": str(x), "y": str(y + 31), "font-size": "24", "fill": "#263645",
            })
            text.text = "--"
        else:
            ET.SubElement(group, "{" + SVG + "}rect", {
                "x": str(x), "y": str(y + 8), "width": str(width), "height": "36", "fill": "none", "stroke": "none",
            })
            foreign = ET.SubElement(group, "{" + SVG + "}foreignObject", {
                "id": "H-" + ident, "x": str(x), "y": str(y + 8), "width": str(width), "height": "38",
            })
            element = {"html_input": "input", "html_select": "select", "html_button": "button"}[kind]
            # FUXA inserts SVG into an HTML document. Use native unprefixed
            # foreignObject controls; an html:select becomes an unknown element.
            child = ET.SubElement(foreign, element, {
                "xmlns": XHTML,
                "id": {"input": "I-", "select": "S-", "button": "B-"}[element] + ident,
                "style": f"box-sizing:border-box;width:{width}px;height:36px;font:16px Arial;color:#263645;background:#eef1f4;border:1px solid #8795a1;border-radius:3px;padding:4px 8px",
            })
            if element == "input":
                child.set("type", "number")
                child.set("step", "any")
            if element == "button":
                child.text = label
                prop["text"] = label
        return prop

    def value(self, x, y, label, tag, unit="", digits=2):
        prop = self.widget("value", label, x, y, tag)
        prop["ranges"] = [{"type": 1, "text": unit, "fractionDigits": digits}]

    def status(self, x, y, label, tag, states, abnormal=(), readonly=True):
        prop = self.widget("html_select", label, x, y, tag, readonly)
        prop["ranges"] = [{"type": 4, "min": "", "max": "", "text": "No data", "color": "#fff1cf", "stroke": "#594000"}]
        for value, text in states.items():
            prop["ranges"].append({"type": 4, "min": value, "max": value, "text": text,
                                   "color": "#ffe0df" if value in abnormal else "#eef1f4",
                                   "stroke": "#8c1c13" if value in abnormal else "#263645"})

    def input(self, x, y, label, tag, lower, upper):
        prop = self.widget("html_input", label, x, y, tag, False)
        prop["options"] = {"type": "number", "numeric": True, "min": lower, "max": upper, "actionesc": "update"}
        prop["ranges"] = [{"type": 6, "min": lower, "max": upper, "fractionDigits": 3}]

    def button(self, x, y, label, action, parameter, tag=None):
        prop = self.widget("html_button", label, x, y, tag, action in ("onpage", "onOpenTab"))
        options = {"params": []} if action == "onRunScript" else {}
        if action == "onOpenTab":
            options = {"newTab": True, "addressType": "url"}
        prop["events"] = [{"type": "click", "action": action, "actparam": parameter, "actoptions": options}]

    def document(self):
        return {"id": self.spec["id"], "name": self.spec["name"], "type": "svg",
                "profile": {"width": 1200, "height": 840, "bkcolor": "#f5f7f9", "margin": 10, "align": "topCenter"},
                "items": self.items, "variables": {}, "svgcontent": ET.tostring(self.svg, encoding="unicode", short_empty_elements=False),
                "property": {"events": []}}


def build_project(previous: dict, namespace: int) -> dict:
    model = json.loads((HERE / "views.json").read_text())
    register = json.loads((HERE / "../site/tags.json").read_text())
    project = copy.deepcopy(previous)
    tags = {t["variable"]: {"id": t["variable"], "name": t["variable"],
            "address": f"ns={namespace};s=CRR.{t['variable']}",
            "type": {"REAL": "Float", "UINT": "UInt16", "BOOL": "Boolean"}[t["type"]],
            "daq": {"enabled": False}, "options": {}} for t in register["tags"]}
    project["devices"] = {"crr-plc": {"id": "crr-plc", "name": "Cairn Reach PLC", "type": "OPCUA",
        "enabled": True, "polling": 500, "property": {"address": "opc.tcp://plc:4840/arwc"}, "tags": tags}}
    views = []
    for spec in model["views"]:
        view = View(spec)
        if spec["id"] == "crr-overview":
            view.text(30, 190, "Reservoir and two motor-operated outlet valves", 20)
            view.shape("rect", x=40, y=230, width=275, height=260, fill="#edf3f7", stroke="#506575", **{"stroke-width": 3})
            view.shape("rect", x=43, y=315, width=269, height=172, fill="#b7d8e9")
            view.text(65, 269, "CRR reservoir", 20)
            view.value(65, 345, "Measured level", "LevelM", "m", 3)
            view.value(65, 420, "Usable volume", "UsableVolumeML", "ML", 3)
            for y, letter, position, flow in [(310, "A", "PositionPct", "FlowM3s"), (490, "B", "PositionBPct", "FlowBM3s")]:
                view.shape("path", d=f"M 315 {y} H 380 L 400 {y-14} V {y+14} L 380 {y} M 420 {y} L 400 {y-14} M 420 {y} L 400 {y+14} M 420 {y} H 580", fill="none", stroke="#347fa5", **{"stroke-width": 4})
                view.value(610, y-48, f"Outlet {letter} measured position", position, "%", 1)
                view.value(930, y-48, f"Outlet {letter} measured flow", flow, "m³/s", 3)
                view.button(610, y+15, f"Open outlet {letter}", "onpage", "crr-outlet-" + letter.lower())
            view.value(40, 580, "Measured total outlet flow", "TotalFlowM3s", "m³/s", 3)
            view.status(430, 580, "Motion authorization", "Armed", {0: "Disarmed", 1: "Armed"})
            view.text(30, 700, "Blue lines show water connections. Values are live measurements; the drawing is schematic.", 15)
        elif spec["id"] == "crr-controls":
            view.text(30, 180, "Proposed request — enter each number, then Apply", 20)
            view.input(30, 215, "Proposed outlet A (%)", "HmiTargetPct", 0, 100)
            view.input(430, 215, "Proposed outlet B (%)", "HmiTargetBPct", 0, 100)
            view.input(830, 215, "Proposed total flow (m³/s)", "HmiFlowM3s", 0, 1)
            view.status(30, 300, "Proposed mode", "HmiAutoMode", {0: "Manual position", 1: "Automatic total flow"}, readonly=False)
            view.button(430, 300, "Apply complete request", "onRunScript", "crr-apply")
            view.status(830, 300, "Dispatcher selection", "HmiRemoteEnabled", {0: "Local HMI only", 1: "Remote enabled"}, readonly=False)
            view.text(30, 405, "Accepted controller settings", 20)
            view.value(30, 440, "Accepted A manual setting", "RequestedTargetPct", "%", 1)
            view.value(430, 440, "Accepted B manual setting", "RequestedTargetBPct", "%", 1)
            view.value(830, 440, "Accepted automatic total flow", "RequestedFlowM3s", "m³/s", 3)
            view.value(30, 525, "Accepted sequence", "HmiAccepted", digits=0)
            view.value(430, 525, "Rejected sequence", "HmiRejected", digits=0)
            view.status(830, 525, "Last HMI decision", "HmiRejectReason", {int(k): v for k, v in register["commands"]["reject_reasons"].items()}, abnormal=set(range(1, 9)))
            view.button(30, 635, "OPERATOR STOP", "onSetValue", "true", "HmiStop")
            view.button(430, 635, "Clear operator stop", "onSetValue", "false", "HmiStop")
            view.status(830, 635, "Operator stop", "HmiStop", {0: "Clear", 1: "STOP ACTIVE"}, abnormal={1})
            view.text(30, 730, "Apply commits all four proposed settings. A new accepted HMI request removes remote selection.", 15)
            view.text(30, 757, "Clearing stop does not resume motion. Check permissives and apply a fresh request.", 15)
        else:
            outlet_b = spec["id"].endswith("b")
            letter = "B" if outlet_b else "A"
            position, flow, target = ("PositionBPct", "FlowBM3s", "RequestedTargetBPct") if outlet_b else ("PositionPct", "FlowM3s", "RequestedTargetPct")
            view.text(30, 190, f"Outlet {letter} motor-operated valve", 22)
            view.value(30, 235, "Measured valve position", position, "%", 1)
            view.value(430, 235, "Measured outlet flow", flow, "m³/s", 3)
            view.value(830, 235, "Accepted manual setting", target, "%", 1)
            for x, y, label, tag, states, bad in [
                (30, 340, "Permissive", "Permissive" + letter, {0: "Hold / unavailable", 1: "Available"}, {0}),
                (430, 340, "Valve motion", "Moving" + letter, {0: "Stopped", 1: "Moving"}, set()),
                (830, 340, "Manual target feedback", "AtTarget" + letter, {0: "Away from target", 1: "At target"}, set()),
                (30, 440, "Travel fault", "TravelFault" + letter, {0: "Clear", 1: "TRAVEL TIMEOUT"}, {1}),
                (430, 440, "Motion state", "MotionState" + letter, {int(k): v for k, v in register["motion_states"].items()}, {4, 5}),
            ]:
                view.status(x, y, label, tag, states, abnormal=bad)
            view.button(30, 555, "Reset PLC travel faults", "onRunScript", "crr-reset")
            view.button(430, 555, "Open site controls", "onpage", "crr-controls")
            view.text(30, 660, "Reset clears eligible PLC faults for both outlets. Acknowledging an alarm does not reset a fault.", 15)
            view.text(30, 692, "Automatic mode regulates half the total flow through each outlet. The manual setting is retained.", 15)
        view.button(830, 780, model["history"]["label"], "onOpenTab", model["history"]["url"])
        views.append(view.document())
    project["hmi"] = {"layout": {"start": "crr-overview", "autoresize": True,
        "navigation": {"mode": "fix", "type": "block", "items": [
            {"id": s["id"], "view": s["id"], "text": s["name"], "icon": "water_drop" if i == 0 else "settings", "link": "", "permission": DISPLAY}
            for i, s in enumerate(model["views"])]},
        "header": {"title": "Cairn Reach Reservoir", "alarms": "fix", "infos": "hide", "items": [], "height": 46,
                   "buttonHeight": 36, "loginInfo": "username", "language": "nothing", "dateTimeDisplay": ""},
        "showdev": False, "loginonstart": True, "show_connection_error": True, "zoom": "autoresize", "inputdialog": "false"}, "views": views}
    project["scripts"] = [
        {"id": "crr-apply", "name": "crr_apply_request", "mode": "SERVER", "sync": False, "permission": 2, "parameters": [],
         "code": 'const raw = $getTag("HmiSeen");\nconst seen = Number(raw);\nif (raw === null || raw === undefined || !Number.isInteger(seen) || seen < 0 || seen > 65535) throw new Error("HMI sequence unavailable");\nif (!await $setTag("HmiSequence", (seen % 65535) + 1)) throw new Error("HMI commit failed");'},
        {"id": "crr-reset", "name": "crr_reset_faults", "mode": "SERVER", "sync": False, "permission": 2, "parameters": [],
         "code": 'if (!await $setTag("HmiResetFaults", false)) throw new Error("PLC unavailable");\nawait new Promise(resolve => setTimeout(resolve, 150));\ntry {\n if (!await $setTag("HmiResetFaults", true)) throw new Error("Reset failed");\n await new Promise(resolve => setTimeout(resolve, 250));\n} finally { await $setTag("HmiResetFaults", false); }'},
    ]
    project["alarms"] = [{"name": a["id"], "property": {"variableId": a["tag"], "permission": OPERATE},
        "high": {"enabled": True, "min": a["active_value"], "max": a["active_value"], "text": a["text"],
                 "group": a["group"], "ackmode": "ackactive", "checkdelay": 1, "timedelay": 0,
                 "bkcolor": "#ffe0df", "color": "#8c1c13"},
        "highhigh": {"enabled": False}, "low": {"enabled": False}, "info": {"enabled": False},
        "actions": {"enabled": False, "values": []}} for a in model["alarms"]]
    validate_project(project, model, register)
    return project


def validate_project(project, model, register):
    """Check the authored bindings and permission boundary before any import."""
    tags = {t["variable"]: t for t in register["tags"]}
    assert set(project["devices"]["crr-plc"]["tags"]) == set(tags)
    assert all(not t["daq"]["enabled"] for t in project["devices"]["crr-plc"]["tags"].values())
    for spec, view in zip(model["views"], project["hmi"]["views"], strict=True):
        tree = ET.fromstring(view["svgcontent"])
        assert "<html:" not in view["svgcontent"]
        # HTML insertion ignores self-closing syntax on non-void controls and
        # can consume later widgets as malformed select content.
        assert not re.search(r"<select\b[^>]*?/>", view["svgcontent"])
        ids = {e.get("id") for e in tree.iter() if e.get("id")}
        bound = set()
        for ident, item in view["items"].items():
            assert ident in ids
            prop = item["property"]
            if prop.get("variableId"):
                tag = prop["variableId"]
                assert tag in tags
                bound.add(tag)
                if not prop["readonly"]:
                    assert tags[tag]["write"] and tag.startswith("Hmi")
                    assert prop["permission"] & 255 == 2
            if any(e["action"] == "onRunScript" for e in prop["events"]):
                assert prop["permission"] & 255 == 2
        assert set(spec.get("reads", [])) | set(spec.get("writes", [])) <= bound
    assert {a["property"]["variableId"] for a in project["alarms"]} == {a["tag"] for a in model["alarms"]}
    assert all(a["property"]["permission"] & 255 == 2 for a in project["alarms"])
    # FUXA's native alarm delays are seconds, not milliseconds.
    assert all(a["high"]["checkdelay"] == 1 and a["high"]["timedelay"] == 0 for a in project["alarms"])
    assert all(s["permission"] == 2 and s["parameters"] == [] and s["mode"] == "SERVER" for s in project["scripts"])
