"""Static Training authoring checks; never starts a service or performs a solve."""
from collections import Counter
import csv
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import re

from validate_challenges import require

PACK = Path(__file__).resolve().parents[1]
ASSETS = PACK / 'assets/training'
OUT_OF_WORLD = re.compile(
    r'\b(?:ctf|challenges?|hints?|flags?|players?|scoring|score|unlock(?:ed|s)?)\b|\b[TKW]\d{2}\.\d+\b',
    re.I,
)


def _ident(path):
    return re.sub(r'[^a-z0-9]+', '-', path.lower()).strip('-')


RECORDS = {}


def _records(namespace, target, rows):
    """Rows are asset, destination, route, access, visible."""
    for asset, destination, route, access, visible in rows:
        RECORDS[f'{namespace}.{_ident(asset)}'] = (asset, target, destination, route, access, visible)


_records('training-workstation-content', 'participant.kali', [
    ('workstation/TRAINING.md', '/home/cinder/TRAINING.md', None, 'local', True),
])
_records('training-workbench-content', 'training.t-workbench', [
    ('workbench/index.md', '/srv/cinder-workbench/public/index.md', '/', 'public', True),
    ('workbench/workspace/handover-current.md', '/srv/cinder-workbench/public/workspace/handover-current.md', '/workspace/handover/current.md', 'public', True),
    ('workbench/workspace/delivery-tracker.csv', '/srv/cinder-workbench/public/workspace/delivery-tracker.csv', '/workspace/delivery-tracker.csv', 'public', True),
    ('workbench/workspace/repository-seed.json', '/var/lib/cinder-workbench/repository-seed.json', None, 'seed', True),
    ('workbench/dispatch/index.md', '/srv/cinder-workbench/dispatch/index.md', '/', 'public', True),
    ('workbench/dispatch/notice-DL-204.md', '/srv/cinder-workbench/dispatch/notice-DL-204.md', '/notice-DL-204.md', 'public', True),
    ('workbench/dispatch/site.webmanifest', '/srv/cinder-workbench/dispatch/site.webmanifest', '/site.webmanifest', 'public', True),
    ('workbench/dispatch/current.json', '/srv/cinder-workbench/dispatch/content/current.json', '/content/current.json', 'public', True),
    ('workbench/dispatch/retired.json', '/srv/cinder-workbench/dispatch/content/retired.json', '/content/retired.json', 'public', True),
    ('workbench/dispatch/amendment-AMEND-204.json', '/srv/cinder-workbench/dispatch/retired/amendment-AMEND-204.json', '/retired/amendment-AMEND-204.json', 'public', True),
    ('workbench/courier/profile.json', '/srv/cinder-workbench/public/retired-client/profile.json', '/retired-client/profile.json', 'public', True),
    ('workbench/courier/request-history.txt', '/srv/cinder-workbench/public/retired-client/request-history.txt', '/retired-client/request-history.txt', 'public', True),
    ('workbench/courier/manifest-DL-204.json', '/var/lib/cinder-workbench/courier/manifest-DL-204.json', '/api/deliveries/{delivery_id}/manifest', 'bearer', True),
    ('workbench/diagnostics/public/DL-204.json', '/var/lib/cinder-workbench/diagnostics/public/DL-204.json', '/api/diagnostics/render', 'public', True),
    ('workbench/diagnostics/internal/DL-204.json', '/var/lib/cinder-workbench/diagnostics/internal/DL-204.json', '/api/diagnostics/render', 'public', True),
    ('workbench/service-contract.json', '/etc/cinder-workbench/service-contract.json', None, 'private', False),
])
_records('training-accounts-content', 'training.t-accounts', [
    ('accounts/index.md', '/srv/cinder-accounts/public/index.md', '/', 'public', True),
    ('accounts/candidates.md', '/srv/cinder-accounts/public/candidates.md', '/candidates.md', 'public', True),
    ('accounts/directory/index.json', '/srv/cinder-accounts/public/directory/index.json', ('/directory/', '/api/directory/staff'), 'public', True),
    ('accounts/directory/app.js', '/srv/cinder-accounts/public/directory/app.js', '/directory/app.js', 'public', True),
    ('accounts/directory/assignment-STF-204.json', '/var/lib/cinder-accounts/directory/assignment-STF-204.json', '/api/directory/staff/{staff_id}/assignment', 'public', True),
    ('accounts/realm.json', '/var/lib/cinder-accounts/realm.json', None, 'private', False),
    ('accounts/handover-rhea-moss.md', '/var/lib/cinder-accounts/handovers/rhea.moss.md', '/api/handover', 'session', True),
    ('accounts/assignment-ASG-204.json', '/var/lib/cinder-accounts/assignments/ASG-204.json', '/api/assignments/{assignment_id}/brief', 'session', True),
    ('accounts/assignment-ASG-317.json', '/var/lib/cinder-accounts/assignments/ASG-317.json', '/api/assignments/{assignment_id}/brief', 'session', True),
    ('accounts/service-contract.json', '/etc/cinder-accounts/service-contract.json', None, 'private', False),
])
_records('training-developer-content', 'training.t-developer', [
    ('developer/consumer-contract.md', '/srv/cinder-developer/public/consumer-contract.md', '/consumer-contract.md', 'public', True),
])
_records('training-developer-system-content', 'training.t-developer', [
    ('developer/index.md', '/srv/cinder-developer/public/index.md', '/', 'public', True),
    ('developer/repository-seed.json', '/var/lib/cinder-developer/repository-seed.json', None, 'seed', True),
    ('developer/build-BLD-204.log', '/srv/cinder-developer/public/build/BLD-204.log', '/jobs/BLD-204/log', 'public', True),
    ('developer/channel-manifest.json', '/var/lib/cinder-developer/registry/channel-manifest.json', '/api/channels/rehearsal/manifest', 'bearer', True),
    ('developer/sample-package/package.json', '/srv/cinder-developer/public/sample-package/package.json', '/sample-package/package.json', 'public', True),
    ('developer/sample-package/package-lock.json', '/srv/cinder-developer/public/sample-package/package-lock.json', '/sample-package/package-lock.json', 'public', True),
    ('developer/sample-package/scripts/register-rehearsal.js', '/srv/cinder-developer/public/sample-package/scripts/register-rehearsal.js', '/sample-package/scripts/register-rehearsal.js', 'public', True),
    ('developer/sample-package/fixtures/rehearsal-source.json', '/srv/cinder-developer/public/sample-package/fixtures/rehearsal-source.json', '/sample-package/fixtures/rehearsal-source.json', 'public', True),
    ('developer/baseline-package.json', '/var/lib/cinder-developer/registry/packages/1.4.0.json', None, 'private', False),
    ('developer/service-contract.json', '/etc/cinder-developer/service-contract.json', None, 'private', False),
])
_records('training-state-content', 'training.t-state', [
    ('state/index.md', '/srv/cinder-state/public/index.md', '/', 'public', True),
    ('state/field-guide.md', '/srv/cinder-state/public/field-guide.md', '/field-guide.md', 'public', True),
    ('state/captures/volume.json', '/srv/cinder-state/public/captures/volume.json', '/captures/volume.json', 'public', True),
    ('state/captures/status.json', '/srv/cinder-state/public/captures/status.json', '/captures/status.json', 'public', True),
    ('state/replay/report.json', '/srv/cinder-state/public/replay/report.json', '/replay/report.json', 'public', True),
    ('state/replay/requests.json', '/srv/cinder-state/public/replay/requests.json', '/replay/requests.json', 'public', True),
    ('state/replay/observations.csv', '/srv/cinder-state/public/replay/observations.csv', '/replay/observations.csv', 'public', True),
    ('state/practice-initial.json', '/var/lib/cinder-state/initial.json', None, 'private', False),
])
_records('training-state-config-content', 'training.t-state', [
    ('state/service-contract.json', '/etc/cinder-state/service-contract.json', None, 'private', False),
])

