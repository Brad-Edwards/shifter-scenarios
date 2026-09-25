#!/usr/bin/env python3
"""Validate the complete challenge graph and its agreement with the briefs.

Uses only the Python standard library. AND groups live inside OR alternatives.
Enumerates minimal prerequisite sets; does not infer solve times or prove that
an implementation supplies the capability its brief promises.
"""
import argparse
from collections import Counter
from copy import deepcopy
import csv
import json
from pathlib import Path
import re

BASE = Path(__file__).resolve().parent
BRIEFS = BASE / 'challenges'
TIERS = {'Easy': 0, 'Medium': 1, 'Hard': 2, 'Expert': 3, 'Elite': 4}
PHASE_INDEX = {'Training': 'training.md', 'KeplerOps': 'keplerops.md', 'ARWC': 'arwc.md'}
ROOT_TEXT = {'the supplied training workspace': 'TRAINING',
             'the supplied KeplerOps developer foothold': 'FOOTHOLD'}
CARD_ID = re.compile(r'[TKW]\d{2}\.\d+')
TECHNICAL_SECTIONS = ('Surface and normal behavior', 'Vulnerability and intended solution',
                      'Evidence and completion', 'Boundaries and reset', 'Author checks')


class DesignError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise DesignError(message)


def read_json(path):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f'Duplicate JSON key in {path.name}: {key}')
            result[key] = value
        return result
    try:
        return json.loads(path.read_text(), object_pairs_hook=unique_keys)
    except json.JSONDecodeError as error:
        raise DesignError(f'Invalid JSON in {path.name}: {error}') from error


def canonical(groups):
    return tuple(sorted(tuple(sorted(g)) for g in groups))


def parse_requirements(text):
    """Parse the briefs' small AND/OR grammar, including grouped alternatives."""
    expression = text.strip().removesuffix('.')
    if expression in ROOT_TEXT:
        return [[ROOT_TEXT[expression]]]
    expression = re.sub(r'\[([^]]+)\]\([^)]+\)',
                        lambda m: m[1].split(' — ')[0].split(' / ')[0], expression)
    tokens = re.findall(r'\(|\)|\bAND\b|\bOR\b|[A-Z][A-Z0-9_.]*', expression)
    require(''.join(tokens) == re.sub(r'\s+', '', expression),
            f'Unrecognized prerequisite expression: {text}')
    pos = 0

    def atom():
        nonlocal pos
        require(pos < len(tokens), f'Incomplete prerequisite expression: {text}')
        token = tokens[pos]
        pos += 1
        if token == '(':
            value = disjunction()
            require(pos < len(tokens) and tokens[pos] == ')', f'Missing parenthesis: {text}')
            pos += 1
            return value
        require(token not in ('AND', 'OR', ')'), f'Unexpected {token}: {text}')
        return [[token]]

    def conjunction():
        nonlocal pos
        value = atom()
        while pos < len(tokens) and tokens[pos] == 'AND':
            pos += 1
            right = atom()
            value = [a + b for a in value for b in right]
        return value

    def disjunction():
        nonlocal pos
        value = conjunction()
        while pos < len(tokens) and tokens[pos] == 'OR':
            pos += 1
            value += conjunction()
        return value

    result = disjunction()
    require(pos == len(tokens), f'Trailing prerequisite tokens: {text}')
    return result


def check_design_sections(text, status, ident):
    require(status in ('Challenge brief', 'Technical draft'), f'Unexpected design stage: {ident}')
    matches = list(re.finditer(r'^## Technical design\n(.*?)(?=^## |\Z)', text, re.M | re.S))
    require(len(matches) == 1, f'Missing/duplicate technical design section: {ident}')
    technical = matches[0][1]
    if status == 'Challenge brief':
        require(not technical.strip(), f'Technical content in brief-only stage: {ident}')
    else:
        sections = tuple('Boundaries' if ident.startswith('T') and section == 'Boundaries and reset'
                         else section for section in TECHNICAL_SECTIONS)
        for section in sections:
            parts = re.findall(r'^### ' + re.escape(section) + r'\n(.*?)(?=^### |\Z)',
                               technical, re.M | re.S)
            require(len(parts) == 1 and parts[0].strip(),
                    f'Missing/empty/duplicate technical subsection: {ident}/{section}')
    for section in ('Hint 1', 'Hint 2', 'Hint 3'):
        parts = re.findall(r'^### ' + re.escape(section) + r'\n(.*?)(?=^#{2,3} |\Z)',
                           text, re.M | re.S)
        require(len(parts) == 1 and not parts[0].strip(),
                f'Reserved hint is missing, duplicated, or populated: {ident}/{section}')
    outside = text[:matches[0].start()] + text[matches[0].end():]
    require('```' not in outside and
            not re.search(r'^#+ .*\b(solution|implementation)\b', outside, re.M | re.I),
            f'Solution/implementation material outside technical design: {ident}')


