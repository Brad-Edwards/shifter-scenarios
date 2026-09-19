#!/usr/bin/env python3
"""Executable topology sketch: boxes, zones, scoped routes, and triggered events.

Run: python3 cinder-typhoon/design/model_topology.py --self-test
Optional exports: --json /tmp/cinder-topology.json --dot /tmp/cinder-topology.dot

Read-only inputs are the existing challenge briefs and dependency ledger. This
is a logical model, not a deployment specification or packet/physics simulator.
Network access is checked separately from challenge/evidence prerequisites.
Reachable services are NOT automatically compromised or forwarding traffic.
Boxes are role envelopes; co-hosted challenge services require separate scoped
state where their briefs require it. That isolation is an assumption, not proved
here. This model does not estimate resources, latency, exploitability, or cost.
It models one player's copy; isolation between deployed player networks is not
established by independent completion sets in this sketch.
"""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
import json
from pathlib import Path

from validate_challenges import (
    BASE, DesignError, Graph, check_campaign, check_documents, check_indexes,
    load_briefs, read_json, require,
)


@dataclass(frozen=True)
class Box:
    ident: str
    label: str
    zone: str


@dataclass(frozen=True)
class Link:
    ident: str
    source: str
    target: str
    modes: tuple
    requires_any: tuple = ((),)


@dataclass(frozen=True)
class Surface:
    box: str
    mode: str = 'service'


@dataclass
class Topology:
    zones: dict = field(default_factory=dict)
    boxes: dict = field(default_factory=dict)
    links: list = field(default_factory=list)
    placements: dict = field(default_factory=dict)
    # Only these boxes forward the specified channels, through explicit links.
    relays: dict = field(default_factory=dict)
    events: dict = field(default_factory=dict)


def either(*groups):
    """Each string is an AND group; multiple strings are OR alternatives."""
    return tuple(tuple(group.split()) for group in groups)


def satisfied(groups, facts):
    return any(set(group) <= facts for group in groups)


def earned(graph, completed, roots=None):
    facts = set(completed) | (graph.roots if roots is None else set(roots))
    while True:
        additions = {cap for cap, groups in graph.capabilities.items()
                     if satisfied(groups, facts)} - facts
        if not additions:
            return facts
        facts.update(additions)


