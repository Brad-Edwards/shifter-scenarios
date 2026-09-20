#!/usr/bin/env python3
"""Check narrative source bytes, correspondence, audience, and native SDL bindings."""
from __future__ import annotations
from datetime import datetime
from datetime import timezone
import csv
import io
from email.parser import BytesParser
from email.policy import default
from email.utils import getaddresses, parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import sys
import yaml

PACK = Path(__file__).resolve().parents[1]
ROOT = PACK / 'assets/narrative'
TARGETS = {'keplerops': 'k-corporate.k-staff', 'arwc': 'a-corporate.a-business'}
KINDS = ('mail', 'documents', 'directory', 'employment')
NARRATIVE_EVIDENCE = {f'narrative-{org}.{kind}-visible' for org in TARGETS for kind in KINDS}
STORIES = {'bicycle', 'lunch', 'workshop', 'anniversary', 'choir', 'photography', 'outreach', 'billing'}


def require(value, message):
    if not value:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text())


def check_assets():
    identity = yaml.safe_load((ROOT / 'authoring/people.yaml').read_text())
    workforce = yaml.safe_load((ROOT / 'authoring/workforce.yaml').read_text())
    roster = workforce['employees']
    require(workforce['snapshot'] == identity['snapshot'], 'Workforce snapshot drift')
    require(len(roster) == len({p['key'] for p in roster}) == 294, 'Employee inventory drift')
    expected_departments = {
        'keplerops': {'Product engineering': 22, 'Support and implementation': 14,
                      'Platform and release': 7, 'Product management and quality': 8,
                      'Commercial': 6, 'Leadership and business operations': 7},
        'arwc': {'Operations, treatment, and distribution': 94,
                 'Maintenance and engineering': 48, 'Planning, quality, and compliance': 32,
                 'Information technology': 12, 'Customer service and business support': 36,
                 'Leadership and finance': 8},
    }
    for org, departments in expected_departments.items():
        for department, count in departments.items():
            require(sum(p['employer'] == org and p['department'] == department for p in roster) == count,
                    f'Workforce headcount drift: {org}/{department}')
    by_key = {p['key']: p for p in roster}
    require(len({p['email'] for p in roster}) == 294, 'Duplicate staff address')
    require(set(identity['people']) - {'jules'} <= set(by_key), 'Established employee missing')
    require('jules' not in by_key, 'Contractor counted as employee')
    require(all(all(p[field] == identity['people'][p['key']][field] for field in
                    ('name', 'email', 'employer', 'department', 'job'))
                for p in roster if p['key'] in identity['people']), 'Established cast changed')
    for person in roster:
        require(person['email'].endswith('@' + ('keplerops.com' if person['employer'] == 'keplerops'
                                               else 'alterrawaterco.com')), 'Staff domain drift')
        require(datetime.fromisoformat(person['start_date']) <= datetime.fromisoformat(person['effective_date'])
                <= datetime.fromisoformat(identity['snapshot']).replace(tzinfo=None),
                f'Impossible employment date: {person["key"]}')
        if person['employer'] == 'keplerops':
            require(person['start_date'] >= '2016-03-14', 'KeplerOps tenure predates founding')
        slug = lambda value: '-'.join(''.join(c if c.isalnum() else ' ' for c in value.lower()).split())
        expected_groups = [person['employer'] + '-staff',
                           person['employer'] + '-' + slug(person['department']),
                           person['employer'] + '-' + slug(person['team'])]
        require(person['groups'] == expected_groups,
                f'Unexpected distribution group: {person["key"]}')
        require(person['context_note'] and person['writing_note'] and person['extension'],
                f'Incomplete workforce profile: {person["key"]}')
        seen = {person['key']}
        manager = person['manager']
        while manager:
            require(manager in by_key and manager not in seen, f'Reporting loop or unknown manager: {person["key"]}')
            require(by_key[manager]['employer'] == person['employer'], 'Cross-company manager')
            seen.add(manager)
            manager = by_key[manager]['manager']
    require({p['key'] for p in roster if not p['manager']} == {'leah', next(p['key'] for p in roster
            if p['employer'] == 'arwc' and p['job'] == 'General manager')}, 'Unexpected reporting root')
    people = dict(identity['people'])
    for person in roster:
        people.setdefault(person['key'], {k: person[k] for k in ('name','email','employer','department','job')})
    identity['people'] = people
    contacts = identity['people'] | identity['correspondents']
    snapshot = datetime.fromisoformat(identity['snapshot'])
    mail = []
    for p in sorted((ROOT / 'authoring').glob('mail-*.yaml')):
        mail.extend(yaml.safe_load(p.read_text())['messages'])
    docs = yaml.safe_load((ROOT / 'authoring/documents.yaml').read_text())['documents']
    events = yaml.safe_load((ROOT / 'authoring/calendars.yaml').read_text())['events']
    doc_by_id = {d['id']: d for d in docs}
    coverage = read_json(ROOT / 'story-coverage.json')
    workforce_actions = yaml.safe_load((ROOT / 'authoring/workforce-actions.yaml').read_text())['actions']
    require(len(workforce_actions) == 280, 'Workforce action inventory drift')
    source_by_id = {m['id']: m for m in mail}
    for action in workforce_actions:
        require(action['employee'] in by_key and action['manager'] in by_key,
                'Workforce action has unknown people')
        require(action['manager'] == (by_key[action['employee']]['manager'] or 'luc'),
                'Workforce action manager drift')
        require(action['last_message'] in source_by_id and action['reference'] in
                source_by_id[action['last_message']]['subject'], 'Workforce action has no matching exchange')
        require(datetime.fromisoformat(action['opened']) <= snapshot,
                'Workforce action after snapshot')
    packaged_messages = {}
    for org in TARGETS:
        for record in read_json(ROOT / 'generated/packages' / (org + '-mail.json'))['messages']:
            raw = record['rfc822'].encode('ascii')
            mid = record['message_id']
            require(mid not in packaged_messages or packaged_messages[mid] == raw,
                    'Retained exchange differs between organizations')
            packaged_messages[mid] = raw
    require(len(identity['people']) == 295, 'Cast or workforce differs from reviewed world')
    require(len(mail) == len({m['id'] for m in mail}) == 1475, 'Authored message inventory drift')
    require(len(docs) == len(doc_by_id) == 155, 'Authored document inventory drift')
    require(STORIES <= {m['story'] for m in mail}, 'An ordinary story has no correspondence')
    require({d['file'] for d in docs} == {str(p.relative_to(ROOT)) for p in (ROOT / 'documents').rglob('*') if p.is_file()}, 'Uncatalogued document')
    parsed = {}
    for m in mail:
        c = coverage['messages'][m['id']]
        raw = (ROOT / c['file']).read_bytes() if c['file'] else packaged_messages[c['message_id']]
        message = BytesParser(policy=default).parsebytes(raw)
        require(not message.defects and all(not part.defects for part in message.walk()), f'Malformed RFC822: {m["id"]}')
        require(message['Message-ID'] == c['message_id'], f'Message identity drift: {m["id"]}')
        require(getaddresses([str(message['From'])])[0][1] == contacts[m['from']]['email'], f'Sender mismatch: {m["id"]}')
        require({address for _, address in getaddresses([str(message['To'])])} == {contacts[k]['email'] for k in m['to']}, f'Recipients mismatch: {m["id"]}')
        require(parsedate_to_datetime(message['Date']) == datetime.fromisoformat(m['date']) <= snapshot, f'Time mismatch: {m["id"]}')
        require(message.get_body(preferencelist=('plain',)).get_content().replace('\r\n', '\n') == m['body'], f'Body mismatch: {m["id"]}')
        attachments = {p.get_filename(): p.get_payload(decode=True) for p in message.iter_attachments()}
        require(all(datetime.fromisoformat(doc_by_id[d]['published_at']) <= datetime.fromisoformat(m['date']) for d in m.get('attachments', [])), f'Attachment from the future: {m["id"]}')
        expected = {Path(doc_by_id[d]['file']).name: (ROOT / doc_by_id[d]['file']).read_bytes() for d in m.get('attachments', [])}
        require(attachments == expected, f'Attachment mismatch: {m["id"]}')
        if m.get('reply_to'):
            parent = coverage['messages'][m['reply_to']]['message_id']
            require(message['In-Reply-To'] == parent and parent in str(message['References']), f'Thread mismatch: {m["id"]}')
        else:
            require(message['In-Reply-To'] is None, f'Unexpected reply: {m["id"]}')
        parsed[m['id']] = raw
    catalog = read_json(ROOT / 'artifact-catalog.json')['artifacts']
    require(len(catalog) == 8, 'Expected eight service-owned collections')
    payloads = {}
    for entry in catalog:
        path = (PACK / entry['path']).resolve()
        require(path.is_relative_to(ROOT.resolve()) and path.is_file(), 'Artifact path escapes or missing')
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        require(entry['sha256'] == digest and entry['source']['version'] == 'sha256-' + digest, 'Source digest drift')
        org = entry['content_ref'].split('.')[0].removeprefix('narrative-')
        require(entry['target'] == TARGETS[org], 'Wrong narrative target')
        payload = json.loads(raw)
        payloads[entry['content_ref']] = payload
        require(payload['schema_version'] == entry['format'], 'Format mismatch')
        if entry['content_ref'].endswith('.mail'):
            records = {x['message_id']: x for x in payload['messages']}
            require(len(records) == len(payload['messages']), 'Duplicate source message')
            expected_copies = set()
            for m in mail:
                c = coverage['messages'][m['id']]
                if org not in c['retained']: continue
                mid = c['message_id']
                require(records[mid]['rfc822'].encode('ascii') == parsed[m['id']], 'Collection changed RFC822 bytes')
                require(records[mid]['sha256'] == hashlib.sha256(parsed[m['id']]).hexdigest(), 'RFC822 digest drift')
                for k, folder in [(m['from'], 'Sent')] + [(x, 'INBOX') for x in m['to']]:
                    if contacts[k]['employer'] == org:
                        expected_copies.add((contacts[k]['email'], folder, mid))
            actual_copies = set()
            for owner, box in payload['mailboxes'].items():
                require(box['owner'] == owner and owner.endswith('@' + ('keplerops.com' if org == 'keplerops' else 'alterrawaterco.com')), 'Mailbox owner mismatch')
                for folder, mids in box['folders'].items():
                    require(folder in ('Sent', 'INBOX') and len(mids) == len(set(mids)), 'Invalid folder inventory')
                    actual_copies.update((owner, folder, mid) for mid in mids)
            require(actual_copies == expected_copies, 'Mailbox audience mismatch or missing copy')
            require(set(records) == {m[2] for m in actual_copies}, 'Unreferenced or absent message')
        else:
            kind = entry['content_ref'].split('.')[1]
            if kind in ('directory', 'employment'):
                requirement = payload['identity_requirements']
                require(requirement['authentication'] == 'individual staff identity', 'Collection authentication drift')
                require(requirement['access'] == ('same-employer staff readers' if kind == 'directory'
                                                  else 'exact item readers'), 'Collection access model drift')
                groups = {}
                for person in roster:
                    if person['employer'] == org:
                        for group in person['groups']:
                            groups.setdefault(group, []).append(person['email'])
                require(payload['reader_groups'] == groups, 'Reader group membership drift')
            require(all(d['readers'] and len(d['readers']) == len(set(d['readers'])) for d in payload['documents']), 'Invalid document audience')
            allowed = {p['email'] for p in identity['people'].values() if p['employer'] == org}
            require(all(set(d['readers']) <= allowed for d in payload['documents']), 'Cross-company document audience')
            for d in docs:
                if d['employer'] != org or d.get('collection', 'documents') != kind: continue
                if kind == 'employment':
                    require(d['audience'] == 'restricted', 'Personnel document became staff-readable')
                if kind == 'directory':
                    require(d['audience'] == 'staff', 'Directory document has inconsistent reader scope')
                match = [item for item in payload['documents'] if item['name'] == d['id']]
                require(len(match) == 1 and match[0]['text'] == (ROOT / d['file']).read_text(), 'Library omitted or changed document')
                groups = {'support': {'rowan', 'maya', 'talia'}, 'platform': {'noor', 'evan'}, 'outreach': {'mina', 'owen', 'rosa'}}
                if d['audience'] == 'staff':
                    readers = allowed
                elif d['audience'] == 'restricted':
                    readers = {identity['people'][k]['email'] for k in d['reader_keys']}
                    require(readers < allowed, 'Restricted document exposed to all staff')
                else:
                    readers = {identity['people'][k]['email'] for k in groups[d['audience']]}
                require(set(match[0]['readers']) == readers, 'Document reader set changed')
                require(match[0]['media_type'] == d.get('media_type', 'text/markdown'), 'Document format drift')
                require(match[0]['published_at'] == d['published_at'] and datetime.fromisoformat(d['published_at']) <= snapshot, 'Document date changed')
            library = {d['name']: d for d in payload['documents']}
            expected_items = {d['id'] for d in docs if d['employer'] == org and d.get('collection', 'documents') == kind}
            expected_items |= {e['id'] for e in events if e['employer'] == org and
                               ('employment' if '-induction-' in e['id'] else 'documents') == kind}
            if kind == 'directory': expected_items.add(org + '-directory')
            require(set(library) == expected_items, 'Library item inventory drift')
            if kind == 'directory':
                directory = library[org + '-directory']
                require(set(directory['readers']) == allowed, 'Directory audience drift')
                rows = list(csv.DictReader(io.StringIO(directory['text'])))
                require(rows == [{'name': p['name'], 'email': p['email'], 'department': p['department'],
                                  'team': p['team'], 'job': p['job'],
                                  'manager': by_key[p['manager']]['name'] if p['manager'] else '',
                                  'work_contact': p['extension'], 'base': p['site']}
                                 for p in roster if p['employer'] == org], 'Staff directory differs from roster')
            for event in events:
                if event['employer'] != org or ('employment' if '-induction-' in event['id'] else 'documents') != kind: continue
                item = library[event['id']]
                readers = {contacts[k]['email'] for k in [event['organizer']] + event['attendees'] if contacts[k]['employer'] == org}
                require(set(item['readers']) == readers, 'Private calendar audience widened')
                raw_calendar = (ROOT / 'generated/calendars' / (event['id'] + '.ics')).read_bytes()
                require(raw_calendar == item['text'].encode(), 'Calendar bytes differ')
                require(all(len(line) <= 75 for line in raw_calendar.split(b'\r\n')), 'Calendar line folding invalid')
                text = item['text'].replace('\r\n ', '')
                for field, value in [('DTSTART', event['start']), ('DTEND', event['end']),
                                     ('DTSTAMP', event.get('created_at', identity['snapshot']))]:
                    stamp = datetime.fromisoformat(value).astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                    require(field + ':' + stamp + '\r\n' in text, 'Calendar time drift')
                require('STATUS:' + event['status'] + '\r\n' in text, 'Calendar status drift')
    for org in TARGETS:
        directory = {d['name']: d for d in payloads[f'narrative-{org}.directory']['documents']}
        employment = {d['name']: d for d in payloads[f'narrative-{org}.employment']['documents']}
        staff = [p for p in roster if p['employer'] == org]
        prefix = 'k' if org == 'keplerops' else 'a'
        register = employment[prefix + '-personnel-register']
        require(set(register['readers']) < {p['email'] for p in staff},
                'Personnel register has broad staff readership')
        rows = list(csv.DictReader(io.StringIO(register['text'])))
        require(len(rows) == len(staff), 'Personnel register row count drift')
        for row, person in zip(rows, staff):
            require(row['employee_id'] == person['key'].upper() and row['name'] == person['name']
                    and row['work_email'] == person['email'] and row['team'] == person['team']
                    and row['role'] == person['job'] and row['start_date'] == person['start_date']
                    and row['current_role_effective'] == person['effective_date']
                    and row['manager'] == (by_key[person['manager']]['name'] if person['manager'] else ''),
                    f'Personnel register differs from roster: {person["key"]}')
        for department in {p['department'] for p in staff}:
            slug = ''.join(c if c.isalnum() else '-' for c in department.lower()).strip('-')
            while '--' in slug: slug = slug.replace('--', '-')
            page = directory[prefix + '-staff-' + slug]['text']
            members = [p for p in staff if p['department'] == department]
            require(all(p['email'] in page and p['name'] in page for p in members),
                    f'Department contact page omits a colleague: {department}')
        hires = [p for p in staff if p['start_date'].startswith('2026')]
        require(all(prefix + '-onboard-' + p['key'] in employment and
                    prefix + '-induction-' + p['key'] in employment for p in hires),
                'Starter record or induction missing')
        require(all(p['name'] in employment[prefix + '-onboard-' + p['key']]['text']
                    and p['start_date'] in employment[prefix + '-onboard-' + p['key']]['text']
                    for p in hires), 'Onboarding record disagrees with roster')
        require((ROOT / 'generated/directories' / (org + '.csv')).read_text() ==
                directory[org + '-directory']['text'], 'CSV directory differs from source package')
    ownership = read_json(PACK / 'docs/narrative/workforce-ownership.json')
    require(ownership['required_base']['snapshot'] == identity['snapshot'], 'Ownership base snapshot drift')
    require(ownership['source_versions'] == {e['source']['name']: e['source']['version'] for e in catalog},
            'Ownership source versions drift')
    owned = ownership['ownership']
    expected_ownership = {
        'messages': {m['id'] for m in mail},
        'documents': {d['id'] for d in docs},
        'calendars': {e['id'] for e in events},
        'directories': {org + '-directory' for org in TARGETS},
        'source_files': {str(p.relative_to(PACK)) for p in (ROOT / 'authoring').glob('*.yaml')}
            | {str(p.relative_to(PACK)) for p in (ROOT / 'documents').rglob('*') if p.is_file()},
        'generated_files': {str(p.relative_to(PACK)) for p in (ROOT / 'generated').rglob('*') if p.is_file()}
            | {'assets/narrative/artifact-catalog.json', 'assets/narrative/story-coverage.json',
               'sdl/modules/world/narrative-keplerops.yaml', 'sdl/modules/world/narrative-arwc.yaml'},
    }
    for kind, expected in expected_ownership.items():
        require(set(owned[kind]) == expected and set(owned[kind].values()) == {'environment'},
                f'Ownership inventory drift: {kind}')
    require(ownership['scenario_overlay']['requires_world_release'] == ownership['world_release']
            and not ownership['scenario_overlay']['additions']
            and not ownership['scenario_overlay']['replacements'], 'Scenario overlay drift')
    return catalog


