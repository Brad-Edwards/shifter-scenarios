#!/usr/bin/env python3
"""Check narrative source bytes, correspondence, audience, and native SDL bindings."""
from __future__ import annotations
from collections import Counter
import base64
from datetime import datetime
from datetime import timezone
from decimal import Decimal
import csv
import io
from email.parser import BytesParser
from email.policy import default
from email.utils import getaddresses, parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import re
import sys
import yaml
import zipfile
from validate_release_platform import check_release_platform
from validate_customer_followup import check_customer_followup
from validate_commercial import check_commercial
from validate_finance import check_finance
from validate_office_life import check_calendar_part, check_office_life

PACK = Path(__file__).resolve().parents[1]
ROOT = PACK / 'assets/narrative'
TARGETS = {'keplerops': 'k-corporate.k-staff', 'arwc': 'a-corporate.a-business'}
KINDS = ('mail', 'documents', 'directory', 'employment')
NARRATIVE_EVIDENCE = {f'narrative-{org}.{kind}-visible' for org in TARGETS for kind in KINDS}
STORIES = {'bicycle', 'lunch', 'workshop', 'anniversary', 'choir', 'photography', 'outreach', 'billing'}
BUSINESS_MESSAGE_COUNT = 1600
SUPPORT_MESSAGE_COUNT = 5500
SUPPORT_DOCUMENT_COUNT = 578
FIELDKEST_MESSAGE_COUNT = 5500
FIELDKEST_DOCUMENT_COUNT = 720
PRODUCT_QUALITY_MESSAGE_COUNT = 4000
PRODUCT_QUALITY_DOCUMENT_COUNT = 1976
RELEASE_PLATFORM_MESSAGE_COUNT = 1572
RELEASE_PLATFORM_DOCUMENT_COUNT = 530
CUSTOMER_FOLLOWUP_MESSAGE_COUNT = 2504
CUSTOMER_FOLLOWUP_DOCUMENT_COUNT = 310
COMMERCIAL_MESSAGE_COUNT = 1376
COMMERCIAL_DOCUMENT_COUNT = 251
FINANCE_MESSAGE_COUNT = 1133
FINANCE_DOCUMENT_COUNT = 562
OFFICE_MESSAGE_COUNT = 1730
OFFICE_DOCUMENT_COUNT = 1385
TOTAL_MESSAGE_COUNT = (1475 + BUSINESS_MESSAGE_COUNT + SUPPORT_MESSAGE_COUNT +
                       FIELDKEST_MESSAGE_COUNT + PRODUCT_QUALITY_MESSAGE_COUNT +
                       RELEASE_PLATFORM_MESSAGE_COUNT + CUSTOMER_FOLLOWUP_MESSAGE_COUNT + COMMERCIAL_MESSAGE_COUNT + FINANCE_MESSAGE_COUNT + OFFICE_MESSAGE_COUNT)
TOTAL_DOCUMENT_COUNT = (155 + 89 + SUPPORT_DOCUMENT_COUNT + FIELDKEST_DOCUMENT_COUNT +
                        PRODUCT_QUALITY_DOCUMENT_COUNT + RELEASE_PLATFORM_DOCUMENT_COUNT +
                        CUSTOMER_FOLLOWUP_DOCUMENT_COUNT + COMMERCIAL_DOCUMENT_COUNT + FINANCE_DOCUMENT_COUNT + OFFICE_DOCUMENT_COUNT)


def require(value, message):
    if not value:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text())


def document_text(document):
    return document['text'] if 'text' in document else (ROOT / document['file']).read_text()


def document_bytes(document):
    if 'archive' in document:
        with zipfile.ZipFile(ROOT / document['archive']) as archive:
            raw = archive.read(document['member'])
        require(hashlib.sha256(raw).hexdigest() == document['binary_sha256'], 'Binary digest drift')
        return raw
    return document_text(document).encode()


def document_path(document):
    return document['path'] if 'path' in document else Path(document['file']).name


