#!/usr/bin/env python3
"""Executable topology sketch: boxes, zones, scoped routes, and triggered events.

Run: python3 cinder-typhoon/docs/design/model_topology.py --self-test
Optional exports: --json /tmp/cinder-topology.json --dot /tmp/cinder-topology.dot

Read-only inputs are the existing challenge briefs and dependency ledger. This
is a logical model, not a deployment specification or packet/physics simulator.
Network access is checked separately from challenge/evidence prerequisites.
Authority domains belong to boxes; reaching a domain does not own its identity.
Earned execution and delegated contexts become scoped origins. Normal business
flows are usable from those origins, but do not implicitly forward callers.
Domain separation is a logical requirement, not proof of OS isolation. This
model does not estimate resources, latency, exploitability, or cost.
It models one player's copy; isolation between deployed player networks is not
established by independent completion sets in this sketch.
"""
import argparse
from collections import defaultdict
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
    kind: str = 'access'
    purpose: str = ''


@dataclass(frozen=True)
class Domain:
    ident: str
    box: str
    label: str


@dataclass(frozen=True)
class Context:
    ident: str
    endpoint: str
    requires_any: tuple
    kind: str = 'execution'
    modes: tuple = ('service', 'artifact', 'read', 'delivery', 'control', 'report', 'telemetry')


@dataclass(frozen=True)
class Surface:
    endpoint: str
    mode: str = 'service'

    @property
    def box(self):
        return self.endpoint.split('/')[0]


@dataclass
class Topology:
    zones: dict = field(default_factory=dict)
    boxes: dict = field(default_factory=dict)
    domains: dict = field(default_factory=dict)
    contexts: dict = field(default_factory=dict)
    links: list = field(default_factory=list)
    placements: dict = field(default_factory=dict)
    # Only these authority domains forward named channels through explicit links.
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
            ('a-connector', 'FieldKest customer connector'), ('a-business', 'Business applications'),
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
        ('K13 K15', 'k-data', 'service'), ('K30', 'k-data/backup', 'service'),
        ('K14 K31', 'k-cloud-api/authority', 'service'),
        ('K16', 'k-workload/scheduler', 'service'), ('K17 K25 K27', 'k-support', 'service'),
        ('K18', 'k-staff', 'service'), ('K19', 'k-cert', 'service'),
        ('K20', 'k-identity', 'service'), ('K21 K22 K23 K24', 'k-assistant', 'service'),
        ('W01', 'a-connector', 'service'), ('W02 W03 W10 W35', 'a-business', 'service'),
        ('W04', 'a-archive', 'service'), ('W05 W06', 'a-identity', 'service'),
        ('W07', 'a-data/query', 'service'), ('W09 W11 W34', 'a-data', 'service'),
        ('W08 W12 W16', 'a-archive', 'artifact'),
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

    # Local recovery and the subsequent authenticated service action are
    # distinct surfaces. Their proof owners are specified separately.
    place('K01.1', 'k-dev:service', 'k-source:service')
    place('K01.2', 'k-dev:service', 'k-support:service')
    place('K06.3', 'k-registry:service', 'k-ci:service')
    place('K13.4', 'k-cloud-api:service')
    place('K14.3', 'k-data:service')
    place('K18.3', 'k-identity:service')
    place('K18.4', 'k-support/customer-records:service')
    place('K19.3', 'k-staff:service')
    place('K20.1', 'k-identity/delegation:service')
    place('K20.2', 'k-staff/managed-record:service')
    place('K20.3', 'k-registry:service', 'k-ci/rehearsals:service')
    place('K26.2', 'a-connector:delivery')
    place('K26.3', 'k-registry:service', 'a-connector:delivery')
    place('K27.2', 'k-support:service', 'k-registry:service')
    place('K27.3', 'a-connector:delivery')
    place('K29.2', 'k-source:service')
    place('K29.3', 'k-ci/rehearsals:service', 'k-registry:service')
    place('K29.4', 'k-ci/rehearsals:service')
    place('K30.1', 'k-cloud-api/build-records:service')
    place('K31.2', 'k-workload/manage:service')
    place('K31.3', 'k-data/field-archive:service')
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
    place('W26.4', 'a-control-broker/maintenance-issuer:service')
    place('W27.3', 'a-diagnostics:service')
    place('W28.3', 'a-control-broker/utility-issuer:service')
    place('W29.2', 'a-data:service', 'a-instruments:read')
    place('W29.3', 'a-hmi:service', 'a-data:service')
    place('W30.1', 'a-hmi:service', 'a-reservoir:control')
    place('W30.2', 'a-reservoir:control', 'a-instruments:read')
    place('W33.1', 'a-hmi:service', 'a-historian:read')
    place('W33.2', 'a-hmi:service', 'a-data:service')
    for ident in ('W33.3', 'W33.4'):
        place(ident, 'a-reservoir:control', 'a-distribution:control', 'a-instruments:read')
    place('W34.1', 'a-data/planning:report', 'a-data:service')
    place('W34.2', 'a-data/planning:report', 'a-data:service')
    place('W34.3', 'a-data/planning:report', 'a-data:service', 'a-reservoir:control', 'a-instruments:read')

    configure_routes(model)

    # Validated completions permit consequence presentation/retention. The
    # in-world actions have already produced their independently observed
    # effects: a score cannot cause the process transition needed to earn it.
    # This graph does not simulate command execution or hydraulic state.
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