# The first two hand-authored content modules predate the path-derived ids used
# by the later modular files. Preserve their published stable identifiers.
for _derived, _stable in {
    'training-developer-content.developer-consumer-contract-md': 'training-developer-content.consumer-contract',
    'training-state-content.state-index-md': 'training-state-content.index',
    'training-state-content.state-field-guide-md': 'training-state-content.field-guide',
    'training-state-content.state-captures-volume-json': 'training-state-content.captures-volume',
    'training-state-content.state-captures-status-json': 'training-state-content.captures-status',
    'training-state-content.state-replay-report-json': 'training-state-content.replay-report',
    'training-state-content.state-replay-requests-json': 'training-state-content.replay-requests',
    'training-state-content.state-replay-observations-csv': 'training-state-content.replay-observations',
    'training-state-content.state-practice-initial-json': 'training-state-content.practice-initial',
}.items():
    RECORDS[_stable] = RECORDS.pop(_derived)


def _all_routes(node):
    return [route for app in node.runtime.applications for route in app.routes]


def _data(name):
    return json.loads((ASSETS / name).read_text())


def check_training(scenario, briefs):
    require(Counter(b['tier_name'] for i, b in briefs.items() if i.startswith('T')) ==
            {'Easy': 12, 'Medium': 4}, 'Training allocation changed')
    prefixes = tuple(key.split('.', 1)[0] + '.' for key in RECORDS)
    authored = {key for key in scenario.content if key.startswith(prefixes)}
    require(authored == set(RECORDS), 'Training authored content inventory drift')

    for key, (asset, owner, path, route_path, access, visible) in RECORDS.items():
        content = scenario.content[key]
        require(content.type.value == 'file' and content.target == owner and content.path == path,
                f'Training artifact placement drift: {key}')
        expected = (ASSETS / asset).read_text()
        require(content.text == expected and content.source is None and content.text_from is None,
                f'Training artifact bytes drift: {key}')
        if visible:
            require(not OUT_OF_WORLD.search(expected), f'Training artifact breaks the fourth wall: {key}')

        node = scenario.nodes[owner]
        inventory = {item.path: item for item in node.runtime.filesystem_inventory}
        require(path in inventory, f'Training file ownership missing: {key}')
        entry = inventory[path]
        expected_owner = 'cinder' if owner == 'participant.kali' else 'root'
        expected_mode = '0440' if path.startswith(('/var/', '/etc/')) else '0444'
        require(entry.owner_user == expected_owner and entry.mode == expected_mode
                and entry.content_digest == sha256(expected.encode()).hexdigest()
                and entry.digest_algorithm == 'sha256', f'Training file ownership/digest drift: {key}')

        exposed = [route for route in _all_routes(node) if path in route.static_assets]
        if route_path is None:
            require(not exposed, ('Private Training initialization exposed' if key == 'training-state-content.practice-initial'
                                  else f'Private or seed Training file has a static route: {key}'))
        else:
            expected_paths = {route_path} if isinstance(route_path, str) else set(route_path)
            require({route.path for route in exposed} == expected_paths and len(exposed) == len(expected_paths),
                    f'Training route binding drift: {key}')
            if access == 'public':
                require(all(route.auth_required is False and route.session_required is False
                            for route in exposed),
                        f'Training public route drift: {key}')
            elif access == 'bearer':
                require(all(route.auth_required is True and route.auth_scheme == 'Bearer'
                            and route.session_required is False for route in exposed),
                        f'Training bearer route drift: {key}')
            elif access == 'session':
                require(all(route.auth_required is True and route.session_required is True
                            for route in exposed),
                        f'Training session route drift: {key}')

    require(not any(k.startswith(('t01.', 't02.', 't03.', 't04.')) for k in scenario.content),
            'Training operation modules contain placeholder content')
    for key, relationship in scenario.relationships.items():
        if key.startswith(('t01.', 't02.', 't03.', 't04.', 'flows-participant.')):
            require(not relationship.properties, f'Training private SDL semantics returned: {key}')
    require('contexts.context-player' not in scenario.relationships
            and 'contexts.context-player' not in scenario.workflows,
            'Workstation access duplicates the native interactive_access declaration')
    for key, contract in scenario.action_contracts.items():
        if key.startswith(('t01.', 't02.', 't03.', 't04.')):
            require([p.precondition_id for p in contract.preconditions] ==
                    ['eligibility', 'normal-surface', 'boundaries'], 'Training reset precondition returned')
    require('T03.1' not in briefs['T03.4']['requires_any'][0], 'Formatter has a hidden history prerequisite')
    require(briefs['T04.3']['requires_any'] == [['TRAINING']], 'Practice requires the recorded capture')
    check_network(scenario)
    check_workbench_records()
    check_account_records()
    check_developer_records()
    check_state_records()