def check_business_network(identity, roster, mail, docs):
    network = yaml.safe_load((ROOT / 'authoring/business-network.yaml').read_text())
    require(network['snapshot'] == identity['snapshot'], 'Business snapshot drift')
    organizations = network['organizations']
    contacts = network['contacts']
    cases = network['cases']
    require(len(organizations) == 19 and len({o['key'] for o in organizations}) == 19,
            'Business organization inventory drift')
    require(sum(o['kind'] == 'utility_customer' for o in organizations) == 12,
            'Utility customer inventory drift')
    require(len(contacts) == 47 and len({c['key'] for c in contacts}) == 47,
            'Business contact inventory drift')
    require(len(cases) == 400 and len({c['id'] for c in cases}) == 400,
            'Business case inventory drift')
    business_mail = {m['id']: m for m in mail if m['id'].startswith('bn-')}
    require(len(business_mail) == BUSINESS_MESSAGE_COUNT, 'Business message inventory drift')
    business_docs = {d['id']: d for d in docs if d['story'] == 'business-network'}
    require(len(business_docs) == 89, 'Business document inventory drift')
    require(sum(d['title'].endswith('accepted service schedule') for d in business_docs.values()) == 10,
            'Signed/accepted schedule inventory drift')
    for document in business_docs.values():
        if not document['title'].endswith('accepted service schedule'):
            continue
        agreement = document_text(document)
        company_signer = 'Leah Calder-Voss' if document['employer'] == 'keplerops' else 'Priya Naravel'
        require('/s/ ' + company_signer in agreement,
                'Accepted schedule signed by the wrong company representative')
        accepted = datetime.fromisoformat(agreement.split('Accepted: **')[1].split('**')[0])
        signer = next(p for p in roster if p['name'] == company_signer)
        require(datetime.fromisoformat(signer['start_date']) <= accepted
                and document['published_at'].startswith(accepted.date().isoformat()),
                'Accepted schedule date or representative tenure drift')
    source_contacts = identity['people'] | identity['correspondents']
    staff_keys = {p['key'] for p in roster}
    keys = {o['key'] for o in organizations}
    account_ids = {o['account_id'] for o in organizations}
    require(len(account_ids) == 19 and len({o['agreement_id'] for o in organizations}) == 19,
            'Duplicate business identifier')
    require(all(o['holder'] in ('arwc', 'keplerops') and o['owner'] in staff_keys
                and o['commercial_owner'] in staff_keys for o in organizations),
            'Unknown company account owner')
    require(all(next(p for p in roster if p['key'] == o['owner'])['employer'] == o['holder']
                and next(p for p in roster if p['key'] == o['commercial_owner'])['employer'] == o['holder']
                for o in organizations), 'Cross-company account owner')
    require(all(datetime.fromisoformat(o['effective']) < datetime.fromisoformat(o['end'])
                and datetime.fromisoformat(o['effective']).date() <=
                    datetime.fromisoformat(identity['snapshot']).date() for o in organizations),
            'Business agreement dates invalid')
    for org in organizations:
        require(org['domain'] in ('keplerops.com', 'alterrawaterco.com') or org['domain'].endswith('.test'),
                'Nonfictional supporting domain')
        require(all(key in source_contacts and source_contacts[key]['employer'] == org['key']
                    for key in org['contact_keys']), 'Contact employment or account join drift')
        related = [d for d in business_docs.values() if org['account_id'] in document_text(d)]
        require(len(related) >= 3, f'Missing account, contract, or contact record: {org["key"]}')
        summaries = [d for d in related if d['title'].endswith('agreement summary')]
        require(any(org['agreement_id'] in document_text(d)
                    and org['effective'] in document_text(d)
                    and org['end'] in document_text(d)
                    for d in summaries), f'Agreement summary drift: {org["key"]}')
        if org['kind'] == 'utility_customer':
            require(org['holder'] == 'keplerops' and 'annual service fee' in org['terms'],
                    'Utility contract type drift')
            fee = int(org['terms'].split('USD ')[1].split(' annual')[0].replace(',', ''))
            instalment = int(org['terms'].split('instalments of USD ')[1].replace(',', ''))
            require(4 * instalment == fee, 'Quarterly instalments do not total annual fee')
        if org['key'] == 'merewick':
            require('20,000 m³' in org['terms'] and 'reservation' in org['scope'],
                    'Bulk supply limit or condition drift')
        if org['key'] == 'talvern':
            require('7,500 m³' in org['terms'] and 'supplementary' in org['scope'],
                    'Talvern allowance drift')
        if org['key'] == 'orrenvale':
            require('excluding FieldKest production workloads' in org['scope'],
                    'Internal IT service scope drift')
        if 'settled_activity' in org:
            ledger = org['settled_activity']
            require(len({row['reference'] for row in ledger}) == len(ledger),
                    'Duplicate accepted activity reference')
            unit = 'pages' if org['key'] == 'ternwick' else 'm³'
            expected_rate = {'merewick': Decimal('0.92'), 'talvern': Decimal('1.15'),
                             'ternwick': Decimal('0.42')}[org['key']]
            account_text = '\n'.join(document_text(d) for d in related)
            for row in ledger:
                day = datetime.fromisoformat(row['date'])
                charge = Decimal(row['quantity']) * Decimal(row['unit_price_usd'])
                if org['key'] == 'ternwick':
                    charge += Decimal('180')
                require(day.date() <= datetime.fromisoformat(identity['snapshot']).date()
                        and row['quantity'] > 0 and row['unit'] == unit
                        and Decimal(row['unit_price_usd']) == expected_rate
                        and Decimal(row['accepted_amount_usd']) == charge,
                        'Accepted activity arithmetic or date drift')
                require(row['reference'] in account_text
                        and any(row['reference'] in m['body']
                                and datetime.fromisoformat(m['date']).date() >= day.date()
                                for m in business_mail.values()),
                        'Accepted activity absent from account or correspondence')
            volume = sum(row['quantity'] for row in ledger)
            require(volume <= (20000 if org['key'] == 'merewick' else 7500 if org['key'] == 'talvern'
                               else 100000), 'Accepted activity exceeds contract ceiling')
    for contact in contacts:
        require(contact['key'] in identity['correspondents'] and contact['key'] not in staff_keys,
                'External contact entered staff roster')
        source = identity['correspondents'][contact['key']]
        require(source['name'] == contact['name'] and source['email'] == contact['email']
                and source['employer'] == contact['employer'], 'Contact identity drift')
        require(contact['sample_message_id'] in business_mail
                and business_mail[contact['sample_message_id']]['from'] == contact['key']
                and contact['context_note'] and contact['writing_note'], 'Business voice sample missing')
    seen_messages = set()
    org_by_key = {o['key']: o for o in organizations}
    for case in cases:
        require(case['organization'] in keys and case['id'].startswith(org_by_key[case['organization']]['account_id']),
                'Business case account join drift')
        chain = []
        current = case['last_message']
        while current:
            require(current in business_mail and current not in chain, 'Missing or cyclic business thread')
            chain.append(current)
            item = business_mail[current]
            require(item['story'] == case['organization'] and case['id'] in item['subject'],
                    'Business message organization or reference drift')
            current = item.get('reply_to')
        require(chain[-1] == case['opened'] and len(chain) == case['message_count'],
                'Business thread inventory drift')
        seen_messages.update(chain)
    require(seen_messages == set(business_mail), 'Unjoined business message')
    visible = [m['subject'] + '\n' + m['body'] for m in business_mail.values()]
    visible += [document_text(d) for d in business_docs.values()]
    leak = ('cinder typhoon', 'issue 113', 'scenario layer', 'author-only', 'openrae',
            'shifter-scenarios', 'challenge-specific')
    require(all(not any(term in text.lower() for term in leak) for text in visible),
            'Authoring or challenge language in business content')


