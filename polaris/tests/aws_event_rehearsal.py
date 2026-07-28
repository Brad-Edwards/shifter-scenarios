#!/usr/bin/env python3
"""Live rehearsal for the event-proven Polaris ``aws_event`` range.

Terraform and SSM are used only for provisioning, health observation, reset,
and teardown. Every scenario action enters through A14's public,
key-authenticated SSH service.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


TEST_ROOT = Path(__file__).resolve().parent
PACK_ROOT = TEST_ROOT.parent
REPO_ROOT = PACK_ROOT.parent
AWS_RANGE_ROOT = PACK_ROOT / "aws-range"
PARTICIPANT_SOURCE = TEST_ROOT / "aws_event_participant.py"
RESET_SOURCE = AWS_RANGE_ROOT / "reset.sh"
DEFAULT_REPORT = PACK_ROOT / "docs" / "aws-event-rehearsal-report.md"
RESULT_PREFIX = "POLARIS_REHEARSAL_RESULT="
REPORT_SCHEMA = "polaris.aws-event.rehearsal-report/v1"
RUN_ID_RE = re.compile(r"^run-[0-9a-f]{16}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
PARTICIPANT_ANSWER_OVERRIDES = {
    # This challenge is value-derived: CTFd accepts the concatenated live
    # controller models, while placement.yaml carries the awarded flag.
    "bunker-controller-map": "AHS-TAIL-7741AHS-LEG-MN07AHS-ARM-AL42",
}

sys.path.insert(0, str(AWS_RANGE_ROOT))


class RehearsalError(RuntimeError):
    """A bounded rehearsal failure whose text is safe to report."""


@dataclass(frozen=True)
class Contracts:
    expected: dict[str, str]
    walkthroughs: dict[str, str]


@dataclass(frozen=True)
class Check:
    check_id: str
    status: str
    phase: str
    walkthrough: str | None = None
    failure_stage: str | None = None


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RehearsalError(f"invalid contract: {path.name}")
    return value


def load_contracts(pack_root: Path = PACK_ROOT) -> Contracts:
    placements = _load_yaml(pack_root / "flags" / "placement.yaml").get("flags")
    challenges = _load_yaml(pack_root / "challenges" / "challenges.yaml").get(
        "challenges"
    )
    if not isinstance(placements, list) or not isinstance(challenges, list):
        raise RehearsalError("flag contracts require list roots")
    expected = {
        row["flag_id"]: PARTICIPANT_ANSWER_OVERRIDES.get(
            row["flag_id"], row.get("value")
        )
        for row in placements
        if isinstance(row, dict)
    }
    challenge_ids = {
        row.get("flag_id") for row in challenges if isinstance(row, dict)
    }
    if (
        len(expected) != len(placements)
        or set(expected) != challenge_ids
        or not all(isinstance(value, str) for value in expected.values())
    ):
        raise RehearsalError("flag and challenge contracts do not form a bijection")

    walkthroughs: dict[str, str] = {}
    root = pack_root / "docs" / "walkthroughs"
    for path in sorted(root.glob("flags-*.md")):
        body = path.read_text(encoding="utf-8")
        for flag_id, value in expected.items():
            if value in body:
                if flag_id in walkthroughs:
                    raise RehearsalError(f"duplicate walkthrough binding: {flag_id}")
                walkthroughs[flag_id] = path.relative_to(pack_root).as_posix()
    if set(walkthroughs) != set(expected):
        raise RehearsalError("walkthrough coverage is incomplete")
    return Contracts(expected=expected, walkthroughs=walkthroughs)


def _pack_version() -> str:
    version = _load_yaml(PACK_ROOT / "pack.yaml").get("version")
    rendered = str(version)
    if not VERSION_RE.fullmatch(rendered):
        raise RehearsalError("pack version is unavailable")
    return rendered


def render_participant_program(
    *,
    run_id: str,
    key: bytes,
    phase: str,
    generation: int,
    source: str | None = None,
) -> str:
    if not RUN_ID_RE.fullmatch(run_id) or len(key) != 32:
        raise RehearsalError("invalid run namespace")
    if phase not in {"initial", "after-reset"} or generation not in {1, 2}:
        raise RehearsalError("invalid rehearsal phase")
    program = source if source is not None else PARTICIPANT_SOURCE.read_text(
        encoding="utf-8"
    )
    replacements = {
        "__POLARIS_RUN_ID__": run_id,
        "__POLARIS_RUN_KEY_HEX__": key.hex(),
        "__POLARIS_PHASE__": phase,
        "__POLARIS_ATTEMPT_GENERATION__": str(generation),
    }
    for marker, value in replacements.items():
        if program.count(marker) != 1:
            raise RehearsalError(f"participant marker is invalid: {marker}")
        program = program.replace(marker, value)
    return program


def _digest(key: bytes, value: str) -> str:
    return "hmac-sha256:" + hmac.new(
        key, value.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def parse_participant_result(
    raw: str,
    *,
    run_id: str,
    phase: str,
    generation: int,
    key: bytes,
    contracts: Contracts,
) -> list[Check]:
    lines = [line for line in raw.splitlines() if line.startswith(RESULT_PREFIX)]
    if len(lines) != 1:
        raise RehearsalError("participant result marker is missing or duplicated")
    try:
        payload = json.loads(lines[0][len(RESULT_PREFIX) :])
    except json.JSONDecodeError as error:
        raise RehearsalError("participant result is invalid") from error
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != "polaris.aws-event.participant-result/v1"
        or payload.get("run_id") != run_id
        or payload.get("phase") != phase
        or payload.get("attempt_generation") != generation
        or not isinstance(payload.get("checks"), list)
    ):
        raise RehearsalError("participant result namespace is invalid")

    rows: list[Check] = []
    seen: set[str] = set()
    for row in payload["checks"]:
        if not isinstance(row, dict):
            raise RehearsalError("participant check is invalid")
        check_id = row.get("id")
        status = row.get("status")
        digest = row.get("digest")
        failure_stage = row.get("failure_stage")
        if (
            not isinstance(check_id, str)
            or check_id in seen
            or status not in {"PASS", "FAIL"}
            or (
                failure_stage is not None
                and (
                    status != "FAIL"
                    or check_id != "domain-admin-secrets"
                    or failure_stage
                    not in {
                        "kerberoast-request",
                        "kerberoast-crack",
                        "dcsync",
                        "administrator-share",
                        "administrator-flag",
                    }
                )
            )
        ):
            raise RehearsalError("participant check namespace is invalid")
        seen.add(check_id)
        walkthrough = contracts.walkthroughs.get(check_id)
        if check_id in contracts.expected:
            expected_digest = _digest(key, contracts.expected[check_id])
            if status == "PASS" and digest != expected_digest:
                status = "FAIL"
            elif status == "FAIL" and digest is not None:
                raise RehearsalError("failed recovery exposed an unexpected digest")
        elif digest is not None:
            raise RehearsalError("non-recovery check carried a digest")
        rows.append(Check(check_id, status, phase, walkthrough, failure_stage))

    if phase == "initial":
        required = set(contracts.expected) | {
            "start-state-a14",
            "negative-direct-lab",
            "negative-direct-scada",
            "negative-pre-splice",
            "positive-post-blackout-splice",
        }
    else:
        required = {
            "start-state-a14",
            "negative-direct-lab",
            "negative-direct-scada",
            "negative-pre-splice",
            "reset-controller-state",
            "reset-brain-state",
        }
    if seen != required:
        raise RehearsalError("participant check coverage is incomplete")
    return rows


def _run(
    argv: list[str],
    *,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        argv,
        cwd=REPO_ROOT,
        env=env,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout)[-2000:].strip()
        raise RehearsalError(
            f"{Path(argv[0]).name} exited {completed.returncode}: {detail}"
        )
    return completed


def _public_cidr() -> str:
    with urllib.request.urlopen("https://checkip.amazonaws.com", timeout=15) as reply:
        value = reply.read(64).decode("ascii").strip()
    return f"{ipaddress.IPv4Address(value)}/32"


class TerraformRange:
    def __init__(
        self,
        *,
        profile: str,
        region: str,
        range_id: str,
        participant_cidr: str,
        public_key: str,
        runtime_root: Path,
    ) -> None:
        self.range_id = range_id
        self.state_path = runtime_root / "terraform.tfstate"
        self.env = os.environ.copy()
        self.env.update(
            {
                "AWS_PROFILE": profile,
                "AWS_REGION": region,
                "AWS_DEFAULT_REGION": region,
            }
        )
        self.vars = [
            "-var",
            f"aws_region={region}",
            "-var",
            f"range_id={range_id}",
            "-var",
            f"participant_cidr={participant_cidr}",
            "-var",
            f"kali_authorized_key={public_key.strip()}",
        ]

    def _terraform(self, action: str, *extra: str, timeout: int) -> str:
        result = _run(
            [
                "terraform",
                f"-chdir={AWS_RANGE_ROOT}",
                action,
                f"-state={self.state_path}",
                *extra,
            ],
            env=self.env,
            timeout=timeout,
        )
        return result.stdout

    def apply(self) -> dict[str, Any]:
        _run(
            ["terraform", f"-chdir={AWS_RANGE_ROOT}", "init", "-input=false"],
            env=self.env,
            timeout=600,
        )
        self._terraform(
            "apply",
            "-auto-approve",
            "-input=false",
            *self.vars,
            timeout=3600,
        )
        raw = self._terraform("output", "-json", timeout=120)
        values = json.loads(raw)
        return {key: row["value"] for key, row in values.items()}

    def destroy(self) -> None:
        self._terraform(
            "destroy",
            "-auto-approve",
            "-input=false",
            *self.vars,
            timeout=3600,
        )
        remaining = _run(
            [
                "terraform",
                f"-chdir={AWS_RANGE_ROOT}",
                "state",
                "list",
                f"-state={self.state_path}",
            ],
            env=self.env,
            timeout=120,
        ).stdout.strip()
        if remaining:
            raise RehearsalError("Terraform state is not empty after destroy")


def _generate_ssh_key(runtime_root: Path) -> tuple[Path, str]:
    private_key = runtime_root / "participant_ed25519"
    _run(
        [
            "ssh-keygen",
            "-q",
            "-t",
            "ed25519",
            "-N",
            "",
            "-C",
            "polaris-rehearsal",
            "-f",
            str(private_key),
        ],
        timeout=30,
    )
    return private_key, private_key.with_suffix(".pub").read_text(encoding="utf-8")


def _run_participant(
    public_ip: str,
    private_key: Path,
    known_hosts: Path,
    program: str,
    timeout: int,
) -> str:
    result = subprocess.run(
        [
            "ssh",
            "-i",
            str(private_key),
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=20",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={known_hosts}",
            f"kali@{public_ip}",
            "python3",
            "-",
        ],
        cwd=REPO_ROOT,
        input=program,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode and RESULT_PREFIX not in result.stdout:
        detail = "\n".join(
            part.strip() for part in (result.stderr, result.stdout) if part.strip()
        )[-2000:]
        raise RehearsalError(f"participant SSH exited {result.returncode}: {detail}")
    return result.stdout


def _bash_payload(script: str) -> str:
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    return f"printf '%s' '{encoded}' | base64 -d | bash"


def _aws_error_code(error: Exception) -> str | None:
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return None
    detail = response.get("Error")
    if not isinstance(detail, dict):
        return None
    code = detail.get("Code")
    return str(code) if code is not None else None


def _bootstrap_a2(
    *,
    profile: str,
    region: str,
    instance_id: str,
    timeout: int,
) -> None:
    env = os.environ.copy()
    env.update({"AWS_PROFILE": profile, "AWS_REGION": region})
    _run(
        [str(AWS_RANGE_ROOT / "a2_cold_bootstrap.sh"), instance_id],
        env=env,
        timeout=timeout,
    )


def _wait_operator_health(
    executor: SsmExecutor,
    instance_id: str,
    timeout_seconds: int,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not started"
    while time.monotonic() < deadline:
        try:
            _operator_health(executor, instance_id)
            return
        except Exception as error:
            last_error = type(error).__name__
            time.sleep(30)
    raise RehearsalError(f"operator health timed out ({last_error})")


def _wait_participant_ssh(
    public_ip: str,
    private_key: Path,
    known_hosts: Path,
    timeout_seconds: int,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            result = _run_participant(
                public_ip,
                private_key,
                known_hosts,
                "print('POLARIS_SSH_READY')\n",
                60,
            )
            if "POLARIS_SSH_READY" in result:
                return
        except Exception:
            pass
        time.sleep(15)
    raise RehearsalError("participant SSH did not become ready")


def _write_participant_known_hosts(
    executor: SsmExecutor,
    instance_id: str,
    public_ip: str,
    runtime_root: Path,
) -> Path:
    """Bind A14 SSH to the host identity read over the trusted SSM plane."""
    result = executor.run_bash(
        instance_id,
        _bash_payload(
            "docker exec a14-kali cat /etc/ssh/ssh_host_ed25519_key.pub"
        ),
        timeout_s=60,
        comment="Read the Polaris participant SSH host identity",
    )
    rows = [row.strip() for row in result.stdout.splitlines() if row.strip()]
    if len(rows) != 1:
        raise RehearsalError("A14 SSH host identity is missing or ambiguous")
    fields = rows[0].split()
    if (
        len(fields) not in {2, 3}
        or fields[0] != "ssh-ed25519"
        or not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", fields[1])
    ):
        raise RehearsalError("A14 SSH host identity is invalid")
    known_hosts = runtime_root / "known_hosts"
    known_hosts.write_text(
        f"{public_ip} {fields[0]} {fields[1]}\n",
        encoding="utf-8",
    )
    known_hosts.chmod(0o600)
    return known_hosts


def _live_inventory_count(
    context: PolarisAwsContext,
    range_id: str,
) -> int:
    ec2 = context.ec2()
    tag = [{"Name": "tag:RangeId", "Values": [range_id]}]
    count = 0
    instances = ec2.describe_instances(
        Filters=tag
        + [
            {
                "Name": "instance-state-name",
                "Values": [
                    "pending",
                    "running",
                    "stopping",
                    "stopped",
                    "shutting-down",
                ],
            }
        ]
    )
    count += sum(
        len(row.get("Instances", []))
        for row in instances.get("Reservations", [])
    )
    for operation, key in (
        (ec2.describe_volumes, "Volumes"),
        (ec2.describe_vpcs, "Vpcs"),
        (ec2.describe_subnets, "Subnets"),
        (ec2.describe_security_groups, "SecurityGroups"),
        (ec2.describe_route_tables, "RouteTables"),
        (ec2.describe_internet_gateways, "InternetGateways"),
    ):
        count += len(operation(Filters=tag).get(key, []))

    account = context.client("sts").get_caller_identity()["Account"]
    bucket = f"{range_id}-{account}"
    try:
        context.client("s3").head_bucket(Bucket=bucket)
        count += 1
    except Exception as error:
        if _aws_error_code(error) not in {
            "404",
            "NoSuchBucket",
            "NotFound",
        }:
            raise

    iam = context.client("iam")
    for operation, kwargs in (
        (iam.get_role, {"RoleName": f"{range_id}-role"}),
        (
            iam.get_instance_profile,
            {"InstanceProfileName": f"{range_id}-profile"},
        ),
    ):
        try:
            operation(**kwargs)
            count += 1
        except Exception as error:
            if _aws_error_code(error) != "NoSuchEntity":
                raise
    return count


def _verify_live_inventory_empty(
    context: PolarisAwsContext,
    range_id: str,
    timeout_seconds: int,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _live_inventory_count(context, range_id) == 0:
            return
        time.sleep(15)
    raise RehearsalError("live AWS resource inventory is not empty after destroy")


def _operator_health(executor: SsmExecutor, instance_id: str) -> None:
    probe = r"""