def load_briefs():
    result = {}
    for path in sorted(BRIEFS.glob('[TKW][0-9][0-9]/*.md')):
        text = path.read_text()
        ident = path.stem
        require(CARD_ID.fullmatch(ident) is not None, f'Bad challenge filename: {path}')
        require(ident not in result, f'Duplicate challenge ID: {ident}')
        heading = re.match(r'# ([TKW]\d{2}\.\d+): (.+)\n', text)
        require(heading and heading[1] == ident, f'Heading/filename mismatch: {path}')
        pairs = re.findall(r'^\| ([^|]+?) \| ([^|]+?) \|$', text, re.M)
        fields = dict(pairs)
        require(len(fields) == len(pairs), f'Duplicate metadata field: {ident}')
        require(fields.get('Primary work'), f'Missing activity category: {ident}')
        require(fields.get('Proposed difficulty') in TIERS, f'Invalid tier: {ident}')
        require(fields.get('Phase') in PHASE_INDEX, f'Invalid phase: {ident}')
        owner = ident.split('.')[0]
        require(path.parent.name == owner and fields.get('Operation', '').startswith(owner + ':'),
                f'Operation/ID mismatch: {ident}')
        for section in ('Challenge description — player-facing', 'Story purpose',
                        'Prerequisites and starting position', 'Completion and downstream use',
                        'Difficulty and inspiration'):
            match = re.search(r'^## ' + re.escape(section) + r'\n(.*?)(?=^## |\Z)', text, re.M | re.S)
            require(match and match[1].strip(), f'Missing/empty section: {ident}/{section}')
        check_design_sections(text, fields.get('Design status'), ident)
        match = re.search(r'^\*\*Required access or evidence:\*\* (.+)$', text, re.M)
        require(match, f'Missing prerequisite field: {ident}')
        result[ident] = dict(path=path, title=heading[2], operation=owner,
                            phase=fields['Phase'], category=fields['Primary work'],
                            status=fields['Design status'],
                            tier=TIERS[fields['Proposed difficulty']], tier_name=fields['Proposed difficulty'],
                            requires_any=parse_requirements(match[1]), text=text)
    return result


def minimize(candidates):
    kept = []
    for candidate in sorted(set(candidates), key=lambda s: (len(s), tuple(sorted(s)))):
        if not any(previous <= candidate for previous in kept):
            kept.append(candidate)
    return tuple(kept)


class Graph:
    def __init__(self, data, briefs):
        require(data.get('schema_version') == 1, 'Unsupported graph schema')
        require(data.get('roots') == ['FOOTHOLD', 'TRAINING'], 'Unexpected graph roots')
        self.roots = set(data['roots'])
        self.cards = data['challenges']
        self.capabilities = data['capabilities']
        require(set(self.cards) == set(briefs), 'Graph/brief inventory mismatch')
        require(not (set(self.cards) & set(self.capabilities) or
                     self.roots & (set(self.cards) | set(self.capabilities))), 'Overlapping node IDs')
        self.briefs = briefs
        self.edges = {i: n['requires_any'] for i, n in self.cards.items()}
        self.edges.update(self.capabilities)
        known = set(self.edges) | self.roots
        for ident, groups in self.edges.items():
            require(isinstance(groups, list) and groups, f'No alternatives: {ident}')
            for group in groups:
                require(isinstance(group, list) and group, f'Empty AND group: {ident}')
                require(all(isinstance(d, str) for d in group), f'Invalid dependency type: {ident}')
                require(len(group) == len(set(group)), f'Duplicate AND member: {ident}')
                require(set(group) <= known, f'Unknown dependencies: {ident}: {set(group) - known}')
            require(len(canonical(groups)) == len(set(canonical(groups))), f'Duplicate OR alternative: {ident}')
        self.memo = {}
        for ident in self.edges:
            self.paths(ident)

    def paths(self, ident, visiting=()):
        require(ident not in visiting, f'Dependency cycle: {" -> ".join((*visiting, ident))}')
        if ident in self.roots:
            return (frozenset({ident}),)
        if ident in self.memo:
            return self.memo[ident]
        candidates = []
        for group in self.edges[ident]:
            joined = (frozenset({ident}),)
            for dep in group:
                options = self.paths(dep, (*visiting, ident))
                joined = minimize(a | b for a in joined for b in options)
            candidates.extend(joined)
        self.memo[ident] = minimize(candidates)
        return self.memo[ident]

    def scored(self, path):
        return set(path) & set(self.cards)

    def ceiling(self, path):
        return max((self.briefs[i]['tier'] for i in self.scored(path)), default=-1)

    def ordinary(self, ident):
        return [p for p in self.paths(ident) if self.ceiling(p) <= TIERS['Medium']]

    def every_path_has(self, ident, required):
        required = set(required)
        for path in self.paths(ident):
            require(required <= path, f'{ident} omits required evidence/authority: {sorted(required - path)}')

    def frontier(self, completed):
        earned = set(completed) | self.roots
        while True:
            additions = {i for i, groups in self.capabilities.items()
                         if any(set(group) <= earned for group in groups)} - earned
            if not additions:
                break
            earned.update(additions)
        return [i for i in self.cards if i not in earned and
                any(set(group) <= earned for group in self.edges[i])]