def configure_routes(model):
    """In-world authorities and business flows; no hosting or protocol choices."""
    for box in model.boxes.values():
        # Workload management and execution use only their named interfaces.
        if box.ident != 'k-workload':
            model.domains[box.ident] = Domain(box.ident, box.ident, 'Published interfaces')
    roles = {
        'k-ci': [('runner', 'Build job identity'), ('rehearsals', 'Private consumer submission interface'),
                 ('consumer-state', 'Private consumer state'), ('release-client', 'Release rehearsal client')],
        'k-indexer': [('worker', 'Indexer execution'), ('queue', 'Release exception queue')],
        'k-preview': [('renderer', 'Constrained preview renderer')],
        'k-support': [('staff-client', 'Support staff delegation'), ('customer-records', 'Federated customer records'),
                      ('review-item', 'Assistant duplicate-review item')],
        'k-staff': [('delegated-client', 'Staff delegation client'), ('managed-record', 'Managed identity record')],
        'k-identity': [('support-federation', 'Support application trust'), ('delegation', 'Supplier service delegation')],
        'k-cloud-api': [('workload-client', 'Limited workload identity'), ('delegated-client', 'Scoped cloud role'),
                        ('authority', 'Role and scheduling policy'), ('build-records', 'Authenticated build metadata')],
        'k-workload': [('scheduler', 'Support schedule configuration'), ('manage', 'Maintenance workload management'),
                       ('task', 'Scheduled support execution'), ('runtime', 'Maintenance runtime identity')],
        'k-data': [('export-client', 'Export destination delegation'), ('backup-client', 'Backup recovery principal'),
                   ('backup', 'Backup recovery interface'), ('source-db', 'Protected source history'),
                   ('field-archive', 'Runtime-protected field archive')],
        'k-assistant': [('completion', 'Completion job execution'), ('handover', 'Completion handover'),
                        ('review-tool', 'Duplicate-review tool identity')],
        'a-connector': [('planner-client', 'Earned planner session')],
        'a-archive': [('helper', 'Archive helper execution'), ('handover', 'Archive helper handover')],
        'a-data': [('query', 'Planner query interface'), ('query-worker', 'Reconciliation job execution'),
                   ('reconciliation', 'Protected reconciliation log'), ('planning', 'Estimate-consuming planner')],
        'a-renderer': [('worker', 'Approved maintenance renderer execution')],
        'a-control-broker': [('maintenance-issuer', 'Approval-bound client issuance'),
                             ('utility-issuer', 'Engineering client issuance')],
        'a-data-bridge': [('estimates', 'Outbound estimate publication')],
        'a-hmi': [('dispatch', 'Live supervisory command dispatcher')],
        'a-engineering': [('utility-worker', 'Constrained engineering utility execution')],
        'a-diagnostics': [('vault-worker', 'Diagnostic vault execution'), ('history', 'Retained approval history'),
                          ('estimate-output', 'Controlled estimator output'), ('program-output', 'Accepted diagnostic output'),
                          ('export-log', 'Signed calibration export')],
    }
    for box, entries in roles.items():
        for suffix, label in entries:
            ident = f'{box}/{suffix}'
            model.domains[ident] = Domain(ident, box, label)

    def context(ident, endpoint, *gates, kind='execution', modes=None):
        args = {} if modes is None else {'modes': tuple(modes.split())}
        model.contexts[ident] = Context(ident, endpoint, either(*gates) if gates else ((),), kind, **args)

    context('player', 'player', kind='workspace')
    context('developer', 'k-dev', 'FOOTHOLD')
    context('runner', 'k-ci/runner', 'K09.4')
    context('indexer', 'k-indexer/worker', 'K04.4')
    context('preview', 'k-preview/renderer', 'K12.4')
    context('completion', 'k-assistant/completion', 'K24.3')
    context('support-staff', 'k-support/staff-client', 'B01', kind='delegated identity')
    context('support-federation', 'k-identity/support-federation', 'K18.3', kind='delegated identity')
    context('staff-delegation', 'k-staff/delegated-client', 'K19.3', kind='delegated identity')
    context('release-client', 'k-ci/release-client', 'K29.2', 'K20.2', kind='delegated identity')
    context('workload-base', 'k-cloud-api/workload-client', 'K13.4', kind='delegated identity')
    context('cloud-role', 'k-cloud-api/delegated-client', 'K14.2', kind='delegated identity')
    context('export-delegation', 'k-data/export-client', 'K15.3', kind='delegated identity')
    context('backup-principal', 'k-data/backup-client', 'K30.1', kind='delegated identity')
    context('support-task', 'k-workload/task', 'K16.3')
    context('maintenance-runtime', 'k-workload/runtime', 'K31.2')
    context('customer', 'a-connector', 'CORPORATE')
    context('archive-helper', 'a-archive/helper', 'W04.3')
    context('planner', 'a-connector/planner-client', 'W06.3', kind='delegated identity')
    context('query-worker', 'a-data/query-worker', 'W07.3')
    context('maintenance-renderer', 'a-renderer/worker', 'W26.3')
    context('engineering-utility', 'a-engineering/utility-worker', 'W28.2')
    context('diagnostic-vault', 'a-diagnostics/vault-worker', 'W31.4')
    context('estimator-output', 'a-diagnostics/estimate-output', 'W23.3', kind='output control', modes='report')
    context('program-output', 'a-diagnostics/program-output', 'W27.3', kind='output control', modes='report')
    context('assistant-review', 'k-assistant/review-tool', 'K22.3', kind='scoped tool action', modes='service')

    def link(ident, source, target, modes, *gates, kind='access', purpose=''):
        model.links.append(Link(ident, source, target, tuple(modes.split()),
                                either(*gates) if gates else ((),), kind, purpose))

    # Broad published interfaces stay available for independent opening work.
    # Privileged interfaces below require an earned execution or identity context.
    for box in model.boxes.values():
        if box.zone == 'training':
            link('training-' + box.ident, 'player', box.ident, 'service artifact')
        elif box.ident.startswith('k-') and box.ident not in ('k-dev', 'k-staff', 'k-cert', 'k-workload'):
            modes = 'service artifact delivery' if box.ident in ('k-registry', 'k-support') else 'service artifact'
            link('developer-' + box.ident, 'k-dev', box.ident, modes, 'FOOTHOLD')
        elif box.zone in ('a-corporate', 'a-maintenance') and box.ident != 'a-connector':
            link('corporate-' + box.ident, 'a-connector', box.ident, 'service artifact', 'CORPORATE')

    # Normal supplier flows. A reached build or registry does not forward a
    # caller through these paths; only the named service identity can use them.
    link('source-build', 'k-source', 'k-ci', 'artifact', kind='operation', purpose='Source selected by build')
    link('build-job-dispatch', 'k-ci', 'k-ci/runner', 'service', kind='operation', purpose='Build service starts a job')
    link('runner-source', 'k-ci/runner', 'k-source', 'artifact', kind='operation', purpose='Runner source checkout')
    link('runner-package-read', 'k-ci/runner', 'k-registry', 'artifact', kind='operation', purpose='Build dependency reads')
    link('build-publication', 'k-ci', 'k-registry', 'delivery', 'A01', 'K20.3',
         kind='operation', purpose='Separately approved build publication')
    link('release-rehearsal', 'k-registry', 'k-ci/rehearsals', 'delivery', 'K29.2', 'K20.2',
         kind='operation', purpose='Candidate delivered to private consumers')
    link('consumer-state', 'k-ci/rehearsals', 'k-ci/consumer-state', 'artifact',
         kind='operation', purpose='Evaluator owns its private reference state')
    link('release-client', 'k-ci/release-client', 'k-ci/rehearsals', 'service')
    for source in ('k-ci/runner', 'k-support/staff-client'):
        for target in ('k-staff', 'k-cert'):
            link(source + '-' + target, source, target, 'service artifact')
    link('staff-service-delegation', 'k-staff/delegated-client', 'k-identity/delegation', 'service')
    link('managed-identity-record', 'k-staff/delegated-client', 'k-staff/managed-record', 'service')
    link('support-federation-use', 'k-identity/support-federation', 'k-support/customer-records', 'service')
    for source in ('k-ci/runner', 'k-cloud-api/workload-client'):
        for target in ('k-cloud-api/authority', 'k-cloud-api/build-records'):
            link(source + '-' + target, source, target, 'service')
    for source in ('k-ci/runner', 'k-cloud-api/delegated-client'):
        link(source + '-maintenance', source, 'k-workload/manage', 'service')
        link(source + '-policy', source, 'k-cloud-api/authority', 'service')
    for source in ('k-cloud-api/delegated-client', 'k-data/export-client'):
        link(source + '-schedule', source, 'k-workload/scheduler', 'service')
    link('scheduled-task-output', 'k-workload/task', 'k-data', 'artifact', kind='operation', purpose='Support job output')
    link('runtime-field-archive', 'k-workload/runtime', 'k-data/field-archive', 'service',
         kind='operation', purpose='Runtime identity evaluated by archive policy')
    link('maintenance-job-dispatch', 'k-workload/manage', 'k-workload/runtime', 'service',
         kind='operation', purpose='Workload starts under its distinct runtime identity')
    link('backup-recovery', 'k-data/backup-client', 'k-data/backup', 'service')
    link('backup-source-read', 'k-data/backup', 'k-data/source-db', 'artifact',
         kind='operation', purpose='Backup service reads source; recovery caller cannot')
    link('indexer-queue', 'k-indexer/worker', 'k-indexer/queue', 'artifact')
    link('preview-result', 'k-preview/renderer', 'k-preview', 'report', kind='operation', purpose='Compatible preview output')
    link('completion-handover', 'k-assistant/completion', 'k-assistant/handover', 'artifact')
    link('assistant-review-action', 'k-assistant/review-tool', 'k-support/review-item', 'service',
         kind='operation', purpose='Duplicate-review update; no customer delivery authority')

    link('package-delivery', 'k-registry', 'a-connector', 'delivery', 'A03')
    link('diagnostic-delivery', 'k-support', 'a-connector', 'delivery', 'B03')
    model.relays.update({'k-registry': {'delivery'}, 'k-support': {'delivery'}})

    link('archive-helper-handover', 'a-archive/helper', 'a-archive/handover', 'artifact')
    link('archive-helper-dispatch', 'a-archive', 'a-archive/helper', 'service',
         kind='operation', purpose='Archive invokes its restricted helper')
    link('planner-query', 'a-connector/planner-client', 'a-data/query', 'service')
    link('query-job-dispatch', 'a-data/query', 'a-data/query-worker', 'service',
         kind='operation', purpose='Database executes a reconciliation job')
    link('query-reconciliation', 'a-data/query-worker', 'a-data/reconciliation', 'artifact')
    link('business-planning-view', 'a-business', 'a-data/planning', 'read',
         kind='operation', purpose='Allocation workflow consumes planning decisions')
    link('renderer-approval-read', 'a-renderer/worker', 'a-approval', 'read',
         kind='operation', purpose='Validate bound inspection; cannot issue approval')
    link('renderer-dispatch', 'a-renderer', 'a-renderer/worker', 'service',
         kind='operation', purpose='Maintenance application invokes renderer')
    link('utility-dispatch', 'a-engineering', 'a-engineering/utility-worker', 'service',
         kind='operation', purpose='Published utility invocation; caller does not inherit privilege')
    link('vault-dispatch', 'a-diagnostics', 'a-diagnostics/vault-worker', 'service',
         kind='operation', purpose='Diagnostic application invokes native record service')

    link('integration-entry', 'a-connector', 'a-data-bridge', 'service artifact read', 'W03.READ W09.DATA')
    link('contractor-entry', 'a-connector', 'a-contractor-bridge', 'service artifact read', 'W13.SESSION')
    for bridge, grant in (('a-data-bridge', 'W09.4'), ('a-contractor-bridge', 'W14.READ')):
        model.relays[bridge] = {'read', 'artifact', 'service'}
        for box in model.boxes.values():
            if box.zone in ('a-engineering', 'a-control'):
                modes = 'read artifact service' if box.zone == 'a-engineering' else 'read artifact'
                link(bridge + '-' + box.ident, bridge, box.ident, modes, grant)

    # Issuance is performed from the earned service context. Neither native
    # flow control nor renderer execution is itself the resulting CONTROL grant.
    link('utility-issuance', 'a-engineering/utility-worker', 'a-control-broker/utility-issuer', 'service')
    link('maintenance-issuance', 'a-renderer/worker', 'a-control-broker/maintenance-issuer', 'service')
    link('control-entry', 'a-connector', 'a-control-broker', 'control', 'CONTROL')
    link('supervisory-command', 'a-control-broker', 'a-hmi/dispatch', 'control', 'CONTROL',
         kind='operation', purpose='Authorized maintenance request to supervisory dispatcher')
    model.relays['a-control-broker'] = {'control'}
    model.relays['a-hmi/dispatch'] = {'control'}
    for target in sorted(ACTUATORS):
        link('commands-' + target, 'a-hmi/dispatch', target, 'control', 'CONTROL',
             kind='operation', purpose='Supervisory command to actuator')
        link('observations-' + target, target, 'a-instruments', 'telemetry',
             kind='operation', purpose='Measured process outcome')
    link('instrument-history', 'a-instruments', 'a-historian', 'telemetry',
         kind='operation', purpose='Independent observations retained by historian')
    link('historian-hmi', 'a-historian', 'a-hmi', 'telemetry',
         kind='operation', purpose='Operator observations and history')
    link('engineering-hmi', 'a-engineering', 'a-hmi', 'artifact',
         kind='operation', purpose='Approved project and tag configuration')
    link('diagnostic-history', 'a-diagnostics/vault-worker', 'a-diagnostics/history', 'artifact')
    link('signed-diagnostic-export', 'a-diagnostics', 'a-diagnostics/export-log', 'artifact',
         kind='operation', purpose='Diagnostic service verifies export authorization internally')
    for source in ('a-diagnostics/estimate-output', 'a-diagnostics/program-output'):
        link(source + '-publication', source, 'a-data-bridge/estimates', 'report',
             kind='operation', purpose='Accepted estimate output; never raw measurements')
    model.relays['a-data-bridge/estimates'] = {'report'}
    link('estimate-planning', 'a-data-bridge/estimates', 'a-data/planning', 'report',
         kind='operation', purpose='Planning refresh consumes estimate feed')