def make_topology(graph):
    model = Topology()
    inventory = {
        'training': ('Training', 'Training', [
            ('t-workbench', 'Workbench'), ('t-accounts', 'Accounts'),
            ('t-developer', 'Developer artifacts'), ('t-state', 'State exercise')]),
        'k-corporate': ('KeplerOps', 'Corporate / identity', [
            ('k-dev', 'Developer foothold'), ('k-staff', 'Staff workflow'),
            ('k-identity', 'Identity services'), ('k-cert', 'Certificate service')]),
        'k-delivery': ('KeplerOps', 'Development / delivery', [
            ('k-source', 'Source and retained releases'), ('k-registry', 'Packages / inspection'),
            ('k-ci', 'CI and private test consumers'), ('k-preview', 'Preview / browser workers'),
            ('k-support', 'Support and customer delivery'), ('k-indexer', 'Native support indexer')]),
        'k-cloud': ('KeplerOps', 'Cloud services / workloads', [
            ('k-cloud-api', 'Cloud authority / job metadata'), ('k-workload', 'Workload execution'),
            ('k-data', 'Cloud data / backup services'), ('k-assistant', 'Assistant services')]),
        'a-corporate': ('ARWC', 'Corporate IT', [
            ('a-connector', 'FieldLink customer connector'), ('a-business', 'Business applications'),
            ('a-data', 'Business data / planning'), ('a-archive', 'Corporate archive / retained artifacts'),
            ('a-identity', 'Staff identity / browser workflow')]),
        'a-maintenance': ('ARWC', 'Maintenance / contractors', [
            ('a-contractors', 'Contractor portal / field exports'), ('a-approval', 'Drawing / approval workflow'),
            ('a-renderer', 'Maintenance renderer')]),
        'a-dmz': ('ARWC', 'Industrial DMZ', [
            ('a-data-bridge', 'Integration read gateway'), ('a-contractor-bridge', 'Contractor read gateway'),
            ('a-control-broker', 'Scoped maintenance broker')]),
        'a-engineering': ('ARWC', 'OT engineering / supervision', [
            ('a-hmi', 'HMI / practice / scheduler'), ('a-historian', 'Historian / tag records'),
            ('a-engineering', 'Engineering workstation / projects'), ('a-diagnostics', 'Diagnostic services')]),
        'a-control': ('ARWC', 'Process control', [
            ('a-reservoir', 'Reservoir / outlet endpoint'), ('a-distribution', 'Distribution endpoint'),
            ('a-instruments', 'Instrumentation / retained device images')]),
    }
    for zone, (org, label, boxes) in inventory.items():
        model.zones[zone] = {'organization': org, 'label': label}
        for ident, name in boxes:
            model.boxes[ident] = Box(ident, name, zone)

    # Explicit placement independent of dependency generation. Artifact means
    # retrieve/analyze a retained object, not shell access to its original host.
    assignments = [
        ('T01', 't-workbench', 'service'), ('T02', 't-accounts', 'service'),
        ('T03', 't-developer', 'service'), ('T04', 't-state', 'service'),
        ('K01', 'k-dev', 'service'), ('K03', 'k-dev', 'artifact'),
        ('K02 K09 K29', 'k-ci', 'service'), ('K04', 'k-indexer', 'service'),
        ('K05 K06 K07 K08 K26', 'k-registry', 'service'),
        ('K10 K12', 'k-preview', 'service'), ('K11 K28', 'k-source', 'artifact'),
        ('K13 K15 K30', 'k-data', 'service'), ('K14 K31', 'k-cloud-api', 'service'),
        ('K16', 'k-workload', 'service'), ('K17 K25 K27', 'k-support', 'service'),
        ('K18', 'k-staff', 'service'), ('K19', 'k-cert', 'service'),
        ('K20', 'k-identity', 'service'), ('K21 K22 K23 K24', 'k-assistant', 'service'),
        ('W01', 'a-connector', 'service'), ('W02 W03 W10 W35', 'a-business', 'service'),
        ('W04', 'a-archive', 'service'), ('W05 W06', 'a-identity', 'service'),
        ('W07 W09 W11 W34', 'a-data', 'service'), ('W08 W12 W16', 'a-archive', 'artifact'),
        ('W13', 'a-contractors', 'service'), ('W14', 'a-contractors', 'artifact'),
        ('W15', 'a-approval', 'service'), ('W17 W25', 'a-hmi', 'read'),
        ('W18', 'a-historian', 'read'), ('W19 W21 W22 W27 W32', 'a-engineering', 'artifact'),
        ('W20', 'a-instruments', 'artifact'), ('W23 W24 W31', 'a-diagnostics', 'service'),
        ('W26', 'a-renderer', 'service'), ('W28', 'a-engineering', 'service'),
        ('W29', 'a-data', 'service'), ('W30', 'a-reservoir', 'control'),
        ('W33', 'a-hmi', 'service'),
    ]
    by_operation = {}
    for operations, box, mode in assignments:
        for operation in operations.split():
            require(operation not in by_operation, f'Duplicate placement: {operation}')
            by_operation[operation] = (Surface(box, mode),)
    require(set(by_operation) == {b['operation'] for b in graph.briefs.values()},
            'Operation placement coverage mismatch')
    model.placements = {i: by_operation[b['operation']] for i, b in graph.briefs.items()}

    def place(ident, *surfaces):
        model.placements[ident] = tuple(Surface(*surface.split(':')) for surface in surfaces)

    place('K06.3', 'k-ci:service')
    place('K13.4', 'k-cloud-api:service')
    place('K14.3', 'k-data:service')
    place('K18.3', 'k-identity:service')
    place('K18.4', 'k-support:service')
    place('K19.3', 'k-staff:service')
    place('K20.2', 'k-staff:service')
    place('K20.3', 'k-registry:service', 'k-ci:service')
    place('K26.2', 'a-connector:delivery')
    place('K26.3', 'k-registry:service', 'a-connector:delivery')
    place('K27.2', 'k-support:service', 'k-registry:service')
    place('K27.3', 'a-connector:delivery')
    place('K29.2', 'k-source:service')
    place('K29.3', 'k-ci:service', 'k-registry:service')
    place('K30.1', 'k-cloud-api:service')
    place('K31.2', 'k-workload:service')
    place('K31.3', 'k-data:service')
    place('W09.4', 'a-data-bridge:service')
    place('W12.4', 'a-archive:service')
    place('W14.2', 'a-contractor-bridge:service')
    place('W14.3', 'a-contractor-bridge:service')
    place('W17.4', 'a-hmi:read', 'a-instruments:read')
    place('W18.4', 'a-historian:read', 'a-instruments:read')
    place('W21.2', 'a-engineering:artifact', 'a-instruments:read')
    place('W22.4', 'a-engineering:service')  # Retained review context, not a live control identity.
    place('W25.3', 'a-hmi:service')  # Practice, not physical actuation.
    place('W25.4', 'a-hmi:service', 'a-instruments:read')
    place('W26.4', 'a-control-broker:service')
    place('W27.3', 'a-diagnostics:service')
    place('W28.3', 'a-control-broker:service')
    place('W29.2', 'a-data:service', 'a-instruments:read')
    place('W29.3', 'a-hmi:service', 'a-data:service')
    place('W30.1', 'a-hmi:service', 'a-reservoir:control')
    place('W30.2', 'a-reservoir:control', 'a-instruments:read')
    place('W33.1', 'a-hmi:service', 'a-historian:read')
    place('W33.2', 'a-hmi:service', 'a-data:service')
    for ident in ('W33.3', 'W33.4'):
        place(ident, 'a-reservoir:control', 'a-distribution:control', 'a-instruments:read')
    place('W34.3', 'a-data:service', 'a-reservoir:control', 'a-instruments:read')

    def link(ident, source, target, modes, *gates):
        model.links.append(Link(ident, source, target, tuple(modes.split()), either(*gates) if gates else ((),)))

    # Merely sharing a subnet creates no edges. These are application/service
    # conduits, not unrestricted forwarding or a claim of obtained authority.
    for box in model.boxes.values():
        if box.zone == 'training':
            link('training-' + box.ident, 'player', box.ident, 'service artifact', 'TRAINING')
        elif box.ident.startswith('k-') and box.ident != 'k-dev':
            gates = ('B01', 'K09.4') if box.ident in ('k-staff', 'k-cert') else ('FOOTHOLD',)
            if box.ident == 'k-workload':
                gates = ('K13.4', 'K09.4', 'K14.2', 'K15.3')
            modes = 'service artifact delivery' if box.ident in ('k-registry', 'k-support') else 'service artifact'
            link('developer-' + box.ident, 'k-dev', box.ident, modes, *gates)
        elif box.zone in ('a-corporate', 'a-maintenance') and box.ident != 'a-connector':
            link('corporate-' + box.ident, 'a-connector', box.ident, 'service artifact', 'CORPORATE')

    link('package-delivery', 'k-registry', 'a-connector', 'delivery', 'A03')
    link('diagnostic-delivery', 'k-support', 'a-connector', 'delivery', 'B03')
    model.relays.update({'k-registry': {'delivery'}, 'k-support': {'delivery'}})

    link('integration-entry', 'a-connector', 'a-data-bridge', 'service artifact read', 'W03.READ W09.DATA')
    link('contractor-entry', 'a-connector', 'a-contractor-bridge', 'service artifact read', 'W13.SESSION')
    for bridge, grant in (('a-data-bridge', 'W09.4'), ('a-contractor-bridge', 'W14.READ')):
        model.relays[bridge] = {'read', 'artifact', 'service'}
        for box in model.boxes.values():
            if box.zone in ('a-engineering', 'a-control'):
                # Only the named engineering/diagnostic service surfaces are
                # published for interaction. Controller endpoints remain read-only.
                modes = 'read artifact service' if box.zone == 'a-engineering' else 'read artifact'
                link(bridge + '-' + box.ident, bridge, box.ident, modes, grant)

    # The issuance surface must be usable BEFORE CONTROL is earned. Requiring
    # CONTROL here would deadlock both challenges that establish that capability.
    link('control-issuance', 'a-connector', 'a-control-broker', 'service', 'W26.3', 'W28.2')
    link('control-entry', 'a-connector', 'a-control-broker', 'control', 'CONTROL')
    model.relays['a-control-broker'] = {'control'}
    for box in model.boxes.values():
        if box.ident in ACTUATORS:
            link('commands-' + box.ident, 'a-control-broker', box.ident, 'control', 'CONTROL')

    # Flags/validated completions cause discrete events. No time loop, hydraulic
    # model, or automatic opening when the player merely earns control.
    live = 'PROCESS_INTERPRETATION CONTROL MODE CONSEQUENCE_PLAN'
    model.events = {
        'reservoir_release': either('W30.2 ' + live),
        'costly_release_rehearsal': either('W33.3 ' + live),
        'feedback_rehearsal': either('W33.4 ' + live),
        'false_planning_decision': either('W34.2'),
        'covered_release_rehearsal': either('W34.3 ' + live),
        'procurement_loss': either('W35.3'),
    }
    return model