def check_campaign(graph):
    """Independent design contracts: these are not derived from editable edges."""
    producers = {'G01': 'K01.1', 'G02': 'K25.2', 'G03': 'K05.1', 'A01': 'K06.1',
                 'A03': 'K26.1', 'A04': 'K26.2', 'B01': 'K17.1', 'B02': 'K27.1',
                 'B03': 'K27.2', 'B04': 'K27.3', 'W03.READ': 'W03.3', 'W09.DATA': 'W09.3',
                 'W13.SESSION': 'W13.4', 'W14.READ': 'W14.3', 'W17.OBS': 'W17.4',
                 'W18.MAP': 'W18.4', 'W19.MAP': 'W19.4', 'W21.REVISION': 'W21.2',
                 'W25.ENVELOPE': 'W25.1', 'W25.MODE': 'W25.4', 'W15.APPROVAL': 'W15.4',
                 'W26.CONTROL': 'W26.4', 'W28.CONTROL': 'W28.3', 'W29.PLAN': 'W29.3',
                 'W30.RESULT': 'W30.2'}
    for alias, owner in producers.items():
        require(graph.capabilities.get(alias) == [[owner]], f'Capability producer changed: {alias}')
    for ident, brief in graph.briefs.items():
        for path in graph.paths(ident):
            if brief['phase'] == 'Training':
                require('TRAINING' in path and 'FOOTHOLD' not in path, f'Training has campaign gate: {ident}')
            else:
                require('FOOTHOLD' in path and 'TRAINING' not in path, f'Campaign depends on training: {ident}')
            if brief['phase'] == 'ARWC':
                require(bool({'K26.2', 'K27.3'} & path), f'ARWC challenge bypasses entry: {ident}')
    expected_entries = {
        'A04': {'K01.1', 'K25.2', 'K05.1', 'K06.1', 'K26.1', 'K26.2'},
        'B04': {'K01.1', 'K25.2', 'K05.1', 'K17.1', 'K27.1', 'K27.2', 'K27.3'}}
    for terminal, expected in expected_entries.items():
        paths = graph.ordinary(terminal)
        require(paths and all(graph.scored(p) == expected for p in paths),
                f'Ordinary medium entry changed or disappeared: {terminal}')
    for target in ('CORPORATE', 'OT_READ', 'PROCESS_INTERPRETATION', 'W29.PLAN'):
        require(graph.ordinary(target), f'No medium-or-easier route: {target}')
        for entry, other in (('K26.2', 'K27.3'), ('K27.3', 'K26.2')):
            require(any(entry in p and other not in p for p in graph.ordinary(target)),
                    f'{entry} cannot independently reach {target}')
    require(any('W09.4' in p and 'W14.3' not in p for p in graph.ordinary('OT_READ')),
            'Integration read route lost')
    require(any('W14.3' in p and 'W09.4' not in p for p in graph.ordinary('OT_READ')),
            'Contractor read route lost')
    graph.every_path_has('PROCESS_INTERPRETATION', ['MAPPING', 'W09.DATA', 'W21.REVISION', 'ENVELOPE'])
    graph.every_path_has('W26.CONTROL', ['W13.SESSION', 'W15.APPROVAL'])
    graph.every_path_has('W28.CONTROL', ['W21.REVISION'])
    required = ['PROCESS_INTERPRETATION', 'CONTROL', 'MODE', 'CONSEQUENCE_PLAN',
                'W09.3', 'W21.2', 'W25.1', 'W25.4', 'W29.3']
    graph.every_path_has('W30.RESULT', required)
    excluded = {'K29', 'K30', 'K31', 'W16', 'W22', 'W23', 'W24', 'W27', 'W33', 'W34', 'W35'}
    for path in graph.paths('W30.RESULT'):
        require(bool({'W18.4', 'W19.4'} & path), 'Finale has no mapping result')
        require(bool({'W26.4', 'W28.3'} & path), 'Finale has no control result')
        require(not {i.split('.')[0] for i in graph.scored(path)} & excluded,
                'Optional operation became a finale prerequisite')
        require(not any(graph.briefs[i]['category'] == 'AI' for i in graph.scored(path)),
                'Main campaign depends on an AI target')
    require(min(graph.ceiling(p) for p in graph.paths('W30.RESULT')) == TIERS['Hard'],
            'Finale lost its complete Hard-or-easier route or bypassed control difficulty')
    for entry, other in (('K26.2', 'K27.3'), ('K27.3', 'K26.2')):
        require(any(entry in p and other not in p for p in graph.paths('W30.RESULT')),
                f'Entry route cannot independently reach the ending: {entry}')
    for first, second in (('W18.4', 'W19.4'), ('W26.4', 'W28.3')):
        for producer, other in ((first, second), (second, first)):
            require(any(producer in p and other not in p for p in graph.paths('W30.RESULT')),
                    f'Finale alternative is no longer independent: {producer}')
    for path in graph.paths('K30.1'):
        require(bool({'K09.4', 'K13.4'} & path), 'Backup branch has discovery evidence but no workload access')
    graph.every_path_has('W22.4', ['W22.3', 'W21.REVISION'])
    graph.every_path_has('W24.4', ['W24.3', 'W21.REVISION'])
    for target in ('W33.1', 'W33.2', 'W34.1', 'W34.2'):
        require(any('CONTROL' not in p for p in graph.paths(target)), f'Planning-only work gated by live control: {target}')
    for target in ('W33.3', 'W33.4', 'W34.3'):
        graph.every_path_has(target, required[:4])
    for target in ('W34.1', 'W34.2', 'W34.3'):
        for path in graph.paths(target):
            require(bool({'W23.3', 'W27.3'} & path), f'{target} lacks a planning-view capability')
        for choice, other in (('W23.3', 'W27.3'), ('W27.3', 'W23.3')):
            require(any(choice in p and other not in p for p in graph.paths(target)),
                    f'{target} requires both research alternatives')


