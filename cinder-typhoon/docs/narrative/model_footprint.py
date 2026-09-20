#!/usr/bin/env python3
"""Illustrative world-content capacity arithmetic, not an asset generator.

Rates are explicit design assumptions, not measured enterprise statistics.
Counts refer to distinct messages before retained mailbox copies are expanded.
Run from any directory; prints JSON and does not modify the environment pack.
"""
from decimal import Decimal, ROUND_HALF_UP
import json


DEPARTMENTS = {
    'keplerops': [
        ('Product engineering', 22, '5'),
        ('Support and implementation', 14, '8'),
        ('Platform and release', 7, '5'),
        ('Product management and quality', 8, '4'),
        ('Commercial', 6, '9'),
        ('Leadership and business operations', 7, '5'),
    ],
    'arwc': [
        ('Operations, treatment, and distribution', 94, '0.6'),
        ('Maintenance and engineering', 48, '2.5'),
        ('Planning, quality, and compliance', 32, '3'),
        ('Information technology', 12, '4'),
        ('Customer service and business support', 36, '6'),
        ('Leadership and finance', 8, '7'),
    ],
}


def rounded(value):
    return int(value.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def estimate(multiplier='1'):
    """Aggregate 60 effective working days; actual rosters belong to generation."""
    companies = {}
    for org, departments in DEPARTMENTS.items():
        rows = []
        for name, employees, rate in departments:
            messages = Decimal(employees) * Decimal(rate) * 60 * Decimal(multiplier)
            rows.append({'department': name, 'employees': employees,
                         'staff_sent_per_effective_workday': rate,
                         'expected_staff_sent_messages': rounded(messages)})
        human = sum(Decimal(row['expected_staff_sent_messages']) for row in rows)
        incoming = human * Decimal('0.30')
        automated = human * Decimal('0.20')
        # Human mail: 70% internal with 1.6 recipients on average, plus Sent;
        # 30% external with 0.3 internal CCs on average, plus Sent.
        # Incoming external mail: 1.3 local recipients; automation: 3 local
        # recipients. These are sensitivity assumptions, not measured fan-outs.
        copies = human * (Decimal('0.70') * Decimal('2.6') +
                          Decimal('0.30') * Decimal('1.3'))
        copies += incoming * Decimal('1.3') + automated * 3
        companies[org] = {
            'employees': sum(row['employees'] for row in rows),
            'departments': rows,
            'staff_sent_unique': rounded(human),
            'external_incoming_unique': rounded(incoming),
            'automated_unique': rounded(automated),
            'unique_messages': rounded(human + incoming + automated),
            'retained_mailbox_copies': rounded(copies),
        }
    # KeplerOps/ARWC exchanges must each be counted once in the real corpus.
    # At this planning stage assume their mutual correspondence is 2% of the
    # smaller organization's incoming mail and also present in the sender total.
    cross_org = rounded(Decimal(min(c['external_incoming_unique'] for c in companies.values())) * Decimal('0.02'))
    unique = sum(c['unique_messages'] for c in companies.values()) - cross_org
    return {
        'activity_multiplier': multiplier,
        'effective_workdays': 60,
        'companies': companies,
        'cross_company_message_overlap': cross_org,
        'combined_unique_messages': unique,
        'combined_retained_mailbox_copies': sum(c['retained_mailbox_copies'] for c in companies.values()),
        'requested_scale_reference': 29400,
        'above_scale_reference': unique >= 29400,
    }


if __name__ == '__main__':
    assert sum(d[1] for d in DEPARTMENTS['keplerops']) == 64
    assert sum(d[1] for d in DEPARTMENTS['arwc']) == 230
    result = {
        'status': 'planning_estimates_only',
        'units': 'unique messages versus separately counted retained mailbox copies',
        'assumptions': 'Rates, routing, and sensitivity multipliers are authored assumptions; no corpus was sampled or generated.',
        'cases': {name: estimate(multiplier) for name, multiplier in
                  [('lighter', '0.6'), ('working', '1'), ('busier', '1.5')]},
    }
    print(json.dumps(result, indent=2))
