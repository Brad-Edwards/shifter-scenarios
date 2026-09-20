"""Check release and operating records against accepted evidence and shipped bytes."""
from collections import Counter
from datetime import datetime
import csv
import hashlib
import io
import json
import re
import yaml


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_release_platform(root, identity, roster, mail, docs, calendars):
    manifest = yaml.safe_load((root / 'authoring/release-platform.yaml').read_text())
    quality = yaml.safe_load((root / 'authoring/product-quality.yaml').read_text())['records']
    accepted = {q['id']: q for q in quality if q['decision'] == 'accepted'}
    by_doc = {d['id']: d for d in docs}
    source_docs = {d['id']: d for d in docs if d['story'] == 'release-platform'}
    source_mail = {m['id']: m for m in mail if m['story'] == 'release-platform'}
    by_event = {e['id']: e for e in calendars}
    people = {p['key']: p for p in roster}
    team = {p['key'] for p in roster if p['department'] == 'Platform and release'}
    contacts = people | identity['correspondents']
    records = manifest['records']
    snapshot = datetime.fromisoformat(identity['snapshot'])
    require(manifest['snapshot'] == identity['snapshot'], 'Release snapshot drift')
    require(manifest['required_base'] == {'repository_commit': '631dfa1',
            'product_quality_commit': '1ac57ee', 'fieldkest_engineering_commit': 'da8e33e',
            'workforce_commit': 'cf20e3e'}, 'Release accepted-base drift')
    require(len(records) == len({r['id'] for r in records}) == 120,
            'Release/platform history inventory drift')
    require(Counter(r['kind'] for r in records) ==
            {'release': 60, 'maintenance': 24, 'backup': 24, 'capacity': 12},
            'Release/platform work allocation drift')
    require(set(r['owner'] for r in records) == team, 'Platform staff participation drift')
    require(manifest['counts']['messages'] == len(source_mail) == 1572
            and manifest['counts']['documents'] == len(source_docs) == 530,
            'Release/platform content inventory drift')
    require(manifest['counts']['retained_copies'] ==
            sum(1 + len(m['to']) for m in source_mail.values()) == 3144,
            'Release/platform copy count drift')
    owners = {'k-delivery.k-source', 'k-delivery.k-ci', 'k-delivery.k-registry',
              'k-delivery.k-preview', 'k-corporate.k-staff', 'k-cloud.k-data'}
    require({s['logical_owner'] for s in manifest['services']} == owners
            and len(manifest['services']) == 6, 'Platform service inventory drift')
    # These are existing logical nodes, not new service names invented for an operating report.
    pack = root.parents[1]
    for owner in owners:
        module, node = owner.split('.')
        world = yaml.safe_load((pack / f'sdl/modules/world/{module}.yaml').read_text())
        require(node in world['nodes'], 'Unknown platform logical owner')
    seen_docs = set(manifest['shared_documents'])
    seen_mail = set()
    seen_calendars = set()
    seen_accepted = []
    for r in records:
        rid = r['id']
        require(r['owner'] in team and r['operator'] in team
                and r['owner'] != r['operator'], f'Operating roles drift: {rid}')
        require(r['service_owner'] in owners, f'Unknown operating service: {rid}')
        start, end = map(datetime.fromisoformat, (r['opened_at'], r['closed_at']))
        require(start < end <= snapshot, f'Operating chronology drift: {rid}')
        require(set(r['readers']) <= set(people) and team <= set(r['readers']),
                f'Operating reader drift: {rid}')
        require(len(set(r['documents'])) == len(r['documents'])
                and not seen_docs.intersection(r['documents']), f'Duplicate operating document: {rid}')
        require(len(set(r['messages'])) == len(r['messages'])
                and not seen_mail.intersection(r['messages']), f'Duplicate operating mail: {rid}')
        require(set(r['documents']) <= set(source_docs)
                and set(r['messages']) <= set(source_mail), f'Missing operating content: {rid}')
        seen_docs.update(r['documents']); seen_mail.update(r['messages'])
        for key in r['documents']:
            d = source_docs[key]
            require(set(d['reader_keys']) == set(r['readers']) and d['audience'] == 'restricted',
                    f'Operating document audience drift: {key}')
            require(start <= datetime.fromisoformat(d['published_at']) <= end,
                    f'Operating document chronology drift: {key}')
        for key in r['messages']:
            m = source_mail[key]
            require(start <= datetime.fromisoformat(m['date']) <= end,
                    f'Operating mail chronology drift: {key}')
            require('[' + rid + ']' in m['subject'], f'Operating message join drift: {key}')
            require(m['from'] in contacts and set(m['to']) <= set(r['readers'])
                    and m['from'] not in m['to'], f'Operating message audience drift: {key}')
            if m['from'].startswith('k_'):
                fields = dict(token.split('=', 1) for token in m['body'].split() if '=' in token)
                require(fields.get('release', fields.get('change', fields.get('check'))) == rid,
                        f'Machine notice record drift: {key}')
                if 'sha256' in fields:
                    require(fields['sha256'] == r.get('artifact_sha256'),
                            f'Machine notice artifact drift: {key}')
                if 'duration_seconds' in fields and r['kind'] == 'release':
                    build = next(e for e in r['events']
                                 if e['action'] == 'attempt-' + fields['attempt'])
                    require(int(fields['duration_seconds']) == build['duration_seconds'],
                            f'Machine build duration drift: {key}')
                if 'observed' in fields:
                    require(int(fields['observed']) == r['after'],
                            f'Machine maintenance count drift: {key}')
                if r['kind'] == 'backup' and fields['result'] == 'PASS' and 'files' in fields:
                    require(int(fields['files']) == int(fields['digest_matches']) == len(r['sample'])
                            and int(fields['bytes']) == r['total_bytes']
                            and int(fields['duration_seconds']) == r['restore_seconds'],
                            f'Machine recovery result drift: {key}')
            for attachment in m.get('attachments', []):
                d = by_doc[attachment]
                require(attachment in r['documents']
                        and set(m['to']) <= set(d['reader_keys'])
                        and datetime.fromisoformat(d['published_at']) <= datetime.fromisoformat(m['date']),
                        f'Operating attachment audience/date drift: {key}')
            if m.get('reply_to'):
                parent = source_mail[m['reply_to']]
                require(parent['id'] in r['messages']
                        and datetime.fromisoformat(parent['date']) < datetime.fromisoformat(m['date']),
                        f'Operating reply chronology drift: {key}')
        if 'calendar' in r:
            e = by_event[r['calendar']]
            seen_calendars.add(e['id'])
            require(e['start'] == r['window_start'] and e['end'] == r['window_end']
                    and datetime.fromisoformat(e['created_at']) <= datetime.fromisoformat(e['start'])
                    < datetime.fromisoformat(e['end']) <= end,
                    f'Operating calendar chronology drift: {rid}')
            require({e['organizer'], *e['attendees']} <= set(r['readers'])
                    and r['operator'] in e['attendees'], f'Operating calendar audience drift: {rid}')
            require(e['status'] == ('CANCELLED' if r['status'] == 'deferred' else 'CONFIRMED'),
                    f'Operating calendar disposition drift: {rid}')
        if r['kind'] == 'release':
            require(r['status'] in {'published', 'deferred'}, f'Unknown release state: {rid}')
            require(set(r['quality_records']) <= set(accepted),
                    f'Release uses unaccepted quality decision: {rid}')
            seen_accepted.extend(r['quality_records'])
            qs = [accepted[k] for k in r['quality_records']]
            require(r['product_version'] == '4.9.1'
                    and all(q['repository'] == r['repository'] and q['acceptance_baseline'] == '4.9.1'
                            for q in qs), f'Release product/repository join drift: {rid}')
            require(r['accepted_at'] == max(q['decided_at'] for q in qs)
                    and datetime.fromisoformat(r['accepted_at']) < start,
                    f'Release precedes product acceptance: {rid}')
            artifact = source_docs[r['manifest_document']]['text']
            require(hashlib.sha256(artifact.encode()).hexdigest() == r['artifact_sha256'],
                    f'Release artifact digest drift: {rid}')
            content = json.loads(artifact)
            require(content['release'] == rid and content['repository'] == r['repository']
                    and content['product_version'] == r['product_version'],
                    f'Release manifest identity drift: {rid}')
            expected = [{'quality_record': q['id'], 'engineering_work': q['engineering_work'],
                         'revision': q['engineering_revision'], 'accepted_at': q['decided_at'],
                         'test_outcome': q['test_outcome'],
                         'test_result_sha256': hashlib.sha256(by_doc[q['documents'][-1]]['text'].encode()).hexdigest(),
                         'limitation': q['outstanding_limitation']} for q in qs]
            require(content['revisions'] == expected, f'Release accepted-evidence drift: {rid}')
            require(r['limitations'] == list(dict.fromkeys(q['outstanding_limitation'] for q in qs
                                                          if q['outstanding_limitation'])),
                    f'Release lost quality limitation: {rid}')
            event_doc = source_docs[rid.lower() + '-events']
            require([json.loads(line) for line in event_doc['text'].splitlines()] == r['events'],
                    f'Release event artifact drift: {rid}')
            require(all(start <= datetime.fromisoformat(e['at']) <=
                        datetime.fromisoformat(event_doc['published_at']) for e in r['events']),
                    f'Release events from the future: {rid}')
            if r['status'] == 'deferred':
                require(all(r[k] is None for k in ('approved_at', 'published_at', 'deployed_at', 'readback_at'))
                        and r['build_attempts'] == 0
                        and [e['result'] for e in r['events']] == ['deferred'],
                        f'Deferred release claims execution: {rid}')
            else:
                approval, publication, deployment, readback = (
                    datetime.fromisoformat(r[k]) for k in
                    ('approved_at', 'published_at', 'deployed_at', 'readback_at'))
                require(start < approval < publication < deployment < readback <= end,
                        f'Release execution order drift: {rid}')
                for action, at in [('approval', 'approved_at'), ('publish', 'published_at'),
                                   ('select', 'deployed_at'), ('readback', 'readback_at')]:
                    matching = [e for e in r['events'] if e['action'] == action]
                    require(len(matching) == 1 and matching[0]['at'] == r[at],
                            f'Release event time drift: {rid}/{action}')
                    if action != 'approval':
                        require(matching[0]['sha256'] == r['artifact_sha256'],
                                f'Published/selected release bytes differ: {rid}')
                builds = [e for e in r['events'] if e['action'].startswith('attempt-')]
                require(len(builds) == r['build_attempts'] and builds[-1]['result'] == 'passed'
                        and all(approval < datetime.fromisoformat(e['at']) < publication for e in builds),
                        f'Release lacks successful authorized build: {rid}')
                require([e['result'] for e in builds] in (['passed'], ['failed', 'passed']),
                        f'Release build retry history drift: {rid}')
            notes = source_docs[rid.lower() + '-notes-v2']['text']
            require(r['artifact_sha256'] in notes and all(v in notes for v in r['limitations']),
                    f'Final release notes lose artifact/limitations: {rid}')
        elif r['kind'] == 'maintenance':
            rows = list(csv.DictReader(io.StringIO(source_docs[rid.lower() + '-result']['text'])))
            require(len(rows) == 1 and rows[0]['change'] == rid
                    and int(rows[0]['before']) == r['before']
                    and int(rows[0]['observed_after']) == r['after']
                    and int(rows[0]['planned_after']) == r['planned_after']
                    and rows[0]['result'] == r['status'], f'Maintenance result drift: {rid}')
            require(datetime.fromisoformat(rows[0]['observed_at']) <=
                    datetime.fromisoformat(source_docs[rid.lower() + '-result']['published_at']),
                    f'Maintenance report precedes observation: {rid}')
            if r['status'] == 'deferred':
                require(r['after'] == r['before'] and r['approved_at'] is None
                        and r['executed_at'] is None, f'Deferred maintenance claims execution: {rid}')
            else:
                require(start < datetime.fromisoformat(r['approved_at']) <
                        datetime.fromisoformat(r['executed_at']) <= end
                        and r['after'] == r['planned_after'], f'Maintenance execution drift: {rid}')
        elif r['kind'] == 'backup':
            require(r['dataset'] == 'narrative-keplerops.documents', f'Unknown backup dataset: {rid}')
            sample = json.loads(source_docs[rid.lower() + '-sample']['text'])
            require(sample['documents'] == r['sample'], f'Backup sample manifest drift: {rid}')
            require(len({s['document'] for s in r['sample']}) == len(r['sample']),
                    f'Duplicate recovery sample entry: {rid}')
            for entry in r['sample']:
                d = by_doc[entry['document']]
                require(d['employer'] == 'keplerops' and d.get('collection', 'documents') == 'documents'
                        and d['published_at'] == entry['published_at']
                        and datetime.fromisoformat(d['published_at']) <= start,
                        f'Backup sample from wrong collection or future: {rid}')
                require(d['path'] == entry['path'] and len(d['text'].encode()) == entry['bytes']
                        and hashlib.sha256(d['text'].encode()).hexdigest() == entry['sha256'],
                        f'Backup sample bytes differ: {rid}')
            require(sum(s['bytes'] for s in r['sample']) == r['total_bytes']
                    and r['restore_seconds'] > 0, f'Backup arithmetic drift: {rid}')
            require(r['attempts'] == (2 if r['status'] == 'passed_after_retry' else 1),
                    f'Backup retry history drift: {rid}')
        elif r['kind'] == 'capacity':
            require(r['capacity_hours'] - r['booked_hours'] - r['recovery_reserved_hours'] ==
                    r['available_hours'] >= 0, f'Capacity arithmetic drift: {rid}')
            row = next(csv.DictReader(io.StringIO(source_docs[rid.lower() + '-capacity']['text'])))
            require([int(row[k]) for k in ('available_operator_hours', 'booked_qualification_hours',
                                          'reserved_recovery_hours', 'unallocated_hours')] ==
                    [r[k] for k in ('capacity_hours', 'booked_hours', 'recovery_reserved_hours',
                                   'available_hours')], f'Capacity workbook drift: {rid}')
    require(Counter(seen_accepted) == Counter(accepted.keys()),
            'Release coverage duplicates or omits accepted revisions')
    require(seen_docs == set(source_docs) and seen_mail == set(source_mail),
            'Unjoined release/platform content')
    require(len(seen_calendars) == manifest['counts']['calendar_items'] == 84,
            'Operating calendar inventory drift')
    require(sum(r['kind'] == 'release' and r['status'] == 'published' for r in records) == 54
            and sum(r.get('build_attempts') == 2 for r in records) == 6,
            'Release outcome allocation drift')
    visible = '\n'.join(d['text'] + d['path'] for d in source_docs.values()) + '\n'.join(
        m['subject'] + m['body'] for m in source_mail.values())
    require(not re.search(r'cinder-typhoon|scenario[_ -]overlay|author.only|issue[ -]117|'
                          r'challenge|flag\{|TEN-ARWC-047|FLK-7\.4\.2|SUP-2841|'
                          r'k-delivery\.|k-cloud\.|k-corporate\.', visible, re.I),
            'Operating content leaks authoring or overrides campaign-specific records')
    return manifest['counts']
