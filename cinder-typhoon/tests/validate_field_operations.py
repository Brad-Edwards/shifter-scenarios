"""Check finished operations records, temporal joins, resources and reader boundaries."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import csv
import hashlib
import io
from pathlib import Path
import yaml
import zipfile

SNAPSHOT = '2026-09-16T08:30:00-04:00'
PRIMARY_COUNTS = {'shifts': 252, 'visits': 600, 'dispatch': 60, 'training': 24}


def require(value, message):
    if not value:
        raise ValueError(message)


def load_tables(root):
    with zipfile.ZipFile(root/'documents/field-operations-records.zip') as archive:
        return {Path(n).stem: list(csv.DictReader(io.StringIO(archive.read(n).decode())))
                for n in archive.namelist()}


def rows(tables, prefix):
    return [row for key, values in tables.items()
            if key == prefix or key.startswith(prefix+'-') for row in values]


def no_overlap(intervals, message, rest_hours=0):
    for values in intervals.values():
        previous = None
        for begin, end in sorted(values):
            require(begin < end, message)
            if previous is not None:
                require(begin >= previous + timedelta(hours=rest_hours), message)
            previous = end


def check_records(tables, workforce, service):
    staff = {p['key']: p for p in workforce}
    ops = {k for k, p in staff.items() if p['department'] == 'Operations, treatment, and distribution'}
    require(len(ops) == 94 and {r['employee'] for r in tables['staff']} == ops, 'staff coverage')
    for r in tables['staff']:
        p = staff[r['employee']]
        require((r['name'], r['team'], r['role'], r['effective_from']) ==
                (p['name'], p['team'], p['job'], p['effective_date']), 'effective role')
    for prefix, count in PRIMARY_COUNTS.items():
        require(len(rows(tables, prefix)) == count, 'primary record inventory')
    sites = {r['site_id']: r for r in tables['sites']}
    assets = {r['asset_id']: r for r in tables['assets']}
    require(len(sites) == 8 and len(assets) == 44, 'site/asset inventory')
    require(all(a['site_id'] in sites for a in assets.values()), 'asset site')
    duties = defaultdict(list)
    for r in rows(tables, 'roster'):
        p = staff[r['employee']]
        require(r['start'][:10] >= max(p['start_date'], p['effective_date']) and
                r['team'] == p['team'] and r['start'] < r['end'] <= SNAPSHOT, 'duty effective date')
        duties[r['employee']].append((datetime.fromisoformat(r['start']), datetime.fromisoformat(r['end'])))
    require(set(duties) == ops, 'duty staff coverage')
    no_overlap(duties, 'overlapping duty or short rest', rest_hours=11)

    def on_duty(key, begin, end):
        return any(a <= datetime.fromisoformat(begin) < datetime.fromisoformat(end) <= b
                   for a, b in duties[key])

    shifts = {r['shift_id']: r for r in rows(tables, 'shifts')}
    obs = {r['observation_id']: r for r in rows(tables, 'observations')}
    requests = {r['request_id']: r for r in tables['maintenance']}
    require(len(shifts) == 252 and len(obs) == 504 and len(requests) == 24, 'operating record inventory')
    plant_coverage = defaultdict(list)
    for r in shifts.values():
        require(r['start'] < r['handover_at'] < r['end'], 'handover time')
        plant_coverage[r['site_id']].append((r['start'], r['end']))
        crew = r['people'].split(';')
        require(r['lead'] in crew and len(crew) >= 4, 'plant crew')
        for k in crew:
            require(staff[k]['team'] == r['team'] and on_duty(k, r['start'], r['end']), 'plant duty join')
        if 'awm029' in crew:
            require(r['start'] >= '2026-08-27' and r['lead'] != 'awm029', 'local orientation')
        ownobs = [o for o in obs.values() if o['shift_id'] == r['shift_id']]
        require(len(ownobs) == 2, 'round count')
        for o in ownobs:
            require(r['start'] <= o['observed_at'] <= r['handover_at'] and
                    o['recorded_by'] in crew and assets[o['asset_id']]['site_id'] == r['site_id'], 'future handover observation')
        known = {m['request_id'] for m in requests.values() if
                 m['source_id'].startswith(r['shift_id'][:10]) and m['opened_at'] <= r['handover_at']}
        require(set(filter(None, r['open_requests'].split(';'))) == known, 'handover request knowledge')
    for coverage in plant_coverage.values():
        coverage.sort()
        require(coverage[0][0] == '2026-08-03T06:00:00-04:00' and
                coverage[-1][1] == '2026-09-14T06:00:00-04:00' and
                all(a[1] == b[0] for a, b in zip(coverage, coverage[1:])), 'plant continuity')
    visits = {r['visit_id']: r for r in rows(tables, 'visits')}
    work = defaultdict(list)
    meters = {r['meter_id']: r for r in service['meters']}
    points = {r['service_point_id']: r for r in service['service-points']}
    relationships = {r['service_point_id']: r for r in service['account-services']}
    for v in visits.values():
        require(v['start'] <= v['observed_at'] <= v['end'] <= SNAPSHOT, 'visit observation time')
        require(v['lead'] != v['partner'] and v['lead'] != 'owen', 'apprentice supervision')
        for k in [v['lead'], v['partner']]:
            require(staff[k]['team'] == v['team'] and on_duty(k, v['start'], v['end']), 'field duty join')
            work[k].append((datetime.fromisoformat(v['start']), datetime.fromisoformat(v['end'])))
        require(staff[v['scheduler']]['team'] == 'Field coordination', 'scheduler role')
        if v['asset_id']:
            require(assets[v['asset_id']]['site_id'] == v['site_id'], 'field asset site')
        if v['meter_id']:
            m = meters.get(v['meter_id'], {})
            p = points[v['service_point_id']]
            require(m.get('service_point_id') == v['service_point_id'] and m.get('status') == 'active' and
                    m['role'] == 'billing' and m['installed_at'] <= v['start'] and
                    relationships[v['service_point_id']]['account_id'] == v['account_id'], 'meter/account join')
            require(p['district'] == sites[v['site_id']]['district'].upper() and
                    (' West ' in p['address']) == v['site_id'].endswith('W'), 'field district join')
        require(v['status'] in ['completed', 'no_access', 'follow_up'], 'visit outcome')
        require((v['status'] == 'follow_up') == bool(v['maintenance_request']), 'follow-up request')
    require(Counter(v['status'] for v in visits.values()) ==
            Counter(completed=582, no_access=6, follow_up=12), 'outcome distribution')
    for t in rows(tables, 'training'):
        require(t['learner'] != t['instructor'] and t['instructor'] != 'mina' and
                t['authorization'] == 'supervised practice only', 'training authority')
        require(t['start'] < t['end'] <= t['recorded_at'] <= SNAPSHOT, 'training chronology')
        for k in [t['learner'], t['instructor']]:
            require(staff[k]['team'] == t['team'] and on_duty(k, t['start'], t['end']), 'training duty join')
            work[k].append((datetime.fromisoformat(t['start']), datetime.fromisoformat(t['end'])))
        if t['related_visit'] != 'depot practice':
            v = visits[t['related_visit']]
            require(t['learner'] in [v['lead'], v['partner']] and v['end'] <= t['start'], 'training visit join')
    no_overlap(work, 'overlapping field work or training')
    # The accepted outreach rehearsal is an afternoon engagement, not a field qualification.
    for k in ['mina', 'owen']:
        require(not any(a < datetime.fromisoformat('2026-09-10T14:00:00-04:00') and
                        b > datetime.fromisoformat('2026-09-10T13:00:00-04:00')
                        for a, b in work[k]), 'outreach conflict')
    resource_times = defaultdict(list)
    resources = {r['resource_id']: r for r in tables['resources']}
    for b in rows(tables, 'bookings'):
        v = visits[b['visit_id']]
        require(b['resource_id'] in resources and b['start'] <= v['start'] < v['end'] <= b['returned_at'] <= b['end'], 'resource/visit join')
        require(resources[b['resource_id']]['home_site'][5] == v['site_id'][5], 'resource district')
        require(b['reserved_by'] == v['scheduler'], 'booking owner')
        if resources[b['resource_id']]['kind'] == 'vehicle':
            require(b['driver'] == v['lead'] and b['driver'] != 'owen', 'driver scope')
        resource_times[b['resource_id']].append((datetime.fromisoformat(b['start']), datetime.fromisoformat(b['end'])))
    no_overlap(resource_times, 'resource collision')
    appointments = rows(tables, 'appointments')
    require(len(appointments) == 120, 'appointment inventory')
    for a in appointments:
        v = visits[a['visit_id']]
        require(a['arranged_at'] < a['start'] <= v['start'] < v['end'] <= a['end'], 'appointment chronology')
        require(all(a[k] == v[k] for k in ['service_point_id', 'meter_id', 'account_id', 'scheduler']), 'appointment identity')
        require(a['serial'] == meters[a['meter_id']]['serial'] and
                all(a[k] == points[a['service_point_id']][k] for k in ['address', 'access_instruction']), 'appointment field extract')
    for f in rows(tables, 'field-extract'):
        a = next(a for a in appointments if a['visit_id'] == f['visit_id'])
        require(all(v == a[k] for k, v in f.items()), 'field extract drift')
    for s in rows(tables, 'samples'):
        v = visits[s['visit_id']]
        require(v['sample_id'] == s['sample_id'] and v['asset_id'] == s['asset_id'] and
                [v['lead'], v['partner']] == [s['collector'], s['witness']], 'sample visit join')
        require(v['start'] <= s['collected_at'] <= s['sealed_at'] <= v['end'] < s['handed_over_at'] <= SNAPSHOT,
                'sample custody chronology')
        require(staff[s['received_by']]['team'] == 'Laboratory' and s['seal_status'] == 'intact' and
                s['laboratory_result'] == 'not in field return', 'sample scope')
    for m in requests.values():
        source = obs.get(m['observation_id'], visits.get(m['source_id']))
        require(source is not None and source['maintenance_request'] == m['request_id'] and
                source['asset_id'] == m['asset_id'] and source['observed_at'] == m['observed_at'], 'maintenance source')
        require(m['observed_at'] < m['opened_at'] < m['received_at'] <= SNAPSHOT and
                m['received_by'] == 'theo' and m['status'] == 'awaiting planning', 'maintenance chronology')
    stock = defaultdict(list)
    for s in rows(tables, 'stock'):
        require(visits[s['used_by_visit']]['kind'] == 'service markers' and
                visits[s['visit_id']]['kind'] == 'consumables', 'stock visit join')
        require(int(s['opening']) - int(s['issued']) + int(s['returned']) == int(s['closing']) >= 0 and
                s['unit'] == 'each', 'stock arithmetic')
        stock[s['site_id']].append(s)
    for history in stock.values():
        history.sort(key=lambda r: r['visit_id'])
        require(history[0]['opening'] == '200' and all(a['closing'] == b['opening'] for a, b in zip(history, history[1:])), 'stock continuity')
    for d in rows(tables, 'dispatch'):
        assignments = [visits[k] for k in d['visits'].split(';')]
        counts = Counter(v['status'] for v in assignments)
        require(len(assignments) == 10 and all(v['end'] <= d['recorded_at'] for v in assignments) and
                [counts['completed'], counts['no_access'], counts['follow_up']] ==
                [int(d['complete']), int(d['no_access']), int(d['follow_up'])], 'dispatch reconciliation')


def load_service(root):
    with zipfile.ZipFile(root/'documents/service-account-records.zip') as archive:
        return {n: list(csv.DictReader(io.StringIO(archive.read(n+'.csv').decode())))
                for n in ['meters', 'service-points', 'account-services']}


def check_field_operations(root, workforce, mail, docs, events):
    manifest = yaml.safe_load((root/'authoring/field-operations.yaml').read_text())
    tables = load_tables(root)
    require(manifest['snapshot'] == SNAPSHOT and manifest['primary_records'] == PRIMARY_COUNTS, 'operations scope')
    check_records(tables, workforce, load_service(root))
    documents = {d['id']: d for d in docs if d.get('story') == 'field-operations'}
    messages = {m['id']: m for m in mail if m.get('story') == 'field-operations'}
    calendars = {e['id']: e for e in events if e['id'].startswith('op-')}
    require(not set(documents).intersection(calendars), 'native item name collision')
    require(len(documents) == manifest['document_count'] == 1113 and
            len(messages) == manifest['message_count'] == 196 and
            len(calendars) == manifest['calendar_count'] == 144, 'operations artifact inventory')
    require(sum(1 + len(m['to']) for m in messages.values()) == manifest['retained_copies'] == 809, 'operations retained copies')
    require(len(tables) == len(manifest['tables']) == 32 and sum(map(len, tables.values())) == 5879, 'operations table inventory')
    staff = {p['key']: p for p in workforce}
    with zipfile.ZipFile(root/'documents/field-operations-records.zip') as archive:
        for key, info in manifest['tables'].items():
            d = documents[info['document']]
            require(len(tables[key]) == info['rows'] and len({r[info['primary_key']] for r in tables[key]}) == info['rows'], 'table primary key')
            require(hashlib.sha256(archive.read(key+'.csv')).hexdigest() == info['sha256'] == d['binary_sha256'], 'table digest')
            require(d['reader_keys'] == info['readers'] and d['content_encoding'] == 'gzip', 'table readership')
    for d in documents.values():
        require(d['audience'] == 'restricted' and all(staff[k]['employer'] == 'arwc' for k in d['reader_keys']), 'operations audience')
    for v in rows(tables, 'visits'):
        d = documents[v['document']]
        expected = {k for k, p in staff.items() if p['team'] == v['team'] or
                    (p['team'] == 'Field coordination' and p['site'].startswith(v['team'].split()[0]))} | {'rosa'}
        if v['sample_id']:
            expected.add('awm147' if v['team'].startswith('Pine') else 'awm148')
        require(set(d['reader_keys']) == expected, 'field form reader scope')
        require(v['note'] in d['text'] and v['visit_id'] in d['text'] and v['end'] <= d['published_at'], 'field form readback')
    for a in rows(tables, 'appointments'):
        v = next(v for v in rows(tables, 'visits') if v['visit_id'] == a['visit_id'])
        e = calendars[a['calendar']]
        m = messages['op-appointment-'+a['appointment_id'].lower()]
        require(e['start'] == a['start'] and e['end'] == a['end'] and e['organizer'] == a['scheduler'] and
                set(e['attendees']) == {v['lead'], v['partner']}, 'appointment calendar')
        require(m['from'] == 'arwc_field_desk' and set(m['to']) == {v['lead'], v['partner'], a['scheduler'], 'rosa'} and
                m['attachments'] == [a['document']], 'appointment notice audience')
    for t in rows(tables, 'training'):
        d = documents[t['document']]; e = calendars[t['calendar']]
        require(set(d['reader_keys']) == {t['learner'], t['instructor'], staff[t['learner']]['manager']}, 'private training audience')
        require(e['start'] == t['start'] and e['end'] == t['end'] and e['attendees'] == [t['learner']] and e['organizer'] == t['instructor'], 'training calendar')
    for s in rows(tables, 'shifts'):
        d = documents[s['document']]
        require(s['end'] == d['published_at'] and s['handover_at'] in d['text'] and
                all(ref in d['text'] for ref in filter(None, s['open_requests'].split(';'))), 'handover form readback')
    for r in tables['maintenance']:
        msg = messages['op-maint-'+r['request_id'].lower()]
        reply = messages[msg['id']+'-reply']
        require(msg['from'] == r['reporter'] and msg['to'] == ['theo'] and
                msg['attachments'] == [r['document']] and reply['from'] == 'theo' and
                reply['date'] == r['received_at'] and reply['reply_to'] == msg['id'], 'maintenance mail join')


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]/'assets/narrative'
    a = root/'authoring'
    check_field_operations(root, yaml.safe_load((a/'workforce.yaml').read_text())['employees'],
                           yaml.safe_load((a/'mail-field-operations.yaml').read_text())['messages'],
                           yaml.safe_load((a/'documents-field-operations.yaml').read_text())['documents'],
                           yaml.safe_load((a/'calendars-field-operations.yaml').read_text())['events'])
    print('Operations: 936 primary records, 94 staff, temporal/resource/account joins and reader scopes verified')
