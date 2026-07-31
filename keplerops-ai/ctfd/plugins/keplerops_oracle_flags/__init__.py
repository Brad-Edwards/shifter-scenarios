"""CTFd flag type for participant- and range-bound oracle receipts."""

from __future__ import annotations

import json
import os
import queue
import re
import secrets
import ssl
import stat
import threading
import time
import urllib.request
from fcntl import LOCK_EX, LOCK_UN, flock

from .receipt import (
    STATUS_EXPIRED_RECEIPT,
    STATUS_PASSED,
    STATUS_STALE_RESET_GENERATION,
    verify_receipt_status,
)

MAX_BINDINGS_BYTES = 1_048_576
TELEMETRY_QUEUE = queue.Queue(maxsize=256)
TELEMETRY_DROPPED = 0
TELEMETRY_LOCK = threading.Lock()
CHALLENGE_API = re.compile(r"^/api/v1/challenges/([0-9]+)$")
HINT_API = re.compile(r"^/api/v1/hints/([0-9]+)$")
SAFE_EVENT_FIELDS = {
    "attempt_sequence",
    "challenge_id",
    "failure_class",
    "hint_cost",
    "hint_tier",
    "participant_interface",
}
STALE_RECEIPT_STATUSES = {STATUS_STALE_RESET_GENERATION, STATUS_EXPIRED_RECEIPT}
MODULES = {
    "agent-control": "module-01-agent-control",
    "model-evasion": "module-02-model-evasion",
    "context-poisoning": "module-03-context-poisoning",
    "model-secrets": "module-04-model-secrets",
    "agent-persistence": "module-05-agent-persistence",
    "adversarial-input": "module-06-adversarial-input",
    "training-poisoning": "module-07-training-poisoning",
    "model-extraction": "module-08-model-extraction",
    "model-backdoor": "module-09-model-backdoor",
    "ai-capstone": "module-10-ai-capstone",
}


def _secure_read(path: str, limit: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
            raise ValueError("runtime verifier file must be regular and owner-only")
        value = os.read(descriptor, limit + 1)
    finally:
        os.close(descriptor)
    if not value or len(value) > limit:
        raise ValueError("runtime verifier file has invalid size")
    return value


def _runtime_binding(account_id: int):
    path = os.environ["KEPLEROPS_CTFD_BINDINGS_FILE"]
    body = json.loads(_secure_read(path, MAX_BINDINGS_BYTES))
    binding = body.get("accounts", {}).get(str(account_id))
    if not isinstance(binding, dict):
        raise ValueError("participant binding unavailable")
    return binding


def _next_sequence() -> int:
    path = os.environ["KEPLEROPS_CTFD_TELEMETRY_SEQUENCE_FILE"]
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "r+", encoding="ascii") as handle:
        flock(handle.fileno(), LOCK_EX)
        raw = handle.read().strip()
        value = int(raw) + 1 if raw else 1
        handle.seek(0)
        handle.truncate()
        handle.write(f"{value}\n")
        handle.flush()
        os.fsync(handle.fileno())
        flock(handle.fileno(), LOCK_UN)
    return value


def _record_telemetry_drop() -> None:
    global TELEMETRY_DROPPED
    with TELEMETRY_LOCK:
        TELEMETRY_DROPPED += 1


def _telemetry_drop_count() -> int:
    with TELEMETRY_LOCK:
        return TELEMETRY_DROPPED


def _telemetry_payload(binding, contract, event_name, status, trace_id, **fields):
    module_id = MODULES.get(contract.get("outcome"))
    if module_id is None:
        raise ValueError("unknown KeplerOps outcome")
    event = {
        "event_name": event_name,
        "occurred_at": time.time_ns(),
        "module_id": module_id,
        "participant_interface": "ctfd",
        "source_sequence": _next_sequence(),
        "status": status,
        "trace_id": trace_id,
        "dropped_event_count": _telemetry_drop_count(),
    }
    if isinstance(contract.get("challenge_id"), str):
        event["challenge_id"] = contract["challenge_id"]
    event.update({
        key: value for key, value in fields.items()
        if key in SAFE_EVENT_FIELDS and value is not None
    })
    return {
        "event": event,
        "range_instance": binding["range_instance"],
        "participant": binding["participant"],
        "reset_generation": binding["reset_generation"],
    }


def _enqueue_telemetry(binding, contract, event_name, status, trace_id, **fields):
    if "KEPLEROPS_CTFD_RESEARCH_URL" not in os.environ:
        return
    try:
        TELEMETRY_QUEUE.put_nowait(
            _telemetry_payload(
                binding, contract, event_name, status, trace_id, **fields
            )
        )
    except (KeyError, OSError, TypeError, ValueError, queue.Full):
        _record_telemetry_drop()
        return


def _telemetry_worker():
    while True:
        payload = TELEMETRY_QUEUE.get()
        try:
            request = urllib.request.Request(
                os.environ["KEPLEROPS_CTFD_RESEARCH_URL"] + "/v1/research/events",
                data=json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "X-Producer-ID": "lab-portal",
                    "X-Producer-Token": _secure_read(
                        os.environ["KEPLEROPS_CTFD_RESEARCH_TOKEN_FILE"], 4096
                    ).strip().decode("utf-8"),
                },
                method="POST",
            )
            context = ssl.create_default_context(
                cafile=os.environ["KEPLEROPS_CTFD_RESEARCH_CA_FILE"]
            )
            context.load_cert_chain(
                os.environ["KEPLEROPS_CTFD_RESEARCH_CERT_FILE"],
                os.environ["KEPLEROPS_CTFD_RESEARCH_KEY_FILE"],
            )
            with urllib.request.urlopen(request, context=context, timeout=0.5):
                pass
        except Exception:
            _record_telemetry_drop()
            pass
        finally:
            TELEMETRY_QUEUE.task_done()


