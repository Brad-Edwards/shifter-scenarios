#!/usr/bin/env python3
"""Validate the complete Cinder Typhoon SDL using native RAE semantics only.

The phase gates independently compare the composed native model with the
authored Training, KeplerOps, and ARWC contracts. No project-private
relationship decoder is present and no deployment or materialization occurs.
"""
from __future__ import annotations

import argparse
from importlib.metadata import version
from pathlib import Path
import sys

import yaml
from raes._errors import SDLParseError
from raes.explicitness import ExplicitnessClass
from raes.instantiate import instantiate_scenario
from raes.parser import parse_sdl, parse_sdl_file
from raes.realization_designation import AuthorRealizationPosture
from raes_processor.compiler import compile_runtime_model

from validate_narrative import (
    adversarial_narrative_checks,
    check_narrative_runtime,
    check_narrative_sdl,
)

PACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK / "docs/design"))

from validate_arwc import check_arwc  # noqa: E402
from validate_challenges import DesignError, load_briefs, require  # noqa: E402
from validate_keplerops import check_keplerops  # noqa: E402
from validate_training import check_training, hand_build_gaps  # noqa: E402

KALI = "participant.kali"


def enum(value):
    return getattr(value, "value", value)


def check_authored_open(entry: Path) -> int:
    """Check the complete one-level module tree and its native open posture."""
    root = yaml.safe_load(entry.read_text())
    docs = [(entry, root)]
    for imported in root["imports"]:
        require(imported["source"].startswith("local:"), "Unexpected nonlocal module resolution")
        path = (entry.parent / imported["source"][6:]).resolve()
        require(path.is_relative_to(entry.parent.resolve()), "Module escapes the SDL directory")
        docs.append((path, yaml.safe_load(path.read_text())))
    require(
        {path.resolve() for path, _ in docs} == {path.resolve() for path in entry.parent.rglob("*.yaml")},
        "Unimported module or duplicate source tree",
    )
    for path, document in docs:
        require(
            document.get("realization") == {"default": "open"},
            f"Missing native default-open declaration: {path.name}",
        )
        require(
            document.get("semantic_revision") == "raes-progressive-semantics/v1",
            f"Mixed semantic revisions: {path.name}",
        )
    return len(docs) - 1


def check_compiled_open(instantiated, runtime) -> int:
    records = instantiated.instantiation_provenance.realization_designations
    require(
        records and all(record.posture is AuthorRealizationPosture.OPEN for record in records),
        "Open designation lost during composition/instantiation",
    )
    requirements = {requirement.field_path: requirement for requirement in runtime.realization_requirements}
    for key, node in instantiated.nodes.items():
        if enum(node.type) != "compute":
            continue
        require(node.resources is None, f"Unexpected resource sizing: {key}")
        substrate = f"nodes.{key}.realization.compute-substrate"
        require(
            substrate in requirements
            and requirements[substrate].explicitness is ExplicitnessClass.OPEN,
            f"Unspecified realization is not open after compilation: {substrate}",
        )
        for suffix in ("architecture", "os_version"):
            path = f"nodes.{key}.{suffix}"
            authored = getattr(node, suffix)
            expected = ExplicitnessClass.EXACT if authored not in (None, "") else ExplicitnessClass.OPEN
            require(
                path in requirements and requirements[path].explicitness is expected,
                f"Node {suffix} explicitness drift after compilation: {path}",
            )
        os_path = f"nodes.{key}.os"
        if node.os is not None:
            require(
                requirements[os_path].explicitness is ExplicitnessClass.EXACT,
                f"Explicit node OS was weakened: {key}",
            )
        elif key != KALI:
            require(
                requirements[os_path].explicitness is ExplicitnessClass.OPEN,
                f"Unspecified OS closed: {key}",
            )
    for suffix in ("os", "os_distribution"):
        requirement = requirements[f"nodes.{KALI}.{suffix}"]
        require(
            requirement.explicitness is ExplicitnessClass.EXACT,
            f"Explicit Kali {suffix} was weakened by default open",
        )
    return len(requirements)


def check_compiled_observations(scenario, runtime) -> int:
    """Check normalized runtime selectors rather than only authored references."""
    expected = {}
    for key, evidence in scenario.evidence_requirements.items():
        selector = evidence.observation_demand.selector
        expected[scenario.propositions[key].predicate.property] = (
            selector.semantic_scope,
            {
                "provision.content." + ref.removeprefix("content.")
                if ref.startswith("content.")
                else "template.feature." + ref.removeprefix("features.")
                for ref in evidence.source_refs
            },
        )
    seen = set()
    for demand in runtime.observation_demands:
        require(
            demand.required
            and enum(demand.mode) == "selected"
            and enum(demand.collection) == "require"
            and enum(demand.retention) == "require"
            and enum(demand.basis) == "observed"
            and demand.redaction == "redact-secrets"
            and demand.integrity == "checksum",
            "Compiled observation lifecycle drift",
        )
        for selector in demand.selectors:
            require(
                len(selector.names) == 1 and selector.names[0] in expected,
                "Unexpected compiled observation name",
            )
            name = selector.names[0]
            scope, sources = expected[name]
            require(
                selector.semantic_scope == scope
                and set(selector.component_refs) == sources
                and selector.data_kind == "artifact"
                and not selector.excluded_scopes
                and not selector.window_refs,
                f"Compiled observation binding drift: {name}",
            )
            seen.add(name)
    require(seen == set(expected), "Required observations lost during compilation")
    return len(seen)


