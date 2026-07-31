"""Typed accessors for the canonical Polaris ACES SDL.

Private oracle and validation code consumes this module instead of parsing a
second topology or objective ledger.  The helpers are read-only and return
small projections joined to stable ACES identifiers.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from aces_sdl import parse_sdl_file


PACK_ROOT = Path(__file__).resolve().parent
SDL_RELATIVE_PATH = Path("sdl/polaris-operation-northstorm.sdl.yaml")


class AcesContractError(ValueError):
    """Raised when the canonical SDL cannot produce a required projection."""


@lru_cache(maxsize=16)
def _load_cached(path: str, modified_ns: int, size: int):
    del modified_ns, size
    return parse_sdl_file(Path(path))


def load_scenario(pack_root: str | Path = PACK_ROOT):
    """Parse and semantically validate the full canonical Polaris scenario."""

    root = Path(pack_root).resolve()
    path = root / SDL_RELATIVE_PATH
    stat = path.stat()
    return _load_cached(str(path), stat.st_mtime_ns, stat.st_size)


def _local_keys(rows: dict[str, Any]) -> set[str]:
    return {key.rsplit(".", 1)[-1] for key in rows}


def service_ids(scenario: Any) -> set[str]:
    """Return stable service names declared on canonical ACES nodes."""

    return {
        service.name
        for node in scenario.nodes.values()
        for service in node.services
    }


def reference_ids(scenario: Any, collection: str) -> set[str]:
    """Return the stable identifiers available for one supported ACES kind."""

    if collection == "services":
        return service_ids(scenario)
    rows = getattr(scenario, collection, None)
    if not isinstance(rows, dict):
        raise AcesContractError(f"unsupported ACES reference collection: {collection}")
    return _local_keys(rows)


def reference_exists(scenario: Any, collection: str, identifier: str) -> bool:
    """Check a private join without exposing or duplicating the ACES object."""

    return identifier in reference_ids(scenario, collection)


def objective_projection(
    pack_root: str | Path = PACK_ROOT,
) -> dict[str, dict[str, Any]]:
    """Project objective dependencies and evidence joins from canonical ACES."""

    scenario = load_scenario(pack_root)
    projection: dict[str, dict[str, Any]] = {}
    for objective_id, objective in scenario.objectives.items():
        assertions = list(objective.success.assertions)
        propositions: list[str] = []
        evidence_requirements: list[str] = []
        for assertion_id in assertions:
            assertion = scenario.assertions[assertion_id]
            propositions.append(assertion.proposition)
            evidence_requirements.extend(
                scenario.propositions[assertion.proposition].evidence_requirements
            )
        projection[objective_id.rsplit(".", 1)[-1]] = {
            "agent": objective.agent.rsplit(".", 1)[-1],
            "depends_on": [
                value.rsplit(".", 1)[-1] for value in objective.depends_on
            ],
            "targets": [
                value.rsplit(".", 1)[-1] for value in objective.targets
            ],
            "assertions": [
                value.rsplit(".", 1)[-1] for value in assertions
            ],
            "propositions": [
                value.rsplit(".", 1)[-1] for value in propositions
            ],
            "evidence_requirements": [
                value.rsplit(".", 1)[-1] for value in evidence_requirements
            ],
        }
    return projection


def participant_start_projection(
    pack_root: str | Path = PACK_ROOT,
) -> dict[str, Any]:
    """Return the server-authored participant start context."""

    scenario = load_scenario(pack_root)
    agent = scenario.agents["polaris-participant"]
    return {
        "agent": "polaris-participant",
        "entity": agent.entity,
        "starting_accounts": [
            value.rsplit(".", 1)[-1] for value in agent.starting_accounts
        ],
        "hosts": [
            value.rsplit(".", 1)[-1] for value in agent.initial_knowledge.hosts
        ],
        "subnets": [
            value.rsplit(".", 1)[-1] for value in agent.initial_knowledge.subnets
        ],
        "services": [
            value.rsplit(".", 1)[-1] for value in agent.initial_knowledge.services
        ],
    }


def workflow_objectives(
    pack_root: str | Path = PACK_ROOT,
) -> set[str]:
    """Return objective ids referenced by the canonical campaign workflow."""

    scenario = load_scenario(pack_root)
    workflow = scenario.workflows["operation-northstorm"]
    return {
        step.objective.rsplit(".", 1)[-1]
        for step in workflow.steps.values()
        if step.objective
    }
