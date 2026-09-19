#!/usr/bin/env python3
"""Check allocations, source lineage, and declared campaign evidence contracts.

This validates document contracts, not runtime reachability or difficulty.
Run with: python3 cinder-typhoon/design/validate_design.py
"""
from collections import Counter
import csv
import json
from itertools import product
from pathlib import Path
import re

from render_portfolio import render
from validate_challenges import validate as validate_challenges

BASE = Path(__file__).resolve().parent
TIERS = ('easy', 'medium', 'hard', 'expert', 'elite')
EXPECTED = {
    'Training': (4, 16),
    'KeplerOps': (31, 104),
    'ARWC': (35, 120),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_capabilities(operations, entry_nodes, graph):
    """Enumerate minimal declared paths; preserve every AND join within ORs."""
    nodes = {}
    for ident, entry in entry_nodes.items():
        nodes[ident] = dict(operation=entry['operation'],
                            conditional_ceiling=entry['tier'],
                            requires_any=[entry['requires_all']])
    internal_ids = {n['id'] for n in graph['nodes']}
    require(len(internal_ids) == len(graph['nodes']), 'Duplicate capability node')
    require(not internal_ids.intersection(nodes), 'Capability ID overlaps entry ID')
    actual_external = set()
    for node in graph['nodes']:
        ident = node['id']
        require(node['output'].strip(), f'Empty capability output: {ident}')
        alternatives = node['requires_any']
        require(alternatives and all(alternatives), f'Unconditional capability: {ident}')
        for deps in alternatives:
            require(len(deps) == len(set(deps)), f'Duplicate dependency: {ident}')
            actual_external.update(d for d in deps if d not in internal_ids)
        owner, tier = node['operation'], node['conditional_ceiling']
        if owner:
            require(owner in operations, f'Unknown capability owner: {ident}')
            require(tier in TIERS, f'Unknown capability tier: {ident}')
            require(operations[owner][tier] > 0, f'Unfunded capability tier: {ident}')
            require(operations[owner]['primary_work'] != 'AI',
                    f'Main capability depends on an AI target: {ident}')
        else:
            require(tier is None, f'Unscored join has a tier: {ident}')
        nodes[ident] = node
    require(actual_external == set(graph['external_nodes']), 'External capability drift')
    require(actual_external <= set(entry_nodes), 'Missing entry output')
    require(graph['aliases'] == {'ENVELOPE': 'W25.ENVELOPE', 'MODE': 'W25.MODE',
                                 'CONSEQUENCE_PLAN': 'W29.PLAN'}, 'Capability alias drift')
    for ident, node in nodes.items():
        require(all(d in nodes for deps in node['requires_any'] for d in deps),
                f'Missing capability dependency: {ident}')

    memo = {}

    def paths(ident, visiting=()):
        require(ident not in visiting, f'Capability cycle through {ident}')
        if ident in memo:
            return memo[ident]
        candidates = set()
        for deps in nodes[ident]['requires_any']:
            alternatives = [paths(d, visiting + (ident,)) for d in deps]
            for choices in product(*alternatives):
                candidates.add(frozenset({ident}).union(*choices))
        minimal = set()
        for path in sorted(candidates, key=len):
            if not any(earlier <= path for earlier in minimal):
                minimal.add(path)
        memo[ident] = minimal
        return minimal

    for ident in nodes:
        paths(ident)

    def ceiling(path):
        return max(TIERS.index(nodes[n]['conditional_ceiling'])
                   for n in path if nodes[n]['conditional_ceiling'] is not None)

    for ident in ('CORPORATE', 'OT_READ', 'PROCESS_INTERPRETATION', 'W29.PLAN'):
        require(min(map(ceiling, paths(ident))) <= TIERS.index('medium'),
                f'No ordinary medium path to {ident}')
    for ident in ('CORPORATE', 'OT_READ'):
        require(all(ceiling(path) <= TIERS.index('medium') for path in paths(ident)),
                f'An ordinary entry/visibility alternative exceeds medium: {ident}')
    require(nodes['W30.RESULT']['conditional_ceiling'] == 'medium',
            'Final effect adds a harder local barrier')
    final_paths = paths('W30.RESULT')
    required = set(graph['required_final_evidence'])
    # Required evidence is fixed independently of the editable graph declaration.
    expected = {'MAPPING', 'W09.DATA', 'W21.REVISION', 'W25.ENVELOPE',
                'W25.MODE', 'W29.PLAN'}
    require(required == expected, 'Required final evidence contract changed')
    for path in final_paths:
        require(required <= path, 'A finale route omits required current evidence')
        require('CONTROL' in path, 'A finale route has no control authority')
        require(ceiling(path) >= TIERS.index('hard'), 'Finale bypasses control difficulty')
        owners = {nodes[n]['operation'] for n in path}
        require(not owners.intersection(graph['optional_operations_excluded_from_final']),
                'An optional operation became a mandatory-path dependency')
    require(min(map(ceiling, final_paths)) == TIERS.index('hard'),
            'No complete hard-or-easier finale route')
    require(any('W19.MAP' in path for path in final_paths), 'W19 alternative disappeared')
    require(any('W18.MAP' in path for path in final_paths), 'Ordinary mapping disappeared')
    for terminal in graph['external_nodes']:
        require(any(terminal in path and not (actual_external - {terminal}).intersection(path)
                    for path in final_paths), f'Entry route cannot independently reach finale: {terminal}')
    print(f'Main campaign: {len(internal_ids)} capability outputs/joins; '
          f'{len(final_paths)} minimal declared finale closures preserve all required evidence')
    return final_paths


def main():
    with (BASE / 'portfolio.csv').open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    operations = {}
    catalog = (BASE / 'reference-catalog.md').read_text()
    references = set(re.findall(r'^## (C\d+)\s*$', catalog, re.M))
    totals = Counter()
    for row in rows:
        ident = row['id']
        require(ident not in operations, f'Duplicate operation: {ident}')
        require(row['phase'] in EXPECTED, f'Unknown phase: {ident}')
        for tier in TIERS:
            row[tier] = int(row[tier])
            require(row[tier] >= 0, f'Negative allocation: {ident}/{tier}')
            totals[tier] += row[tier]
        require(sum(row[t] for t in TIERS) > 0, f'Empty operation: {ident}')
        refs = row['references'].split()
        require(all(ref in references or ref == 'ATLAS' for ref in refs),
                f'Unknown reference: {ident}')
        if sum(row[t] for t in TIERS[2:]):
            require(any(ref in references for ref in refs),
                    f'Hard operation has no named CTF precedent: {ident}')
        if row['primary_work'] == 'AI':
            require(not sum(row[t] for t in TIERS[2:]),
                    f'AI-target work exceeds medium: {ident}')
        operations[ident] = row

    rendered = (BASE / 'operation-portfolio.md').read_text()
    require(rendered == render(), 'Portfolio rendering differs from the authoritative CSV')
    for phase, (count, allocation) in EXPECTED.items():
        group = [r for r in rows if r['phase'] == phase]
        tier_totals = [sum(r[t] for r in group) for t in TIERS]
        require(len(group) == count, f'Operation count drift: {phase}')
        require(sum(tier_totals) == allocation, f'Allocation drift: {phase}')
        if phase != 'Training':
            require(all(tier_totals), f'Organization missing a tier: {phase}')
        summary = '| ' + ' | '.join(map(str, [phase, count, allocation] + tier_totals)) + ' |'
        require(summary in rendered, f'Rendered allocation drift: {phase}')
        print(f'{phase}: {count} operations, {allocation} slots; {tier_totals}')
    require(len(rows) == 70 and sum(totals.values()) == 240, 'Total count drift')
    for row in rows:
        tier_text = ', '.join(f'{row[t]}{abbr}' for t, abbr in zip(TIERS, 'EMHXL') if row[t])
        require(f"| {row['id']}: {row['operation']} | {tier_text} |" in rendered,
                f'Rendered operation drift: {row["id"]}')

    graph = json.loads((BASE / 'entry-routes.json').read_text())
    require(graph['join_ceiling'] == 'medium', 'Entry join ceiling changed')
    nodes = {node['id']: node for node in graph['nodes']}
    require(len(nodes) == len(graph['nodes']), 'Duplicate entry node')
    ownership = Counter()
    for ident, node in nodes.items():
        require(node['operation'] in operations, f'Unknown owner: {ident}')
        require(node['tier'] in TIERS[:2], f'Entry exceeds medium: {ident}')
        require(not node['model_inference_required'], f'Entry requires inference: {ident}')
        require(all(dep in nodes for dep in node['requires_all']), f'Missing dependency: {ident}')
        ownership[node['operation'], node['tier']] += 1
    for (owner, tier), count in ownership.items():
        require(count <= operations[owner][tier], f'Entry overbooks allocation: {owner}/{tier}')

    def closure(ident, visiting=()):
        require(ident not in visiting, f'Cycle through {ident}')
        result = {ident}
        for dep in nodes[ident]['requires_all']:
            result |= closure(dep, visiting + (ident,))
        return result

    routes = graph['entry_routes']
    require(len(routes) == 2, 'Expected two ordinary entry routes')
    closures = []
    for route in routes:
        c = closure(route['terminal'])
        expected_length = {'package': 6, 'diagnostic': 7}[route['id']]
        require(route['expected_achievements'] == expected_length,
                f'Entry route declared count drift: {route["id"]}')
        require(len(c) == expected_length, f'Entry route length drift: {route["id"]}')
        closures.append(c)
        print(f'Entry {route["id"]}: {len(c)} achievements, max medium, no model dependency')
    require(closures[0] != closures[1], 'The two routes are identical')
    require(not (closures[0] <= closures[1] or closures[1] <= closures[0]),
            'One route requires completing the other')
    require(set.union(*closures) == set(nodes), 'Unreachable entry ledger node')
    require(len({route['effect'] for route in routes}) == 1, 'Routes promise different capabilities')

    check_capabilities(operations, nodes,
                       json.loads((BASE / 'capability-routes.json').read_text()))
    cards = re.findall(r'^\| ([KW]\d+\.\d+) \| ([EMHXL]) \|',
                       (BASE / 'campaign-operations.md').read_text(), re.M)
    require(len(cards) == 20 and len({c[0] for c in cards}) == 20,
            'Expected twenty unique new card contracts')
    expected_new = {'K29', 'K30', 'K31', 'W33', 'W34', 'W35'}
    card_counts = Counter((ident.split('.')[0], tier) for ident, tier in cards)
    require({owner for owner, tier in card_counts} == expected_new, 'New card owners changed')
    for owner in expected_new:
        for tier, abbr in zip(TIERS, 'EMHXL'):
            require(card_counts[owner, abbr] == operations[owner][tier],
                    f'New card allocation mismatch: {owner}/{tier}')
    with (BASE / 'portfolio-v2.csv').open(newline='') as handle:
        old = {r['id']: sum(int(r[t]) for t in TIERS) for r in csv.DictReader(handle)}
    removed = sum(old[i] - sum(operations[i][t] for t in TIERS) for i in old)
    require(removed == 20, 'Audit no longer removes twenty allocations')
    require(sum(sum(operations[i][t] for t in TIERS) for i in expected_new) == removed,
            'Audit replacement capacity differs from removed capacity')

    validate_challenges()

    for path in BASE.parent.rglob('*.md'):
        text = path.read_text()
        for target in re.findall(r'\]\(([^)]+)\)', text):
            if re.match(r'(?:https?://|mailto:|#)', target):
                continue
            filename = target.split('#', 1)[0].strip('<>')
            require((path.parent / filename).exists(), f'Broken local link in {path.name}: {target}')
    for ref in re.findall(r'reference-catalog\.md#(c\d+)', rendered):
        require(ref.upper() in references, f'Broken catalog anchor: {ref}')
    print(f'{len(references)} source entries; all upper-tier operations have named lineage')
    print('PASS: allocation audit, rendered portfolio, entry/capability closures, new cards, AI ceiling, and local links')
    print('Not tested: runtime, cognitive difficulty, source reproduction, cost, or player experience')


if __name__ == '__main__':
    main()
