# Cinder Typhoon: environment pack

Draft scenario for BSides Ottawa: approximately 300 individual players over
sixteen hours, with a provided agent and optional bring-your-own agents.
Participants operate as Cinder Typhoon, progressing from training through
KeplerOps Software to Alterra Regional Water Company. The final reservoir
operation causes fictional financial loss and water restrictions.

This directory follows the [OpenRAE/env-packs template](https://github.com/OpenRAE/env-packs/tree/679356d762971600f22e6ff3228f4c2b48376eee/src/raes_env_packs/resources/template).
It contains the preserved design material, a modular in-world SDL draft, and
authored workplace correspondence and documents.
[pack.yaml](pack.yaml) records `status: draft`; its optional content layers
remain disabled until populated. The SDL covers the logical world, participant,
challenge objectives, dependencies, scoped routes, required records, and consequences.

| Location | Purpose and current contents |
| --- | --- |
| [sdl/](sdl/README.md) | Native OpenRAE/rae SDL, with default-open realization and a Kali attacker workstation. |
| [docs/design/](docs/design/README.md) | Preserved architecture, research, reviews, 240 challenge documents, ledgers, and existing design checks. |
| [docs/narrative/](docs/narrative/README.md) | Enterprise world design: company stories, people, suppliers/customers, ambient-content direction, and name screening. |
| [docs/diagrams/](docs/diagrams/) | Existing logical network diagrams. |
| [docs/concepts.md](docs/concepts.md) | Concept-document entry point. |
| [docs/attack-path.md](docs/attack-path.md) | Route-document entry point. |
| [docs/lineage.md](docs/lineage.md) | Template source and folder mapping. |
| [assets/](assets/README.md) | Workplace emails, documents, contacts, calendars, and source artifacts bound into SDL. |
| [flags/placement.yaml](flags/placement.yaml) | Empty template placement map. |
| [challenges/challenges.yaml](challenges/challenges.yaml) | Empty template delivery catalog; authoring briefs are under `docs/design/challenges/`. |
| [ctfd/](ctfd/README.md) | Reserved for the reference challenge loader. |
| [tests/](tests/README.md) | Native SDL validation and independent design/graph agreement checks. |
| [build/](build/README.md) | Deterministic workplace asset renderer; no target provisioning. |
| [docs/walkthroughs/](docs/walkthroughs/README.md) | Reserved for reference walkthroughs. |
| [runtime-adapter/](runtime-adapter/README.md) | Reserved for the eventual adapter. |

The existing challenge cards include 50 technical drafts; the remaining 190
are briefs. All hint sections remain blank. Start at the
[design index](docs/design/README.md) for the retained work.

Existing design checks, run from the repository root:

```sh
python3 cinder-typhoon/docs/design/validate_design.py
python3 cinder-typhoon/docs/design/validate_challenges.py --self-test
python3 cinder-typhoon/docs/design/model_topology.py --self-test
```

For SDL validation, follow [tests/README.md](tests/README.md). The checker reads
the graph back from composed SDL and replays it against the existing design
contracts. The design ledgers remain independent authoring expectations.
The [workplace collection](assets/narrative/README.md) includes 8,575 messages,
822 source documents, contacts for 294 employees and 47 additional external
business correspondents, and 85 calendar invitations.
Eight native SDL content declarations bind the source artifacts to existing
workplace systems.
The runtime adapter, hosting layout, and consumer delivery bundle remain pending.
