#!/usr/bin/env python3
"""Render the allocation ledger without inventing extra scored achievements."""
from collections import defaultdict
import csv
from pathlib import Path

BASE = Path(__file__).resolve().parent
TIERS = ('easy', 'medium', 'hard', 'expert', 'elite')


def render():
    with (BASE / 'portfolio.csv').open(newline='') as handle:
        rows = list(csv.DictReader(handle))

    def counts(group):
        return [sum(int(r[t]) for r in group) for t in TIERS]

    def table_row(cells):
        return '| ' + ' | '.join(map(str, cells)) + ' |\n'

    text = '''# Cinder Typhoon operation portfolio: draft 3

The [CSV ledger](portfolio.csv) allocates **240 achievements across 70 operations**.
These are authoring contracts, not implemented flags or measured hours. Read
with the [architecture](challenge-architecture.md), [source catalog](reference-catalog.md),
[twenty new card contracts and campaign outcomes](campaign-operations.md), and
[player-experience contract](player-experience.md).

## Allocation

E = easy; M = medium; H = hard; X = expert; L = elite. Tier describes remaining
work with the provided agent after stated prerequisites. Whole-route difficulty
also includes the burden of discovery and joins and must be tested separately.

| Phase | Operations | Challenges | E | M | H | X | L |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
'''
    for phase in ('Training', 'KeplerOps', 'ARWC'):
        group = [r for r in rows if r['phase'] == phase]
        c = counts(group)
        text += table_row([phase, len(group), sum(c), *c])
    c = counts(rows)
    text += table_row(['**Total**', f'**{len(rows)}**', f'**{sum(c)}**', *c])
    text += '''
The [allocation audit](allocation-audit.md) removes twenty weakly separated
milestones and replaces them with six operations. Both organizations retain
all tiers. Training remains four optional jeopardy boxes. Seven elite
milestones occur in six operations; those counts do not predict specialist
solve time. Accessible work continues after each major pivot.

### Principal activity

Each operation has one principal category. Secondary work is described in its
brief; the table therefore underdescribes mixed operations. These are slot
shares, not shares of hours, attainable points, or audience participation.

| Principal work | Challenges | E | M | H | X | L |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
'''
    categories = defaultdict(list)
    for row in rows:
        categories[row['primary_work']].append(row)
    for category, group in categories.items():
        c = counts(group)
        text += table_row([category, sum(c), *c])
    text += '''
The new supply, cloud, and process depth comes from K29/K30/K31/W33/W34.
Their eleven hard-or-higher allocations add operational composition without
reclassifying existing binary puzzles. AI-target work remains fifteen
easy/medium slots, with no generative target on a compulsory route.

## Operation briefs

An operation in an access condition means its stated output, not completion of
every flag. Capability names refer to the [main campaign ledger](capability-routes.json).
The [entry ledger](entry-routes.json) records ordinary ARWC entry at challenge
level. All 240 allocations now have [individual challenge briefs](challenges/README.md):
[16 training](challenges/training.md), [104 KeplerOps](challenges/keplerops.md),
and [120 ARWC](challenges/arwc.md). Their technical design and three hint sections
remain blank; the briefs specify objectives and outcomes without solutions.

The work column groups distinct insights and effects. A receipt, login,
confirmation, or repeated use of a capability adds no score by itself.
Published sources support mechanisms; new constraints need fresh calibration.
No host, subnet, deployment unit, or infrastructure size is assigned here.
'''
    phase = chapter = None
    for row in rows:
        if row['phase'] != phase:
            phase, chapter = row['phase'], None
            text += f'\n### {phase}\n'
        if row['chapter'] != chapter:
            chapter = row['chapter']
            text += f'\n#### {chapter}\n\n'
            text += '| Operation | Slots | Available from | Principal work and story effect | Source |\n'
            text += '| --- | --- | --- | --- | --- |\n'
        allocation = ', '.join(f'{row[t]}{a}' for t, a in zip(TIERS, 'EMHXL') if int(row[t]))
        refs = []
        for ref in row['references'].split():
            target = 'threat-inspiration.md#atlas' if ref == 'ATLAS' else f'reference-catalog.md#{ref.lower()}'
            refs.append(f'[{ref}]({target})')
        text += table_row([f"{row['id']}: {row['operation']}", allocation,
                           row['available_from'], row['work_and_effect'],
                           ', '.join(refs) or 'Original accessible task'])
    text += '''
## Acceptance boundaries

Use operation-level point budgets. Partial proof should preserve worthwhile
progress without multiplying rewards for one exploit. Alternative methods that
achieve the same effect do not create additional flags. Story conclusions and
room-wide recognition are unscored.

Source reuse is intentional. Preserve the mechanism and explain its product
purpose; do not preserve an old tier through obscure clues, retries, or waiting.
Every challenge still needs a complete proof contract, hint ladder, explicit
prerequisites, reset behavior, and independent solve. Validate later easy work
through an appropriate easier access route, rather than counting an obvious
file hidden behind an elite-only prerequisite as novice content.

The [calibration plan](calibration.md) checks the full assisted experience,
including source-aware transfer, optional campaign composition, and day-two
continuation. The 240 allocation remains a capacity hypothesis until accepted
cards and fresh-player trajectories support it.
'''
    return text


if __name__ == '__main__':
    (BASE / 'operation-portfolio.md').write_text(render())
    print('Rendered draft-3 portfolio from portfolio.csv')