def check_narrative_sdl(scenario):
    catalog = check_assets()
    expected = {e['content_ref'] for e in catalog}
    require({k for k in scenario.content if k.startswith('narrative-')} == expected, 'SDL narrative inventory drift')
    for entry in catalog:
        key = entry['content_ref']
        c = scenario.content[key]
        readback = key + '-visible'
        require(c.target == entry['target'] and c.source.model_dump(exclude_none=True) == entry['source'], 'SDL asset source or owner drift')
        require(c.sensitive == (key.split('.')[1] != 'directory'), 'Native content sensitivity drift')
        binding = c.service_materialization
        require(binding and binding.target_service_ref == 'nodes.' + entry['target'] + '.services.workplace', 'Wrong service materialization')
        require(binding.readback_assertion_refs == [readback] and binding.evidence_requirement_refs == [readback] and binding.observation_boundary_refs == [readback], 'Readback bindings drift')
        require(binding.requirements.operation == 'ensure-owned-items' and binding.requirements.conflict_policy == 'reject-unowned-collision' and binding.requirements.readback == 'canonical-content-digest', 'Weakened service contract')
        p = scenario.propositions[readback]
        require(str(getattr(p.basis, 'value', p.basis)) == 'observed_state' and p.subjects == ['content.' + key], 'Readback must observe exact content')
        evidence = scenario.evidence_requirements[readback]
        require(evidence.source_refs == ['content.' + key], 'Readback evidence owner drift')
        require(evidence.observation_demand.selector.component_refs == ('content.' + key,), 'Readback selector owner drift')
        require(evidence.observation_demand.selector.semantic_scope == '/content', 'Readback scope drift')
    return len(expected)