set -euo pipefail
running=$(docker ps --format '{{.Names}}' | grep -cE '^(dns|a[0-9]+(-[a-z0-9-]+)?)$' || true)
test "$running" -ge 17
test "$(docker inspect -f '{{.State.Status}}' a14-kali)" = running
systemctl is-active --quiet polaris-splice-watcher.service
echo HEALTH=PASS
"""
    result = executor.run_bash(
        instance_id,
        _bash_payload(probe),
        timeout_s=300,
        comment="Polaris rehearsal operator health observation",
    )
    if "HEALTH=PASS" not in result.stdout:
        raise RehearsalError("operator health check failed")


def _reset(executor: SsmExecutor, instance_id: str) -> None:
    result = executor.run_bash(
        instance_id,
        _bash_payload(RESET_SOURCE.read_text(encoding="utf-8")),
        timeout_s=2400,
        comment="Polaris rehearsal reset",
    )
    if result.status != "Success":
        raise RehearsalError("range reset failed")


def render_report(
    *,
    pack_version: str,
    started_at: str,
    completed_at: str,
    checks: list[Check],
    health: str,
    reset: str,
    teardown: str,
) -> str:
    verdict = (
        "PASS"
        if health == reset == teardown == "PASS"
        and checks
        and all(row.status == "PASS" for row in checks)
        else "FAIL"
    )
    lines = [
        "# Polaris automated aws_event rehearsal",
        "",
        f"- schema: `{REPORT_SCHEMA}`",
        "- runtime_profile_id: `aws_event`",
        "- runtime_source: `aws-range/` + `build/build-v1.tar.gz`",
        f"- pack_version: `{pack_version}`",
        f"- started_at: `{started_at}`",
        f"- completed_at: `{completed_at}`",
        f"- operator_health: `{health}`",
        f"- reset: `{reset}`",
        f"- teardown: `{teardown}`",
        f"- verdict: `{verdict}`",
        "",
        "Participant actions used A14's public key-authenticated SSH endpoint. AWS/SSM",
        "was limited to provisioning, health observation, reset, and teardown.",
        "This report does not claim the separate manual walkthrough or golden",
        "promotion.",
        "",
        "## Participant checks",
        "",
    ]
    for row in checks:
        suffix = f"; walkthrough={row.walkthrough}" if row.walkthrough else ""
        if row.failure_stage:
            suffix += f"; failure_stage={row.failure_stage}"
        lines.append(
            f"- [{row.status}] `{row.phase}:{row.check_id}`{suffix}"
        )
    rendered = "\n".join(lines) + "\n"
    if re.search(r"FLAG\{|private_key|instance_id|request_id", rendered, re.I):
        raise RehearsalError("report contains forbidden live material")
    return rendered


def _utc_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _write_report(path: Path, body: str) -> None:
    if path.is_symlink():
        raise RehearsalError("report path may not be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=None, help="Optional AWS profile")
    parser.add_argument("--region", default="us-east-2")
    parser.add_argument("--ready-timeout", type=int, default=7200)
    parser.add_argument("--a2-timeout", type=int, default=3600)
    parser.add_argument("--teardown-timeout", type=int, default=1800)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser


def main(argv: list[str] | None = None) -> int:
    from common import (  # noqa: PLC0415
        PolarisAwsContext,
        SsmExecutor,
    )

    args = build_parser().parse_args(argv)
    profile = args.profile or os.environ.get("AWS_PROFILE")
    if not profile:
        raise RehearsalError("an AWS profile is required")
    run_id = "run-" + secrets.token_hex(8)
    range_id = "polaris-" + run_id[4:16]
    key = secrets.token_bytes(32)
    contracts = load_contracts()
    pack_version = _pack_version()
    started_at = _utc_now()
    checks: list[Check] = []
    health = reset = teardown = "FAIL"

    context = PolarisAwsContext(profile=profile, region=args.region)
    executor = SsmExecutor(context.ssm())
    with tempfile.TemporaryDirectory(prefix=f"{range_id}-") as runtime:
        runtime_root = Path(runtime)
        private_key, public_key = _generate_ssh_key(runtime_root)
        terraform_range = TerraformRange(
            profile=profile,
            region=args.region,
            range_id=range_id,
            participant_cidr=_public_cidr(),
            public_key=public_key,
            runtime_root=runtime_root,
        )
        lifecycle_started = False
        try:
            lifecycle_started = True
            outputs = terraform_range.apply()
            instance_id = str(outputs["range_polaris_instance_ids"]["0"])
            a2_instance_id = str(outputs["range_a2_instance_ids"]["0"])
            public_ip = str(outputs["range_polaris_public_ips"]["0"])

            _bootstrap_a2(
                profile=profile,
                region=args.region,
                instance_id=a2_instance_id,
                timeout=args.a2_timeout,
            )
            _wait_operator_health(executor, instance_id, args.ready_timeout)
            known_hosts = _write_participant_known_hosts(
                executor, instance_id, public_ip, runtime_root
            )
            _wait_participant_ssh(public_ip, private_key, known_hosts, 600)
            health = "PASS"

            initial = _run_participant(
                public_ip,
                private_key,
                known_hosts,
                render_participant_program(
                    run_id=run_id,
                    key=key,
                    phase="initial",
                    generation=1,
                ),
                2100,
            )
            checks.extend(
                parse_participant_result(
                    initial,
                    run_id=run_id,
                    phase="initial",
                    generation=1,
                    key=key,
                    contracts=contracts,
                )
            )

            _reset(executor, instance_id)
            _wait_operator_health(executor, instance_id, 900)
            known_hosts = _write_participant_known_hosts(
                executor, instance_id, public_ip, runtime_root
            )
            after_reset = _run_participant(
                public_ip,
                private_key,
                known_hosts,
                render_participant_program(
                    run_id=run_id,
                    key=key,
                    phase="after-reset",
                    generation=2,
                ),
                900,
            )
            checks.extend(
                parse_participant_result(
                    after_reset,
                    run_id=run_id,
                    phase="after-reset",
                    generation=2,
                    key=key,
                    contracts=contracts,
                )
            )
            reset = "PASS"
        except Exception as error:
            print(f"rehearsal failed: {type(error).__name__}: {error}", file=sys.stderr)
        finally:
            if lifecycle_started:
                try:
                    terraform_range.destroy()
                    _verify_live_inventory_empty(
                        context,
                        range_id,
                        args.teardown_timeout,
                    )
                    teardown = "PASS"
                except Exception as error:
                    print(
                        f"teardown failed: {type(error).__name__}: {error}",
                        file=sys.stderr,
                    )
            report = render_report(
                pack_version=pack_version,
                started_at=started_at,
                completed_at=_utc_now(),
                checks=checks,
                health=health,
                reset=reset,
                teardown=teardown,
            )
            _write_report(args.report.resolve(), report)

    return 0 if health == reset == teardown == "PASS" and all(
        row.status == "PASS" for row in checks
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