def check_support_intake(identity, roster, mail, docs, events):
    manifest = yaml.safe_load((ROOT / 'authoring/support-intake.yaml').read_text())
    network = yaml.safe_load((ROOT / 'authoring/business-network.yaml').read_text())
    require(manifest['snapshot'] == identity['snapshot'], 'Support snapshot drift')
    require(manifest['required_base']['business_commit'] == 'ef9c89f',
            'Support slice is not pinned to the accepted business content')
    require(manifest['counts'] == {'cases': 500, 'messages': 5500, 'case_documents': 500,
                                   'supporting_documents': 78, 'appointments': 64},
            'Support declared counts drift')
    cases = manifest['cases']
    require(len(cases) == len({c['id'] for c in cases}) == 500,
            'Support case inventory drift')
    expected_categories = {'routine': 300, 'customer_waiting': 60, 'implementation': 70,
                           'engineering_escalation': 30, 'onboarding': 40}
    expected_statuses = {'resolved_support': 300, 'waiting_customer': 60,
                         'implementation_complete': 50, 'implementation_scheduled': 20,
                         'engineering_accepted': 30, 'onboarding_complete': 28,
                         'onboarding_scheduled': 12}
    require(Counter(c['category'] for c in cases) == Counter(expected_categories),
            'Support case-category allocation drift')
    require(Counter(c['status'] for c in cases) == Counter(expected_statuses),
            'Support case-state allocation drift')
    require([c['id'] for c in cases] == [f'SUP-2026-{n:04d}' for n in range(1, 501)],
            'Support case identifiers are not stable and contiguous')

    support_keys = {p['key'] for p in roster if p['employer'] == 'keplerops'
                    and p['department'] == 'Support and implementation'}
    require(len(support_keys) == 14, 'Support staff allocation drift')
    organizations = {o['key']: o for o in network['organizations'] if o['kind'] == 'utility_customer'}
    require(len(organizations) == 12, 'Support customer book drift')
    support_mail = {m['id']: m for m in mail if m['id'].startswith('si-')}
    require(len(support_mail) == SUPPORT_MESSAGE_COUNT
            and list(support_mail) == [f'si-{n:04d}' for n in range(1, SUPPORT_MESSAGE_COUNT + 1)],
            'Support message inventory drift')
    require(len({m['body'] for m in support_mail.values()}) == SUPPORT_MESSAGE_COUNT,
            'Support mail contains repeated bodies')
    system_notices = [m for m in support_mail.values() if m['from'] == 'k_case_updates']
    require(len(system_notices) == 500
            and all(m['body'].startswith('Case: SUP-2026-')
                    and 'This automated notice records the current service-desk state.' in m['body']
                    for m in system_notices),
            'Support system-notice inventory or format drift')
    normalized_bodies = []
    for message in support_mail.values():
        body = message['body'].lower()
        body = re.sub(r'sup-2026-\d{4}|eng-2026-\d{3}|\b4\.[0-9]+\.[0-9]+\b', '<id>', body)
        body = re.sub(r'\n\n[a-z]+\n$', '\n<signature>\n', body)
        normalized_bodies.append(body)
    normalized_counts = Counter(normalized_bodies)
    require(len(normalized_counts) >= 3400 and normalized_counts.most_common(1)[0][1] <= 25,
            'Support prose is repetitive after identifiers and signatures are removed')
    support_docs = {d['id']: d for d in docs if d['story'] == 'support-intake'}
    require(len(support_docs) == SUPPORT_DOCUMENT_COUNT,
            'Support document inventory drift')
    require(sum(k.startswith('support-case-') for k in support_docs) == 500
            and sum(k.startswith('support-kb-') for k in support_docs) == 24
            and sum(k.startswith('support-onboarding-') for k in support_docs) == 12
            and sum(k.startswith('support-implementation-') for k in support_docs) == 12
            and sum(k.startswith('support-escalation-') for k in support_docs) == 30,
            'Support document-family allocation drift')
    support_events = {e['id']: e for e in events if e['id'].startswith('support-appointment-')}
    require(len(support_events) == 64, 'Support appointment inventory drift')

    contacts = identity['people'] | identity['correspondents']
    snapshot = datetime.fromisoformat(identity['snapshot'])
    seen_messages = set()
    seen_appointments = set()
    engineering_ids = set()
    for case in cases:
        require(case['organization'] in organizations, f'Unknown support customer: {case["id"]}')
        org = organizations[case['organization']]
        require(case['account_id'] == org['account_id']
                and case['entitlement_effective'] == org['effective']
                and case['account_owner'] == org['owner'],
                f'Support account join drift: {case["id"]}')
        require(case['owner'] in support_keys and case['customer_contact'] in org['contact_keys']
                and case['customer_contact'] in contacts,
                f'Support owner or customer contact drift: {case["id"]}')
        opened = datetime.fromisoformat(case['opened_at'])
        last = datetime.fromisoformat(case['last_activity'])
        require(datetime.fromisoformat(case['entitlement_effective']).date() <= opened.date()
                and opened <= last <= snapshot,
                f'Support case outside entitlement or snapshot: {case["id"]}')
        require(case['product_version'] in {'4.8.2', '4.9.0', '4.9.1'}
                and len(case['prior_attempts']) == 2 and len(set(case['prior_attempts'])) == 2,
                f'Incomplete support facts: {case["id"]}')
        closed = case['status'].endswith(('_support', '_complete'))
        require((case['closed_at'] == case['last_activity']) if closed else case['closed_at'] is None,
                f'Support closure state drift: {case["id"]}')
        require(set(case['threads']) == {'customer_visible', 'internal'},
                f'Support visibility threads missing: {case["id"]}')

        case_messages = {}
        thread_messages = {}
        for boundary, thread in case['threads'].items():
            chain = []
            current = thread['last']
            while current:
                require(current in support_mail and current not in chain and current not in seen_messages,
                        f'Missing, cyclic, or cross-case support thread: {case["id"]}')
                item = support_mail[current]
                chain.append(current)
                require(item['story'] == 'support-intake' and case['id'] in item['subject'],
                        f'Support message case join drift: {current}')
                participants = [item['from']] + item['to']
                employers = {contacts[k]['employer'] for k in participants}
                if boundary == 'internal':
                    require(employers == {'keplerops'}, f'Customer included in internal thread: {current}')
                else:
                    require(case['organization'] in employers and 'keplerops' in employers,
                            f'Customer-visible thread lacks both parties: {current}')
                current = item.get('reply_to')
            chain.reverse()
            require(chain[0] == thread['root'] and len(chain) == thread['message_count'],
                    f'Support thread count or root drift: {case["id"]}/{boundary}')
            require(all(datetime.fromisoformat(support_mail[mid]['date']) <
                        datetime.fromisoformat(support_mail[next_mid]['date'])
                        for mid, next_mid in zip(chain, chain[1:])),
                    f'Support reply chronology drift: {case["id"]}/{boundary}')
            thread_messages[boundary] = chain
            case_messages.update({mid: support_mail[mid] for mid in chain})
            seen_messages.update(chain)
        require(len(case_messages) == case['message_count']
                == sum(t['message_count'] for t in case['threads'].values()),
                f'Support case message count drift: {case["id"]}')
        case_notices = [m for m in case_messages.values() if m['from'] == 'k_case_updates']
        require(len(case_notices) == 1
                and set(case_notices[0]['to']) == {case['owner'], case['customer_contact']},
                f'Support system notice audience drift: {case["id"]}')
        require(case['opened_at'] == min(m['date'] for m in case_messages.values())
                and case['last_activity'] == max(m['date'] for m in case_messages.values()),
                f'Support case activity bounds drift: {case["id"]}')

        customer_attachments = {a for mid in thread_messages['customer_visible']
                                for a in support_mail[mid].get('attachments', [])}
        internal_attachments = {a for mid in thread_messages['internal']
                                for a in support_mail[mid].get('attachments', [])}
        require(customer_attachments == set(case['customer_visible_attachments'])
                and internal_attachments == set(case['internal_attachments'])
                and not customer_attachments & internal_attachments,
                f'Support attachment visibility drift: {case["id"]}')
        require(customer_attachments | internal_attachments <= set(support_docs),
                f'Support attachment missing from document source: {case["id"]}')

        document = support_docs[case['case_document']]
        expected_readers = support_keys | ({'rowan'} if case['category'] == 'engineering_escalation' else set())
        require(document['audience'] == 'restricted' and set(document['reader_keys']) == expected_readers,
                f'Support case reader boundary drift: {case["id"]}')
        text = document_text(document)
        require(all(value in text for value in (case['id'], case['account_id'], case['product_version'],
                                                case['observed_behavior'].capitalize(), case['expected_follow_up'])),
                f'Support case document facts drift: {case["id"]}')
        require(case['case_document'] not in customer_attachments | internal_attachments,
                f'Internal support case attached to mail: {case["id"]}')

        if case['category'] == 'engineering_escalation':
            engineering_ids.add(case['engineering_change_id'])
            require(case['status'] == 'engineering_accepted'
                    and case['engineering_change_id'] in case['expected_follow_up']
                    and len(internal_attachments) == 1
                    and next(iter(internal_attachments)).endswith(case['engineering_change_id'].lower())
                    and not customer_attachments,
                    f'Engineering escalation contract drift: {case["id"]}')
            require('no fix is recorded' in case['outcome'].lower()
                    and 'release date' not in case['outcome'].lower(),
                    f'Engineering outcome fabricated: {case["id"]}')
        elif case['category'] in {'routine', 'customer_waiting', 'implementation', 'onboarding'}:
            require(len(customer_attachments) == 1 and not internal_attachments,
                    f'Customer material allocation drift: {case["id"]}')

        appointment = case.get('appointment_id')
        if appointment:
            require(appointment in support_events and appointment not in seen_appointments,
                    f'Support appointment join drift: {case["id"]}')
            event = support_events[appointment]
            require(event['organizer'] == case['owner']
                    and case['customer_contact'] in event['attendees']
                    and case['id'] in event['description'],
                    f'Support appointment facts drift: {case["id"]}')
            event_start = datetime.fromisoformat(event['start'])
            require((event_start > snapshot) if case['status'].endswith('_scheduled')
                    else (opened <= event_start <= last),
                    f'Support appointment chronology drift: {case["id"]}')
            seen_appointments.add(appointment)
        else:
            require(not case['status'].endswith('_scheduled'),
                    f'Scheduled support work lacks appointment: {case["id"]}')

    require(seen_messages == set(support_mail), 'Unjoined support message')
    require(seen_appointments == set(support_events), 'Unjoined support appointment')
    require(engineering_ids == {f'ENG-2026-{n:03d}' for n in range(1, 31)},
            'Engineering escalation identifiers drift')
    require({c['owner'] for c in cases} == support_keys,
            'Support case ownership does not cover all fourteen staff')
    require(all(any(m['from'] == key for m in support_mail.values()) for key in support_keys),
            'A support staff member has no authored correspondence')
    visible = [m['subject'] + '\n' + m['body'] for m in support_mail.values()]
    visible += [document_text(d) for d in support_docs.values()]
    leak = ('cinder typhoon', 'issue 114', 'scenario layer', 'author-only', 'openrae',
            'shifter-scenarios', 'challenge-specific')
    require(all(not any(term in text.lower() for term in leak) for text in visible),
            'Authoring or challenge language in support content')


