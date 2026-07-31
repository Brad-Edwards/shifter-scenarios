"""Render the SDL-bound deployment policy from seven realization values."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from policy import DeploymentPolicy, parse_policy


TEMPLATE_PATH = Path(__file__).with_name("policy-template.json")
PLACEHOLDER = re.compile(r"__[A-Z][A-Z0-9_]*__")
SUBSTITUTION_KEYS = frozenset(
    {
        "__RANGE_INSTANCE__",
        "__PARTICIPANT__",
        "__PROJECT_ID__",
        "__REGION__",
        "__SERVICE_ACCOUNT__",
        "__EXPORT_BUCKET__",
        "__PLATFORM_DEPLOYMENT_IMAGE__",
    }
)


def _confined_output(value: Path, root: Path) -> Path:
    resolved_root = root.resolve()
    resolved = value.resolve()
    if resolved == resolved_root or not resolved.is_relative_to(resolved_root):
        raise ValueError(
            "policy output must be a file inside the configured output root"
        )
    if not resolved.name or resolved.name in {".", ".."}:
        raise ValueError("policy output must name a file")
    return resolved


def _replace(value: Any, substitutions: dict[str, str], seen: set[str]) -> Any:
    if isinstance(value, dict):
        return {key: _replace(item, substitutions, seen) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace(item, substitutions, seen) for item in value]
    if not isinstance(value, str):
        return value
    tokens = set(PLACEHOLDER.findall(value))
    unknown = tokens - SUBSTITUTION_KEYS
    if unknown:
        raise ValueError(
            f"policy template contains unsupported placeholders: {sorted(unknown)}"
        )
    seen.update(tokens)
    result = value
    for token in tokens:
        result = result.replace(token, substitutions[token])
    if PLACEHOLDER.search(result):
        raise ValueError(
            "rendered deployment policy contains an unresolved placeholder"
        )
    return result


def _require_platform_image(image: str) -> None:
    name, separator, digest = image.rpartition("@")
    if not separator or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError(
            "platform-deployment image must be an immutable sha256 reference"
        )
    last = name.rsplit("/", 1)[-1]
    repository_name = last.rsplit(":", 1)[0]
    if repository_name != "keplerops-platform-deployment":
        raise ValueError("image must be the exact platform-deployment repository")


def render_document(
    template: Any, substitutions: dict[str, str]
) -> tuple[dict[str, Any], DeploymentPolicy]:
    if set(substitutions) != SUBSTITUTION_KEYS:
        raise ValueError(
            "renderer requires exactly the seven realization substitutions"
        )
    if any(not isinstance(value, str) or not value for value in substitutions.values()):
        raise ValueError("realization substitutions must be non-empty strings")
    _require_platform_image(substitutions["__PLATFORM_DEPLOYMENT_IMAGE__"])
    seen: set[str] = set()
    rendered = _replace(template, substitutions, seen)
    if seen != SUBSTITUTION_KEYS:
        raise ValueError("policy template must consume every realization substitution")
    policy = parse_policy(rendered)
    return rendered, policy


def write_policy(destination: Path, document: dict[str, Any]) -> None:
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".deployment-policy-", dir=destination.parent
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(document, output, sort_keys=True, separators=(",", ":"))
            output.write("\n")
        os.replace(temporary, destination)
        destination.chmod(0o600)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--range-instance", required=True)
    parser.add_argument("--participant", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--service-account", required=True)
    parser.add_argument("--export-bucket", required=True)
    parser.add_argument("--platform-deployment-image", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output_root = Path(
        os.environ.get(
            "PLATFORM_DEPLOYMENT_POLICY_OUTPUT_ROOT",
            "/var/lib/keplerops/data/platform-deployment",
        )
    )
    output = _confined_output(args.output, output_root)
    template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    substitutions = {
        "__RANGE_INSTANCE__": args.range_instance,
        "__PARTICIPANT__": args.participant,
        "__PROJECT_ID__": args.project_id,
        "__REGION__": args.region,
        "__SERVICE_ACCOUNT__": args.service_account,
        "__EXPORT_BUCKET__": args.export_bucket,
        "__PLATFORM_DEPLOYMENT_IMAGE__": args.platform_deployment_image,
    }
    document, _policy = render_document(template, substitutions)
    write_policy(output, document)


if __name__ == "__main__":
    main()
