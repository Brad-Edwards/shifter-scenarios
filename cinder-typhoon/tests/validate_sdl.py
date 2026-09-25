#!/usr/bin/env python3
"""Validate native RAE SDL, then replay the design using the graph read from SDL.

Run with the dependencies in tests/requirements-sdl.txt. No deployment occurs.
The design ledger is an independent expectation, never the source of decoded
SDL edges. Relationship properties have the small vocabulary in sdl/README.md.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
import re
import sys

import yaml
from raes._errors import SDLParseError
from raes.explicitness import ExplicitnessClass
from raes.instantiate import instantiate_scenario
from raes.parser import parse_sdl, parse_sdl_file
from raes.realization_designation import AuthorRealizationPosture
from raes_processor.compiler import compile_runtime_model
from validate_narrative import (
    NARRATIVE_EVIDENCE, check_narrative_sdl, check_narrative_runtime,
    adversarial_narrative_checks,
)

PACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK / 'docs/design'))
from validate_challenges import (  # noqa: E402
    DesignError, Graph, canonical, check_campaign, load_briefs, read_json, require,
)
from model_topology import (  # noqa: E402
    Box, Context, Domain, Link, Surface, Topology, assert_completes,
    check_boundaries, check_closures, check_context_acquisition,
    check_context_scopes, check_structure, make_topology, self_test,
)
from sdl_contracts import (  # noqa: E402
    CONSEQUENCES, CONSEQUENCE_SUFFIX, ELIGIBILITY, FAILURE_CLASSES, RESET_CONTEXT, TRAINING_CONTENT,
    action_refs, capability_sources, evidence_refs, record_specs, technical_sections,
    text_section,
)
from validate_k09_handoff import check_k09_handoff  # noqa: E402
from validate_training import check_training, hand_build_gaps  # noqa: E402

FACT_PREFIX = 'urn:cinder-typhoon:fact:'
KALI = 'participant.kali'
ACTOR = 'participant.operator'


def enum(value):
    return getattr(value, 'value', value)


def card_id(key):
    match = re.fullmatch(r'([tkw]\d{2})\.c(\d+)', key)
    require(match is not None, f'Unexpected objective identifier: {key}')
    return f'{match[1].upper()}.{match[2]}'


def assertion_fact(scenario, reference, role='precondition'):
    assertion = scenario.assertions[reference]
    require(enum(assertion.role) == role and enum(assertion.polarity) == 'positive',
            f'Unexpected assertion use: {reference}')
    proposition = scenario.propositions[assertion.proposition]
    pred = proposition.predicate
    require(pred.kind == 'boolean' and pred.operator == 'equals' and pred.expected is True,
            f'Fact truth weakened: {reference}')
    require(pred.semantic_ref.startswith(FACT_PREFIX), f'Unknown fact meaning: {reference}')
    return pred.semantic_ref.removeprefix(FACT_PREFIX)


def guard_groups(scenario, key, objective=None):
    """Read AND within switch cases, OR across cases; check the whole control graph."""
    workflow = scenario.workflows[key]
    steps = workflow.steps
    destination = 'attempt' if objective else 'available'
    for terminal in ('available', 'unavailable'):
        if terminal in steps:
            require(enum(steps[terminal].type) == 'end', f'Nonterminal {key}/{terminal}')
    if workflow.start == destination and not objective:
        require(set(steps) == {'available'}, f'Unexpected unconditional guard: {key}')
        return ((),)
    require(workflow.start == 'requirements', f'Guard bypass: {key}')
    branch = steps['requirements']
    require(enum(branch.type) == 'switch' and branch.default_step == 'unavailable',
            f'Guard default bypass: {key}')
    require(set(steps) == {'requirements', 'available', 'unavailable'} | ({'attempt'} if objective else set()),
            f'Unexpected workflow steps: {key}')
    groups = []
    for case in branch.cases:
        require(case.next_step == destination and case.when.assertions and
                not case.when.objectives and not case.when.steps,
                f'Unexpected predicate or destination: {key}')
        groups.append(tuple(assertion_fact(scenario, ref) for ref in case.when.assertions))
    require(groups, f'Empty guard: {key}')
    if objective:
        attempt = steps['attempt']
        require(enum(attempt.type) == 'objective' and enum(attempt.execution_mode) == 'objective'
                and attempt.objective == objective and attempt.on_success == 'available'
                and attempt.on_failure == 'unavailable' and not attempt.procedure_ref,
                f'Changed objective execution semantics: {key}')
    return tuple(groups)


def decode(scenario, briefs):
    """Recover the campaign and scoped topology entirely from parsed SDL constructs."""
    model = Topology()
    node_endpoints = {'nodes.' + KALI: 'player'}
    feature_endpoints = {}
    for key, node in scenario.nodes.items():
        if key == KALI:
            continue
        zone, ident = key.split('.', 1)
        infra = scenario.infrastructure[key]
        if enum(node.type) == 'switch':
            require(ident == 'subnet' and not infra.links, f'Unexpected network group: {key}')
            organization = scenario.entities[zone + '.organization']
            model.zones[zone] = {'organization': organization.name, 'label': organization.description}
            continue
        require(enum(node.type) == 'compute', f'Non-compute logical target: {key}')
        require(infra.links == [zone + '.subnet'] and infra.count == 1,
                f'Changed subnet membership or replication: {key}')
        model.boxes[ident] = Box(ident, node.description, zone)
        node_endpoints['nodes.' + key] = ident
        for feature_key in node.features:
            domain_id = feature_key.split('.', 1)[1].replace('--', '/')
            require(domain_id not in model.domains, f'Authority assigned to two boxes: {feature_key}')
            feature = scenario.features[feature_key]
            model.domains[domain_id] = Domain(domain_id, ident, feature.name)
            feature_endpoints['features.' + feature_key] = domain_id
    require(set(feature_endpoints) == {'features.' + key for key in scenario.features},
            'Undecoded or unattached authority feature')
    endpoints = {**node_endpoints, **feature_endpoints}

    cards = {}
    for key, objective in scenario.objectives.items():
        ident = card_id(key)
        require(ident in briefs, f'Undocumented objective: {ident}')
        require(objective.agent == ACTOR and objective.actions == [key], f'Changed actor/action: {ident}')
        require(not objective.depends_on, f'Additional conjunctive dependency: {ident}')
        require(objective.window is not None and objective.window.workflows == [key],
                f'Objective detached from eligibility workflow: {ident}')
        require(enum(objective.success.mode) == 'all_of' and len(objective.success.assertions) == 1
                and assertion_fact(scenario, objective.success.assertions[0], 'postcondition') == ident,
                f'Changed completion assertion: {ident}')
        cards[ident] = {'requires_any': [list(g) for g in guard_groups(scenario, key, key)]}

    capabilities = defaultdict(list)
    capability_injects = set()
    for key, event in scenario.events.items():
        require(event.assertions and len(event.injects) == 1, f'Unbounded event: {key}')
        group = tuple(assertion_fact(scenario, ref) for ref in event.assertions)
        if key.startswith('capabilities.'):
            require(event.name not in cards, f'Capability collides with challenge: {key}')
            inject_key = event.injects[0]
            require(inject_key.startswith('capabilities.'), f'Capability triggers consequence: {key}')
            require(assertion_fact(scenario, inject_key + '-ready') == event.name,
                    f'Capability event/output mismatch: {key}')
            capability_injects.add(inject_key)
            capabilities[event.name].append(list(group))
        elif key.startswith('consequences.'):
            ident = key.removeprefix('consequences.').replace('-', '_')
            require(event.injects == [key], f'Consequence writes another outcome: {key}')
            model.events[ident] = (group,)
        else:
            raise DesignError(f'Unexpected event namespace: {key}')
    require(capability_injects == {k for k in scenario.injects if k.startswith('capabilities.')},
            'Orphan capability transition')
    roots = sorted(assertion_fact(scenario, ref) for ref in scenario.agents[ACTOR].starting_assertions)
    graph = Graph({'schema_version': 1, 'roots': roots, 'challenges': cards,
                   'capabilities': dict(capabilities)}, briefs)
    placements = defaultdict(list)
    # Native objective targets are sufficient for Training's service surfaces.
    # This projection into the old design test model adds no language semantics,
    # permission grant, network policy, or materialization adapter.
    for key, objective in scenario.objectives.items():
        if key.startswith(('t01.', 't02.', 't03.', 't04.')):
            for ref in objective.targets:
                require(ref in feature_endpoints and
                        enum(scenario.features[ref.removeprefix('features.')].type) == 'service',
                        f'Training target is not a declared service feature: {key}')
                placements[card_id(key)].append(Surface(feature_endpoints[ref], 'service'))
    access = scenario.agents[ACTOR].interactive_access
    require('workstation' in access and access['workstation'].target_ref == 'nodes.' + KALI
            and enum(access['workstation'].channel) == 'ssh', 'Missing native workstation access')
    model.contexts['player'] = Context('player', 'player', ((),), 'workspace')
    for key, relation in scenario.relationships.items():
        props = relation.properties
        kind = props.get('cinder_kind')
        if key.startswith('flows-participant.'):
            require(not props and enum(relation.type) == 'connects_to'
                    and relation.source == 'nodes.' + KALI
                    and relation.target in feature_endpoints
                    and relation.target.startswith('features.training.'),
                    f'Invalid native Training connection: {key}')
            model.links.append(Link(key.split('.', 1)[1], 'player',
                                    feature_endpoints[relation.target],
                                    ('service', 'artifact'), ((),), 'access', relation.description))
        elif kind == 'challenge_surface':
            require(not key.startswith(('t01.', 't02.', 't03.', 't04.')),
                    f'Training reintroduces private surface semantics: {key}')
            require(set(props) == {'cinder_kind', 'objective', 'mode'} and enum(relation.type) == 'depends_on',
                    f'Unknown surface contract: {key}')
            require(relation.source == 'agents.' + ACTOR, f'Surface uses another actor: {key}')
            ident = card_id(props['objective'].removeprefix('objectives.'))
            placements[ident].append(Surface(endpoints[relation.target], props['mode']))
        elif kind in ('flow', 'context'):
            require(set(props) == {'cinder_kind', 'modes', 'guard', kind + '_kind'},
                    f'Unknown route contract: {key}')
            guard = props['guard'].removeprefix('workflows.')
            require(guard == key, f'Route detached from its guard: {key}')
            groups = guard_groups(scenario, guard)
            modes = tuple(props['modes'].split(','))
            if kind == 'flow':
                require(enum(relation.type) == 'connects_to', f'Wrong flow relationship: {key}')
                ident = key.split('.', 1)[1].replace('--', '/')
                model.links.append(Link(ident, endpoints[relation.source], endpoints[relation.target],
                                        modes, groups, props['flow_kind'], relation.description))
            else:
                require(enum(relation.type) == 'authenticates_with' and relation.source == 'agents.' + ACTOR,
                        f'Wrong context relationship: {key}')
                ident = key.split('.', 1)[1].removeprefix('context-')
                model.contexts[ident] = Context(ident, endpoints[relation.target], groups,
                                                props['context_kind'], modes)
        elif kind == 'relay':
            require(set(props) == {'cinder_kind', 'modes'} and enum(relation.type) == 'manages',
                    f'Unknown forwarding contract: {key}')
            ep = endpoints[relation.source]
            require(endpoints[relation.target] == model.domains[ep].box and ep not in model.relays,
                    f'Invalid or duplicated relay: {key}')
            model.relays[ep] = set(props['modes'].split(','))
        else:
            raise DesignError(f'Uninterpreted relationship: {key}')
    model.placements = {i: tuple(s) for i, s in placements.items()}
    for key, objective in scenario.objectives.items():
        require(set(objective.targets) == {ref for ref, ep in feature_endpoints.items()
                if ep in {s.endpoint for s in model.placements[card_id(key)]}},
                f'Objective and surface targets differ: {key}')
    require(set(scenario.workflows) == set(scenario.objectives) |
            {k for k, r in scenario.relationships.items() if r.properties.get('cinder_kind') in ('flow', 'context')},
            'Orphan workflow or missing guard')
    return graph, model


def check_expected(scenario, briefs, expected_graph, expected_model):
    graph, model = decode(scenario, briefs)
    require(set(graph.capabilities) == set(expected_graph.capabilities), 'Capability inventory changed')
    for ident, groups in graph.edges.items():
        require(canonical(groups) == canonical(expected_graph.edges[ident]), f'Dependency drift: {ident}')
    # These are independent expected design objects, not regeneration of SDL.
    actual = asdict(model)
    expected = asdict(expected_model)
    actual['links'] = sorted(actual['links'], key=lambda link: link['ident'])
    expected['links'] = sorted(expected['links'], key=lambda link: link['ident'])
    for section in expected:
        require(actual[section] == expected[section], f'Logical topology drift: {section}')
    require(set(scenario.agents) == {ACTOR}, 'Unexpected participant inventory')
    operator = scenario.agents[ACTOR]
    require(set(operator.actions) == set(scenario.objectives), 'Participant action inventory differs')
    require(not operator.starting_accounts, 'Unexpected supplied target credentials')
    require(operator.initial_knowledge.hosts == [KALI, 'k-corporate.k-dev']
            and operator.initial_knowledge.subnets == ['training.subnet'], 'Changed initial knowledge')
    access = operator.interactive_access
    require(set(access) == {'workstation'} and access['workstation'].target_ref == 'nodes.' + KALI
            and enum(access['workstation'].channel) == 'ssh', 'Missing or changed Kali access')
    kali = scenario.nodes[KALI]
    require(enum(kali.os) == 'linux' and str(kali.os_distribution) == 'x-kali:kali', 'Kali OS requirement changed')
    require(scenario.infrastructure[KALI].links == ['training.subnet'],
            'Kali has an undeclared direct subnet attachment')
    require(set(scenario.action_contracts) == set(scenario.objectives), 'Missing action contracts')
    require(not scenario.scripts, 'Unexpected continuously timed scenario script')
    require(set(scenario.evidence_requirements) == set(scenario.objectives) |
            {'capabilities.' + re.sub(r'[^a-z0-9-]', '-', i.lower()) for i in graph.capabilities} | NARRATIVE_EVIDENCE,
            'Unexpected evidence inventory')
    check_narrative_sdl(scenario)
    for key, objective in scenario.objectives.items():
        ident = card_id(key)
        brief = briefs[ident]
        require(objective.name == ident + ': ' + brief['title'], f'Title drift: {ident}')
        require(objective.description == text_section(brief, 'Challenge description') + '\n\n' +
                text_section(brief, 'Story purpose'), f'Challenge meaning drift: {ident}')
        completion = text_section(brief, 'Completion and downstream use')
        proposition = scenario.propositions[key]
        sources = evidence_refs(expected_model, ident)
        require(enum(proposition.basis) == 'observed_state' and enum(proposition.quantifier) == 'all'
                and proposition.description == completion
                and proposition.evidence_requirements == [key], f'Completion evidence drift: {ident}')
        require(proposition.subjects == sources, f'Completion subjects drift: {ident}')
        check_action_contract(scenario, key, brief, expected_model, ident)
        technical = technical_sections(brief)
        evidence = scenario.evidence_requirements[key]
        expected_proof = completion + ('\n\nRequired technical proof: ' +
                                      technical['Evidence and completion'] if technical else '')
        require(evidence.description == expected_proof and evidence.source_refs == sources,
                f'Evidence-source drift: {ident}')
        require(evidence.notes == (['Author checks: ' + technical['Author checks']] if technical else []),
                f'Author-check drift: {ident}')
        check_observation(scenario, key, sources)
        expected_records = record_specs(brief, expected_model, ident)
        records = {name: c for name, c in scenario.content.items() if name.startswith(key + '-records-')}
        require(set(records) == {f'{key}-records-{n}' for n in range(1, len(expected_records) + 1)},
                f'Seed inventory drift: {ident}')
        for n, expected_record in enumerate(expected_records, 1):
            record = records[f'{key}-records-{n}']
            require(record.target == expected_record['target'] and
                    record.description == expected_record['description'] and
                    enum(record.type) == 'dataset' and len(record.items) == 1 and
                    record.items[0].name == 'starting-records' and
                    record.items[0].description == expected_record['item'], f'Seed contract drift: {ident}')
            require(record.text is None and record.source is None,
                    f'Seed declaration contains unexpected asset bytes: {ident}')
    for ident in graph.capabilities:
        key = 'capabilities.' + re.sub(r'[^a-z0-9-]', '-', ident.lower())
        proposition = scenario.propositions[key]
        sources = capability_sources(expected_graph, expected_model, ident)
        require(proposition.subjects == ['agents.' + ACTOR] and
                enum(proposition.quantifier) == 'all' and enum(proposition.basis) == 'observed_state' and
                proposition.evidence_requirements == [key], f'Capability evidence drift: {ident}')
        require(scenario.evidence_requirements[key].source_refs == sources,
                f'Capability producer drift: {ident}')
        check_observation(scenario, key, sources)
        inject = scenario.injects[key]
        require(inject.environment == ['agents.' + ACTOR] and inject.description ==
                f'Retain the {ident} capability/evidence for this participant after one complete acquisition alternative is verified. This updates participant state only; it does not write to every possible evidence producer. It is a derived state update, not an extra player action or a progress message.',
                f'Capability state-update drift: {ident}')
    for ident, (name, owners, description) in CONSEQUENCES.items():
        inject = scenario.injects['consequences.' + ident]
        require(inject.name == name and inject.environment == ['nodes.' + ref for ref in owners]
                and inject.description == description + CONSEQUENCE_SUFFIX,
                f'Consequence effect drift: {ident}')
    check_k09_handoff(scenario, briefs, graph, model)
    check_training(scenario, briefs)
    return graph, model


def check_action_contract(scenario, key, brief, model, ident):
    contract = scenario.action_contracts[key]
    targets = action_refs(model, ident)
    sources = evidence_refs(model, ident)
    technical = technical_sections(brief)
    require(enum(contract.lifecycle_state) == 'draft' and
            str(contract.semantic_version) == '1.0.0' and
            enum(contract.behavioral_granularity) == 'aggregate' and
            contract.realization_profile == 'backend-declared' and
            [enum(c) for c in contract.failure_classes] == FAILURE_CLASSES,
            f'Action contract drift: {ident}')
    require(contract.procedure_basis == technical.get('Vulnerability and intended solution',
            text_section(brief, 'Challenge description')), f'Action mechanism drift: {ident}')
    preconditions = [{'precondition_id': 'eligibility', 'precondition_class': 'authority',
                      'description': ELIGIBILITY, 'support_refs': ['workflows.' + key] + targets,
                      'evidence_refs': []}]
    effects = [{'effect_id': 'outcome', 'effect_class': 'intended_effect',
                'description': text_section(brief, 'Completion and downstream use'),
                'target_refs': targets, 'evidence_refs': ['evidence_requirements.' + key]}]
    if technical:
        preconditions.extend([
            {'precondition_id': 'normal-surface', 'precondition_class': 'target',
             'description': technical['Surface and normal behavior'],
             'support_refs': targets + ['content.' + ref for ref in TRAINING_CONTENT.get(ident, ())],
             'evidence_refs': []},
            {'precondition_id': 'boundaries' if ident.startswith('T') else 'boundaries-and-reset',
             'precondition_class': 'realization',
             'description': technical['Boundaries'] if ident.startswith('T') else
                            RESET_CONTEXT + technical['Boundaries and reset'],
             'support_refs': list(dict.fromkeys(targets + sources)), 'evidence_refs': []},
        ])
        effects.append({'effect_id': 'verified-evidence', 'effect_class': 'evidence_effect',
                        'description': technical['Evidence and completion'], 'target_refs': sources,
                        'evidence_refs': ['evidence_requirements.' + key]})
    require([p.model_dump(mode='json') for p in contract.preconditions] == preconditions,
            f'Action precondition drift: {ident}')
    require([e.model_dump(mode='json') for e in contract.effects] == effects,
            f'Action outcome drift: {ident}')


def check_observation(scenario, key, sources):
    evidence = scenario.evidence_requirements[key]
    demand = evidence.observation_demand
    # One collection scope avoids inherited policy partitions; component_refs
    # supply the exact owner restriction, including joined evidence.
    scope = '/features'
    require(demand is not None and demand.selector is not None and demand.required and
            enum(demand.mode) == 'selected' and enum(demand.purpose) == 'experimental' and
            enum(demand.collection) == 'require' and enum(demand.retention) == 'require' and
            enum(demand.basis) == 'observed' and demand.integrity == 'checksum' and
            demand.redaction == 'redact-secrets', f'Observation contract drift: {key}')
    selector = demand.selector
    require(demand.scope == scope and selector.semantic_scope == scope and
            selector.component_refs == tuple(sources) and selector.data_kind == 'artifact' and
            selector.names == (scenario.propositions[key].predicate.property,) and
            not selector.excluded_scopes and not selector.window_refs,
            f'Observation binding drift: {key}')


def check_compiled_observations(scenario, runtime):
    """Check the normalized runtime selectors, not just authored source_refs."""
    expected = {}
    for key, evidence in scenario.evidence_requirements.items():
        expected[scenario.propositions[key].predicate.property] = (
            evidence.observation_demand.selector.semantic_scope,
            {('provision.content.' + ref.removeprefix('content.')) if ref.startswith('content.')
             else ('template.feature.' + ref.removeprefix('features.')) for ref in evidence.source_refs},
        )
    seen = set()
    for demand in runtime.observation_demands:
        require(demand.required and enum(demand.mode) == 'selected' and
                enum(demand.collection) == 'require' and enum(demand.retention) == 'require' and
                enum(demand.basis) == 'observed' and demand.redaction == 'redact-secrets' and
                demand.integrity == 'checksum', 'Compiled observation lifecycle drift')
        for selector in demand.selectors:
            require(len(selector.names) == 1 and selector.names[0] in expected,
                    'Unexpected compiled observation name')
            name = selector.names[0]
            scope, sources = expected[name]
            require(selector.semantic_scope == scope and set(selector.component_refs) == sources and
                    selector.data_kind == 'artifact' and not selector.excluded_scopes and
                    not selector.window_refs, f'Compiled observation binding drift: {name}')
            seen.add(name)
    require(seen == set(expected), 'Required observations lost during compilation')
    return len(seen)


def check_authored_open(entry):
    root = yaml.safe_load(entry.read_text())
    docs = [(entry, root)]
    for imp in root['imports']:
        require(imp['source'].startswith('local:'), 'Unexpected nonlocal module resolution')
        path = (entry.parent / imp['source'][6:]).resolve()
        require(path.is_relative_to(entry.parent.resolve()), 'Module escapes the SDL directory')
        docs.append((path, yaml.safe_load(path.read_text())))
    require({p.resolve() for p, _ in docs} == {p.resolve() for p in entry.parent.rglob('*.yaml')},
            'Unimported module or duplicate source tree')
    for path, doc in docs:
        require(doc.get('realization') == {'default': 'open'}, f'Missing native default-open declaration: {path.name}')
        require(doc.get('semantic_revision') == 'raes-progressive-semantics/v1',
                f'Mixed semantic revisions: {path.name}')
    return len(docs) - 1


def check_compiled_open(instantiated, runtime):
    records = instantiated.instantiation_provenance.realization_designations
    require(records and all(r.posture is AuthorRealizationPosture.OPEN for r in records),
            'Open designation lost during composition/instantiation')
    requirements = {r.field_path: r for r in runtime.realization_requirements}
    for key, node in instantiated.nodes.items():
        if enum(node.type) != 'compute':
            continue
        require(node.resources is None, f'Unexpected resource sizing: {key}')
        for suffix in ('realization.compute-substrate', 'architecture', 'os_version'):
            path = f'nodes.{key}.{suffix}'
            require(path in requirements and requirements[path].explicitness is ExplicitnessClass.OPEN,
                    f'Unspecified realization is not open after compilation: {path}')
        path = f'nodes.{key}.os'
        if key in {'training.t-workbench', 'training.t-accounts',
                   'training.t-state', 'training.t-developer'}:
            require(enum(node.os) == 'linux' and
                    requirements[path].explicitness is ExplicitnessClass.EXACT,
                    f'Training POSIX ownership requires exact Linux intent: {key}')
        elif key != KALI:
            require(requirements[path].explicitness is ExplicitnessClass.OPEN, f'Unspecified OS closed: {key}')
    for suffix in ('os', 'os_distribution'):
        requirement = requirements[f'nodes.{KALI}.{suffix}']
        require(requirement.explicitness is ExplicitnessClass.EXACT,
                f'Explicit Kali {suffix} was weakened by default open')
    return len(requirements)


def adversarial_checks(scenario, briefs, expected_graph, expected_model):
    """Type-valid native SDL mutations must be rejected by the meaning checks."""
    cases = []
    def route_key(ident):
        keys = [key for key in scenario.relationships if key.endswith('.' + ident)]
        require(len(keys) == 1, f'Ambiguous route fixture: {ident}')
        return keys[0]
    def case(label, mutate, expected):
        changed = scenario.model_copy(deep=True)
        mutate(changed)
        # Native type validation establishes these are not merely malformed YAML.
        # The unchanged baseline receives full native semantic validation in main.
        changed = type(scenario).model_validate(changed.model_dump())
        try:
            check_expected(changed, briefs, expected_graph, expected_model)
        except DesignError as error:
            require(expected in str(error), f'Wrong failure for {label}: {error}')
            cases.append(label)
        else:
            raise DesignError(f'Adversarial SDL accepted: {label}')
    case('OR entry route removed', lambda s: s.events.pop('capabilities.corporate-2'), 'Dependency drift: CORPORATE')
    # The final cards inherit revision evidence through their operation's first
    # challenge. Replace that gate with mere OT visibility, keeping valid types.
    case('current revision omitted from W22.4 ancestry',
         lambda s: setattr(s.workflows['w22.c1'].steps['requirements'].cases[0].when,
                           'assertions', ['capabilities.ot-read-ready']),
         'Dependency drift: W22.1')
    case('current revision omitted from W24.4 ancestry',
         lambda s: setattr(s.workflows['w24.c1'].steps['requirements'].cases[0].when,
                           'assertions', ['capabilities.ot-read-ready']),
         'Dependency drift: W24.1')
    case('package conduit removed', lambda s: s.relationships.pop(route_key('package-delivery')), 'Orphan workflow')
    case('read conduit made command-capable',
         lambda s: s.relationships[route_key('integration-entry')].properties.update(modes='read,artifact,service,control'),
         'Logical topology drift: links')
    case('reservoir event missing interpretation',
         lambda s: s.events['consequences.reservoir-release'].assertions.remove('capabilities.process-interpretation-ready'),
         'Logical topology drift: events')
    case('rehearsal writes live outcome',
         lambda s: setattr(s.events['consequences.feedback-rehearsal'], 'injects', ['consequences.reservoir-release']),
         'Consequence writes another outcome')
    case('Kali directly attached to control subnet',
         lambda s: s.infrastructure[KALI].links.append('a-control.subnet'), 'undeclared direct subnet')
    case('asserted completion replaces observed evidence',
         lambda s: setattr(s.propositions['w30.c2'], 'basis', type(s.propositions['w30.c2'].basis).DECLARED_STATE),
         'Completion evidence drift')
    case('joined reservoir proof weakened to ANY',
         lambda s: setattr(s.propositions['w30.c2'], 'quantifier', type(s.propositions['w30.c2'].quantifier).ANY),
         'Completion evidence drift: W30.2')
    case('explicit source binding omitted',
         lambda s: setattr(s.evidence_requirements['w30.c2'].observation_demand.selector, 'component_refs', ()),
         'Observation binding drift: w30.c2')
    case('explicit source binding points to unrelated feature',
         lambda s: setattr(s.evidence_requirements['w30.c2'].observation_demand.selector,
                           'component_refs', ('features.a-corporate.a-business',)),
         'Observation binding drift: w30.c2')
    case('capability producer replaced by semantic-only actor',
         lambda s: setattr(s.evidence_requirements['capabilities.corporate'].observation_demand.selector,
                           'component_refs', ('agents.' + ACTOR,)),
         'Observation binding drift: capabilities.corporate')
    case('Forge proof incorrectly collected at developer workspace',
         lambda s: setattr(s.evidence_requirements['k01.c1'], 'source_refs', ['features.k-corporate.k-dev']),
         'Evidence-source drift: K01.1')
    case('eligibility detached from actual access surfaces',
         lambda s: setattr(s.action_contracts['k06.c1'].preconditions[0], 'support_refs', ['nodes.' + KALI]),
         'Action precondition drift: K06.1')
    case('authority precondition changed to mere knowledge',
         lambda s: setattr(s.action_contracts['k06.c1'].preconditions[0], 'precondition_class',
                           type(s.action_contracts['k06.c1'].preconditions[0].precondition_class).KNOWLEDGE),
         'Action precondition drift: K06.1')
    case('selected importer mechanism omitted',
         lambda s: setattr(s.action_contracts['k06.c1'], 'procedure_basis', 'Obtain a registry credential.'),
         'Action mechanism drift: K06.1')
    case('bounded daemon routine changed to generic execution',
         lambda s: setattr(s.action_contracts['k04.c4'], 'procedure_basis', 'Execute arbitrary commands.'),
         'Action mechanism drift: K04.4')
    case('technical normal behavior omitted',
         lambda s: setattr(s.action_contracts['k06.c1'].preconditions[1], 'description', 'Ordinary public registry.'),
         'Action precondition drift: K06.1')
    case('scope and revocation requirements omitted',
         lambda s: setattr(s.action_contracts['k06.c1'].preconditions[2], 'description', 'No reset required.'),
         'Action precondition drift: K06.1')
    case('training lifecycle execution exclusion removed',
         lambda s: setattr(s.action_contracts['t03.c3'].preconditions[2], 'description', 'Run the package installer.'),
         'Action precondition drift: T03.3')
    case('technical proof collapsed into generic completion',
         lambda s: setattr(s.evidence_requirements['k06.c1'], 'description',
                           text_section(briefs['K06.1'], 'Completion and downstream use')),
         'Evidence-source drift: K06.1')
    case('evidence effect incorrectly updates the workstation',
         lambda s: setattr(s.action_contracts['k01.c1'].effects[1], 'target_refs', ['features.k-corporate.k-dev']),
         'Action outcome drift: K01.1')
    case('author acceptance criteria lost',
         lambda s: setattr(s.evidence_requirements['k06.c1'], 'notes', []), 'Author-check drift: K06.1')
    case('seed requirements replaced by empty public records',
         lambda s: setattr(s.content['k06.c1-records-1'], 'description', 'Ordinary empty public records.'),
         'Seed contract drift: K06.1')
    case('protected handover seeded onto the workstation',
         lambda s: setattr(s.content['k01.c1-records-2'], 'target', 'k-corporate.k-dev'),
         'Seed contract drift: K01.1')
    case('reservoir consequence affects only a business application',
         lambda s: setattr(s.injects['consequences.reservoir-release'], 'environment', ['nodes.a-corporate.a-business']),
         'Consequence effect drift: reservoir-release')
    case('rehearsal consequence description permits live effects',
         lambda s: setattr(s.injects['consequences.feedback-rehearsal'], 'description', 'Advance live reservoir state.'),
         'Consequence effect drift: feedback-rehearsal')
    # Independent parser test for the exact spelling of the native posture.
    try:
        parse_sdl('name: invalid-posture\nrealization:\n  default: default-open\n')
    except SDLParseError as error:
        require('/realization/default' in str(error), f'Unexpected posture parser failure: {error}')
    else:
        raise DesignError('Invalid realization posture was accepted')
    print(f'PASS: {len(cases)} native type-valid SDL mutations rejected; invalid posture spelling rejected', flush=True)


def adversarial_compiled_checks(scenario, runtime):
    """A valid runtime selector can still lose the authored source restriction."""
    from types import SimpleNamespace
    for label, sources in (
        ('unbound', ()),
        ('wrong owner', ('template.feature.a-corporate.a-business',)),
    ):
        demands = list(runtime.observation_demands)
        for n, demand in enumerate(demands):
            selectors = list(demand.selectors)
            position = next((i for i, s in enumerate(selectors) if s.names == ('cinder.w30-2.satisfied',)), None)
            if position is None:
                continue
            selector = selectors[position]
            selectors[position] = type(selector).model_validate({**selector.model_dump(), 'component_refs': sources})
            demands[n] = type(demand).model_validate({**demand.model_dump(), 'selectors': tuple(selectors)})
            break
        else:
            raise DesignError('Missing compiled reservoir mutation fixture')
        try:
            check_compiled_observations(scenario, SimpleNamespace(observation_demands=tuple(demands)))
        except DesignError as error:
            require('Compiled observation binding drift' in str(error), f'Wrong compiled rejection: {error}')
        else:
            raise DesignError(f'Compiled selector mutation accepted: {label}')
    print('PASS: 2 type-valid compiled observation mutations rejected', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--pack-check', action='store_true')
    parser.add_argument('--pack-max-members', type=int, default=1024,
                        help='Explicit upstream pack file/directory budget; default remains 1024')
    parser.add_argument('--training-hand-build-gate', action='store_true',
                        help='Also fail for unresolved Training starting records and service placement')
    args = parser.parse_args()
    require(version('raes') == '5.0.0', 'Use pinned raes==5.0.0 for reproducible validation')
    entry = PACK / 'sdl/cinder-typhoon.sdl.yaml'
    count = check_authored_open(entry)
    if args.pack_check:
        require(version('raes-env-packs') == '6.1.0', 'Use pinned raes-env-packs==6.1.0')
        from raes_env_packs.validation import _validate_pack_for_author_ci, PackValidationLimits
        require(args.pack_max_members > 0, 'Pack member budget must be positive')
        result, scenarios = _validate_pack_for_author_ci(
            PACK, limits=PackValidationLimits(max_members=args.pack_max_members))
        require(result.ok, f'Environment-pack author validation failed: {result.errors}')
        require(len(scenarios) == 1, 'Expected exactly one pack scenario entry point')
        scenario = scenarios[0]
        print(f'PASS: env-packs 6.1.0 author validation (local imports enabled; '
              f'member budget {args.pack_max_members})', flush=True)
    else:
        scenario = parse_sdl_file(entry)
    print(f'PASS: RAE 5.0.0 parsed and composed {count} modules', flush=True)
    briefs = load_briefs()
    expected_graph = Graph(read_json(PACK / 'docs/design/challenge-dependencies.json'), briefs)
    expected_model = make_topology(expected_graph)
    graph, model = check_expected(scenario, briefs, expected_graph, expected_model)
    check_campaign(graph)
    check_structure(graph, model)
    check_boundaries(graph, model)
    check_context_scopes(graph, model)
    check_context_acquisition(graph, model)
    closures = check_closures(graph, model)
    assert_completes(graph, model, set(graph.cards), 'SDL complete portfolio')
    print(f'PASS: SDL matches {len(graph.cards)} challenges, {len(graph.capabilities)} capabilities, '
          f'{len(model.boxes)} targets + Kali, {len(model.zones)} subnets, {len(model.domains)} authority domains', flush=True)
    print(f'PASS: {closures} minimal prerequisite closures and all 16 route combinations replay from SDL', flush=True)
    instantiated = instantiate_scenario(scenario)
    runtime = compile_runtime_model(instantiated)
    requirements = check_compiled_open(instantiated, runtime)
    observations = check_compiled_observations(scenario, runtime)
    check_narrative_runtime(scenario, runtime)
    print(f'PASS: instantiated and compiled {requirements} realization requirements; '
          'node open defaults and exact Kali intent verified', flush=True)
    print(f'PASS: {observations} named observations retain explicit runtime source bindings; '
          '50 technical drafts, record ownership and six consequence contracts verified', flush=True)
    if args.self_test:
        print(f'PASS: {adversarial_narrative_checks(scenario)} type-valid narrative SDL mutations rejected', flush=True)
        adversarial_checks(scenario, briefs, expected_graph, expected_model)
        adversarial_compiled_checks(scenario, runtime)
        self_test(graph, model)
    print('PASS: eight narrative collections retain compiled source and service bindings', flush=True)
    print('Static proof only: assets are authored; runtime materialization and deployment remain untested.', flush=True)
    if args.training_hand_build_gate:
        gaps = hand_build_gaps(scenario)
        require(not gaps, 'Training hand-build gate has gaps:\n- ' + '\n- '.join(gaps))
        print('PASS: Training hand-build design gate; no materialization was performed', flush=True)


if __name__ == '__main__':
    try:
        main()
    except DesignError as error:
        raise SystemExit(f'FAIL: {error}')