def active_contexts(model, facts, mode):
    return {c.endpoint for c in model.contexts.values()
            if mode in c.modes and satisfied(c.requires_any, facts)}


def accessible(model, facts, mode, origins=None):
    """Return domain -> witnessed route from earned contexts and named relays."""
    if origins is None:
        origins = active_contexts(model, facts, mode)
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
                       and all(s.endpoint in routes[s.mode] for s in model.placements[i]))
        if not ready:
            break
        waves.append(ready)
        completed.update(ready)
        remaining.difference_update(ready)
    facts = earned(graph, completed)
    return {'completed': completed, 'remaining': remaining, 'waves': waves,
            'facts': facts, 'events': events(model, facts)}


MODES = {'service', 'artifact', 'read', 'delivery', 'control', 'report', 'telemetry'}
PROCESS_ENDPOINTS = {'a-reservoir', 'a-distribution', 'a-instruments'}
ACTUATORS = {'a-reservoir', 'a-distribution'}


def check_structure(graph, model):
    require(model.zones and model.boxes, 'Empty topology')
    require(all(key == b.ident and b.zone in model.zones for key, b in model.boxes.items()),
            'Invalid box identity or subnet membership')
    require({b.zone for b in model.boxes.values()} == set(model.zones), 'Empty subnet')
    require(all(key == d.ident and d.box in model.boxes and key.split('/')[0] == d.box
                for key, d in model.domains.items()), 'Invalid authority domain')
    require(set(model.placements) == set(graph.cards), 'Challenge placement coverage differs')
    used = set()
    for ident, surfaces in model.placements.items():
        require(surfaces, f'No target surface: {ident}')
        for surface in surfaces:
            require(surface.endpoint in model.domains and surface.mode in MODES, f'Invalid surface: {ident}/{surface}')
            used.add(surface.box)
    require(used == set(model.boxes), f'Unused boxes: {set(model.boxes) - used}')
    known = set(graph.edges) | graph.roots
    require(len({e.ident for e in model.links}) == len(model.links), 'Duplicate link ID')
    for edge in model.links:
        require(edge.source in set(model.domains) | {'player'} and edge.target in model.domains,
                f'Unknown link endpoint: {edge.ident}')
        require(set(edge.modes) <= MODES and edge.modes, f'Unknown/empty link mode: {edge.ident}')
        require(edge.requires_any and all(set(g) <= known for g in edge.requires_any),
                f'Invalid link capability: {edge.ident}')
        require(edge.kind in ('access', 'operation'), f'Invalid link kind: {edge.ident}')
        require(edge.kind != 'operation' or edge.purpose, f'Unnamed business flow: {edge.ident}')
    for key, context in model.contexts.items():
        require(key == context.ident and context.endpoint in set(model.domains) | {'player'},
                f'Invalid context: {key}')
        require(context.modes and set(context.modes) <= MODES, f'Invalid context modes: {key}')
        require(context.requires_any and all(set(g) <= known for g in context.requires_any),
                f'Invalid context acquisition: {key}')
    referenced = ({s.endpoint for surfaces in model.placements.values() for s in surfaces}
                  | {e.source for e in model.links} | {e.target for e in model.links}
                  | {c.endpoint for c in model.contexts.values()}) - {'player'}
    require(set(model.domains) == referenced, 'Unused or undeclared authority domain')
    require(all(endpoint in model.domains and modes and modes <= MODES
                for endpoint, modes in model.relays.items()), 'Invalid relay scope')
    for event, groups in model.events.items():
        require(groups and all(g and set(g) <= known for g in groups), f'Invalid event: {event}')


