# Cinder Typhoon

Draft 3 of the BSides Ottawa challenge architecture: approximately 300 individual
players, sixteen hours over two days, a provided agent, and optional BYO agents.
The campaign moves through Cinder Typhoon training, KeplerOps Software, and
Alterra Regional Water Company. The challenge briefs now have a first logical
network architecture with explicit authority boundaries and operational flows;
this is not yet an executable scenario pack.

- [Architecture](challenge-architecture.md): product and story, medium
  entry routes, explicit process-evidence joins, progression, and review responses.
- [Enterprise world design](../narrative/README.md): the company histories,
  cultures, people, business relationships, and ambient-content direction,
  separate from required challenge evidence. Records the narrative naming
  revisions to align before later asset authoring.
- [Logical network architecture](logical-architecture.md): the in-world
  networks, 36 logical systems, and connection points between phases, with
  separate training, KeplerOps, ARWC corporate, and ARWC OT diagrams.
- [Authority and flow register](logical-authorities.md): earned execution
  positions, delegated identities, shared-system boundaries, and the operational
  connections used to check pivots and prevent unintended shortcuts.
- [Operation portfolio](operation-portfolio.md): 240 challenge allocations
  across 70 operation briefs, with both organizations spanning every tier.
- [Campaign operations](campaign-operations.md): twenty new card contracts
  in six operations, plus concrete outcomes for the existing difficult work.
- [Individual challenge briefs](challenges/README.md): all 240 documents,
  covering [training](challenges/training.md),
  [KeplerOps](challenges/keplerops.md), and [ARWC](challenges/arwc.md).
  Each includes its description, story purpose, prerequisites, outcome, and
  difficulty/source references. Fifty cards have technical drafts; 190 await
  technical design. All three hint sections remain blank.
- [Challenge template](challenges/TEMPLATE.md): the common brief structure,
  without solutions or implementation detail.
- [Challenge quality review](challenge-quality-review.md): the review of
  all 240 briefs, corrected access and outcome contracts, and the revised
  W22.4/W24.4 problems that resolve the two Expert-allocation findings.
- [Full dependency report](challenge-dependency-report.md): complete
  prerequisite sets, route alternatives, cumulative tier bounds, and available
  work at the major transitions.
- [Player experience](player-experience.md): choices at each access stage,
  a worked co-hacking episode, day-two continuation, and shared event identity.
- [Allocation audit](allocation-audit.md): twenty merged or removed slots
  and their replacements, preserving the sixteen-hour content ambition.
- [Challenge reference catalog](reference-catalog.md): 32 named precedents,
  original ratings, retained mechanisms, adaptation choices, and evidence limits.
- [Threat inspiration](threat-inspiration.md): MITRE's Adversary Emulation
  Library, ATT&CK Enterprise/ICS, and a small, inexpensive-to-prototype AI section.
- [Calibration](calibration.md): fresh assisted solves, medium-gate checks,
  experience testing, depth, reliability, event capacity, and cost validation.
- [Research](research.md): Polaris reconciliation and professional design
  and agent-performance evidence.
- [Draft 2 adversarial review](adversarial-review-v2.md): critique of the
  preserved second draft. The current architecture records the response.
- [First adversarial review](adversarial-review.md): critique of the
  preserved first draft. The current architecture includes a response ledger.

[Portfolio CSV](portfolio.csv), [entry routes](entry-routes.json),
[main capability routes](capability-routes.json), and the
[complete challenge dependency ledger](challenge-dependencies.json)
make the allocation and evidence constraints reviewable. Run
`python3 cinder-typhoon/docs/design/validate_design.py` to check their consistency.
This includes all 240 briefs and their index rows. Run
`python3 cinder-typhoon/docs/design/validate_challenges.py --self-test` to additionally
exercise deliberately broken graphs. These checks validate the declared
contracts; distinctness and difficulty also require editorial judgment.
Run `python3 cinder-typhoon/docs/design/model_topology.py --self-test` to check
logical access, earned execution contexts, authority boundaries, operational
routes, and deliberately broken topologies.
The [SDL contracts](sdl_contracts.py) separately record proof and seed ownership
where it differs from player access, and the six bounded consequence effects.
[Native SDL validation](../../tests/README.md) checks those expectations and
the authored technical sections against the composed and compiled scenario.
The portfolio can be regenerated with
`python3 cinder-typhoon/docs/design/render_portfolio.py`.
