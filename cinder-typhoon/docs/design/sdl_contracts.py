"""Expected SDL meaning from challenge cards and reviewed in-world ownership.

This is a design-side contract, independent of the decoded SDL. Interaction
surfaces remain in model_topology; proof producers need not be player-accessible.
The functions read authored requirements, never infer meaning from SDL output.
"""
import re

from validate_challenges import require


# Most outcomes belong to the acted-on feature. These cards explicitly name a
# different producer, or a join of producers, in their technical evidence.
EVIDENCE_OWNERS = {
    'K01.1': ('k-source',),
    'K01.2': ('k-support',),
    'K06.3': ('k-registry', 'k-ci'),
    'K09.4': ('k-ci/runner',),
}

# Partition these records explicitly: a local recovery clue is not a copy of
# the protected service record. Descriptions specify assets, not asset bytes.
RECORD_OWNERS = {
    'K01.1': {
        'k-dev': "Rowan's local Gitea credential-helper/session material and FieldKest Forge project reference; the protected current handover and Forge audit remain at the source service.",
        'k-source': "The protected current FieldKest handover and revision, read-only developer project role, session binding, and authenticated handover-read audit. The developer workspace holds the recovery material.",
    },
    'K01.2': {
        'k-dev': 'Browser session-restoration material and the support gateway reference; the authoritative ARWC conversation and restoration audit remain at the support service.',
        'k-support': 'The retained ARWC conversation, SUP-2841 reference, player-scoped restored session, and gateway audit of restoration and protected conversation retrieval.',
    },
    'K06.3': {
        'k-registry': 'Player-scoped release-channel versions, compatible package metadata, and publication audit. The protected execution receipt belongs to the isolated test consumer.',
        'k-ci': 'Isolated rehearsal-consumer contract, synthetic input, consumed package revision, execution record, and protected fresh receipt; no ARWC delivery route.',
    },
}

ELIGIBILITY = ('Satisfy one complete alternative in the referenced workflow and obtain '
               'the required scoped access to every listed surface.')
RESET_CONTEXT = ('These are requirements on the realized environment. Apply reset behavior '
                 'only when a participant reset is requested, not on challenge completion.\n\n')
SEED_CONTEXT = ('required in-world starting records. Allocate each record to its actual owning '
                'service; this declaration does not duplicate secrets across services or grant their visibility.')
FAILURE_CLASSES = ['precondition_unsatisfied', 'authority_denied', 'target_unavailable',
                   'partial_success', 'backend_error', 'unknown']
TECHNICAL_HEADINGS = ('Surface and normal behavior', 'Vulnerability and intended solution',
                      'Evidence and completion', 'Boundaries and reset', 'Author checks')


def plain(text):
    return re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text).strip()


def text_section(brief, heading, level=2):
    match = re.search(r'^' + '#' * level + ' ' + re.escape(heading) +
                      r'[^\n]*\n(.*?)(?=^#{1,' + str(level) + r'} |\Z)',
                      brief['text'], re.M | re.S)
    require(match is not None, f'Missing source section: {heading}')
    return plain(match[1])


def technical_sections(brief):
    if brief['status'] != 'Technical draft':
        return {}
    return {h: text_section(brief, h, 3) for h in TECHNICAL_HEADINGS}


def feature_ref(model, endpoint):
    box = model.domains[endpoint].box
    return 'features.' + model.boxes[box].zone + '.' + endpoint.replace('/', '--')


def action_refs(model, ident):
    return list(dict.fromkeys(feature_ref(model, s.endpoint) for s in model.placements[ident]))


def evidence_refs(model, ident):
    if ident in EVIDENCE_OWNERS:
        return [feature_ref(model, ep) for ep in EVIDENCE_OWNERS[ident]]
    return action_refs(model, ident)


def capability_sources(graph, model, ident):
    """Allowable producer provenance; this union does not replace event AND/OR."""
    if ident in graph.cards:
        return evidence_refs(model, ident)
    return sorted({ref for group in graph.capabilities[ident] for dep in group
                   for ref in capability_sources(graph, model, dep)})


def record_specs(brief, model, ident):
    match = re.search(r'\*\*Starting material:\*\* (.*)', brief['text'])
    require(match is not None, f'Missing starting material: {ident}')
    materials = plain(match[1])
    normal = technical_sections(brief).get('Surface and normal behavior', '')
    owners = RECORD_OWNERS.get(ident)
    if owners is None:
        owners = {s.box: materials for s in model.placements[ident]}
    records = []
    for box, owned in owners.items():
        description = f'{ident}: {SEED_CONTEXT}\n{materials}'
        if normal:
            description += '\n\n' + normal
        if ident in RECORD_OWNERS:
            description += '\n\nRecords owned by this system: ' + owned
        records.append({'target': model.boxes[box].zone + '.' + box,
                        'description': description, 'item': owned})
    return records


CONSEQUENCE_SUFFIX = (' Apply once per validated participant event; repeated evidence is '
                      'idempotent. No continuous process simulation.')
# Explicit affected systems and bounded effects, independent of event predicates.
# These protect the distinction between live process state and retained rehearsal.
CONSEQUENCES = {
    'reservoir-release': (
        'Cairn Reach reserve incident',
        ('a-control.a-reservoir', 'a-control.a-instruments', 'a-corporate.a-data'),
        'The verified outlet transition advances this participant’s persisted reservoir stage. Independent gate-position and usable-volume records show the bounded release; reserve planning reports financial loss and water restrictions. A command acknowledgement alone does not establish this result. No catastrophic effects.'),
    'costly-release-rehearsal': (
        'Costed release rehearsal', ('a-engineering.a-hmi', 'a-corporate.a-data'),
        'Advance only the participant’s costed-release rehearsal record. Publish its trace and costed reserve consequence separately from the live reservoir stage.'),
    'feedback-rehearsal': (
        'Feedback rehearsal', ('a-engineering.a-hmi', 'a-control.a-instruments'),
        'Record the accepted supervisory rehearsal and its independent feedback. Rehearsal state cannot overwrite the live reservoir outcome.'),
    'false-planning-decision': (
        'False reserve-planning decision', ('a-corporate.a-data', 'a-engineering.a-diagnostics'),
        'Retain the accepted estimate and changed planning decision. Independent process measurements stay truthful. This planning effect does not open gates.'),
    'covered-release-rehearsal': (
        'Covered release rehearsal', ('a-corporate.a-data', 'a-engineering.a-hmi', 'a-control.a-instruments'),
        'Retain the covered-release rehearsal trace and the discrepancy between planning reports and independent process observations. Separate rehearsal state cannot advance the main release stage.'),
    'procurement-loss': (
        'Replacement-water procurement loss', ('a-corporate.a-business', 'a-corporate.a-data'),
        'Issue the in-world order acknowledgement and financial record for the proved district-attribution error. Retain the selected quote, supplier, quantity, and delivery period; no gate action follows from procurement.'),
}