def assert_completes(graph, model, allowed, label):
    result = simulate(graph, model, allowed)
    if result['remaining']:
        details = []
        facts = result['facts']
        for ident in sorted(result['remaining']):
            if satisfied(graph.edges[ident], facts):
                blocked = [f'{s.endpoint}/{s.mode}' for s in model.placements[ident]
                           if s.endpoint not in accessible(model, facts, s.mode)]
                details.append(f'{ident}: {", ".join(blocked)}')
        raise DesignError(f'{label}: route deadlock: {"; ".join(details) or sorted(result["remaining"])}')
    return result


def shortest(graph, terminal, ceiling=None, without=()):
    options = [p for p in graph.paths(terminal) if not set(without) & p
               and (ceiling is None or graph.ceiling(p) <= ceiling)]
    require(options, f'No declared path for {terminal} without {without}')
    return graph.scored(min(options, key=lambda p: (len(graph.scored(p)), tuple(sorted(p)))))


def maximal_facts_without(graph, *forbidden):
    """Adversarial state: earn every compatible branch, ignoring network limits.

    This deliberately does NOT use simulate(): a broken route must not hide a
    dangerous context from the boundary audit. Re-evaluate all other branches
    while withholding the named capabilities/achievements.
    """
    key = tuple(sorted(forbidden))
    cache = getattr(graph, '_topology_boundary_facts', {})
    if key not in cache:
        completed = set()
        while True:
            before = len(completed)
            for ident in sorted(set(graph.cards) - completed):
                facts = earned(graph, completed)
                if satisfied(graph.edges[ident], facts):
                    candidate = earned(graph, completed | {ident})
                    if not set(forbidden) & candidate:
                        completed.add(ident)
            if len(completed) == before:
                break
        cache[key] = earned(graph, completed)
        graph._topology_boundary_facts = cache
    return cache[key]


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
        require('reservoir_release' not in events(model, facts), f'{terminal}: authority alone published a completed incident')
    before = shortest(graph, 'W30.RESULT') - {'W30.2'}
    require('reservoir_release' not in events(model, earned(graph, before)), 'Preparation published a completed incident')
    require('reservoir_release' in events(model, earned(graph, before | {'W30.2'})), 'Verified completion did not permit incident presentation')

    # Optional compromises are present in these states. Checking only the
    # shortest main route previously missed CI and diagnostic-origin bypasses.
    pre_entry = maximal_facts_without(graph, 'CORPORATE')
    for mode in MODES:
        reached = {i for i in accessible(model, pre_entry, mode) if i.startswith('a-')}
        require(reached <= ({'a-connector'} if mode == 'delivery' else set()),
                f'Post-compromise supplier bypass: {mode}: {sorted(reached)}')
    pre_read = maximal_facts_without(graph, 'OT_READ')
    ot = {i for i, d in model.domains.items() if model.boxes[d.box].zone in ('a-engineering', 'a-control')}
    for mode in ('service', 'artifact', 'read'):
        require(not ot & set(accessible(model, pre_read, mode)), f'OT visibility bypass before OT_READ: {mode}')
    pre_control = maximal_facts_without(graph, 'CONTROL')
    require(not (ACTUATORS | {'a-hmi/dispatch'}) & set(accessible(model, pre_control, 'control')),
            'Post-compromise command bypass without CONTROL')
    complete = earned(graph, set(graph.cards))
    for mode in ('control', 'report', 'telemetry'):
        require('a-instruments' not in accessible(model, complete, mode),
                f'Independent observation authority exposed: {mode}')
    for target in ('k-ci/consumer-state', 'k-data/source-db'):
        for mode in MODES:
            require(target not in accessible(model, complete, mode), f'Private domain exposed: {target}/{mode}')
    before_runtime = maximal_facts_without(graph, 'K31.2')
    require('k-data/field-archive' not in accessible(model, before_runtime, 'service'),
            'Workload management bypasses runtime identity')
    before_estimate = maximal_facts_without(graph, 'W23.3', 'W27.3')
    require('a-data/planning' not in accessible(model, before_estimate, 'report'),
            'Planning write bypasses estimator/program authority')


