# Cinder Typhoon

Draft 3 of the BSides Ottawa challenge architecture: approximately 300 individual
players, sixteen hours over two days, a provided agent, and optional BYO agents.
The campaign moves through Cinder Typhoon training, KeplerOps Software, and
Alterra Regional Water Company. The challenge briefs now have a first logical
network architecture; this is not yet an executable scenario pack.

- [Architecture](design/challenge-architecture.md): product and story, medium
  entry routes, explicit process-evidence joins, progression, and review responses.
- [Logical network architecture](design/logical-architecture.md): the in-world
  networks, 36 logical systems, and connection points between phases, with
  separate training, KeplerOps, ARWC corporate, and ARWC OT diagrams.
- [Operation portfolio](design/operation-portfolio.md): 240 challenge allocations
  across 70 operation briefs, with both organizations spanning every tier.
- [Campaign operations](design/campaign-operations.md): twenty new card contracts
  in six operations, plus concrete outcomes for the existing difficult work.
- [Individual challenge briefs](design/challenges/README.md): all 240 documents,
  covering [training](design/challenges/training.md),
  [KeplerOps](design/challenges/keplerops.md), and [ARWC](design/challenges/arwc.md).
  Each includes its description, story purpose, prerequisites, outcome, and
  difficulty/source references. Technical design and three hints remain blank.
- [Challenge template](design/challenges/TEMPLATE.md): the common brief structure,
  without solutions or implementation detail.
- [Challenge quality review](design/challenge-quality-review.md): the review of
  all 240 briefs, corrected access and outcome contracts, and the revised
  W22.4/W24.4 problems that resolve the two Expert-allocation findings.
- [Full dependency report](design/challenge-dependency-report.md): complete
  prerequisite sets, route alternatives, cumulative tier bounds, and available
  work at the major transitions.
- [Player experience](design/player-experience.md): choices at each access stage,
  a worked co-hacking episode, day-two continuation, and shared event identity.
- [Allocation audit](design/allocation-audit.md): twenty merged or removed slots
  and their replacements, preserving the sixteen-hour content ambition.
- [Challenge reference catalog](design/reference-catalog.md): 32 named precedents,
  original ratings, retained mechanisms, adaptation choices, and evidence limits.
- [Threat inspiration](design/threat-inspiration.md): MITRE's Adversary Emulation
  Library, ATT&CK Enterprise/ICS, and a small, inexpensive-to-prototype AI section.
- [Calibration](design/calibration.md): fresh assisted solves, medium-gate checks,
  experience testing, depth, reliability, event capacity, and cost validation.
- [Research](design/research.md): Polaris reconciliation and professional design
  and agent-performance evidence.
- [Draft 2 adversarial review](design/adversarial-review-v2.md): critique of the
  preserved second draft. The current architecture records the response.
- [First adversarial review](design/adversarial-review.md): critique of the
  preserved first draft. The current architecture includes a response ledger.

[Portfolio CSV](design/portfolio.csv), [entry routes](design/entry-routes.json),
[main capability routes](design/capability-routes.json), and the
[complete challenge dependency ledger](design/challenge-dependencies.json)
make the allocation and evidence constraints reviewable. Run
`python3 cinder-typhoon/design/validate_design.py` to check their consistency.
This includes all 240 briefs and their index rows. Run
`python3 cinder-typhoon/design/validate_challenges.py --self-test` to additionally
exercise deliberately broken graphs. These checks validate the declared
contracts; distinctness and difficulty also require editorial judgment.
The portfolio can be regenerated with
`python3 cinder-typhoon/design/render_portfolio.py`.
