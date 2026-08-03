#!/usr/bin/env python3

import json
import sys


with open(sys.argv[1], encoding="utf-8") as source:
    rows = json.load(source)
assert all({"record_id", "text", "label"} <= set(row) for row in rows)
print(f"records={len(rows)}")
