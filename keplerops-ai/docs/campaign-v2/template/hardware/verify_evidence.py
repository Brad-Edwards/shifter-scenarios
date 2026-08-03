#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

import yaml


SHA256 = re.compile(r"^[0-9a-f]{64}$")


class VerificationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def load_json(raw: bytes, name: str) -> dict:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"{name} is not valid UTF-8 JSON") from error
    require(isinstance(value, dict), f"{name} is not a JSON object")
    return value


def read_archive(contract: dict) -> dict[str, bytes]:
    required = set(contract["required_members"])
    files: dict[str, bytes] = {}
    total = 0
    try:
        with tarfile.open(fileobj=sys.stdin.buffer, mode="r|*") as archive:
            for member in archive:
                path = PurePosixPath(member.name)
                require(
                    not path.is_absolute()
                    and len(path.parts) == 1
                    and path.name in required,
                    f"unexpected archive member {member.name}",
                )
                require(member.isfile(), f"archive member {member.name} is not a file")
                require(member.name not in files, f"duplicate archive member {member.name}")
                require(
                    member.size <= contract["maximum_member_bytes"],
                    f"archive member {member.name} is too large",
                )
                total += member.size
                require(
                    total <= contract["maximum_archive_bytes"],
                    "raw evidence archive is too large",
                )
                stream = archive.extractfile(member)
                require(stream is not None, f"cannot read archive member {member.name}")
                raw = stream.read(member.size + 1)
                require(len(raw) == member.size, f"archive member {member.name} is truncated")
                files[member.name] = raw
    except (tarfile.TarError, OSError, EOFError) as error:
        raise VerificationError("raw evidence is not a valid tar archive") from error

    missing = sorted(required - files.keys())
    require(not missing, f"raw evidence is missing {', '.join(missing)}")
    return files


def parse_time(value: object, name: str) -> dt.datetime:
    require(isinstance(value, str), f"{name} is not a timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise VerificationError(f"{name} is not an ISO-8601 timestamp") from error
    require(parsed.tzinfo is not None, f"{name} has no timezone")
    return parsed.astimezone(dt.timezone.utc)


def number(value: object, name: str) -> float:
    require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{name} is not numeric",
    )
    converted = float(value)
    require(math.isfinite(converted), f"{name} is not finite")
    return converted


def ppm_token(raw: bytes, offset: int) -> tuple[bytes, int]:
    size = len(raw)
    while offset < size:
        if raw[offset] in b" \t\r\n":
            offset += 1
            continue
        if raw[offset] == ord("#"):
            newline = raw.find(b"\n", offset)
            require(newline >= 0, "unterminated PPM comment")
            offset = newline + 1
            continue
        break
    require(offset < size, "truncated PPM header")
    end = offset
    while end < size and raw[end] not in b" \t\r\n#":
        end += 1
    require(end > offset, "empty PPM header token")
    return raw[offset:end], end


def parse_ppm(raw: bytes, name: str, contract: dict) -> tuple[int, int, bytes]:
    offset = 0
    tokens: list[bytes] = []
    for _ in range(4):
        token, offset = ppm_token(raw, offset)
        tokens.append(token)
    require(tokens[0] == b"P6", f"{name} is not raw binary PPM")
    try:
        width, height, maximum = map(int, tokens[1:])
    except ValueError as error:
        raise VerificationError(f"{name} has an invalid PPM header") from error
    require(maximum == 255, f"{name} does not use 8-bit channels")
    require(
        contract["minimum_frame_width"] <= width <= contract["maximum_frame_width"],
        f"{name} width is outside the verifier contract",
    )
    require(
        contract["minimum_frame_height"] <= height <= contract["maximum_frame_height"],
        f"{name} height is outside the verifier contract",
    )
    require(offset < len(raw) and raw[offset] in b" \t\r\n", f"{name} has no pixel separator")
    if raw[offset:offset + 2] == b"\r\n":
        offset += 2
    else:
        offset += 1
    pixels = raw[offset:]
    require(len(pixels) == width * height * 3, f"{name} pixel data length is invalid")
    return width, height, pixels


def require_liveness_marker(raw: bytes, expected: str, name: str) -> None:
    executable = shutil.which("zbarimg")
    require(executable is not None, "zbarimg is unavailable; liveness cannot be verified")
    try:
        result = subprocess.run(
            [executable, "--quiet", "--raw", "-"],
            input=raw,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
        )
    except subprocess.TimeoutExpired as error:
        raise VerificationError(f"liveness decoding timed out for {name}") from error
    require(result.returncode == 0, f"no machine-readable liveness marker in {name}")
    try:
        values = result.stdout.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise VerificationError(f"liveness marker in {name} is not UTF-8") from error
    require(expected in values, f"current nonce/lease marker is absent from {name}")