def accessible(model, facts, mode):
    """Return endpoint -> witnessed route; only controlled origins/relays expand."""
    origins = {'player'}
    if 'FOOTHOLD' in facts:
        origins.add('k-dev')
    if 'CORPORATE' in facts:
        origins.add('a-connector')
    routes = {origin: (origin,) for origin in sorted(origins)}
    queue = list(routes)
    while queue:
        source = queue.pop(0)
        if source not in origins and mode not in model.relays.get(source, set()):
            continue
        for edge in model.links:
            if (edge.source == source and mode in edge.modes and edge.target not in routes
                    and satisfied(edge.requires_any, facts)):
                routes[edge.target] = (*routes[source], edge.target)
                queue.append(edge.target)
    return routes


def events(model, facts):
    return {event for event, groups in model.events.items() if satisfied(groups, facts)}


def simulate(graph, model, allowed=None):
    """Optimistic solver: complete available work, never fabricate access first."""
    remaining = set(graph.cards if allowed is None else allowed)
    completed, waves = set(), []
    while remaining:
        facts = earned(graph, completed)
        routes = {mode: accessible(model, facts, mode) for mode in MODES}
        ready = sorted(i for i in remaining if satisfied(graph.edges[i], facts)
                       and all(s.box in routes[s.mode] for s in model.placements[i]))
        if not ready:
            break
        waves.append(ready)
        completed.update(ready)
        remaining.difference_update(ready)
    facts = earned(graph, completed)
    return {'completed': completed, 'remaining': remaining, 'waves': waves,
            'facts': facts, 'events': events(model, facts)}


