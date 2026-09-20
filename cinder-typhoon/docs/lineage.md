# Pack structure and lineage

The folder structure and metadata scaffold follow the
[OpenRAE/env-packs template](https://github.com/OpenRAE/env-packs/tree/679356d762971600f22e6ff3228f4c2b48376eee/src/raes_env_packs/resources/template)
at commit `679356d762971600f22e6ff3228f4c2b48376eee` (package version 6.1.0).
The template notice is retained in [template-license.txt](template-license.txt).

The initial SDL name-only starter followed that revision's minimal-scaffold
behavior. It has now been expanded into an original modular SDL draft using
the pinned `raes==5.0.0` grammar and semantics. See the
[SDL guide](../sdl/README.md) and [validation record](sdl-validation.md).

Existing authoring material was relocated as follows, retaining its content
and updating relative links and command paths:

| Previous location | Pack location |
| --- | --- |
| `cinder-typhoon/README.md` design index | `docs/design/README.md` |
| `cinder-typhoon/design/` | `docs/design/` |
| `cinder-typhoon/design/logical-network/` | `docs/diagrams/` |

Challenge briefs remain operator authoring documents under
`docs/design/challenges/`. The template's `challenges/challenges.yaml` is
reserved for the later delivery catalog. Existing design scripts remain beside
their inputs; they have not been converted into runtime contracts.

The only structural addition beyond the template is `runtime-adapter/`, reserved
using the folder convention of this repository's Polaris adapter. No adapter
implementation has been copied.

The preserved [reference catalog](design/reference-catalog.md) and
[research](design/research.md) contain the campaign's existing design citations.
The [provenance ledger](provenance-ledger.yaml) records the scaffold sources;
publication review remains pending.
