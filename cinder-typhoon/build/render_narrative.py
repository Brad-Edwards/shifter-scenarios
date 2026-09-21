#!/usr/bin/env python3
"""Render authored workplace content and native RAE service-content declarations.

No network calls, account provisioning, transport, or runtime deployment.
Source packages are self-contained; artifact catalog paths are pack-relative.
"""
from __future__ import annotations
import argparse
import base64
import csv
from datetime import datetime, timezone
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import format_datetime, formataddr
import hashlib
import gzip
import io
import json
from pathlib import Path
import uuid
import zipfile
import yaml

PACK = Path(__file__).resolve().parents[1]
ROOT = PACK / 'assets/narrative'
AUTHOR = ROOT / 'authoring'
ORGS = {
    'keplerops': ('k-corporate.k-staff', 'keplerops.com'),
    'arwc': ('a-corporate.a-business', 'alterrawaterco.com'),
}
AUDIENCES = {'support': ['rowan', 'maya', 'talia'], 'platform': ['noor', 'evan'],
             'outreach': ['mina', 'owen', 'rosa']}
SDL_ITEM_ENUMERATION_LIMIT = 10000


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def document_text(document):
    return document['text'] if 'text' in document else (ROOT / document['file']).read_text()


def document_bytes(document):
    if 'archive' in document:
        with zipfile.ZipFile(ROOT / document['archive']) as archive:
            raw = archive.read(document['member'])
        assert sha(raw) == document['binary_sha256'], document['id']
        return raw
    return document_text(document).encode()


def document_path(document):
    return document['path'] if 'path' in document else Path(document['file']).name


def message_id(key, domain):
    return f'<{uuid.uuid5(uuid.NAMESPACE_URL, "urn:cinder-workplace:" + key)}@{domain}>'