MODES = {'service', 'artifact', 'read', 'delivery', 'control'}
PROCESS_ENDPOINTS = {'a-reservoir', 'a-distribution', 'a-instruments'}
ACTUATORS = {'a-reservoir', 'a-distribution'}


def check_structure(graph, model):
    require(model.zones and model.boxes, 'Empty topology')
    require(all(key == b.ident and b.zone in model.zones for key, b in model.boxes.items()),
            'Invalid box identity or subnet membership')
    require({b.zone for b in model.boxes.values()} == set(model.zones), 'Empty subnet')
    require(set(model.placements) == set(graph.cards), 'Challenge placement coverage differs')
    used = set()
    for ident, surfaces in model.placements.items():
        require(surfaces, f'No target surface: {ident}')
        for surface in surfaces:
            require(surface.box in model.boxes and surface.mode in MODES, f'Invalid surface: {ident}/{surface}')
            used.add(surface.box)
    require(used == set(model.boxes), f'Unused boxes: {set(model.boxes) - used}')
    known = set(graph.edges) | graph.roots
    require(len({e.ident for e in model.links}) == len(model.links), 'Duplicate link ID')
    for edge in model.links:
        require(edge.source in set(model.boxes) | {'player'} and edge.target in model.boxes,
                f'Unknown link endpoint: {edge.ident}')
        require(set(edge.modes) <= MODES and edge.modes, f'Unknown/empty link mode: {edge.ident}')
        require(edge.requires_any and all(set(g) <= known for g in edge.requires_any),
                f'Invalid link capability: {edge.ident}')
    for event, groups in model.events.items():
        require(groups and all(g and set(g) <= known for g in groups), f'Invalid event: {event}')


def assert_completes(graph, model, allowed, label):
    result = simulate(graph, model, allowed)
    if result['remaining']:
        details = []
        facts = result['facts']
        for ident in sorted(result['remaining']):
            if satisfied(graph.edges[ident], facts):
                blocked = [f'{s.box}/{s.mode}' for s in model.placements[ident]
                           if s.box not in accessible(model, facts, s.mode)]
                details.append(f'{ident}: {", ".join(blocked)}')
        raise DesignError(f'{label}: route deadlock: {"; ".join(details) or sorted(result["remaining"])}')
    return result