def check_context_scopes(graph, model):
    """Independently bounded consequences of execution inside shared systems.

    Evaluate with all evidence present, but only this context as an origin.
    Shared facts must not turn a job identity into a sibling service identity.
    These allowlists are authority contracts, not generated from the links.
    """
    contracts = {
        'runner': {'artifact': {'k-source', 'k-registry', 'k-staff', 'k-cert'},
                   'service': {'k-staff', 'k-cert', 'k-cloud-api/authority',
                               'k-cloud-api/build-records', 'k-workload/manage'}},
        'indexer': {'artifact': {'k-indexer/queue'}},
        'preview': {'report': {'k-preview'}},
        'completion': {'artifact': {'k-assistant/handover'}},
        'release-client': {'service': {'k-ci/rehearsals'}},
        'workload-base': {'service': {'k-cloud-api/authority', 'k-cloud-api/build-records'}},
        'cloud-role': {'service': {'k-cloud-api/authority', 'k-workload/manage', 'k-workload/scheduler'}},
        'export-delegation': {'service': {'k-workload/scheduler'}},
        'backup-principal': {'service': {'k-data/backup'}},
        'support-task': {'artifact': {'k-data'}},
        'maintenance-runtime': {'service': {'k-data/field-archive'}},
        'archive-helper': {'artifact': {'a-archive/handover'}},
        'planner': {'service': {'a-data/query'}},
        'query-worker': {'artifact': {'a-data/reconciliation'}},
        'maintenance-renderer': {'read': {'a-approval'}, 'service': {'a-control-broker/maintenance-issuer'}},
        'engineering-utility': {'service': {'a-control-broker/utility-issuer'}},
        'diagnostic-vault': {'artifact': {'a-diagnostics/history'}},
        'estimator-output': {'report': {'a-data-bridge/estimates', 'a-data/planning'}},
        'program-output': {'report': {'a-data-bridge/estimates', 'a-data/planning'}},
        'assistant-review': {'service': {'k-support/review-item'}},
        'support-staff': {'service': {'k-staff', 'k-cert'}, 'artifact': {'k-staff', 'k-cert'}},
        'support-federation': {'service': {'k-support/customer-records'}},
        'staff-delegation': {'service': {'k-identity/delegation', 'k-staff/managed-record'}},
    }
    require(set(contracts) == set(model.contexts) - {'player', 'developer', 'customer'},
            'Context authority contract coverage differs')
    facts = earned(graph, set(graph.cards))
    for ident, allowed in contracts.items():
        context = model.contexts[ident]
        for mode in context.modes:
            reached = set(accessible(model, facts, mode, origins={context.endpoint})) - {context.endpoint}
            permitted = allowed.get(mode, set())
            require(reached <= permitted, f'Context authority escaped: {ident}/{mode}: {sorted(reached - permitted)}')

    # These are real, useful pivots, not merely extra domains on a drawing.
    witnesses = {
        'K30.1': ('K09.4', 'k-cloud-api/build-records', 'k-ci/runner'),
        'K31.3': ('K31.2', 'k-data/field-archive', 'k-workload/runtime'),
        'W07.1': ('W06.3', 'a-data/query', 'a-connector/planner-client'),
        'W26.4': ('W26.3', 'a-control-broker/maintenance-issuer', 'a-renderer/worker'),
        'W28.3': ('W28.2', 'a-control-broker/utility-issuer', 'a-engineering/utility-worker'),
    }
    for ident, (prerequisite, target, origin) in witnesses.items():
        # Isolated context eliminates alternative identity routes from the witness.
        facts = earned(graph, shortest(graph, prerequisite))
        require(origin in active_contexts(model, facts, 'service'), f'Missing earned origin: {ident}')
        route = accessible(model, facts, 'service', origins={origin}).get(target)
        require(route and route[0] == origin, f'Missing pivot witness: {ident}')