def check_documents(data, briefs):
    require(len(briefs) == 240, 'Expected 240 challenge briefs')
    counts = Counter((b['operation'], b['tier_name'].lower()) for b in briefs.values())
    with (BASE / 'portfolio.csv').open(newline='') as handle:
        portfolio = list(csv.DictReader(handle))
    operations = {row['id']: row for row in portfolio}
    require(len(operations) == len(portfolio), 'Duplicate portfolio operation')
    require(set(b['operation'] for b in briefs.values()) == {r['id'] for r in portfolio},
            'Operation inventory differs from portfolio')
    for row in portfolio:
        for tier in TIERS:
            require(counts[row['id'], tier.lower()] == int(row[tier.lower()]),
                    f'Brief allocation differs from portfolio: {row["id"]}/{tier}')
    catalog = (BASE / 'reference-catalog.md').read_text()
    refs = {r.lower() for r in re.findall(r'^## (C\d+)\s*$', catalog, re.M)}
    for ident, b in briefs.items():
        operation = operations[b['operation']]
        require(b['phase'] == operation['phase'] and b['category'] == operation['primary_work'],
                f'Brief phase/activity differs from portfolio: {ident}')
        require(canonical(b['requires_any']) == canonical(data['challenges'][ident]['requires_any']),
                f'Brief/graph prerequisite drift: {ident}')
        expression = re.search(r'^\*\*Required access or evidence:\*\* (.+)$', b['text'], re.M)[1]
        for label, target in re.findall(r'\[([^]]+)\]\(([^)]+)\)', expression):
            dep = label.split(' — ')[0].split(' / ')[0]
            if re.fullmatch(r'[GAB]\d{2}', dep):
                dep = data['capabilities'][dep][0][0]
            expected = (BRIEFS / dep.split('.')[0] / f'{dep}.md' if CARD_ID.fullmatch(dep)
                        else BASE / 'capability-routes.json')
            require((b['path'].parent / target.split('#')[0]).resolve() == expected.resolve(),
                    f'Prerequisite link points to wrong document: {ident}/{label}')
        if b['tier'] >= TIERS['Hard']:
            cited = set(re.findall(r'reference-catalog\.md#(c\d+)', b['text']))
            require(cited and cited <= refs, f'Missing/invalid named precedent: {ident}')


