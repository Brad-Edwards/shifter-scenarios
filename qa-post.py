#!/usr/bin/env python3
"""Post an overseer message to a qa channel with a timestamp later than any entry already in the file."""
import json, sys, datetime
def post(agent, message, kind="status", **extra):
    p = f"/home/atomik/src/shifter-scenarios/{agent}.json"
    m = json.load(open(p))
    now = datetime.datetime.now(datetime.timezone.utc)
    stamps = []
    for x in m:
        try: stamps.append(datetime.datetime.fromisoformat(str(x.get("timestamp","")).replace("Z","+00:00")))
        except ValueError: pass
    ts = max([now] + [s + datetime.timedelta(seconds=1) for s in stamps if s.tzinfo])
    m.append({"from": "overseer", "to": agent, "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "type": kind, "message": message, **extra})
    json.dump(m, open(p, "w"), indent=2)
    return ts
if __name__ == "__main__":
    print(post(sys.argv[1], sys.stdin.read().strip()))
