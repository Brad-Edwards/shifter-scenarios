#!/usr/bin/env python3
"""Copy flag locations reported by qa agents (type 'flag' messages) into flags/placement.yaml."""
import json
import re
from pathlib import Path

ROOT = Path('/home/atomik/src/shifter-scenarios')
PLACEMENT = ROOT / 'cinder-typhoon/flags/placement.yaml'
reported = {}
for agent in ('qa1', 'qa2', 'qa3', 'qa4'):
    try:
        messages = json.loads((ROOT / f'{agent}.json').read_text())
    except (OSError, ValueError):
        continue
    for m in messages:
        if m.get('from') == agent and m.get('type') == 'flag' and m.get('card'):
            text = ' '.join(str(m.get('message') or m.get('detail') or '').split())
            location = re.split(r'\s*Verified live\.?|\s*Walkthrough:', text)[0]
            location = re.sub(r'^Flag FLAG\{[0-9a-f]{16}\}\s*(placed\s*)?', '', location).strip()
            reported[m['card']] = location.replace('"', "'")[:300]
lines = PLACEMENT.read_text().splitlines()
current, updated = None, 0
for i, line in enumerate(lines):
    match = re.match(r'  - flag_id: (\S+)', line)
    if match:
        current = match.group(1)
    elif line.startswith('    path: ') and current in reported:
        new = f'    path: "{reported[current]}"'
        if lines[i] != new:
            lines[i] = new
            updated += 1
PLACEMENT.write_text('\n'.join(lines) + '\n')
placed = sum(1 for l in lines if l.startswith('    path: ') and l != '    path: TBD')
print(f'updated {updated}; placed {placed}/240')