def index_requirements(groups, capabilities):
    def link(ident):
        if ident in ROOT_TEXT.values():
            return 'Supplied training workspace' if ident == 'TRAINING' else 'Supplied developer foothold'
        if CARD_ID.fullmatch(ident):
            return f'[{ident}]({ident.split(".")[0]}/{ident}.md)'
        if ident in ('G01', 'G02', 'G03', 'A01', 'A03', 'A04', 'B01', 'B02', 'B03', 'B04'):
            card = capabilities[ident][0][0]
            return f'[{ident} / {card}]({card.split(".")[0]}/{card}.md)'
        return f'[{ident}](arwc.md#capabilities)'
    return ' OR '.join(('(' + ' AND '.join(map(link, group)) + ')') if len(group) > 1
                       else link(group[0]) for group in groups)


def check_indexes(data, briefs, write=False):
    seen = Counter()
    for phase, filename in PHASE_INDEX.items():
        path = BRIEFS / filename
        rows = []
        for line in path.read_text().splitlines():
            match = re.match(r'^\| \[([TKW]\d{2}\.\d+): ', line)
            if match:
                ident = match[1]
                require(ident in briefs and briefs[ident]['phase'] == phase, f'Unexpected index row: {ident}')
                b = briefs[ident]
                expected = (f'| [{ident}: {b["title"]}]({b["operation"]}/{ident}.md) | {b["tier_name"]} | '
                            f'{index_requirements(data["challenges"][ident]["requires_any"], data["capabilities"])} |')
                require(write or line == expected, f'Index drift: {ident}; use --write-indexes')
                line = expected if write else line
                seen[ident] += 1
            rows.append(line)
        if write:
            path.write_text('\n'.join(rows) + '\n')
    require(set(seen) == set(briefs) and all(v == 1 for v in seen.values()), 'Index coverage/uniqueness failure')