def check_fieldkest_engineering(identity, roster, mail, docs):
    """Check the completed engineering corpus joins support without inventing resolutions."""
    manifest = yaml.safe_load((ROOT / 'authoring/fieldkest-engineering.yaml').read_text())
    support = yaml.safe_load((ROOT / 'authoring/support-intake.yaml').read_text())['cases']
    require(manifest['snapshot'] == identity['snapshot'], 'FieldKest snapshot drift')
    require(manifest['required_base'] == {'support_commit': 'aa48fa8', 'business_commit': 'ef9c89f',
                                          'workforce_commit': 'cf20e3e'},
            'FieldKest source base drift')
    require(manifest['counts'] == {'work_items': 350, 'messages': 5500, 'documents': 720,
                                   'repositories': 5, 'accepted_support_escalations': 30},
            'FieldKest declared inventory drift')
    repositories = {item['name'] for item in manifest['repositories']}
    require(repositories == {'fieldkest-core', 'fieldkest-connectors', 'fieldkest-workspace',
                             'fieldkest-integration-kit', 'fieldkest-verification'},
            'FieldKest repository inventory drift')
    work = manifest['work_items']
    require(len(work) == len({item['id'] for item in work}) == 350, 'FieldKest work-item inventory drift')
    ordinary = [item for item in work if item['id'].startswith('FK-')]
    escalated = [item for item in work if item['id'].startswith('ENG-')]
    require([item['id'] for item in ordinary] == [f'FK-2026-{n:04d}' for n in range(1, 321)],
            'FieldKest ordinary work identifiers drift')
    require([item['id'] for item in escalated] == [f'ENG-2026-{n:03d}' for n in range(1, 31)],
            'FieldKest engineering escalation identifiers drift')
    support_by_change = {item['engineering_change_id']: item for item in support
                         if item['category'] == 'engineering_escalation'}
    require(set(support_by_change) == {item['id'] for item in escalated},
            'Support escalation or FieldKest assessment inventory drift')
    engineering_keys = {person['key'] for person in roster if person['employer'] == 'keplerops'
                        and person['department'] == 'Product engineering'}
    quality_keys = {person['key'] for person in roster if person['employer'] == 'keplerops'
                    and person['team'] == 'Quality assurance'}
    release_keys = {person['key'] for person in roster if person['employer'] == 'keplerops'
                    and person['team'] == 'Release engineering'}
    product_keys = {person['key'] for person in roster if person['employer'] == 'keplerops'
                    and person['team'] == 'Product management'}
    expected_readers = engineering_keys | quality_keys | release_keys | product_keys
    fieldkest_docs = {item['id']: item for item in docs if item['story'] == 'fieldkest-engineering'}
    require(len(fieldkest_docs) == FIELDKEST_DOCUMENT_COUNT, 'FieldKest document inventory drift')
    fieldkest_mail = {item['id']: item for item in mail if item['id'].startswith('fe-')}
    require(len(fieldkest_mail) == FIELDKEST_MESSAGE_COUNT
            and list(fieldkest_mail) == [f'fe-{n:04d}' for n in range(1, FIELDKEST_MESSAGE_COUNT + 1)],
            'FieldKest message inventory drift')
    require(len({item['body'] for item in fieldkest_mail.values()}) == FIELDKEST_MESSAGE_COUNT,
            'FieldKest correspondence contains repeated bodies')
    seen_messages = set()
    for item in work:
        require(item['repository'] in repositories and item['owner'] in engineering_keys
                and item['reviewer'] in engineering_keys and item['quality_owner'] in quality_keys
                and item['release_owner'] in release_keys, f'FieldKest role drift: {item["id"]}')
        require(datetime.fromisoformat(item['opened_at']) <= datetime.fromisoformat(identity['snapshot']),
                f'FieldKest work after snapshot: {item["id"]}')
        require(item['revision'].startswith('fk-') and item['topic'] and item['purpose'],
                f'Incomplete FieldKest work record: {item["id"]}')
        work_doc = fieldkest_docs.get('engineering-work-' + item['id'].lower())
        change_doc = fieldkest_docs.get('engineering-change-' + item['id'].lower())
        require(work_doc and change_doc and set(work_doc['reader_keys']) == expected_readers
                and set(change_doc['reader_keys']) == expected_readers,
                f'FieldKest work or change audience drift: {item["id"]}')
        require(all(value in document_text(work_doc) for value in (item['id'], item['repository'], item['topic']))
                and all(value in document_text(change_doc) for value in (item['id'], item['revision'], item['repository'])),
                f'FieldKest document join drift: {item["id"]}')
        related = [message for message in fieldkest_mail.values() if '[' + item['id'] + ']' in message['subject']]
        expected_count = 16 if item['id'].startswith('FK-') and int(item['id'][-4:]) <= 250 else 15
        require(len(related) == expected_count, f'FieldKest correspondence allocation drift: {item["id"]}')
        roots = [message for message in related if not message.get('reply_to')]
        require(len(roots) == 1, f'FieldKest thread root drift: {item["id"]}')
        current = roots[0]
        chain = [current['id']]
        while True:
            children = [message for message in related if message.get('reply_to') == current['id']]
            require(len(children) <= 1, f'FieldKest reply fanout drift: {item["id"]}')
            if not children:
                break
            current = children[0]
            require(current['id'] not in chain and datetime.fromisoformat(current['date']) >
                    datetime.fromisoformat(fieldkest_mail[chain[-1]]['date']),
                    f'FieldKest reply chronology drift: {item["id"]}')
            chain.append(current['id'])
        require(len(chain) == expected_count, f'FieldKest thread join drift: {item["id"]}')
        seen_messages.update(chain)
        attached = [message for message in related if message.get('attachments')]
        require(len(attached) == 1 and attached[0]['attachments'] == [change_doc['id']],
                f'FieldKest revision attachment drift: {item["id"]}')
        if item['id'].startswith('ENG-'):
            case = support_by_change[item['id']]
            require(item['state'] == 'assessment' and item['support_case'] == case['id']
                    and item['product_version'] == case['product_version'] and item['topic'] == case['topic'],
                    f'FieldKest escalation fact drift: {item["id"]}')
            text = document_text(work_doc).lower() + '\n' + document_text(change_doc).lower()
            require('no fix, acceptance result, or release date is recorded here' in text
                    and 'status:** assessment' in text,
                    f'FieldKest escalation falsely resolves support work: {item["id"]}')
        else:
            require(item['support_case'] is None and item['state'] in
                    {'completed', 'accepted', 'deferred', 'rejected'},
                    f'FieldKest ordinary work-state drift: {item["id"]}')
    require(seen_messages == set(fieldkest_mail), 'Unjoined FieldKest correspondence')
    visible = [message['subject'] + '\n' + message['body'] for message in fieldkest_mail.values()]
    visible += [document_text(document) for document in fieldkest_docs.values()]
    leak = ('cinder typhoon', 'issue 115', 'scenario layer', 'author-only', 'openrae',
            'shifter-scenarios', 'challenge-specific')
    require(all(not any(term in text.lower() for term in leak) for text in visible),
            'Authoring or challenge language in FieldKest content')