def shortest(graph, terminal, ceiling=None, without=()):
    options = [p for p in graph.paths(terminal) if not set(without) & p
               and (ceiling is None or graph.ceiling(p) <= ceiling)]
    require(options, f'No declared path for {terminal} without {without}')
    return graph.scored(min(options, key=lambda p: (len(graph.scored(p)), tuple(sorted(p)))))


def check_boundaries(graph, model):
    initial = earned(graph, set())
    training = earned(graph, set(), roots={'TRAINING'})
    require(not set(accessible(model, training, 'service')) & {b for b in model.boxes if b.startswith(('k-', 'a-'))},
            'Training leaks into the campaign')
    for mode in MODES:
        require(not {b for b in accessible(model, initial, mode) if b.startswith('a-')},
                f'Pre-entry access to ARWC: {mode}')
    for terminal in ('A03', 'B03'):
        facts = earned(graph, shortest(graph, terminal, ceiling=1))
        require('a-connector' in accessible(model, facts, 'delivery'), f'{terminal}: delivery path missing')
        require('a-connector' not in accessible(model, facts, 'service'),
                f'{terminal}: delivery mistaken for corporate execution')
    for terminal in ('A04', 'B04'):
        facts = earned(graph, shortest(graph, terminal, ceiling=1))
        require('a-business' in accessible(model, facts, 'service'), f'{terminal}: corporate arrival stranded')
        require(not PROCESS_ENDPOINTS & set(accessible(model, facts, 'read')), f'{terminal}: corporate access bypasses OT read routes')
    for terminal in ('W09.4', 'W14.READ', 'PROCESS_INTERPRETATION', 'W29.PLAN', 'W34.2'):
        facts = earned(graph, shortest(graph, terminal, without={'CONTROL'}))
        require(not PROCESS_ENDPOINTS & set(accessible(model, facts, 'control')),
                f'{terminal}: read/planning capability grants physical control')
        require('reservoir_release' not in events(model, facts), f'{terminal}: reservoir event fired early')
    for terminal in ('W26.CONTROL', 'W28.CONTROL'):
        facts = earned(graph, shortest(graph, terminal))
        command_targets = set(accessible(model, facts, 'control'))
        require(ACTUATORS <= command_targets, f'{terminal}: control scope incomplete')
        require('a-instruments' not in command_targets, f'{terminal}: independent instrumentation became writable')
        require('reservoir_release' not in events(model, facts), f'{terminal}: authority alone opened the gates')
    before = shortest(graph, 'W30.RESULT') - {'W30.2'}
    require('reservoir_release' not in events(model, earned(graph, before)), 'Preparation opened the gates')
    require('reservoir_release' in events(model, earned(graph, before | {'W30.2'})), 'Final completion did not open the gates')


def check_closures(graph, model):
    """Replay EVERY minimal challenge closure with no helpful extra solves."""
    count = 0
    for ident in sorted(graph.cards):
        for index, path in enumerate(graph.paths(ident), 1):
            assert_completes(graph, model, graph.scored(path), f'{ident} alternative {index}')
            count += 1
    return count


def route_matrix(graph, model):
    """The two entries x two reads x two mappings x two control routes."""
    rows = []
    choices = [('package', 'K26.2', 'K27.3'), ('diagnostic', 'K27.3', 'K26.2')]
    for entry, e, other_e in choices:
        for read, r, other_r in (('integration', 'W09.4', 'W14.3'), ('contractor', 'W14.3', 'W09.4')):
            for mapping, m, other_m in (('observations', 'W18.4', 'W19.4'), ('diagnostic', 'W19.4', 'W18.4')):
                for control, c, other_c in (('utility', 'W28.3', 'W26.4'), ('maintenance', 'W26.4', 'W28.3')):
                    paths = [p for p in graph.paths('W30.RESULT')
                             if {e, r, m, c} <= p and not {other_e, other_r, other_m, other_c, 'K20.3'} & p]
                    require(paths, f'Missing route combination: {entry}/{read}/{mapping}/{control}')
                    path = min(paths, key=lambda p: (len(graph.scored(p)), tuple(sorted(p))))
                    result = assert_completes(graph, model, graph.scored(path), 'Route matrix')
                    require('reservoir_release' in result['events'], 'Completed route has no release event')
                    rows.append({'entry': entry, 'read': read, 'mapping': mapping, 'control': control,
                                 'challenges': len(result['completed']), 'tier': list(('Easy', 'Medium', 'Hard', 'Expert', 'Elite'))[graph.ceiling(path)]})
    return rows