def check_native_parser_self_test() -> None:
    try:
        parse_sdl("name: invalid-posture\nrealization:\n  default: default-open\n")
    except SDLParseError as error:
        require("/realization/default" in str(error), f"Unexpected posture parser failure: {error}")
    else:
        raise DesignError("Invalid realization posture was accepted")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--pack-check", action="store_true")
    parser.add_argument(
        "--pack-max-members",
        type=int,
        default=1024,
        help="Explicit upstream pack file/directory budget; default remains 1024",
    )
    parser.add_argument(
        "--training-hand-build-gate",
        action="store_true",
        help="Run the legal native Training design gate and stop before materialization",
    )
    parser.add_argument(
        "--keplerops-hand-build-gate",
        action="store_true",
        help="Run the legal native KeplerOps design gate and stop before materialization",
    )
    parser.add_argument(
        "--arwc-hand-build-gate",
        action="store_true",
        help="Run the legal native ARWC design gate and stop before materialization",
    )
    args = parser.parse_args()

    require(version("raes") == "5.0.0", "Use pinned raes==5.0.0 for reproducible validation")
    entry = PACK / "sdl/cinder-typhoon.sdl.yaml"
    module_count = check_authored_open(entry)
    if args.pack_check:
        require(version("raes-env-packs") == "6.1.0", "Use pinned raes-env-packs==6.1.0")
        from raes_env_packs.validation import PackValidationLimits, _validate_pack_for_author_ci

        require(args.pack_max_members > 0, "Pack member budget must be positive")
        result, scenarios = _validate_pack_for_author_ci(
            PACK,
            limits=PackValidationLimits(max_members=args.pack_max_members),
        )
        require(result.ok, f"Environment-pack author validation failed: {result.errors}")
        require(len(scenarios) == 1, "Expected exactly one pack scenario entry point")
        scenario = scenarios[0]
        print(
            "PASS: env-packs 6.1.0 author validation "
            f"(local imports enabled; member budget {args.pack_max_members})",
            flush=True,
        )
    else:
        scenario = parse_sdl_file(entry)
    print(f"PASS: RAE 5.0.0 parsed and composed {module_count} modules", flush=True)

    check_narrative_sdl(scenario)
    instantiated = instantiate_scenario(scenario)
    runtime = compile_runtime_model(instantiated)
    requirement_count = check_compiled_open(instantiated, runtime)
    observation_count = check_compiled_observations(scenario, runtime)
    check_narrative_runtime(scenario, runtime)
    print(
        f"PASS: instantiated and compiled {requirement_count} realization requirements and "
        f"{observation_count} source-bound observations",
        flush=True,
    )

    explicit_gate = any(
        (args.training_hand_build_gate, args.keplerops_hand_build_gate, args.arwc_hand_build_gate)
    )
    run_training = args.training_hand_build_gate or not explicit_gate
    run_keplerops = args.keplerops_hand_build_gate or not explicit_gate
    run_arwc = args.arwc_hand_build_gate or not explicit_gate

    if run_training:
        check_training(scenario, load_briefs())
        gaps = hand_build_gaps(scenario)
        require(not gaps, "Training hand-build gate has gaps:\n- " + "\n- ".join(gaps))
        print("PASS: Training native hand-build design gate (16 cards); no materialization was performed", flush=True)
    if run_keplerops:
        cards = check_keplerops(scenario)
        print(
            f"PASS: KeplerOps native hand-build design gate ({cards} cards); no materialization was performed",
            flush=True,
        )
    if run_arwc:
        cards = check_arwc(scenario)
        print(
            f"PASS: ARWC native hand-build design gate ({cards} cards); no materialization was performed",
            flush=True,
        )

    if args.self_test:
        check_native_parser_self_test()
        mutations = adversarial_narrative_checks(scenario)
        print(
            f"PASS: {mutations} type-valid narrative SDL mutations and invalid posture spelling rejected",
            flush=True,
        )
    print(
        "Static design proof only: no repository, binary, service, image, process simulator, or range was built.",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except DesignError as error:
        raise SystemExit(f"FAIL: {error}")
