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
    'K09.4': ('k-ci/runner', 'k-cloud-api/build-records'),
    'W30.2': ('a-reservoir', 'a-instruments', 'a-data'),
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
    'K09.4': {
        'k-ci': 'The review-job input and argv command schema, ordinary render-review and privileged runner-command profiles, read-only runner operations note, non-secret connections.env, per-service client configurations, required native client tools, and private retained workspace with authenticated file transfer. Worker credential leases and trusted execution/file-read audits are generated per run, not seeded successes. Commands may read their own scoped worker credentials or explicitly use separately earned identities; no host or CI administration secrets and no pre-earned colleague credentials are mounted. Persistent workspace files survive retry and job exit; worker leases and processes do not.',
        'k-cloud-api': 'The existing svc-fieldlink-ci principal and its bounded build-record scope, worker-status interface, per-run credential and job-origin validation, independent request audit, and separately protected trust/build records. The authenticated response and audit are generated from a real request, not seeded. A status read neither returns the backup principal nor changes service permissions.',
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
TRAINING_CONTENT = {
    'T01.1': (
        'training-workbench-content.workbench-index-md',
        'training-workbench-content.workbench-workspace-handover-current-md',
        'training-workbench-content.workbench-workspace-delivery-tracker-csv',
        'training-workbench-content.workbench-workspace-repository-seed-json',
    ),
    'T01.2': (
        'training-workbench-content.workbench-dispatch-index-md',
        'training-workbench-content.workbench-dispatch-notice-dl-204-md',
        'training-workbench-content.workbench-dispatch-site-webmanifest',
        'training-workbench-content.workbench-dispatch-current-json',
        'training-workbench-content.workbench-dispatch-retired-json',
        'training-workbench-content.workbench-dispatch-amendment-amend-204-json',
    ),
    'T01.3': (
        'training-workbench-content.workbench-courier-profile-json',
        'training-workbench-content.workbench-courier-request-history-txt',
        'training-workbench-content.workbench-courier-manifest-dl-204-json',
        'training-workbench-content.workbench-service-contract-json',
    ),
    'T01.4': (
        'training-workbench-content.workbench-diagnostics-public-dl-204-json',
        'training-workbench-content.workbench-diagnostics-internal-dl-204-json',
        'training-workbench-content.workbench-service-contract-json',
    ),
    'T02.1': (
        'training-accounts-content.accounts-index-md',
        'training-accounts-content.accounts-candidates-md',
        'training-accounts-content.accounts-realm-json',
        'training-accounts-content.accounts-service-contract-json',
    ),
    'T02.2': (
        'training-accounts-content.accounts-directory-index-json',
        'training-accounts-content.accounts-directory-app-js',
        'training-accounts-content.accounts-directory-assignment-stf-204-json',
        'training-accounts-content.accounts-service-contract-json',
    ),
    'T02.3': (
        'training-accounts-content.accounts-realm-json',
        'training-accounts-content.accounts-directory-assignment-stf-204-json',
        'training-accounts-content.accounts-handover-rhea-moss-md',
        'training-accounts-content.accounts-service-contract-json',
    ),
    'T02.4': (
        'training-accounts-content.accounts-handover-rhea-moss-md',
        'training-accounts-content.accounts-assignment-asg-204-json',
        'training-accounts-content.accounts-assignment-asg-317-json',
        'training-accounts-content.accounts-service-contract-json',
    ),
    'T03.1': (
        'training-developer-system-content.developer-index-md',
        'training-developer-system-content.developer-repository-seed-json',
        'training-developer-content.consumer-contract',
    ),
    'T03.2': (
        'training-developer-system-content.developer-build-bld-204-log',
        'training-developer-system-content.developer-channel-manifest-json',
        'training-developer-system-content.developer-service-contract-json',
    ),
    'T03.3': (
        'training-developer-system-content.developer-sample-package-package-json',
        'training-developer-system-content.developer-sample-package-package-lock-json',
        'training-developer-system-content.developer-sample-package-scripts-register-rehearsal-js',
        'training-developer-system-content.developer-sample-package-fixtures-rehearsal-source-json',
    ),
    'T03.4': (
        'training-developer-content.consumer-contract',
        'training-developer-system-content.developer-channel-manifest-json',
        'training-developer-system-content.developer-baseline-package-json',
        'training-developer-system-content.developer-service-contract-json',
    ),
    'T04.1': ('training-state-content.index', 'training-state-content.field-guide',
             'training-state-content.captures-volume'),
    'T04.2': ('training-state-content.index', 'training-state-content.field-guide',
             'training-state-content.captures-status'),
    'T04.3': ('training-state-content.index', 'training-state-content.field-guide',
             'training-state-content.practice-initial',
             'training-state-config-content.state-service-contract-json'),
    'T04.4': ('training-state-content.index', 'training-state-content.field-guide',
             'training-state-content.replay-report', 'training-state-content.replay-requests',
             'training-state-content.replay-observations'),
}
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
    headings = tuple('Boundaries' if brief['operation'].startswith('T') and h == 'Boundaries and reset'
                     else 'Boundaries and persistence' if brief['operation'].startswith(('K', 'W'))
                     and h == 'Boundaries and reset' else h for h in TECHNICAL_HEADINGS)
    return {h: text_section(brief, h, 3) for h in headings}


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
    # Exact Training content lives in modular native content records, not a
    # second set of anonymous datasets describing the same records.
    if ident.startswith('T'):
        return []
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
        'Retain and present this participant’s already verified reservoir incident and continuity notice. The accepted in-world command produces the persisted process transition and independent gate-position and usable-volume records; reserve planning calculates financial loss and water restrictions before W30.2 is satisfied. This post-completion event neither commands the gates nor creates the evidence required to trigger itself. Replaying it cannot release more water or duplicate the financial loss. A command acknowledgement alone does not establish the result. No catastrophic effects.'),
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