def check_narrative_runtime(scenario, runtime):
    for entry in read_json(ROOT / 'artifact-catalog.json')['artifacts']:
        key = entry['content_ref']
        placement = runtime.content_placements['provision.content.' + key]
        require(placement.target_address == 'provision.node.' + entry['target'], 'Compiled content owner drift')
        require(placement.spec['source'] == scenario.content[key].source.model_dump(mode='json'), 'Compiled source drift')
        require(placement.service_materialization is not None, 'Compiled service binding lost')
        require(placement.service_materialization.target_service_address == 'provision.node.' + entry['target'] + '.service.workplace', 'Compiled service target drift')
    return 8


if __name__ == '__main__':
    check_assets()
    print('PASS: 1475 RFC822 messages, exact attachments and mailbox copies, 294 employees, 155 documents, eight source collections')


def adversarial_narrative_checks(scenario):
    """Reject type-valid source/owner/readback drift without changing authored files."""
    mutations = [
        ('content moved to Kali', lambda s: setattr(s.content['narrative-keplerops.mail'], 'target', 'participant.kali')),
        ('source version changed', lambda s: setattr(s.content['narrative-arwc.documents'].source, 'version', 'unbound')),
        ('declared instead of observed readback', lambda s: setattr(s.propositions['narrative-arwc.mail-visible'], 'basis', type(s.propositions['narrative-arwc.mail-visible'].basis).DECLARED_STATE)),
        ('readback selector moved to unrelated content', lambda s: setattr(s.evidence_requirements['narrative-keplerops.mail-visible'].observation_demand.selector, 'component_refs', ('content.narrative-arwc.mail',))),
    ]
    for label, mutate in mutations:
        candidate = scenario.model_copy(deep=True)
        mutate(candidate)
        candidate = type(scenario).model_validate(candidate.model_dump())
        try:
            check_narrative_sdl(candidate)
        except ValueError:
            pass
        else:
            raise ValueError('Narrative mutation accepted: ' + label)
    return len(mutations)