def report(graph):
    lines = ['# Deterministic challenge dependency report', '',
             f'{len(graph.cards)} challenge nodes; {len(graph.capabilities)} capability nodes; '
             f'{len(graph.roots)} supplied roots. All nodes resolve without cycles.', '',
             'Counts below include scored prerequisites and the terminal challenge. '
             'They are content counts, not time estimates.', '',
             '| Target | Minimal prerequisite sets | Scored challenges, min–max | Lowest required tier |',
             '| --- | ---: | ---: | --- |']
    for target in ('A04', 'B04', 'CORPORATE', 'OT_READ', 'PROCESS_INTERPRETATION',
                   'CONTROL', 'W30.RESULT', 'W33.2', 'W33.4', 'W34.2', 'W34.3'):
        paths = graph.paths(target)
        sizes = [len(graph.scored(p)) for p in paths]
        tier = list(TIERS)[min(graph.ceiling(p) for p in paths)]
        lines.append(f'| {target} | {len(paths)} | {min(sizes)}–{max(sizes)} | {tier} |')
    lines += ['', 'A04 includes its optional K20 authority alternative. Its ordinary medium '
              'closure has exactly six challenges; B04 has seven.', '',
              '## Difficulty including prerequisites', '',
              '| Phase | Easy | Medium | Hard | Expert | Elite |', '| --- | ---: | ---: | ---: | ---: | ---: |']
    for phase in PHASE_INDEX:
        counts = Counter(min(graph.ceiling(p) for p in graph.paths(i))
                         for i, b in graph.briefs.items() if b['phase'] == phase)
        lines.append('| ' + phase + ' | ' + ' | '.join(str(counts[n]) for n in range(5)) + ' |')
    lines += ['', 'This table differs from the portfolio: it counts the lowest tier needed '
              'to reach and complete each challenge, including prerequisites. ARWC still '
              'contains 23 locally Easy tasks; its zero in this table reflects the Medium '
              'customer-entry requirement.', '', '## Available next work', '',
              '| Position | Available campaign challenges | Operations | Principal activities |',
              '| --- | ---: | ---: | ---: |']
    for label, target in (('Developer foothold', None), ('Corporate arrival', 'CORPORATE'), ('OT visibility', 'OT_READ')):
        completed = set() if target is None else graph.scored(min(graph.ordinary(target),
                                              key=lambda p: (len(graph.scored(p)), tuple(sorted(p)))))
        frontier = [i for i in graph.frontier(completed) if graph.briefs[i]['phase'] != 'Training']
        lines.append(f'| {label} | {len(frontier)} | {len({graph.briefs[i]["operation"] for i in frontier})} '
                     f'| {len({graph.briefs[i]["category"] for i in frontier})} |')
    lines += ['', 'Arrival rows use a shortest ordinary prerequisite set and retain unfinished '
              'supplier work. They describe availability, not a requirement to show every '
              'challenge at once.', '', '## Scope', '',
              'The smaller entry/capability ledgers summarize ordinary campaign routes. '
              'Their closure counts differ because they omit optional entry alternatives '
              'and internal challenge steps. This report uses the complete challenge ledger.', '',
              'The checker verifies declared prerequisites, alternatives, capability producers, '
              'difficulty ceilings, mandatory evidence, and agreement with the briefs and indexes. '
              'Whether an outcome is a distinct achievement and actually conveys its stated '
              'authority requires the accompanying editorial review.', '']
    return '\n'.join(lines)