def self_test(graph, model):
    cases = []

    def variant(label, change, check, expected):
        bad = deepcopy(model)
        change(bad)
        cases.append((label, bad, check, expected))

    def remove(ident):
        return lambda m: setattr(m, 'links', [e for e in m.links if e.ident != ident])

    def gate(ident, groups):
        return lambda m: setattr(m, 'links', [replace(e, requires_any=groups) if e.ident == ident else e for e in m.links])

    def route(terminal, ceiling=None):
        return lambda m: assert_completes(graph, m, shortest(graph, terminal, ceiling), terminal)

    variant('package conduit removed', remove('package-delivery'), route('A04', 1), 'route deadlock')
    variant('diagnostic conduit removed', remove('diagnostic-delivery'), route('B04', 1), 'route deadlock')
    variant('integration acquisition needs its own result', gate('integration-entry', either('OT_READ')),
            route('W09.4', 1), 'route deadlock')
    variant('contractor acquisition needs its own result', gate('contractor-entry', either('W14.READ')),
            route('W14.READ', 1), 'route deadlock')
    variant('control acquisition needs control', gate('control-issuance', either('CONTROL')),
            route('W28.CONTROL'), 'route deadlock')
    variant('annex hidden behind the OT route it unlocks',
            lambda m: m.placements.update({'W03.1': (Surface('a-engineering'),)}),
            route('W09.4', 1), 'route deadlock')
    variant('early retained diagnostic placed behind OT',
            lambda m: m.placements.update({'W16.1': (Surface('a-diagnostics'),)}),
            route('W16.1', 1), 'route deadlock')
    variant('package delivery requires existing customer execution',
            lambda m: m.placements.update({'K26.2': (Surface('a-connector'),)}),
            route('A04', 1), 'route deadlock')
    variant('direct supplier-to-customer bypass',
            lambda m: m.links.append(Link('bad-direct', 'k-dev', 'a-business', ('service',))),
            lambda m: check_boundaries(graph, m), 'Pre-entry access')
    variant('read gateway also authorizes commands',
            lambda m: m.links.append(Link('bad-command', 'a-connector', 'a-reservoir', ('control',), either('OT_READ'))),
            lambda m: check_boundaries(graph, m), 'grants physical control')
    variant('control authority includes independent instrumentation',
            lambda m: m.links.append(Link('bad-instruments', 'a-control-broker', 'a-instruments', ('control',), either('CONTROL'))),
            lambda m: check_boundaries(graph, m), 'instrumentation became writable')
    variant('control automatically triggers the reservoir',
            lambda m: m.events.update({'reservoir_release': either('CONTROL')}),
            lambda m: check_boundaries(graph, m), 'authority alone opened')
    variant('command plan mistaken for executed release',
            lambda m: m.events.update({'reservoir_release': either('W30.1')}),
            lambda m: check_boundaries(graph, m), 'Preparation opened')
    for label, bad, check, expected in cases:
        try:
            check(bad)
        except DesignError as error:
            require(expected in str(error), f'{label}: rejected for an unrelated reason: {error}')
        else:
            raise DesignError(f'Broken topology accepted: {label}')
    # Player state is an input, never a mutation of shared topology. Saving and
    # restoring a completion set has identical effects; another player stays put.
    first = sorted(shortest(graph, 'W30.RESULT'))
    restored = json.loads(json.dumps(first))
    require(events(model, earned(graph, first)) == events(model, earned(graph, restored)), 'Resume changes event state')
    require(not events(model, earned(graph, set())), 'A second player inherited event state')
    print(f'PASS: {len(cases)} deliberately broken topologies/events rejected; event replay and independent progress checked')


