# Individual challenge briefs

All **240 challenge briefs across 70 operations** are written. Each scored
challenge has one document, grouped under its parent operation.

| Phase | Operations | Challenge documents | Easy | Medium | Hard | Expert | Elite |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| [Training](training.md) | 4 | 16 | 12 | 4 | 0 | 0 | 0 |
| [KeplerOps](keplerops.md) | 31 | 104 | 25 | 45 | 21 | 9 | 4 |
| [ARWC](arwc.md) | 35 | 120 | 23 | 45 | 31 | 18 | 3 |
| **Total** | **70** | **240** | **60** | **94** | **52** | **27** | **7** |

## Scope of these documents

Use [TEMPLATE.md](TEMPLATE.md) for the common structure: a player-facing
description, story purpose, prerequisites and starting material, completion and
downstream use, and difficulty/source references.

The briefs state the problem and intended outcome. A card starts as a
`Challenge brief`, with empty technical-design and hint sections. A reviewed
`Technical draft` adds logical application behavior, seeded-data requirements,
intended solution class, completion evidence, boundaries, and author checks.
It still contains no deployment layout, grading code, flags, or player-facing
solution walkthrough. **All three hint sections remain deliberately empty**
until the technical work is settled.

Only the challenge description is player-facing text. The remaining populated
sections support author review and may disclose dependencies or source lineage.
Players choose how much work to delegate to their agents; the briefs prescribe
no dialogue, human-only step, or mandatory explanation.

## Identifiers and dependencies

Files use their stable operation-local IDs, for example
[K29.2](K29/K29.2.md). Preserve an assigned ID when its title changes, and do not
reuse an ID retired by a merge.

Requirements name specific outputs, not completion of every challenge in an
operation. AND means all named inputs; OR means an alternative route. The
supplied training workspace and KeplerOps foothold require no earlier scores.

Named entry references such as G01 are linked to their owning challenge.
Shared capabilities such as CORPORATE and OT_READ retain the definitions in
the [main capability ledger](../capability-routes.json). Their challenge-level
producers are listed in each phase index. A capability join is not another
scored challenge.

The ordinary package route remains six required challenges; the ordinary
diagnostic route remains seven. Both stay medium or easier. K20 offers an
optional advanced publication-authority alternative without entering the
ordinary route's prerequisite chain.

## Relationship to the portfolio

The [portfolio CSV](../portfolio.csv) records operation allocations. These
individual briefs expand all of them. The [entry ledger](../entry-routes.json)
and [main capability ledger](../capability-routes.json) remain the campaign's
shared route summaries; the latter is an abstraction of operation outputs,
not an inventory of all 240 prerequisites.

Read related challenges together. A later challenge must earn its score through
a distinct result, rather than a receipt or repeated use of an already credited
capability. Credentials and their ordinary first use stay one achievement.
Update the relevant portfolio and route summaries alongside any later change
to an allocation, prerequisite, or capability.

The proposed difficulty describes work remaining after prerequisites, with the
provided agent. A medium task behind an optional elite capability does not
therefore become an accessible medium entry route. The phase indexes show
those prerequisites explicitly.

## Quality and dependency review

The [quality review](../challenge-quality-review.md) covers every brief and
records the corrections. Its W22.4 and W24.4 findings are resolved at brief
level: each now has a distinct source-backed problem, while its predecessor
earns the complete recovery payoff. Difficulty labels remain proposals for
the stated work with the provided agent.

The [complete dependency ledger](../challenge-dependencies.json) records all
240 challenge nodes, 33 capability nodes, and two supplied roots. Each inner
list is AND; the outer list is OR. It mirrors the briefs' explicit requirements.
Edit both when changing a dependency; the checker rejects disagreement.

From the repository root:

```sh
python3 cinder-typhoon/docs/design/validate_design.py
python3 cinder-typhoon/docs/design/validate_challenges.py --self-test
```

The second command also checks deliberate failures, including cycles, discovery
mistaken for authority, accidentally mandatory alternatives, harder entry gates,
and omitted live-control evidence. It accepts only blank technical sections in
`Challenge brief` cards and complete five-part technical sections in `Technical
draft` cards; hints must always remain empty. These commands do not modify
documents.

After an intentional dependency or title change, regenerate the existing index
rows and [dependency report](../challenge-dependency-report.md) with:

```sh
python3 cinder-typhoon/docs/design/validate_challenges.py --write-indexes --report cinder-typhoon/docs/design/challenge-dependency-report.md
```