def self_test(data, briefs):
    """Mutate the graph in memory; do not let document drift reject mutations for us."""
    cases = []
    def changed(label, node, groups, alias=False):
        altered = deepcopy(data)
        if alias:
            altered['capabilities'][node] = groups
        else:
            altered['challenges'][node]['requires_any'] = groups
        cases.append((label, altered))
    changed('dangling prerequisite', 'K01.1', [['MISSING']])
    changed('challenge cycle', 'K01.1', [['K01.1']])
    changed('capability cycle', 'CORPORATE', [['OT_READ']], True)
    changed('empty AND grants free access', 'K01.1', [[]])
    changed('duplicate AND member', 'K01.1', [['FOOTHOLD', 'FOOTHOLD']])
    changed('training made mandatory', 'K01.1', [['FOOTHOLD', 'T01.1']])
    changed('hard customer-entry gate', 'K25.2', [['G01', 'K04.4']])
    changed('both customer routes required', 'CORPORATE', [['A04', 'B04']], True)
    changed('ending requires both customer entries', 'W30.1',
            [['PROCESS_INTERPRETATION', 'CONTROL', 'MODE', 'CONSEQUENCE_PLAN', 'A04', 'B04']])
    changed('both control routes required', 'CONTROL', [['W26.CONTROL', 'W28.CONTROL']], True)
    changed('both mapping routes required', 'MAPPING', [['W18.MAP', 'W19.MAP']], True)
    changed('mapping replaces current evidence', 'PROCESS_INTERPRETATION', [['W19.MAP']], True)
    changed('finale omits authority', 'W30.1', [['PROCESS_INTERPRETATION', 'MODE', 'CONSEQUENCE_PLAN']])
    changed('finale omits consequence plan', 'W30.1', [['PROCESS_INTERPRETATION', 'CONTROL', 'MODE']])
    changed('optional elite becomes mandatory', 'W09.3', [['W09.1', 'W09.2', 'W16.4']])
    changed('AI target becomes mandatory', 'W09.3', [['W09.1', 'W09.2', 'K21.3']])
    changed('discovery substituted for workload access', 'K30.1', [['K09.1']])
    changed('reviewer analysis skips recovered project', 'W22.4', [['W21.REVISION']])
    changed('signer analysis skips recovered bundle', 'W24.4', [['W21.REVISION']])
    changed('early reporting gated by control', 'W34.1', [['PROCESS_INTERPRETATION', 'CONTROL', 'W23.3'],
                                                      ['PROCESS_INTERPRETATION', 'CONTROL', 'W27.3']])
    changed('live reporting loses control', 'W34.3', [['W34.2']])
    changed('both research alternatives required', 'W34.1', [['PROCESS_INTERPRETATION', 'W23.3', 'W27.3']])
    changed('live scheduler loses authority', 'W33.3', [['W33.2']])
    changed('wrong capability producer', 'W28.CONTROL', [['W27.3']], True)
    changed('ARWC bypasses customer entry', 'W01.1', [['FOOTHOLD']])
    changed('training depends on campaign', 'T01.1', [['FOOTHOLD']])
    changed('ending replaced by preparation', 'W30.RESULT', [['W30.1']], True)
    for label, altered in cases:
        try:
            check_campaign(Graph(altered, briefs))
        except DesignError:
            continue
        raise DesignError(f'Negative test was not rejected: {label}')
    # Positive grammar cases exercise grouping rather than only failure paths.
    require(canonical(parse_requirements('(K01.1 AND G02) OR (K09.1 AND G03).')) ==
            canonical([['K01.1', 'G02'], ['K09.1', 'G03']]), 'AND/OR parser error')
    require(canonical(parse_requirements('K01.1 AND (G02 OR G03).')) ==
            canonical([['K01.1', 'G02'], ['K01.1', 'G03']]), 'Grouped OR parser error')
    require(canonical(parse_requirements('(K01.1 OR K02.1) AND G02.')) ==
            canonical([['K01.1', 'G02'], ['K02.1', 'G02']]), 'Left-grouped OR parser error')
    print(f'PASS: {len(cases)} deliberately broken graphs rejected; grouped AND/OR parser cases passed')
    technical = '\n'.join(f'### {section}\n\nAuthor content.\n' for section in TECHNICAL_SECTIONS)
    empty = ('# T01.1: Example\n\n## Technical design\n\n## Hints\n\n'
             '### Hint 1\n\n### Hint 2\n\n### Hint 3\n')
    complete = empty.replace('## Technical design\n', '## Technical design\n\n' + technical)
    check_design_sections(empty, 'Challenge brief', 'test')
    check_design_sections(complete, 'Technical draft', 'test')
    section_cases = [
        ('technical content without draft status', complete, 'Challenge brief'),
        ('empty technical draft', empty, 'Technical draft'),
        ('missing technical subsection', complete.replace('### Author checks', '### Other'), 'Technical draft'),
        ('populated hint', complete.replace('### Hint 1\n', '### Hint 1\nA hint.\n'), 'Technical draft'),
        ('solution outside technical section', complete + '\n## Solution\nHidden here.\n', 'Technical draft'),
        ('duplicate technical section', complete + '\n## Technical design\n', 'Technical draft'),
        ('unknown design status', empty, 'Implemented'),
    ]
    for label, content, status in section_cases:
        try:
            check_design_sections(content, status, 'test')
        except DesignError:
            continue
        raise DesignError(f'Design-stage negative test was not rejected: {label}')
    print(f'PASS: brief/technical-draft stages accepted; {len(section_cases)} invalid documents rejected')


def validate(write_indexes=False, run_self_test=False, report_path=None):
    data = read_json(BASE / 'challenge-dependencies.json')
    briefs = load_briefs()
    graph = Graph(data, briefs)
    check_campaign(graph)
    check_documents(data, briefs)
    check_indexes(data, briefs, write=write_indexes)
    if run_self_test:
        self_test(data, briefs)
    if report_path:
        report_path.write_text(report(graph))
    print(f'PASS: {len(briefs)} briefs; allocations, full AND/OR closures, capability contracts, and document/index agreement')
    counts = Counter(b['status'] for b in briefs.values())
    print(f'Design stage: {counts["Technical draft"]} technical drafts; '
          f'{counts["Challenge brief"]} briefs awaiting technical design; all hints empty')
    print('PASS: ordinary entry has 6/7 challenges at Medium or easier; both read and control routes survive')
    print('PASS: current evidence and control required for live endings; planning-only work remains available earlier')
    return graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true', help='Run negative graph mutations in memory')
    parser.add_argument('--write-indexes', action='store_true', help='Refresh existing challenge rows from briefs/graph')
    parser.add_argument('--report', type=Path, help='Write the deterministic dependency report')
    args = parser.parse_args()
    validate(write_indexes=args.write_indexes, run_self_test=args.self_test, report_path=args.report)


if __name__ == '__main__':
    try:
        main()
    except DesignError as error:
        raise SystemExit(f'FAIL: {error}')
