"""Operator-only commands for deterministic participant-run telemetry export."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import time
from pathlib import Path

import yaml

try:
    from aces_contract import content_contract_bytes, research_telemetry_contract
except ModuleNotFoundError:  # Source-tree test execution; images copy the helper beside this file.
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from aces_contract import content_contract_bytes, research_telemetry_contract

from domain import ResearchContract, ResearchRuntimeConfig
from research import ResearchStore
from research_readback import verify_export_bundle


ENVIRONMENT_INPUTS = {
    "model": (Path("/opt/keplerops/environment/model.yaml"),),
    "adapter": (Path("/opt/keplerops/environment/deployment-manifest.yaml"),),
    "dataset": (
        Path("/opt/keplerops/environment/context.jsonl"),
        Path("/opt/keplerops/environment/distillation.jsonl"),
        Path("/opt/keplerops/environment/evaluation.jsonl"),
    ),
    "scenario": (Path("/opt/keplerops/sdl/keplerops-ai.sdl.yaml"),),
    "instrumentation": (
        Path("/opt/keplerops/instrumentation.py"),
        Path("/etc/keplerops/otel.yaml"),
    ),
}
SHA256_PREFIX = "sha256:"
RUNTIME_CONFIG_PATH = Path("/etc/keplerops/runtime.yaml")
SESSION_ID = re.compile(r"^ses-[0-9a-f]{24}$")


def digest_files(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item)):
        body = path.read_bytes()
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(body).digest())
    return SHA256_PREFIX + digest.hexdigest()


def environment_manifest(config: dict, store: ResearchStore) -> dict:
    image_lock_path = Path(config["environment_image_lock_path"])
    image_lock = json.loads(image_lock_path.read_text(encoding="utf-8"))
    images = {
        key: value["digest"]
        for key, value in sorted(image_lock["images"].items())
    }
    auxiliary = {
        key: value["digest"]
        for key, value in sorted(image_lock["auxiliary_images"].items())
    }
    return {
        "schema_version": 1,
        "range_profile": "gcp_full",
        "reset_generation": int(config["reset_generation"]),
        "instrumentation_schema": store.contract.schema_version,
        "digests": {
            **{name: digest_files(paths) for name, paths in ENVIRONMENT_INPUTS.items()},
            "runtime_image_lock": SHA256_PREFIX + hashlib.sha256(
                json.dumps(image_lock, separators=(",", ":"), sort_keys=True).encode("utf-8")
            ).hexdigest(),
        },
        "image_digests": images,
        "auxiliary_image_digests": auxiliary,
    }


def owner_file(path: Path, *, exact_size: int | None = None) -> bytes:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode) or metadata.st_mode & 0o077:
        raise ValueError("operator file must be owner-only and regular")
    raw = path.read_bytes()
    body = raw if exact_size is not None else raw.strip()
    if not body or len(body) > 4096 or (exact_size is not None and len(body) != exact_size):
        raise ValueError("operator file has invalid size")
    return body


def load_runtime_config(config_path: Path) -> dict:
    try:
        resolved = config_path.resolve(strict=True)
    except OSError as exc:
        raise ValueError("invalid runtime config path") from exc
    if resolved != RUNTIME_CONFIG_PATH or config_path.is_symlink():
        raise ValueError("invalid runtime config path")
    config = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("invalid runtime config")
    return config


def load_store(config_path: Path) -> tuple[ResearchStore, dict]:
    config = load_runtime_config(config_path)
    runtime = ResearchRuntimeConfig.from_values(
        endpoint=config.get("otel_endpoint"),
        queue_capacity=config.get("telemetry_queue_capacity"),
        capture_signals=config.get("research_capture_signals"),
    )
    sdl_path = Path(config["challenge_contract_path"])
    contract = ResearchContract.from_mapping(
        research_telemetry_contract(sdl_path.resolve().parents[1])
    )
    store = ResearchStore(
        Path(config["research_database_path"]),
        contract=contract,
        pseudonym_key=owner_file(Path(config["research_pseudonym_key_file"])),
        content_key=owner_file(Path(config["research_content_key_file"]), exact_size=32),
    )
    for signal, enabled in runtime.capture_signals.items():
        store.set_capture_signal(signal, enabled=enabled)
    return store, config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("list", "export", "export-content", "lifecycle", "readback"),
    )
    parser.add_argument("--session-id")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--decrypt-content", action="store_true")
    parser.add_argument("--include-content", action="store_true")
    parser.add_argument("--timeline", action="store_true")
    parser.add_argument("--event", choices=(
        "session.started", "session.reset_started", "session.closed",
        "session.reset_completed", "reset.requested", "reset.completed",
        "telemetry.loss_observed",
    ))
    parser.add_argument("--dropped-event-count", type=int, default=0)
    parser.add_argument("--range-instance")
    parser.add_argument("--participant")
    parser.add_argument("--reset-generation", type=int)
    parser.add_argument("--config", type=Path, default=RUNTIME_CONFIG_PATH)
    return parser


def _record_lifecycle(args: argparse.Namespace, store: ResearchStore, config: dict) -> None:
    if (
        args.event is None
        or args.range_instance is None
        or args.participant is None
        or args.reset_generation is None
        or args.reset_generation < 0
    ):
        raise ValueError("lifecycle requires event and binding")
    from domain import ResearchObservation, derive_research_context

    context = derive_research_context(
        key=owner_file(Path(config["research_pseudonym_key_file"])),
        range_instance=args.range_instance,
        participant=args.participant,
        reset_generation=args.reset_generation,
    )
    source_id = "range-ops-controller"
    sequence = store.source_health(context.session_id, source_id)["last_sequence"] + 1
    occurred_at = time.time_ns()
    trace_id = hashlib.sha256(
        f"{context.session_id}:{source_id}:{sequence}:{args.event}".encode("utf-8")
    ).hexdigest()[:32]
    values = {
        "event_name": args.event,
        "occurred_at": occurred_at,
        "source_sequence": sequence,
        "status": "recorded",
        "trace_id": trace_id,
    }
    if args.event == "telemetry.loss_observed":
        if args.dropped_event_count < 1:
            raise ValueError("loss marker requires a positive count")
        values["dropped_event_count"] = args.dropped_event_count
        values["capture_status"] = "loss_observed"
    elif args.dropped_event_count != 0:
        raise ValueError("lifecycle event cannot report loss")
    observation = ResearchObservation.from_mapping(
        values, contract=store.contract, source_id=source_id,
    )
    event = store.record_observation(
        observation,
        source_id=source_id,
        range_instance=args.range_instance,
        participant=args.participant,
        reset_generation=args.reset_generation,
        observed_at=occurred_at,
    )
    print(json.dumps({"event_id": event["event_id"]}, separators=(",", ":"), sort_keys=True))


def _export(args: argparse.Namespace, store: ResearchStore, config: dict) -> None:
    if not isinstance(args.session_id, str) or not SESSION_ID.fullmatch(args.session_id) or args.destination is None:
        raise ValueError("export requires a canonical session and destination")
    destination = args.destination.resolve()
    export_root = Path(
        "/var/lib/keplerops-research/content-exports"
        if args.command == "export-content"
        else "/var/lib/keplerops-research/exports"
    ).resolve()
    if export_root not in destination.parents:
        raise ValueError("export destination escapes operator root")
    if args.command == "export-content":
        digest = store.export_encrypted_content(args.session_id, destination)
        print(json.dumps(
            {"content_digest": digest, "session_id": args.session_id},
            separators=(",", ":"), sort_keys=True,
        ))
        return
    digest = store.export_session(
        args.session_id,
        destination,
        contract_document=content_contract_bytes(
            "research-telemetry-contract",
            Path(config["challenge_contract_path"]).resolve().parents[1],
        ),
        dictionary_path=Path("/opt/keplerops/telemetry/data-dictionary.md"),
        metadata=environment_manifest(config, store),
    )
    print(json.dumps({"digest": digest, "session_id": args.session_id}, separators=(",", ":"), sort_keys=True))


def _readback(args: argparse.Namespace) -> None:
    if args.bundle is None:
        raise ValueError("readback requires a bundle path")
    if args.include_content and not args.decrypt_content:
        raise ValueError("including content requires decryption")
    bundle = args.bundle.resolve(strict=True)
    roots = (
        Path("/var/lib/keplerops-research/exports").resolve(),
        Path("/var/lib/keplerops-research/content-exports").resolve(),
    )
    if not any(root == bundle or root in bundle.parents for root in roots):
        raise ValueError("readback bundle escapes operator export roots")
    config = load_runtime_config(args.config)
    contract = research_telemetry_contract(
        Path(config["challenge_contract_path"]).resolve().parents[1]
    )
    result = verify_export_bundle(
        bundle,
        contract=contract,
        include_timeline=args.timeline,
        content_key=owner_file(Path(config["research_content_key_file"]), exact_size=32)
        if args.decrypt_content else None,
        include_content=args.include_content,
    )
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))


def main() -> None:
    args = _parser().parse_args()
    if args.command == "readback":
        _readback(args)
        return
    store, config = load_store(args.config)
    if args.command == "list":
        print(json.dumps({"sessions": store.session_ids()}, separators=(",", ":"), sort_keys=True))
    elif args.command == "lifecycle":
        _record_lifecycle(args, store, config)
    else:
        _export(args, store, config)


if __name__ == "__main__":
    main()