def export_data(graph, model, matrix, count):
    return {
        'scope': 'Logical role boxes and scoped service routes; not deployment or capacity validation.',
        'zones': model.zones,
        'boxes': [asdict(box) for box in model.boxes.values()],
        'links': [asdict(edge) for edge in model.links],
        'relay_modes': {i: sorted(modes) for i, modes in model.relays.items()},
        'placements': {i: [asdict(s) for s in surfaces] for i, surfaces in model.placements.items()},
        'events': model.events,
        'validated_challenge_closures': count,
        'main_route_matrix': matrix,
    }


def dot_graph(graph, model):
    q = json.dumps
    operations = defaultdict(set)
    for ident, surfaces in model.placements.items():
        for surface in surfaces:
            operations[surface.box].add(ident.split('.')[0])
    lines = ['digraph Cinder {', '  rankdir=LR;', '  compound=true;',
             '  graph [fontname="sans-serif", label="Cinder Typhoon — logical topology sketch", labelloc=t];',
             '  node [shape=box, fontname="sans-serif", fontsize=10];',
             '  edge [fontname="sans-serif", fontsize=8];',
             '  player [label="Player workspace\nnot a target box"];']
    for zone, meta in model.zones.items():
        lines.append(f'  subgraph {q("cluster_" + zone)} {{')
        lines.append(f'    label={q(meta["organization"] + ": " + meta["label"])};')
        for box in model.boxes.values():
            if box.zone == zone:
                label = box.label + '\n' + ', '.join(sorted(operations[box.ident]))
                lines.append(f'    {q(box.ident)} [label={q(label)}];')
        lines.append('  }')
    lines.append('  player -> "k-dev" [label="supplied foothold", style=dashed];')
    for edge in model.links:
        gate = ' OR '.join(' + '.join(g) for g in edge.requires_any if g)
        label = '/'.join(edge.modes) + ('\n' + gate if gate else '')
        color = '#b34835' if 'control' in edge.modes else '#277b91' if 'delivery' in edge.modes else '#667085'
        lines.append(f'  {q(edge.source)} -> {q(edge.target)} [label={q(label)}, color={q(color)}];')
    lines.append('}')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--json', type=Path, help='Export complete graph, placements, and route results')
    parser.add_argument('--dot', type=Path, help='Export Graphviz graph; rendering is optional')
    args = parser.parse_args()
    briefs = load_briefs()
    data = read_json(BASE / 'challenge-dependencies.json')
    graph = Graph(data, briefs)
    check_campaign(graph)
    check_documents(data, briefs)
    check_indexes(data, briefs)
    model = make_topology(graph)
    check_structure(graph, model)
    check_boundaries(graph, model)
    count = check_closures(graph, model)
    matrix = route_matrix(graph, model)
    assert_completes(graph, model, set(graph.cards), 'Complete portfolio')
    operation_count = len({b['operation'] for b in briefs.values()})
    print(f'Cinder Typhoon: {len(model.boxes)} logical targets / {len(model.zones)} scenario subnets / '
          f'{operation_count} operations / {len(graph.cards)} challenges')
    print('Player workspaces, event control plane, and shared hosting are outside this target count.\n')
    for zone, meta in model.zones.items():
        boxes = [b for b in model.boxes.values() if b.zone == zone]
        print(f'{meta["organization"]:10} {meta["label"]:30} {len(boxes):2} boxes')
    print(f'\nPASS: all {count} minimal challenge closures replay without extra solves or missing access')
    print('PASS: all 16 entry/read/mapping/control route combinations reach the reservoir event')
    print('PASS: early corporate/retained-artifact work, independent routes, and control issuance remain reachable')
    print('PASS: service reachability does not grant forwarding; OT reads do not grant commands')
    print('PASS: reservoir changes only on completion events; no continuously running simulation')
    if args.self_test:
        self_test(graph, model)
    if args.json:
        args.json.write_text(json.dumps(export_data(graph, model, matrix, count), indent=2) + '\n')
        print(f'Graph/data: {args.json}')
    if args.dot:
        args.dot.write_text(dot_graph(graph, model))
        print(f'Graphviz: {args.dot}')
    print('\nAssumptions: declared service authority and isolation within shared role boxes hold.')
    print('Not established: exploit correctness, OS/root isolation, VM/container count, or event capacity.')


if __name__ == '__main__':
    try:
        main()
    except DesignError as error:
        raise SystemExit(f'FAIL: {error}')