def check_product_quality(identity, roster, mail, docs):
    """Check product decisions, evidence, and correspondence against shipped engineering history."""
    manifest = yaml.safe_load((ROOT / 'authoring/product-quality.yaml').read_text())
    engineering = yaml.safe_load((ROOT / 'authoring/fieldkest-engineering.yaml').read_text())['work_items']
    support = yaml.safe_load((ROOT / 'authoring/support-intake.yaml').read_text())['cases']
    require(manifest['snapshot'] == identity['snapshot'], 'Product-quality snapshot drift')
    require(manifest['required_base'] == {'fieldkest_engineering_commit': 'da8e33e',
                                          'support_commit': 'aa48fa8',
                                          'workforce_commit': 'cf20e3e'},
            'Product-quality source base drift')
    require(manifest['counts'] == {'decision_records': 250, 'accepted': 220, 'deferred': 20,
                                   'declined': 10, 'messages': 4000, 'documents': 1976,
                                   'roadmap_revisions': 3, 'compatibility_workbooks': 250,
                                   'test_results': 220},
            'Product-quality declared inventory drift')
    records = manifest['records']
    require([item['id'] for item in records] == [f'PQ-2026-{n:04d}' for n in range(1, 251)],
            'Product-quality identifiers are not stable and contiguous')
    require(Counter(item['decision'] for item in records) ==
            Counter({'accepted': 220, 'deferred': 20, 'declined': 10}),
            'Product-quality decision allocation drift')

    work_by_id = {item['id']: item for item in engineering}
    accepted_work = [item for item in engineering if item['id'].startswith('FK-')
                     and item['state'] in {'completed', 'accepted'}][:220]
    assessed_work = [item for item in engineering if item['id'].startswith('ENG-')]
    require([item['engineering_work'] for item in records] ==
            [item['id'] for item in accepted_work + assessed_work],
            'Product-quality engineering selection drift')
    support_by_change = {item['engineering_change_id']: item for item in support
                         if item['category'] == 'engineering_escalation'}
    product_keys = {person['key'] for person in roster if person['employer'] == 'keplerops'
                    and person['team'] == 'Product management'}
    quality_keys = {person['key'] for person in roster if person['employer'] == 'keplerops'
                    and person['team'] == 'Quality assurance'}
    release_keys = {person['key'] for person in roster if person['employer'] == 'keplerops'
                    and person['team'] == 'Release engineering'}
    engineering_keys = {person['key'] for person in roster if person['employer'] == 'keplerops'
                        and person['department'] == 'Product engineering'}
    require(len(product_keys) == 3 and len(quality_keys) == 5,
            'Product or quality roster allocation drift')

    product_docs = {item['id']: item for item in docs if item['story'] == 'product-quality'}
    require(len(product_docs) == PRODUCT_QUALITY_DOCUMENT_COUNT,
            'Product-quality document inventory drift')
    global_ids = {'product-quality-roadmap-v1', 'product-quality-roadmap-v2',
                  'product-quality-roadmap-v3', 'product-quality-acceptance-register',
                  'product-quality-limitations-register', 'product-quality-review-calendar'}
    require(global_ids <= set(product_docs), 'Product-quality roadmap or register missing')
    require('proposal, not commitment' in document_text(product_docs['product-quality-roadmap-v1']).lower()
            and 'working revision, not a release schedule' in
            document_text(product_docs['product-quality-roadmap-v2']).lower()
            and '220 accepted engineering revisions, 20 deferred assessments, and 10 declined assessments'
            in document_text(product_docs['product-quality-roadmap-v3']),
            'Roadmap history loses proposal or revision state')
    acceptance_rows = list(csv.DictReader(io.StringIO(
        document_text(product_docs['product-quality-acceptance-register']))))
    limitation_rows = list(csv.DictReader(io.StringIO(
        document_text(product_docs['product-quality-limitations-register']))))
    require(len(acceptance_rows) == 250 and {row['record_id'] for row in acceptance_rows} ==
            {item['id'] for item in records}, 'Acceptance register inventory drift')
    require(len(limitation_rows) == sum(item['outstanding_limitation'] is not None for item in records),
            'Outstanding-limitation register drift')

    product_mail = {item['id']: item for item in mail if item['id'].startswith('pq-')}
    require(len(product_mail) == PRODUCT_QUALITY_MESSAGE_COUNT
            and list(product_mail) == [f'pq-{n:04d}' for n in range(1, 4001)],
            'Product-quality message inventory drift')
    require(len({item['body'] for item in product_mail.values()}) == PRODUCT_QUALITY_MESSAGE_COUNT,
            'Product-quality correspondence contains repeated bodies')
    normalized = []
    for item in product_mail.values():
        body = item['body'].lower()
        body = re.sub(r'pq-2026-\d{4}|(?:fk|eng)-2026-\d{3,4}|sup-2026-\d{4}|fk-\d{4}-[a-z]+-r\d',
                      '<id>', body)
        body = re.sub(r'\d{4}-\d{2}-\d{2}', '<date>', body)
        normalized.append(body)
    normalized_counts = Counter(normalized)
    require(len(normalized_counts) >= 500 and normalized_counts.most_common(1)[0][1] <= 20,
            'Product-quality prose is repetitive after identifiers and dates are removed')

    seen_messages = set()
    for position, item in enumerate(records):
        work = work_by_id[item['engineering_work']]
        require(item['engineering_revision'] == work['revision']
                and item['repository'] == work['repository'] and item['topic'] == work['topic'],
                f'Product-quality engineering join drift: {item["id"]}')
        require(item['product_owner'] in product_keys and item['quality_owner'] in quality_keys
                and item['engineering_owner'] == work['owner']
                and item['engineering_reviewer'] == work['reviewer']
                and item['release_owner'] in release_keys,
                f'Product-quality role drift: {item["id"]}')
        require(datetime.fromisoformat(work['opened_at']) < datetime.fromisoformat(item['opened_at'])
                <= datetime.fromisoformat(item['decided_at']) <= datetime.fromisoformat(identity['snapshot']),
                f'Product-quality chronology drift: {item["id"]}')
        expected_readers = (product_keys | quality_keys | {work['owner'], work['reviewer'],
                                                           work['release_owner']})
        if item['support_case']:
            expected_readers.add(support_by_change[item['engineering_work']]['owner'])
        record_docs = [product_docs.get(document_id) for document_id in item['documents']]
        require(all(record_docs) and len(record_docs) == (8 if item['decision'] == 'accepted' else 7),
                f'Product-quality record document set drift: {item["id"]}')
        require(all(set(document['reader_keys']) == expected_readers for document in record_docs),
                f'Product-quality document audience drift: {item["id"]}')
        require(all(item['id'] in document_text(document) or
                    document['id'].endswith('-compatibility') for document in record_docs),
                f'Product-quality document join drift: {item["id"]}')
        workbook = next(document for document in record_docs
                        if document['id'].endswith('-compatibility'))
        rows = list(csv.DictReader(io.StringIO(document_text(workbook))))
        require(len(rows) == 3 and {row['fieldkest_version'] for row in rows} ==
                {'4.8.2', '4.9.0', '4.9.1'}
                and all(row['record_id'] == item['id'] and row['engineering_work'] == work['id']
                        and row['revision'] == work['revision'] for row in rows),
                f'Compatibility workbook facts drift: {item["id"]}')
        if item['decision'] == 'accepted':
            require(work['state'] in {'completed', 'accepted'} and item['support_case'] is None
                    and item['acceptance_baseline'] == work['product_version']
                    and item['test_outcome'] in {'passed', 'passed_after_correction',
                                                'passed_with_limitation'}
                    and item['approved_commitment']
                    and sum(document['id'].endswith('-test-result') for document in record_docs) == 1
                    and any(row['fieldkest_version'] == item['acceptance_baseline']
                            and row['result'] == 'PASS' for row in rows),
                    f'Accepted product record lacks engineering or quality evidence: {item["id"]}')
        else:
            case = support_by_change[item['engineering_work']]
            require(work['state'] == 'assessment' and item['support_case'] == case['id']
                    and item['acceptance_baseline'] is None and item['test_outcome'] == 'not_run'
                    and item['approved_commitment'] is None and item['outstanding_limitation']
                    and not any(document['id'].endswith('-test-result') for document in record_docs)
                    and all(row['result'] == 'NOT_RUN' for row in rows),
                    f'Deferred or declined assessment invents product acceptance: {item["id"]}')

        related = [message for message in product_mail.values()
                   if '[' + item['id'] + ' / ' + item['engineering_work'] + ']' in message['subject']]
        require(len(related) == item['message_count'] == 16,
                f'Product-quality message allocation drift: {item["id"]}')
        roots = [message for message in related if not message.get('reply_to')]
        require(len(roots) == 1 and roots[0]['id'] == item['message_root'],
                f'Product-quality thread root drift: {item["id"]}')
        current = roots[0]
        chain = [current['id']]
        while True:
            children = [message for message in related if message.get('reply_to') == current['id']]
            require(len(children) <= 1, f'Product-quality reply fanout drift: {item["id"]}')
            if not children:
                break
            current = children[0]
            require(datetime.fromisoformat(current['date']) >
                    datetime.fromisoformat(product_mail[chain[-1]]['date']),
                    f'Product-quality reply chronology drift: {item["id"]}')
            chain.append(current['id'])
        require(len(chain) == 16 and chain[-1] == item['last_message'],
                f'Product-quality thread join drift: {item["id"]}')
        require({attachment for message in related for attachment in message.get('attachments', [])}
                == set(item['documents']), f'Product-quality attachment set drift: {item["id"]}')
        require(all(message['from'] in expected_readers and set(message['to']) <= expected_readers
                    for message in related), f'Product-quality mail audience drift: {item["id"]}')
        seen_messages.update(chain)
    require(seen_messages == set(product_mail), 'Unjoined product-quality correspondence')
    visible = [message['subject'] + '\n' + message['body'] for message in product_mail.values()]
    visible += [document_text(document) for document in product_docs.values()]
    leak = ('cinder typhoon', 'issue 116', 'scenario layer', 'author-only', 'openrae',
            'shifter-scenarios', 'challenge-specific')
    require(all(not any(term in text.lower() for term in leak) for text in visible),
            'Authoring or challenge language in product-quality content')


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
    docs = []
    for path in sorted((ROOT / 'authoring').glob('documents*.yaml')):
        docs.extend(yaml.safe_load(path.read_text())['documents'])
    events = []
    for path in sorted((ROOT / 'authoring').glob('calendars*.yaml')):
        events.extend(yaml.safe_load(path.read_text())['events'])
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
    require(len(mail) == len({m['id'] for m in mail}) == TOTAL_MESSAGE_COUNT, 'Authored message inventory drift')
    require(len(docs) == len(doc_by_id) == TOTAL_DOCUMENT_COUNT, 'Authored document inventory drift')
    check_business_network(identity, roster, mail, docs)
    check_support_intake(identity, roster, mail, docs, events)
    check_fieldkest_engineering(identity, roster, mail, docs)
    check_product_quality(identity, roster, mail, docs)
    check_release_platform(ROOT, identity, roster, mail, docs, events)
    check_customer_followup(ROOT, identity, roster, mail, docs, events)
    check_commercial(ROOT, identity, roster, mail, docs, events)
    check_finance(ROOT, identity, roster, mail, docs)
    check_office_life(ROOT, identity, roster, mail, docs, events)
    require(STORIES <= {m['story'] for m in mail}, 'An ordinary story has no correspondence')
    require({d['file'] for d in docs if 'file' in d} | {d['archive'] for d in docs if 'archive' in d} ==
            {str(p.relative_to(ROOT)) for p in (ROOT / 'documents').rglob('*') if p.is_file()},
            'Uncatalogued document')
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
        expected = {document_path(doc_by_id[d]): document_bytes(doc_by_id[d])
                    for d in m.get('attachments', [])}
        require(attachments == expected, f'Attachment mismatch: {m["id"]}')
        expected_types = {document_path(doc_by_id[d]): doc_by_id[d].get('media_type', 'text/markdown')
                          for d in m.get('attachments', [])}
        require({p.get_filename(): p.get_content_type() for p in message.iter_attachments()} == expected_types,
                f'Attachment media type mismatch: {m["id"]}')
        for part in message.iter_attachments():
            check_calendar_part(part)
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
                require(len(match) == 1 and match[0]['text'] == document_text(d),
                        'Library omitted or changed document')
                if 'archive' in d:
                    require(payload['schema_version'].endswith('/v2'), 'Binary library schema drift')
                    require(base64.b64decode(match[0]['content_base64'], validate=True) == document_bytes(d)
                            and match[0]['sha256'] == d['binary_sha256'], 'Library binary bytes drift')
                else:
                    require('content_base64' not in match[0], 'Unexpected binary payload')
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
                if '-induction-' in event['id'] or event['id'].startswith(('rel-2026-', 'chg-2026-', 'com-2026-', 'commercial-', 'office-2026-')):
                    raw_calendar = item['text'].encode()
                else:
                    raw_calendar = (ROOT / 'generated/calendars' / (event['id'] + '.ics')).read_bytes()
                require(raw_calendar == item['text'].encode(), 'Calendar bytes differ')
                require(all(len(line) <= 75 for line in raw_calendar.split(b'\r\n')), 'Calendar line folding invalid')
                text = item['text'].replace('\r\n ', '')
                for field, value in [('DTSTART', event['start']), ('DTEND', event['end']),
                                     ('DTSTAMP', event.get('updated_at', event.get('created_at', identity['snapshot'])))]:
                    stamp = datetime.fromisoformat(value).astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                    require(field + ':' + stamp + '\r\n' in text, 'Calendar time drift')
                require('STATUS:' + event['status'] + '\r\n' in text, 'Calendar status drift')
                if 'responses' in event:
                    for person, status in event['responses'].items():
                        require('ATTENDEE;PARTSTAT=' + status + ':mailto:' + contacts[person]['email'] + '\r\n' in text,
                                'Calendar attendee response drift')
                    require('SEQUENCE:' + str(event['sequence']) + '\r\n' in text,
                            'Calendar revision drift')
                    location = event['location'].replace('\\', '\\\\').replace('\n', '\\n').replace(',', '\\,').replace(';', '\\;')
                    require('LOCATION:' + location + '\r\n' in text, 'Calendar location drift')
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
    ownership = read_json(PACK / 'docs/narrative/content-ownership.json')
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
        if not c.items:
            require('Source package is the complete item inventory.' in c.description,
                    'Large SDL inventory omitted without an authoritative package declaration')
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
    print(f'PASS: {TOTAL_MESSAGE_COUNT} RFC822 messages, exact attachments and mailbox copies, '
          f'294 employees, {TOTAL_DOCUMENT_COUNT} documents, eight source collections')


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
