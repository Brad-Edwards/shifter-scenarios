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
NARRATIVE_EVIDENCE = {f'narrative-{org}.{kind}-visible' for org in TARGETS for kind in ('mail', 'documents')}
STORIES = {'bicycle', 'lunch', 'workshop', 'anniversary', 'choir', 'photography', 'outreach', 'billing'}


def require(value, message):
    if not value:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text())


def check_assets():
    identity = yaml.safe_load((ROOT / 'authoring/people.yaml').read_text())
    contacts = identity['people'] | identity['correspondents']
    snapshot = datetime.fromisoformat(identity['snapshot'])
    mail = []
    for p in sorted((ROOT / 'authoring').glob('mail-*.yaml')):
        mail.extend(yaml.safe_load(p.read_text())['messages'])
    docs = yaml.safe_load((ROOT / 'authoring/documents.yaml').read_text())['documents']
    events = yaml.safe_load((ROOT / 'authoring/calendars.yaml').read_text())['events']
    doc_by_id = {d['id']: d for d in docs}
    coverage = read_json(ROOT / 'story-coverage.json')
    require(len(identity['people']) == 15, 'Cast differs from reviewed world')
    require(len(mail) == len({m['id'] for m in mail}) == 75, 'Authored message inventory drift')
    require(len(docs) == len(doc_by_id) == 15, 'Authored document inventory drift')
    require(STORIES <= {m['story'] for m in mail}, 'An ordinary story has no correspondence')
    require({d['file'] for d in docs} == {str(p.relative_to(ROOT)) for p in (ROOT / 'documents').rglob('*.md')}, 'Uncatalogued document')
    parsed = {}
    for m in mail:
        c = coverage['messages'][m['id']]
        raw = (ROOT / c['file']).read_bytes()
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
    require(len(catalog) == 4, 'Expected four service-owned collections')
    for entry in catalog:
        path = (PACK / entry['path']).resolve()
        require(path.is_relative_to(ROOT.resolve()) and path.is_file(), 'Artifact path escapes or missing')
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        require(entry['sha256'] == digest and entry['source']['version'] == 'sha256-' + digest, 'Source digest drift')
        org = entry['content_ref'].split('.')[0].removeprefix('narrative-')
        require(entry['target'] == TARGETS[org], 'Wrong narrative target')
        payload = json.loads(raw)
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
            require(all(d['readers'] and len(d['readers']) == len(set(d['readers'])) for d in payload['documents']), 'Invalid document audience')
            allowed = {p['email'] for p in identity['people'].values() if p['employer'] == org}
            require(all(set(d['readers']) <= allowed for d in payload['documents']), 'Cross-company document audience')
            for d in docs:
                if d['employer'] != org: continue
                match = [item for item in payload['documents'] if item['name'] == d['id']]
                require(len(match) == 1 and match[0]['text'] == (ROOT / d['file']).read_text(), 'Library omitted or changed document')
                groups = {'support': {'rowan', 'maya', 'talia'}, 'platform': {'noor', 'evan'}, 'outreach': {'mina', 'owen', 'rosa'}}
                readers = allowed if d['audience'] == 'staff' else {identity['people'][k]['email'] for k in groups[d['audience']]}
                require(set(match[0]['readers']) == readers, 'Document reader set changed')
                require(match[0]['published_at'] == d['published_at'] and datetime.fromisoformat(d['published_at']) <= snapshot, 'Document date changed')
            library = {d['name']: d for d in payload['documents']}
            require(set(library) == {d['id'] for d in docs if d['employer'] == org} | {org + '-directory'} | {e['id'] for e in events if e['employer'] == org}, 'Library item inventory drift')
            directory = library[org + '-directory']
            require(set(directory['readers']) == allowed, 'Directory audience drift')
            rows = list(csv.DictReader(io.StringIO(directory['text'])))
            require(rows == [{k: p[k] for k in ('name', 'email', 'department', 'job')} for p in identity['people'].values() if p['employer'] == org], 'Staff directory differs from cast')
            for event in events:
                if event['employer'] != org: continue
                item = library[event['id']]
                readers = {contacts[k]['email'] for k in [event['organizer']] + event['attendees'] if contacts[k]['employer'] == org}
                require(set(item['readers']) == readers, 'Private calendar audience widened')
                raw_calendar = (ROOT / 'generated/calendars' / (event['id'] + '.ics')).read_bytes()
                require(raw_calendar == item['text'].encode(), 'Calendar bytes differ')
                require(all(len(line) <= 75 for line in raw_calendar.split(b'\r\n')), 'Calendar line folding invalid')
                text = item['text'].replace('\r\n ', '')
                for field, value in [('DTSTART', event['start']), ('DTEND', event['end']), ('DTSTAMP', identity['snapshot'])]:
                    stamp = datetime.fromisoformat(value).astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                    require(field + ':' + stamp + '\r\n' in text, 'Calendar time drift')
                require('STATUS:' + event['status'] + '\r\n' in text, 'Calendar status drift')
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
    return 4


if __name__ == '__main__':
    check_assets()
    print('PASS: 75 RFC822 messages, exact attachments and mailbox copies, 15 people, 15 documents, four source collections')


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