def frame_delta(before: bytes, after: bytes, name: str, contract: dict) -> dict:
    before_width, before_height, before_pixels = parse_ppm(before, f"{name} before", contract)
    after_width, after_height, after_pixels = parse_ppm(after, f"{name} after", contract)
    require(
        (before_width, before_height) == (after_width, after_height),
        f"{name} frame dimensions changed",
    )
    total_delta = 0
    changed = 0
    threshold = contract["pixel_change_threshold"]
    for before_channel, after_channel in zip(before_pixels, after_pixels):
        delta = abs(before_channel - after_channel)
        total_delta += delta
        if delta >= threshold:
            changed += 1
    mean_delta = total_delta / len(before_pixels)
    changed_ratio = changed / len(before_pixels)
    require(
        mean_delta >= contract["minimum_mean_channel_delta"],
        f"{name} mean image delta is too small",
    )
    require(
        changed_ratio >= contract["minimum_changed_channel_ratio"],
        f"{name} changed-pixel ratio is too small",
    )
    return {
        "width": before_width,
        "height": before_height,
        "mean_channel_delta": round(mean_delta, 4),
        "changed_channel_ratio": round(changed_ratio, 6),
    }


def validate_artifacts(files: dict[str, bytes], manifest: dict) -> dict[str, str]:
    expected_names = set(files) - {"manifest.json"}
    artifacts = manifest.get("artifacts")
    require(isinstance(artifacts, dict), "manifest artifacts are absent")
    require(set(artifacts) == expected_names, "manifest artifact set does not match archive")
    computed: dict[str, str] = {}
    for name in sorted(expected_names):
        declared = artifacts[name]
        require(isinstance(declared, dict), f"manifest entry for {name} is invalid")
        digest = hashlib.sha256(files[name]).hexdigest()
        computed[name] = digest
        require(declared.get("sha256") == digest, f"manifest hash for {name} does not match")
        require(declared.get("bytes") == len(files[name]), f"manifest size for {name} does not match")
    return computed


def validate_telemetry(
    telemetry: dict,
    contract: dict,
    bench_id: str,
    nonce: str,
    lease_sha256: str,
    started: dt.datetime,
    completed: dt.datetime,
) -> dict:
    require(telemetry.get("schema") == contract["telemetry_schema"], "wrong telemetry schema")
    require(telemetry.get("bench_id") == bench_id, "telemetry bench identity mismatch")
    require(telemetry.get("nonce") == nonce, "telemetry nonce mismatch")
    require(telemetry.get("lease_sha256") == lease_sha256, "telemetry lease mismatch")
    unit = telemetry.get("actuator_unit")
    require(unit in contract["actuator_minimum_delta"], "unsupported actuator unit")
    samples = telemetry.get("samples")
    require(isinstance(samples, list), "telemetry samples are absent")
    by_phase: dict[str, dict] = {}
    for sample in samples:
        require(isinstance(sample, dict), "telemetry sample is not an object")
        phase = sample.get("phase")
        require(phase in {"before", "after", "reset"}, "unknown telemetry phase")
        require(phase not in by_phase, f"duplicate {phase} telemetry sample")
        by_phase[phase] = sample
    require(set(by_phase) == {"before", "after", "reset"}, "before/after/reset telemetry is required")

    sequences: list[int] = []
    times: list[dt.datetime] = []
    positions: dict[str, dict[str, float]] = {}
    for phase in ("before", "after", "reset"):
        sample = by_phase[phase]
        sequence = sample.get("sequence")
        require(isinstance(sequence, int) and not isinstance(sequence, bool), f"{phase} sequence is invalid")
        sequences.append(sequence)
        captured = parse_time(sample.get("captured_at"), f"{phase} captured_at")
        times.append(captured)
        require(started <= captured <= completed, f"{phase} telemetry is outside capture interval")
        require(sample.get("limits_ok") is True, f"{phase} actuator limits are unhealthy")
        require(sample.get("emergency_stop") is False, f"{phase} emergency stop is asserted")
        require(sample.get("watchdog_armed") is True, f"{phase} watchdog is not armed")
        raw_position = sample.get("actuator_position")
        require(isinstance(raw_position, dict) and raw_position, f"{phase} actuator position is absent")
        positions[phase] = {
            str(axis): number(value, f"{phase} actuator position {axis}")
            for axis, value in raw_position.items()
        }
        for field, limits in contract["telemetry_limits"].items():
            measured = number(sample.get(field), f"{phase} {field}")
            require(
                limits["minimum"] <= measured <= limits["maximum"],
                f"{phase} {field} is outside the verifier contract",
            )
        number(sample.get("lux"), f"{phase} lux")
        command = number(sample.get("light_command"), f"{phase} light command")
        require(0.0 <= command <= 1.0, f"{phase} light command is outside 0..1")

    require(sequences[0] < sequences[1] < sequences[2], "telemetry sequence is not monotonic")
    require(times[0] < times[1] < times[2], "telemetry timestamps are not monotonic")
    require(by_phase["before"].get("home_sensor") is True, "bench did not start at home")
    require(by_phase["reset"].get("home_sensor") is True, "bench did not return home")

    axes = set(positions["before"])
    require(axes == set(positions["after"]) == set(positions["reset"]), "actuator axes changed")
    movement = max(abs(positions["after"][axis] - positions["before"][axis]) for axis in axes)
    require(
        movement >= contract["actuator_minimum_delta"][unit],
        "actuator movement is below the verifier threshold",
    )
    reset_error = max(abs(positions["reset"][axis] - positions["before"][axis]) for axis in axes)
    require(
        reset_error <= contract["actuator_reset_tolerance"][unit],
        "actuator did not return to its initial position",
    )

    before_command = number(by_phase["before"]["light_command"], "before light command")
    after_command = number(by_phase["after"]["light_command"], "after light command")
    reset_command = number(by_phase["reset"]["light_command"], "reset light command")
    require(
        abs(after_command - before_command) >= contract["minimum_light_command_delta"],
        "light command did not meaningfully change",
    )
    require(
        abs(reset_command - before_command) <= contract["light_reset_command_tolerance"],
        "light command did not reset",
    )
    before_lux = number(by_phase["before"]["lux"], "before lux")
    after_lux = number(by_phase["after"]["lux"], "after lux")
    reset_lux = number(by_phase["reset"]["lux"], "reset lux")
    minimum_lux_delta = max(
        contract["minimum_lux_delta"],
        abs(before_lux) * contract["minimum_lux_delta_ratio"],
    )
    require(abs(after_lux - before_lux) >= minimum_lux_delta, "measured lux did not meaningfully change")
    reset_lux_tolerance = max(
        contract["light_reset_lux_tolerance"],
        abs(before_lux) * contract["light_reset_lux_tolerance_ratio"],
    )
    require(abs(reset_lux - before_lux) <= reset_lux_tolerance, "measured lux did not reset")
    return {
        "actuator_unit": unit,
        "actuator_delta": movement,
        "actuator_reset_error": reset_error,
        "lux_delta": abs(after_lux - before_lux),
        "lux_reset_error": abs(reset_lux - before_lux),
        "sequence_start": sequences[0],
        "sequence_end": sequences[2],
    }


