"""Static K09 handoff checks; not a job executor or authorization implementation."""
from pathlib import Path
import json
import re

from model_topology import active_contexts, assert_completes, earned, shortest
from sdl_contracts import text_section
from validate_challenges import require


PACK = Path(__file__).resolve().parents[1]
ASSETS = PACK / 'assets/keplerops/build-operations'
RECORDS = {
    'diagnostic-request-reference': (
        'diagnostic-request-reference.md',
        '/srv/fieldlink-ci/reviews/diagnostic-request-reference.md',
    ),
    'runner-operations-note': (
        'runner-operations.md',
        '/srv/fieldlink-ci/runner/runner-operations.md',
    ),
}
PROOF_OWNERS = [
    'features.k-delivery.k-ci--runner',
    'features.k-cloud.k-cloud-api--build-records',
]
CONNECTIONS = {'source', 'packages', 'staff', 'certificates', 'cloud-policy',
               'build-records', 'maintenance'}
PRODUCT_READ_PATHS = {
    'source': '/api/v1/user/repos',
    'packages': '/@keplerops%2ffieldlink-connector',
}
STATUS_COMMAND = (
    '. /run/fieldlink-ci/connections.env; exec curl -q --silent --show-error --fail '
    '--config /run/fieldlink-ci/build-records.curl '
    '--url "$FIELDLINK_BUILD_RECORDS_URL/api/build-records/worker-status"'
)
# Authoring requirements, not a runtime command or authorization interpreter.
COMMAND_CONTRACT = {
    'normal-surface': (
        'actual command execution, not a fixed list of service requests',
        'private persistent `/workspace`',
        'operations note and per-run configuration are mounted read-only',
        'Client tools required by the selected downstream mechanisms must already be installed',
    ),
    'scope-and-persistence': (
        'Network enforcement is outside the job',
        'no host paths, device access, runtime socket, CI controller credentials',
        'symlink-safe access',
        'log masking is not a security boundary',
        "restricts use to the issuing job's network origin",
        'real client with that material explicitly',
        'No colleague identity is initially seeded here',
        'revokes its worker lease and terminates all child processes',
        'not the separately earned identities retained in the workspace',
        'Serialize writes to one account',
    ),
}
OUT_OF_WORLD = re.compile(
    r'\b(?:ctf|challenges?|hints?|flags?|players?|scoring|score|unlock(?:ed|s)?)\b'
    r'|\b[TKW]\d{2}\.\d+\b', re.I,
)


def check_k09_assets(scenario, *, prefix='k09.'):
    """Check exact in-world K09 documents without the legacy topology model."""
    texts = {}
    for key, (filename, target_path) in RECORDS.items():
        content = scenario.content[prefix + key]
        text = content.text
        require(content.type.value == 'file' and content.target == 'k-delivery.k-ci'
                and content.path == target_path and content.sensitive is True,
                f'K09 document ownership drift: {key}')
        require(text == (ASSETS / filename).read_text(), f'K09 document text drift: {key}')
        require(not OUT_OF_WORLD.search(text), f'K09 document breaks the fourth wall: {key}')
        require(content.source is None and content.text_from is None,
                f'K09 document has a second content source: {key}')
        texts[key] = text
    reference = texts['diagnostic-request-reference']
    note = texts['runner-operations-note']
    require(all(term in reference for term in (
        'POST /api/review-jobs', '`support_input`', '`diagnostic`',
        '`runner-command`', '`argv`', '/bin/sh',
        '`/srv/fieldlink-ci/runner/runner-operations.md`',
        'Files view', 'exit status',
        'from the completed review', 'not the', 'unresolved input link',
    )), 'K09 request reference omits a necessary discoverable input')
    reference_examples = [json.loads(example) for example in
                          re.findall(r'```json\n(.*?)\n```', reference, re.S)]
    require(reference_examples == [
        {'profile': 'render-review'},
        {'profile': 'runner-command', 'argv': ['/bin/pwd']},
    ], 'K09 request reference loses the ordinary command format')
    examples = re.findall(r'```json\n(.*?)\n```', note, re.S)
    require(len(examples) == 1, 'K09 operations note needs one unambiguous request example')
    request = json.loads(examples[0])
    require(request == {
        'profile': 'runner-command',
        'argv': ['/bin/sh', '-c', STATUS_COMMAND],
    }, 'K09 status example changes authority or returns downstream answers')
    services = set(re.findall(r'^\| `([^`]+)` \|', note, re.M))
    require(services == CONNECTIONS, 'K09 operations note misstates available service connections')
    paths = dict(re.findall(r'^\| `([^`]+)` \| `([^`]+)` \|', note, re.M))
    require(all(paths.get(service) == path for service, path in PRODUCT_READ_PATHS.items()),
            'K09 product connection uses an unsupported read path')
    require('svc-fieldlink-ci' in note and 'retained `support_input`' in note,
            'K09 operations note omits identity or repeat-request continuity')
    compact_note = ' '.join(note.split())
    require(all(term in compact_note for term in (
        'Do not load the worker\'s credential configuration for that request',
        'A failed authentication is not retried as the worker automatically',
        'leaves workspace files and separately issued client material intact',
        'Network policy is enforced outside the job',
    )), 'K09 operations note loses independent identity use or job boundaries')
    return texts