def utc(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def ics_escape(value):
    return value.replace('\\', '\\\\').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def render():
    identity = yaml.safe_load((AUTHOR / 'people.yaml').read_text())
    workforce = yaml.safe_load((AUTHOR / 'workforce.yaml').read_text())
    assert workforce['snapshot'] == identity['snapshot']
    roster = workforce['employees']
    assert len({p['key'] for p in roster}) == len(roster)
    people = dict(identity['people'])
    for person in roster:
        key = person['key']
        if key in people:
            assert all(people[key][field] == person[field] for field in
                       ('name', 'email', 'employer', 'department', 'job')), key
        else:
            people[key] = {field: person[field] for field in
                           ('name', 'email', 'employer', 'department', 'job')}
    contacts = people | identity['correspondents']
    snapshot = datetime.fromisoformat(identity['snapshot'])
    docs = []
    for path in sorted(AUTHOR.glob('documents*.yaml')):
        docs.extend(yaml.safe_load(path.read_text())['documents'])
    docs_by_id = {d['id']: d for d in docs}
    mail = []
    for path in sorted(AUTHOR.glob('mail-*.yaml')):
        mail.extend(yaml.safe_load(path.read_text())['messages'])
    mail.sort(key=lambda m: (datetime.fromisoformat(m['date']), m['id']))
    assert len({m['id'] for m in mail}) == len(mail), 'Duplicate message IDs'
    by_id = {m['id']: m for m in mail}
    native_ids = {m['id']: message_id(m['id'], contacts[m['from']]['email'].split('@')[1]) for m in mail}
    output = {}
    coverage = {}
    packages = {org: {'schema_version': 'cinder-mailbox-set/v1', 'snapshot': identity['snapshot'],
                      'messages': [], 'mailboxes': {}} for org in ORGS}
    libraries = {org: {
        'documents': {'schema_version': 'cinder-document-library/v1', 'documents': []},
        'directory': {'schema_version': 'cinder-staff-directory/v1', 'documents': [], 'reader_groups': {},
                      'identity_requirements': {'authentication': 'individual staff identity',
                                                'access': 'same-employer staff readers'}},
        'employment': {'schema_version': 'cinder-employment-records/v1', 'documents': [], 'reader_groups': {},
                       'identity_requirements': {'authentication': 'individual staff identity',
                                                 'access': 'exact item readers'}},
    } for org in ORGS}
    for person in roster:
        for kind in ('directory', 'employment'):
            groups = libraries[person['employer']][kind]['reader_groups']
            for group in person['groups']:
                groups.setdefault(group, []).append(person['email'])
    for key, person in people.items():
        if person['employer'] in ORGS:
            packages[person['employer']]['mailboxes'][person['email']] = {'owner': person['email'], 'folders': {'INBOX': [], 'Sent': []}}
    for m in mail:
        assert datetime.fromisoformat(m['date']) <= snapshot, m['id']
        assert m['from'] in contacts and all(p in contacts for p in m['to']), m['id']
        sender = contacts[m['from']]
        msg = EmailMessage(policy=SMTP)
        msg['From'] = formataddr((sender['name'], sender['email']))
        msg['To'] = ', '.join(formataddr((contacts[p]['name'], contacts[p]['email'])) for p in m['to'])
        msg['Date'] = format_datetime(datetime.fromisoformat(m['date']))
        msg['Message-ID'] = native_ids[m['id']]
        msg['Subject'] = m['subject']
        if m.get('reply_to'):
            ancestors = []
            parent = m['reply_to']
            while parent:
                assert parent in by_id and parent not in ancestors, m['id']
                assert datetime.fromisoformat(by_id[parent]['date']) < datetime.fromisoformat(m['date']), m['id']
                ancestors.append(parent)
                parent = by_id[parent].get('reply_to')
            msg['In-Reply-To'] = native_ids[m['reply_to']]
            msg['References'] = ' '.join(native_ids[p] for p in reversed(ancestors))
        msg.set_content(m['body'], charset='utf-8', cte='quoted-printable')
        for attachment in m.get('attachments', []):
            d = docs_by_id[attachment]
            assert datetime.fromisoformat(d['published_at']) <= datetime.fromisoformat(m['date']), ('Attachment from the future', m['id'], attachment)
            maintype, subtype = d.get('media_type', 'text/markdown').split('/', 1)
            raw_attachment = document_bytes(d)
            params = {}
            if (maintype, subtype) == ('text', 'calendar'):
                methods = [line[7:] for line in raw_attachment.decode('utf-8').splitlines()
                           if line.startswith('METHOD:')]
                assert len(methods) <= 1, d['id']
                if methods:
                    params['method'] = methods[0]
            msg.add_attachment(raw_attachment, maintype=maintype, subtype=subtype,
                               filename=document_path(d), params=params)
        if msg.is_multipart():
            msg.set_boundary('workplace-' + sha(m['id'].encode())[:24])
        raw = msg.as_bytes()
        # The workplace source package carries every exact RFC822 message.
        # Keep the original story messages as separate review files; the larger
        # workforce and business slices stay in source packages to respect pack member limits.
        path = None if m['id'].startswith(('wm-', 'bn-', 'si-', 'fe-', 'pq-', 'rp-', 'cf-', 'cm-', 'fn-', 'ol-', 'sa-', 'op-', 'me-', 'lq-', 'ps-')) else f'generated/messages/{m["id"]}.eml'
        if path:
            output[path] = raw
        destinations = {}
        for key, folder in [(m['from'], 'Sent')] + [(p, 'INBOX') for p in m['to']]:
            person = contacts[key]
            org = person['employer']
            if org not in ORGS:
                continue
            box = packages[org]['mailboxes'].setdefault(person['email'], {'owner': person['email'], 'folders': {'INBOX': [], 'Sent': []}})
            box['folders'][folder].append(native_ids[m['id']])
            destinations.setdefault(org, []).append({'mailbox': person['email'], 'folder': folder})
        assert destinations, f'No retained principal-company copy: {m["id"]}'
        for org in destinations:
            packages[org]['messages'].append({'message_id': native_ids[m['id']], 'rfc822': raw.decode('ascii'), 'sha256': sha(raw)})
        coverage[m['id']] = {'story': m['story'], 'file': path, 'message_id': native_ids[m['id']],
                             'retained': destinations, 'attachments': m.get('attachments', [])}
    for d in docs:
        assert datetime.fromisoformat(d['published_at']) <= snapshot, d['id']
        if d['audience'] == 'staff':
            audience = [p['email'] for p in people.values() if p['employer'] == d['employer']]
        elif d['audience'] == 'restricted':
            audience = list(dict.fromkeys(people[k]['email'] for k in d['reader_keys']))
        else:
            audience = [people[k]['email'] for k in AUDIENCES[d['audience']]]
        kind = d.get('collection', 'documents')
        libraries[d['employer']][kind]['documents'].append({'name': d['id'], 'title': d['title'], 'path': document_path(d),
            'media_type': d.get('media_type', 'text/markdown'), 'published_at': d['published_at'],
            'readers': audience, 'text': document_text(d)})
        if 'archive' in d:
            library = libraries[d['employer']][kind]
            library['schema_version'] = library['schema_version'].replace('/v1', '/v2')
            content = document_bytes(d)
            if d.get('content_encoding'):
                assert d['content_encoding'] == 'gzip', d['id']
                compressed = io.BytesIO()
                with gzip.GzipFile(fileobj=compressed, mode='wb', filename='', mtime=0) as stream:
                    stream.write(content)
                content = compressed.getvalue()
                library['schema_version'] = library['schema_version'].replace('/v2', '/v3')
                library['documents'][-1]['content_encoding'] = 'gzip'
            library['documents'][-1].update(
                content_base64=base64.b64encode(content).decode('ascii'),
                sha256=d['binary_sha256'])
    for org in ORGS:
        rows = [{'name': p['name'], 'email': p['email'], 'department': p['department'],
                 'team': p['team'], 'job': p['job'],
                 'manager': people[p['manager']]['name'] if p['manager'] else '',
                 'work_contact': p['extension'], 'base': p['site']}
                for p in roster if p['employer'] == org]
        buf = io.StringIO(newline='')
        writer = csv.DictWriter(buf, fieldnames=['name', 'email', 'department', 'team', 'job',
                                                'manager', 'work_contact', 'base'], lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
        output[f'generated/directories/{org}.csv'] = buf.getvalue().encode()
        libraries[org]['directory']['documents'].append({'name': org + '-directory', 'title': 'Staff contacts', 'path': 'staff-contacts.csv',
            'media_type': 'text/csv', 'readers': [p['email'] for p in people.values() if p['employer'] == org], 'text': buf.getvalue()})
    events = []
    for path in sorted(AUTHOR.glob('calendars*.yaml')):
        events.extend(yaml.safe_load(path.read_text())['events'])
    for event in events:
        organizer = contacts[event['organizer']]
        lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Workplace Calendar//EN', 'CALSCALE:GREGORIAN', 'BEGIN:VEVENT',
                 'UID:' + message_id(event['id'], ORGS[event['employer']][1])[1:-1],
                 'DTSTAMP:' + utc(event.get('updated_at', event.get('created_at', identity['snapshot']))),
                 'DTSTART:' + utc(event['start']), 'DTEND:' + utc(event['end']),
                 'ORGANIZER:mailto:' + organizer['email']]
        lines += [('ATTENDEE;PARTSTAT=' + event['responses'][p] if 'responses' in event else 'ATTENDEE') +
                  ':mailto:' + contacts[p]['email'] for p in event['attendees']]
        if 'location' in event:
            lines.append('LOCATION:' + ics_escape(event['location']))
        if 'sequence' in event:
            lines.append('SEQUENCE:' + str(event['sequence']))
        lines += ['SUMMARY:' + ics_escape(event['summary']), 'DESCRIPTION:' + ics_escape(event['description']),
                  'STATUS:' + event['status'], 'END:VEVENT', 'END:VCALENDAR']
        folded = []
        for line in lines:
            # These calendar fields are ASCII; fold using RFC 5545 octet limits.
            assert line.isascii(), event['id']
            while len(line.encode()) > 75:
                cut = 75
                while line[cut - 1] == ' ':
                    cut -= 1
                folded.append(line[:cut]); line = ' ' + line[cut:]
            folded.append(line)
        text = '\r\n'.join(folded) + '\r\n'
        # Bulk operating calendars are complete items in the source package.
        # Avoid redundant standalone members, as with bulk RFC822 messages.
        if '-induction-' not in event['id'] and not event['id'].startswith(('rel-2026-', 'chg-2026-', 'com-2026-', 'commercial-', 'office-2026-', 'support-appointment-', 'op-', 'lq-')):
            output[f'generated/calendars/{event["id"]}.ics'] = text.encode()
        readers = [contacts[k]['email'] for k in [event['organizer']] + event['attendees'] if contacts[k]['employer'] == event['employer']]
        kind = 'employment' if '-induction-' in event['id'] else 'documents'
        libraries[event['employer']][kind]['documents'].append({'name': event['id'], 'title': event['summary'], 'path': event['id'] + '.ics',
            'media_type': 'text/calendar', 'readers': readers, 'text': text})
    catalog = {'schema_version': 'cinder-world-artifacts/v1', 'artifacts': []}
    modules = {}
    for org, (node, domain) in ORGS.items():
        namespace = 'narrative-' + org
        module = {'name': 'cinder-' + namespace, 'version': '0.1.0', 'semantic_revision': 'raes-progressive-semantics/v1',
                  'realization': {'default': 'open'}, 'module': {'id': 'cinder-typhoon/' + namespace, 'version': '0.1.0', 'exports': {}},
                  'content': {}, 'propositions': {}, 'assertions': {}, 'evidence_requirements': {}, 'observation_boundaries': {}}
        for kind, payload in [('mail', packages[org])] + list(libraries[org].items()):
            raw = json_text(payload).encode()
            rel = f'generated/packages/{org}-{kind}.json'
            output[rel] = raw
            source = {'name': f'cinder-typhoon/narrative/{org}-{kind}', 'version': 'sha256-' + sha(raw)}
            key = kind + '-visible'
            item_names = [{'name': m['id'], 'display_name': m['subject']} for m in mail if org in coverage[m['id']]['retained']] if kind == 'mail' else [{'name': d['name'], 'display_name': d['title']} for d in payload['documents']]
            access = ('Exact mailbox membership' if kind == 'mail' else
                      'Same-employer staff readers' if kind == 'directory' else
                      'Exact named personnel readers' if kind == 'employment' else
                      'Exact document readers')
            description = (f'{org} workplace {kind}. Require an individual staff identity; {access}. '
                           'Preserve authored readers and opening state.')
            content_decl = {'type': 'dataset', 'target': node, 'format': payload['schema_version'], 'source': source,
                'description': description}
            # The package source is authoritative. Very large display-name lists duplicate
            # that inventory and can exceed RAE's per-source YAML graph limit without
            # changing what is materialized or read back.
            if len(item_names) <= SDL_ITEM_ENUMERATION_LIMIT:
                content_decl['items'] = item_names
            else:
                content_decl['description'] += ' Source package is the complete item inventory.'
            content_decl.update({'sensitive': kind != 'directory',
                'tags': ['world-content', 'synthetic'], 'service_materialization': {
                    'target_service_ref': f'nodes.{node}.services.workplace', 'interface_profile': 'service-content', 'profile_version': '1',
                    'requirements': {'operation': 'ensure-owned-items', 'conflict_policy': 'reject-unowned-collision', 'readback': 'canonical-content-digest'},
                    'readback_assertion_refs': [key], 'evidence_requirement_refs': [key], 'observation_boundary_refs': [key]}})
            module['content'][kind] = content_decl
            prop = 'cinder.world.' + org + '.' + kind + '.visible'
            module['propositions'][key] = {'description': f'The declared {kind} can be read through the workplace service with the authored audience boundaries.',
                'subjects': ['content.' + kind], 'basis': 'observed_state',
                'predicate': {'kind': 'boolean', 'property': prop, 'semantic_ref': 'urn:cinder-typhoon:world:' + org + ':' + kind + ':visible', 'expected': True},
                'evidence_requirements': [key]}
            module['assertions'][key] = {'proposition': key, 'role': 'postcondition'}
            module['observation_boundaries'][key] = {'projection_basis': 'Ordinary authenticated reader access; each mailbox owner or listed document reader sees their own authorized collection.',
                'observable_refs': ['content.' + kind], 'redaction_policy': 'Preserve authored content only for its listed audience; no collection-wide bypass.',
                'latency_profile': 'Initial content available before participant admission.'}
            module['evidence_requirements'][key] = {'source_refs': ['content.' + kind], 'scope': 'Native workplace service readback',
                'boundary_kind': 'participant_equivalent', 'channel': 'api_response', 'artifact_role': 'service_materialization_readback',
                'media_types': ['application/json'], 'sensitivity': 'plain', 'redaction': 'redact_secrets', 'integrity': 'checksum', 'retention': 'run_lifetime', 'loss_disclosure': 'required',
                'observation_demand': {'rule_id': prop, 'scope': '/content', 'mode': 'selected', 'purpose': 'experimental', 'collection': 'require', 'retention': 'require',
                    'basis': 'observed', 'required': True, 'integrity': 'checksum', 'redaction': 'redact-secrets',
                    'selector': {'semantic_scope': '/content', 'component_refs': ['content.' + namespace + '.' + kind], 'data_kind': 'artifact', 'names': [prop]}}}
            catalog['artifacts'].append({'source': source, 'path': 'assets/narrative/' + rel, 'sha256': sha(raw), 'media_type': 'application/json',
                'content_ref': namespace + '.' + kind, 'target': node, 'format': payload['schema_version']})
        for section in ('content', 'propositions', 'assertions', 'evidence_requirements', 'observation_boundaries'):
            module['module']['exports'][section] = list(module[section])
        modules[org] = yaml.safe_dump(module, sort_keys=False, allow_unicode=True, width=105).encode()
    output['artifact-catalog.json'] = json_text(catalog).encode()
    output['story-coverage.json'] = json_text({'snapshot': identity['snapshot'], 'messages': coverage,
        'documents': {d['id']: {'story': d['story'], 'file': d.get('file'), 'path': document_path(d),
                                'employer': d['employer']} for d in docs}}).encode()
    return output, modules


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    output, modules = render()
    paths = {ROOT / name: data for name, data in output.items()}
    paths.update({PACK / f'sdl/modules/world/narrative-{org}.yaml': data for org, data in modules.items()})
    stale = [str(p.relative_to(PACK)) for p, data in paths.items() if not p.exists() or p.read_bytes() != data]
    expected_generated = {p for p in paths if p.is_relative_to(ROOT / 'generated')}
    extra = {p for p in (ROOT / 'generated').rglob('*') if p.is_file()} - expected_generated
    if extra:
        raise SystemExit('Unexpected generated files; review before removal: ' + ', '.join(map(str, sorted(extra))))
    if args.check:
        if stale: raise SystemExit('Stale narrative output: ' + ', '.join(stale))
        print(f'PASS: {len(paths)} narrative outputs reproduce byte-for-byte')
    else:
        for path, data in paths.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        print(f'Wrote {len(paths)} narrative outputs; no deployment or outbound communication')

if __name__ == '__main__':
    main()