def verify(args: argparse.Namespace) -> dict:
    contract = yaml.safe_load(args.contract.read_text(encoding="utf-8"))
    require(SHA256.fullmatch(args.lease_sha256) is not None, "expected lease digest is invalid")
    files = read_archive(contract)
    manifest = load_json(files["manifest.json"], "manifest.json")
    require(manifest.get("schema") == contract["archive_schema"], "wrong evidence schema")
    require(manifest.get("bench_id") == args.place, "evidence bench identity mismatch")
    require(manifest.get("nonce") == args.nonce, "evidence nonce mismatch")
    require(manifest.get("lease_sha256") == args.lease_sha256, "evidence lease mismatch")

    started = parse_time(manifest.get("captured_at_start"), "captured_at_start")
    completed = parse_time(manifest.get("captured_at_end"), "captured_at_end")
    now = dt.datetime.now(dt.timezone.utc)
    require(started < completed, "capture interval is not increasing")
    require(completed <= now + dt.timedelta(seconds=5), "capture completion is in the future")
    require(
        now - completed <= dt.timedelta(seconds=contract["freshness_seconds"]),
        "raw evidence is stale",
    )

    hashes = validate_artifacts(files, manifest)
    marker = contract["liveness_payload"].format(
        bench_id=args.place,
        nonce=args.nonce,
        lease_sha256=args.lease_sha256,
    )
    frame_names = (
        "primary-before.ppm",
        "primary-after.ppm",
        "witness-before.ppm",
        "witness-after.ppm",
    )
    for name in frame_names:
        parse_ppm(files[name], name, contract)
        require_liveness_marker(files[name], marker, name)
    require(
        hashes["primary-before.ppm"] != hashes["witness-before.ppm"]
        and hashes["primary-after.ppm"] != hashes["witness-after.ppm"],
        "primary and witness evidence are not independent frames",
    )
    frame_deltas = {
        "primary": frame_delta(
            files["primary-before.ppm"], files["primary-after.ppm"], "primary", contract
        ),
        "witness": frame_delta(
            files["witness-before.ppm"], files["witness-after.ppm"], "witness", contract
        ),
    }
    telemetry = validate_telemetry(
        load_json(files["telemetry.json"], "telemetry.json"),
        contract,
        args.place,
        args.nonce,
        args.lease_sha256,
        started,
        completed,
    )
    return {
        "bench_id": args.place,
        "lease_sha256": args.lease_sha256,
        "raw_evidence_verified": True,
        "liveness_marker_verified_in_frames": list(frame_names),
        "frame_deltas": frame_deltas,
        "telemetry_deltas": telemetry,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--place", required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--lease-sha256", required=True)
    try:
        result = verify(parser.parse_args())
    except (KeyError, TypeError, VerificationError, yaml.YAMLError) as error:
        print(f"independent physical evidence verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