def check_k09_handoff(scenario, briefs, graph, model, *, prefix='k09.'):
    """Accept composed SDL, or a structurally parsed module in focused tests.

    The complete SDL checker separately runs upstream reference validation,
    instantiation and compilation. This function checks authored expectedness.
    """
    check_k09_assets(scenario, prefix=prefix)
    description = text_section(briefs['K09.4'], 'Challenge description')
    require(not OUT_OF_WORLD.search(description), 'K09 player-facing description breaks the fourth wall')

    key = prefix + 'c4'
    procedure = ' '.join(scenario.action_contracts[key].procedure_basis.split())
    require(all(term in procedure for term in (
        'retained input reference from a completed integration review',
        'submitting account, and workspace generation',
        'returned by normal review processing in K09.3, not by objective evaluation',
        'server-owned diagnostic eligibility metadata',
    )), 'K09 command dispatch loses its real input prerequisite')
    preconditions = {p.precondition_id: ' '.join(p.description.split())
                     for p in scenario.action_contracts[key].preconditions}
    for ident, requirements in COMMAND_CONTRACT.items():
        require(all(term in preconditions.get(ident, '') for term in requirements),
                f'K09 command contract loses required behavior: {ident}')
    evidence = scenario.evidence_requirements[key]
    require(all(term in ' '.join(evidence.description.split()) for term in (
        'trusted job network origin', 'per-run credential lease',
        'outside the participant-writable job',
    )), 'K09 command evidence trusts participant-controlled proof')
    proposition = scenario.propositions[key]
    require(evidence.source_refs == PROOF_OWNERS and proposition.subjects == PROOF_OWNERS
            and list(evidence.observation_demand.selector.component_refs) == PROOF_OWNERS,
            'K09 handoff needs independent worker and destination proof')
    require(proposition.basis.value == 'observed_state' and proposition.quantifier.value == 'all',
            'K09 handoff cannot accept an asserted or partial result')
    require(briefs['K09.4']['tier_name'] == 'Medium'
            and [briefs[f'K09.{n}']['tier_name'] for n in range(1, 5)] ==
            ['Easy', 'Easy', 'Medium', 'Medium'], 'K09 difficulty allocation changed')

    before = shortest(graph, 'K09.3')
    completed = shortest(graph, 'K09.4')
    require(completed - before == {'K09.4'}, 'K09 handoff introduces an extra prerequisite')
    require('k-ci/runner' not in active_contexts(model, earned(graph, before), 'service'),
            'K09 review retrieval grants worker access early')
    require('k-ci/runner' in active_contexts(model, earned(graph, completed), 'service'),
            'K09 completed handoff does not retain worker access')
    for target in ('K14.1', 'K19.1', 'K30.1', 'K31.1'):
        require(target not in completed, f'K09 prematurely completes {target}')
        assert_completes(graph, model, completed | {target}, f'K09 handoff to {target}')
