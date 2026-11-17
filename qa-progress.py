#!/usr/bin/env python3
"""Summarize e2e QA progress: latest verdict per card from qa1-qa4 channels, plus walkthrough files."""
import json
import re
from pathlib import Path

ROOT = Path('/home/atomik/src/shifter-scenarios')
CATALOG = ROOT / 'cinder-typhoon/challenges/challenges.yaml'
WALK = ROOT / 'cinder-typhoon/docs/walkthroughs'

cards = sorted(set(re.findall(r'id:\s*([TKW]\d+\.\d+)', CATALOG.read_text())),
               key=lambda c: (c[0], [int(x) for x in c[1:].split('.')]))
latest = {}
for agent in ('qa1', 'qa2', 'qa3', 'qa4'):
    path = ROOT / f'{agent}.json'
    try:
        messages = json.loads(path.read_text())
    except (OSError, ValueError):
        continue
    for m in messages:
        card = m.get('card')
        if m.get('from') != agent or not card or not re.fullmatch(r'[TKW]\d+\.\d+', str(card)):
            continue
        kind = m.get('type')
        verdict = m.get('verdict') if kind == 'result' else kind
        if verdict in ('pass', 'fail', 'blocker', 'fix'):
            latest[card] = (verdict, agent, m.get('timestamp', ''))
walks = {p.stem for p in WALK.glob('*/*.md') if p.name != 'README.md'}

status = {}
for c in cards:
    v = latest.get(c, ('untested',))[0]
    status[c] = 'pass' if v in ('pass', 'fix') else v
phases = {'T': 'Training', 'K': 'KeplerOps', 'W': 'ARWC'}
print(f"{'Phase':10} {'total':>5} {'pass':>5} {'fail':>5} {'block':>5} {'untested':>8} {'walkthru':>8}")
for p, name in phases.items():
    cs = [c for c in cards if c[0] == p]
    n = lambda s: sum(1 for c in cs if status[c] == s)
    print(f"{name:10} {len(cs):5} {n('pass'):5} {n('fail'):5} {n('blocker'):5} {n('untested'):8} {sum(1 for c in cs if c in walks):8}")
allp = sum(1 for c in cards if status[c] == 'pass')
print(f"{'ALL':10} {len(cards):5} {allp:5} {sum(1 for c in cards if status[c]=='fail'):5} "
      f"{sum(1 for c in cards if status[c]=='blocker'):5} {sum(1 for c in cards if status[c]=='untested'):8} {len(walks & set(cards)):8}")
open_items = [f"{c}:{latest[c][0]}({latest[c][1]})" for c in cards if status[c] in ('fail', 'blocker')]
print('\nOPEN:', ' '.join(open_items) or 'none')
print('PASS WITHOUT WALKTHROUGH:', ' '.join(c for c in cards if status[c] == 'pass' and c not in walks) or 'none')