def load(app):
    """Register a fail-closed CTFd flag that verifies signed oracle receipts."""
    from CTFd.plugins.flags import BaseFlag, FLAG_CLASSES
    from CTFd.utils.user import get_current_user

    if "KEPLEROPS_CTFD_RESEARCH_URL" in os.environ:
        threading.Thread(
            target=_telemetry_worker,
            name="keplerops-ctfd-telemetry",
            daemon=True,
        ).start()

    class KeplerOpsOracleFlag(BaseFlag):
        name = "keplerops_oracle"
        templates = {}

        @staticmethod
        def compare(saved, provided):
            try:
                user = get_current_user()
                if user is None:
                    return False
                contract = json.loads(saved.content)
                binding = _runtime_binding(user.account_id)
                key_path = os.environ["KEPLEROPS_CTFD_RECEIPT_KEY_FILE"]
                key = _secure_read(key_path, 8192).strip()
                trace_id = secrets.token_hex(16)
                _enqueue_telemetry(
                    binding, contract, "attempt.started", "recorded", trace_id
                )
                _enqueue_telemetry(
                    binding, contract, "flag.submitted", "recorded", trace_id
                )
                verification_status = verify_receipt_status(
                    provided, contract=contract, binding=binding,
                    verification_key=key, now=int(time.time()),
                )
                valid = verification_status == STATUS_PASSED
                failure_fields = (
                    {} if valid else {"failure_class": verification_status}
                )
                _enqueue_telemetry(
                    binding,
                    contract,
                    "objective.attempted",
                    "passed" if valid else "rejected",
                    trace_id,
                    **failure_fields,
                )
                _enqueue_telemetry(
                    binding,
                    contract,
                    "attempt.completed",
                    "passed" if valid else "rejected",
                    trace_id,
                    **failure_fields,
                )
                if valid:
                    _enqueue_telemetry(
                        binding,
                        contract,
                        "objective.satisfied",
                        "passed",
                        trace_id,
                    )
                    _enqueue_telemetry(
                        binding,
                        contract,
                        "challenge.solved",
                        "passed",
                        trace_id,
                    )
                elif verification_status in STALE_RECEIPT_STATUSES:
                    _enqueue_telemetry(
                        binding,
                        contract,
                        "receipt.stale_rejected",
                        "rejected",
                        trace_id,
                        **failure_fields,
                    )
                return valid
            except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
                return False

    def telemetry_contract_for_challenge(challenge_id):
        from CTFd.models import Flags

        flag = Flags.query.filter_by(challenge_id=challenge_id).first()
        if flag is None:
            return None
        return json.loads(flag.content)

    def hint_event_fields(hint):
        from CTFd.models import Hints

        rows = Hints.query.filter_by(challenge_id=hint.challenge_id).order_by(Hints.id).all()
        tier = next(
            (index for index, row in enumerate(rows, 1) if row.id == hint.id),
            None,
        )
        return {"hint_cost": int(getattr(hint, "cost", 0)), "hint_tier": tier}

    FLAG_CLASSES[KeplerOpsOracleFlag.name] = KeplerOpsOracleFlag

    @app.after_request
    def observe_portfolio_events(response):
        """Observe successful CTFd board events without recording content."""
        try:
            from flask import request
            from CTFd.models import Flags, Hints

            user = get_current_user()
            if user is None:
                return response
            binding = _runtime_binding(user.account_id)
            challenge_match = CHALLENGE_API.fullmatch(request.path)
            hint_match = HINT_API.fullmatch(request.path)
            if request.method == "GET" and challenge_match is not None:
                contract = telemetry_contract_for_challenge(int(challenge_match.group(1)))
                if contract is not None:
                    trace_id = secrets.token_hex(16)
                    if response.status_code >= 400:
                        if contract.get("prerequisites"):
                            _enqueue_telemetry(
                                binding,
                                contract,
                                "dependency.blocked",
                                "rejected",
                                trace_id,
                                failure_class="prerequisite_unsatisfied",
                            )
                        return response
                    if contract.get("prerequisites"):
                        _enqueue_telemetry(
                            binding,
                            contract,
                            "dependency.unlocked",
                            "recorded",
                            trace_id,
                        )
                    _enqueue_telemetry(
                        binding, contract, "challenge.presented", "recorded", trace_id
                    )
                    _enqueue_telemetry(
                        binding, contract, "challenge.started", "recorded", trace_id
                    )
                return response
            if response.status_code >= 400:
                return response
            if request.method == "GET" and hint_match is not None:
                hint = Hints.query.filter_by(id=int(hint_match.group(1))).first()
                contract = telemetry_contract_for_challenge(hint.challenge_id) if hint else None
                if contract is not None and hint is not None:
                    _enqueue_telemetry(
                        binding,
                        contract,
                        "hint.viewed",
                        "recorded",
                        secrets.token_hex(16),
                        **hint_event_fields(hint),
                    )
                return response
            if request.method != "POST" or request.path != "/api/v1/unlocks":
                return response
            submitted = request.get_json(silent=True) or {}
            if submitted.get("type") != "hints":
                return response
            hint = Hints.query.filter_by(id=int(submitted["target"])).first()
            flag = Flags.query.filter_by(challenge_id=hint.challenge_id).first() if hint else None
            if flag is None or hint is None:
                return response
            contract = json.loads(flag.content)
            _enqueue_telemetry(
                binding,
                contract,
                "hint.unlocked",
                "recorded",
                secrets.token_hex(16),
                **hint_event_fields(hint),
            )
        except Exception:
            pass
        return response