def check_network(scenario):
    expected = {
        'participant.kali': ('10.77.40.10', 'kali.training', 'training.subnet'),
        'training.t-workbench': ('10.77.40.20', 'workbench.training', 'training.subnet'),
        'training.t-accounts': ('10.77.40.30', 'accounts.training', 'training.subnet'),
        'training.t-developer': ('10.77.40.40', 'developer.training', 'training.subnet'),
        'training.t-state': ('10.77.40.50', 'state.training', 'training.subnet'),
    }
    require(scenario.infrastructure['training.subnet'].properties.cidr == '10.77.40.0/24'
            and scenario.infrastructure['training.subnet'].properties.gateway == '10.77.40.1'
            and scenario.infrastructure['training.subnet'].properties.internal is True,
            'Training subnet addressing or isolation drift')
    require(scenario.infrastructure['participant.kali'].links == ['training.subnet'],
            'Training workstation attachment drift')
    for key, (address, dns_name, network) in expected.items():
        endpoints = scenario.nodes[key].runtime.network.endpoints
        require(len(endpoints) == 1 and endpoints[0].network == network
                and endpoints[0].ip_address == address and endpoints[0].gateway == '10.77.40.1'
                and endpoints[0].ip_prefix_length == 24 and endpoints[0].dns_names == [dns_name],
                f'Training endpoint drift: {key}')