def check_context_acquisition(graph, model):
    milestones = {'runner': ('K09.4',), 'indexer': ('K04.4',), 'preview': ('K12.4',),
                  'completion': ('K24.3',), 'support-task': ('K16.3',),
                  'maintenance-runtime': ('K31.2',), 'archive-helper': ('W04.3',),
                  'query-worker': ('W07.3',), 'maintenance-renderer': ('W26.3',),
                  'engineering-utility': ('W28.2',), 'diagnostic-vault': ('W31.4',),
                  'estimator-output': ('W23.3',), 'program-output': ('W27.3',),
                  'support-staff': ('B01',), 'support-federation': ('K18.3',),
                  'staff-delegation': ('K19.3',), 'release-client': ('K29.2', 'K20.2'),
                  'workload-base': ('K13.4',), 'cloud-role': ('K14.2',),
                  'export-delegation': ('K15.3',), 'backup-principal': ('K30.1',),
                  'customer': ('CORPORATE',), 'planner': ('W06.3',),
                  'assistant-review': ('K22.3',)}
    require(set(milestones) == set(model.contexts) - {'player', 'developer'},
            'Context acquisition contract coverage differs')
    for ident, alternatives in milestones.items():
        context = model.contexts[ident]
        require(not satisfied(context.requires_any, maximal_facts_without(graph, *alternatives)),
                f'Context acquired early: {ident}')
        for milestone in alternatives:
            require(satisfied(context.requires_any, earned(graph, shortest(graph, milestone))),
                    f'Context not acquired at completion: {ident}/{milestone}')


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
    variant('control acquisition needs control', gate('utility-issuance', either('CONTROL')),
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
    variant('control authority publishes a completed reservoir incident',
            lambda m: m.events.update({'reservoir_release': either('CONTROL')}),
            lambda m: check_boundaries(graph, m), 'authority alone published')
    variant('command plan mistaken for executed release',
            lambda m: m.events.update({'reservoir_release': either('W30.1')}),
            lambda m: check_boundaries(graph, m), 'Preparation published')
    variant('compromised CI runner crosses directly into ARWC',
            lambda m: m.links.append(Link('bad-ci-pivot', 'k-ci/runner', 'a-business', ('service',), either('K09.4'))),
            lambda m: check_boundaries(graph, m), 'Post-compromise supplier bypass')
    variant('compromised diagnostic service commands reservoir',
            lambda m: m.links.append(Link('bad-diagnostic-pivot', 'a-diagnostics/vault-worker', 'a-reservoir', ('control',), either('W31.4'))),
            lambda m: check_boundaries(graph, m), 'Post-compromise command bypass')
    variant('runner reads sibling private consumer state',
            lambda m: m.links.append(Link('bad-consumer-state', 'k-ci/runner', 'k-ci/consumer-state', ('artifact',))),
            lambda m: check_boundaries(graph, m), 'Private domain exposed')
    variant('backup recovery principal reads source directly',
            lambda m: m.links.append(Link('bad-backup-source', 'k-data/backup-client', 'k-data/source-db', ('artifact',))),
            lambda m: check_boundaries(graph, m), 'Private domain exposed')
    variant('query execution overwrites planning estimates',
            lambda m: m.links.append(Link('bad-query-planning', 'a-data/query-worker', 'a-data/planning', ('report',))),
            lambda m: check_boundaries(graph, m), 'Planning write bypasses')
    variant('diagnostic vault inherits sibling signing service',
            lambda m: m.links.append(Link('bad-vault-export', 'a-diagnostics/vault-worker', 'a-diagnostics/export-log', ('artifact',))),
            lambda m: check_context_scopes(graph, m), 'Context authority escaped')
    variant('renderer approval read expands to command authority',
            lambda m: m.links.append(Link('bad-renderer-authority', 'a-renderer/worker', 'a-approval', ('control',))),
            lambda m: check_context_scopes(graph, m), 'Context authority escaped')
    variant('workload manager inherits runtime archive identity',
            lambda m: m.links.append(Link('bad-management-runtime', 'k-cloud-api/delegated-client', 'k-data/field-archive', ('service',))),
            lambda m: check_boundaries(graph, m), 'Workload management bypasses')
    variant('corporate context reaches engineering before read scope',
            lambda m: m.links.append(Link('bad-early-engineering', 'a-connector', 'a-engineering', ('service',))),
            lambda m: check_boundaries(graph, m), 'OT visibility bypass')
    variant('preview compromise inherits customer delivery',
            lambda m: m.links.append(Link('bad-preview-delivery', 'k-preview/renderer', 'k-support', ('delivery',))),
            lambda m: check_context_scopes(graph, m), 'Context authority escaped')
    variant('source control becomes automatic build execution',
            lambda m: m.contexts.update({'runner': replace(m.contexts['runner'], requires_any=either('FOOTHOLD'))}),
            lambda m: check_context_acquisition(graph, m), 'Context acquired early')
    variant('missing estimate publication strands reporting branch', remove('estimate-planning'),
            route('W34.2'), 'route deadlock')
    variant('missing supervisory dispatcher strands live commands', remove('supervisory-command'),
            route('W30.RESULT'), 'route deadlock')
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
        'authority_domains': [asdict(domain) for domain in model.domains.values()],
        'earned_contexts': [asdict(context) for context in model.contexts.values()],
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
        label = (edge.purpose or '/'.join(edge.modes)) + ('\n' + gate if gate else '')
        color = '#b34835' if 'control' in edge.modes else '#277b91' if 'delivery' in edge.modes else '#667085'
        source = 'player' if edge.source == 'player' else model.domains[edge.source].box
        target = model.domains[edge.target].box
        if source != target:
            lines.append(f'  {q(source)} -> {q(target)} [label={q(label)}, color={q(color)}];')
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
    check_context_scopes(graph, model)
    check_context_acquisition(graph, model)
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
    print(f'PASS: {len(model.domains)} authority domains / {len(model.contexts)} contexts; scoped compromise and acquisition checked')
    print('PASS: accumulated optional compromises do not bypass supplier, OT visibility, or command boundaries')
    print('PASS: incident presentation requires verified completion; graph does not simulate process effects')
    if args.self_test:
        self_test(graph, model)
    if args.json:
        args.json.write_text(json.dumps(export_data(graph, model, matrix, count), indent=2) + '\n')
        print(f'Graph/data: {args.json}')
    if args.dot:
        args.dot.write_text(dot_graph(graph, model))
        print(f'Graphviz: {args.dot}')
    print('\nLogical requirements checked: named authority domains, scoped contexts, service conduits, and triggered events.')
    print('Not established: exploit correctness, OS/root isolation, VM/container count, or event capacity.')


if __name__ == '__main__':
    try:
        main()
    except DesignError as error:
        raise SystemExit(f'FAIL: {error}')