def check_workbench_records():
    seed = _data('workbench/workspace/repository-seed.json')
    require([c['logical_id'] for c in seed['commits']] == ['handover-written', 'blank-template']
            and seed['commits'][1]['parent'] == 'handover-written'
            and 'DL-204' in seed['commits'][0]['tree']['handover.md']
            and 'DL-204' not in seed['commits'][1]['tree']['handover.md'],
            'Workbench Git history no longer contains a genuine replaced handover')
    tracker = (ASSETS / 'workbench/workspace/delivery-tracker.csv').read_text()
    require(tracker.count('DL-204') == 1, 'Workbench tracker no longer resolves DL-204 once')
    contract = _data('workbench/service-contract.json')
    require(contract['courier']['allowed_delivery_id'] == 'DL-204'
            and contract['courier']['list_status'] == 403 and contract['courier']['write_status'] == 405,
            'Courier authorization contract drift')
    require(contract['diagnostics']['decision_order'][1].startswith('Require the raw')
            and contract['diagnostics']['decision_order'][2] == 'Percent-decode view exactly once.'
            and contract['diagnostics']['intended_view'] == 'public%2F..%2Finternal%2FDL-204.json'
            and contract['diagnostics']['outbound_network'] is False
            and contract['diagnostics']['execution'] is False,
            'Diagnostic weakness or confinement drift')


def check_account_records():
    realm = _data('accounts/realm.json')
    states = {row['account']: row['state'] for row in realm['accounts']}
    detail = _data('accounts/directory/assignment-STF-204.json')
    own = _data('accounts/assignment-ASG-204.json')
    other = _data('accounts/assignment-ASG-317.json')
    contract = _data('accounts/service-contract.json')
    require(states == {'mina.cho': 'inactive', 'rhea.moss': 'active'}
            and realm['unknown_candidates'] == ['owen.pike'], 'Account candidate states drift')
    require(detail['account'] == 'rhea.moss' and detail['staff_detail'] == 'Blue cabinet 17'
            and contract['recovery']['accepted_tuple'] == ['rhea.moss', 'CASE-7Q4M', 'Blue cabinet 17'],
            'Observable recovery factors no longer converge exactly')
    require(own['owner'] == 'rhea.moss' and own['paired_assignment_id'] == other['assignment_id']
            and other['owner'] == 'dax.hale' and set(contract['assignments']['known_assignments']) == {'ASG-204', 'ASG-317'},
            'Assignment discovery or ownership drift')
    require('do not compare' in contract['assignments']['brief_authorization']
            and contract['recovery']['session']['random_bytes'] == 32
            and contract['recovery']['session']['persist_for_environment_lifetime'] is True,
            'Recovery session or record-authorization mechanics drift')


def check_developer_records():
    seed = _data('developer/repository-seed.json')
    first, head = seed['commits']
    fixture = 'test/fixtures/DL-204.json'
    require(first['logical_id'] == 'fixture-added' and fixture in first['tree']
            and head['parent'] == first['logical_id'] and head['delete'] == [fixture]
            and fixture in head['tree']['REVIEW.md'], 'Developer Git history or fair lead drift')
    sample = _data('developer/sample-package/package.json')
    source = _data('developer/sample-package/fixtures/rehearsal-source.json')
    script = (ASSETS / 'developer/sample-package/scripts/register-rehearsal.js').read_text()
    require(sample['scripts']['postinstall'] == 'node scripts/register-rehearsal.js'
            and source['record_id'] == 'SRC-204'
            and '/opt/cinder-sample/fixtures/rehearsal-source.json' in script
            and 'http://developer.training:8084/api/rehearsal/ingest' in script,
            'Static lifecycle source/destination binding drift')
    contract = _data('developer/service-contract.json')
    manifest = _data('developer/channel-manifest.json')
    require(manifest['consumer_range'] == '>=1.4.0 <2.0.0'
            and contract['registry']['allowed_name'] == '@cinder/delivery-formatter'
            and contract['registry']['allowed_versions'] == '>1.4.0 <2.0.0 stable SemVer only',
            'Registry compatibility contract drift')
    process = contract['consumer']['process']
    require(process == {'timeout_seconds': 2, 'memory_mib': 64, 'network': False,
                        'read_only_filesystem': True, 'environment': {}, 'one_invocation': True}
            and contract['consumer']['selection'].startswith('highest compatible SemVer'),
            'Consumer resolution or isolation drift')


def check_state_records():
    volume = _data('state/captures/volume.json')
    status = _data('state/captures/status.json')
    initial = _data('state/practice-initial.json')
    require(volume['observed_volume_l'] == 1200 and volume['requested_volume_l'] == 1000
            and volume['unit'] == 'L' and volume['quality'] == 'good', 'Volume capture drift')
    require(status['controller_revision'] == initial['controller_revision'] == 'TR-1'
            and status['status_word'] == initial['status_word'] == 5, 'Status legend/capture drift')
    require(initial['tank_id'] == 'PT-01' and initial['observed_volume_l'] == 1200
            and initial['capacity_l'] == 1500 and initial['minimum_retained_volume_l'] == 200
            and initial['maximum_transfer_l'] == 200 and initial['flow_l_per_second'] == 20
            and initial['measurement_resolution_l'] == initial['comparison_tolerance_l'] == 0.1
            and initial['outlet_position'] == 'closed' and initial['quality'] == 'good'
            and initial['requests'] == initial['observations'] == [], 'Practice initial state drift')
    service = _data('state/service-contract.json')
    require(service['transfer']['minimum_l'] == 1 and service['transfer']['maximum_l'] == 200
            and service['transfer']['flow_l_per_second'] == 20
            and service['persistence'].startswith('Load initial_state once'), 'Practice service contract drift')
    report = _data('state/replay/report.json')
    requests = {row['request_id']: row for row in _data('state/replay/requests.json')}
    trace = list(csv.DictReader(StringIO((ASSETS / 'state/replay/observations.csv').read_text())))
    current = requests[report['request_id']]
    stale = requests[report['source_request_id']]
    require(current['attempt_id'] == report['attempt_id'] == 'AT-042'
            and stale['attempt_id'] == 'AT-041' and stale['result'] == 'accepted'
            and current['result'] == 'rejected' and current['reason'] == 'service_hold'
            and stale['requested_at'] == report['source_accepted_at'] < current['requested_at'] < report['generated_at'],
            'Replay no longer identifies a unique stale request')
    samples = [row for row in trace if row['attempt_id'] == current['attempt_id']]
    require(len(samples) == 2 and all(row['tank_id'] == current['tank_id'] == 'RT-02'
            and row['request_id'] == current['request_id'] and row['observed_volume_l'] == '1000.0'
            and row['outlet_position'] == 'closed' and row['status_word'] == '5'
            and row['quality'] == 'good' and row['unit'] == 'L' for row in samples),
            'Replay observations do not prove unchanged state')
    require(volume['tank_id'] == status['tank_id'] == 'CT-01'
            and len({volume['tank_id'], initial['tank_id'], current['tank_id']}) == 3,
            'Captured, practice and replay tank identities overlap')


def hand_build_gaps(scenario):
    """Return concrete missing inputs that would force a builder to invent design."""
    gaps = []
    if any(key.startswith(('t01.', 't02.', 't03.', 't04.')) for key in scenario.content):
        gaps.append('Training operation modules still contain placeholder starting records')
    if not set(RECORDS).issubset(scenario.content):
        gaps.append('Training authored content inventory is incomplete')
    for key in ('training.t-workbench', 'training.t-accounts', 'training.t-developer', 'training.t-state'):
        node = scenario.nodes[key]
        if not node.services or node.runtime is None or not node.runtime.applications:
            gaps.append(f'{key}: concrete service/application configuration is missing')
        if node.runtime is None or node.runtime.network is None or len(node.runtime.network.endpoints) != 1:
            gaps.append(f'{key}: exact Training network endpoint is missing')
    if scenario.infrastructure['participant.kali'].links != ['training.subnet']:
        gaps.append('Training transport: workstation is not attached only to the Training segment')
    required_configs = {
        'training.t-workbench': '/etc/cinder-workbench/service-contract.json',
        'training.t-accounts': '/etc/cinder-accounts/service-contract.json',
        'training.t-developer': '/etc/cinder-developer/service-contract.json',
        'training.t-state': '/etc/cinder-state/service-contract.json',
    }
    for key, path in required_configs.items():
        inventory = {entry.path for entry in scenario.nodes[key].runtime.filesystem_inventory}
        if path not in inventory:
            gaps.append(f'{key}: exact application behavior contract is missing')
    return gaps
