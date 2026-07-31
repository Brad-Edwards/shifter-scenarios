"""Contained, challenge-neutral KeplerOps impact and availability platform."""

from __future__ import annotations

import hmac
import ipaddress
import os
import sqlite3
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlparse

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from database import SEED_TIMESTAMP, StateStore
from engines import BeancountLedger, CostRates, ModelArtifacts, body_digest


Identifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,63}$")]
AccountName = Annotated[
    str, Field(pattern=r"^[A-Z][A-Za-z0-9-]*(?::[A-Z][A-Za-z0-9-]*)+$")
]


def now() -> str:
    return datetime.now(UTC).isoformat()


def row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def exact_micros(amount: Decimal) -> int:
    scaled = amount * 1_000_000
    if scaled != scaled.to_integral_value():
        raise HTTPException(
            status_code=422, detail="amount supports at most six decimals"
        )
    value = int(scaled)
    if value <= 0:
        raise HTTPException(status_code=422, detail="amount must be positive")
    return value


def validate_range_url(value: str, *, optional: bool = False) -> str | None:
    if optional and value == "":
        return None
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.hostname
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("URL must be a plain range-local HTTP(S) endpoint")
    host = parsed.hostname.lower()
    allowed = host in {"localhost", "127.0.0.1", "::1"} or host.endswith(
        ".keplerops.lab"
    )
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_loopback:
        allowed = False
    if not allowed:
        raise ValueError("URL host must be loopback or inside keplerops.lab")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("URL has an invalid port") from error
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("URL has an invalid port")
    return value


class LedgerPost(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transaction_id: Identifier
    actor: Identifier
    narration: Annotated[str, Field(min_length=3, max_length=200)]
    amount: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=6)]
    debit_account: AccountName
    credit_account: AccountName


class PublicationPost(BaseModel):
    model_config = ConfigDict(extra="forbid")
    publication_id: Identifier
    author: Identifier
    subject: Identifier
    body: Annotated[str, Field(min_length=3, max_length=10_000)]
    reputation_delta: Annotated[int, Field(ge=-50, le=50)]


class AllocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision_id: Identifier
    subject_id: Identifier
    group_name: Identifier
    income: Annotated[float, Field(ge=0, le=1_000)]
    need_score: Annotated[float, Field(ge=0, le=1)]
    prior_service: Annotated[float, Field(ge=0, le=1)]
    expected_label: Annotated[int, Field(ge=0, le=1)]


class UserSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    simulation_id: Identifier
    user_id: Identifier
    message: Annotated[str, Field(min_length=3, max_length=4_000)]


class BudgetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit_microunits: Annotated[int, Field(ge=0, le=10_000_000_000)]


class CostEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: Identifier
    actor: Identifier
    producer_id: Identifier
    input_tokens: Annotated[int, Field(ge=0, le=10_000_000)]
    output_tokens: Annotated[int, Field(ge=0, le=10_000_000)]
    compute_ms: Annotated[int, Field(ge=0, le=3_600_000)]


class AvailabilityTargetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_id: Identifier
    name: Identifier
    probe_url: Annotated[str, Field(min_length=8, max_length=500)]
    recovery_url: Annotated[str, Field(max_length=500)] = ""
    recovery_after: Annotated[int, Field(ge=1, le=10)] = 2

    @field_validator("probe_url")
    @classmethod
    def probe_is_local(cls, value: str) -> str:
        return str(validate_range_url(value))

    @field_validator("recovery_url")
    @classmethod
    def recovery_is_local(cls, value: str) -> str:
        return str(validate_range_url(value, optional=True) or "")


class PlatformServices:
    def __init__(
        self, data_root: Path, transport: httpx.AsyncBaseTransport | None
    ) -> None:
        data_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.store = StateStore(data_root / "platform-impact.sqlite3")
        self.models = ModelArtifacts(data_root / "models")
        self.ledger = BeancountLedger()
        self.cost_rates = CostRates()
        self.transport = transport

    def ready(self) -> bool:
        return (
            self.store.ready()
            and self.models.allocation_path.is_file()
            and self.models.safety_path.is_file()
            and self.ledger.validate(()) == 0
        )

    async def probe(self, target_id: str) -> dict[str, Any]:
        with self.store.read() as connection:
            target = connection.execute(
                "SELECT * FROM availability_targets WHERE target_id=?", (target_id,)
            ).fetchone()
        if target is None:
            raise HTTPException(status_code=404, detail="availability target not found")

        started = time.perf_counter()
        available = False
        status_code: int | None = None
        error: str | None = None
        timeout = httpx.Timeout(3.0, connect=1.0)
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=timeout
            ) as client:
                response = await client.get(target["probe_url"])
            status_code = response.status_code
            available = 200 <= response.status_code < 400
            if not available:
                error = f"probe returned HTTP {response.status_code}"
        except httpx.HTTPError as caught:
            error = caught.__class__.__name__
        latency_ms = (time.perf_counter() - started) * 1_000

        failures = 0 if available else int(target["consecutive_failures"]) + 1
        recovery_attempted = False
        recovery_succeeded = False
        recovery_status: int | None = None
        recovery_error: str | None = None
        recovery_url = target["recovery_url"]
        if not available and recovery_url and failures >= int(target["recovery_after"]):
            recovery_attempted = True
            try:
                async with httpx.AsyncClient(
                    transport=self.transport, timeout=timeout
                ) as client:
                    recovery = await client.post(recovery_url)
                recovery_status = recovery.status_code
                recovery_succeeded = 200 <= recovery.status_code < 300
                if not recovery_succeeded:
                    recovery_error = f"recovery returned HTTP {recovery.status_code}"
            except httpx.HTTPError as caught:
                recovery_error = caught.__class__.__name__
            if recovery_succeeded:
                failures = 0

        occurred_at = now()
        sample_id = f"sample-{uuid.uuid4().hex}"
        recovery_id = f"recovery-{uuid.uuid4().hex}" if recovery_attempted else None
        with self.store.transaction() as connection:
            connection.execute(
                "UPDATE availability_targets SET consecutive_failures=? WHERE target_id=?",
                (failures, target_id),
            )
            connection.execute(
                "INSERT INTO availability_samples "
                "(sample_id, target_id, available, status_code, latency_ms, error, occurred_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    sample_id,
                    target_id,
                    int(available),
                    status_code,
                    latency_ms,
                    error,
                    occurred_at,
                ),
            )
            if recovery_id is not None:
                connection.execute(
                    "INSERT INTO recovery_events "
                    "(recovery_id, target_id, attempted, succeeded, status_code, error, occurred_at) "
                    "VALUES (?, ?, 1, ?, ?, ?, ?)",
                    (
                        recovery_id,
                        target_id,
                        int(recovery_succeeded),
                        recovery_status,
                        recovery_error,
                        occurred_at,
                    ),
                )
        return {
            "sample_id": sample_id,
            "target_id": target_id,
            "available": available,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "error": error,
            "consecutive_failures": failures,
            "recovery": {
                "attempted": recovery_attempted,
                "succeeded": recovery_succeeded,
                "status_code": recovery_status,
                "error": recovery_error,
                "recovery_id": recovery_id,
            },
            "occurred_at": occurred_at,
        }


AUTH_RESPONSES = {401: {"description": "Operator authorization failed"}}
READY_RESPONSES = {503: {"description": "The impact platform is not ready"}}
LEDGER_RESPONSES = {
    409: {"description": "The ledger transaction conflicts with durable state"},
    422: {"description": "The ledger transaction is invalid"},
}
PUBLICATION_RESPONSES = {
    404: {"description": "The publication does not exist"},
    409: {"description": "The publication conflicts with durable state"},
}
ALLOCATION_RESPONSES = {
    409: {"description": "Allocation state is incomplete or conflicts"}
}
BUDGET_RESPONSES = {
    404: {"description": "The synthetic budget does not exist"},
    409: {"description": "The synthetic budget or cost event conflicts"},
}
AVAILABILITY_RESPONSES = {
    **AUTH_RESPONSES,
    404: {"description": "The availability target does not exist"},
    422: {"description": "The target identifier does not match the request"},
}


class ImpactOperations:
    """Domain operations kept independent from FastAPI route registration."""

    def __init__(self, services: PlatformServices) -> None:
        self.services = services

    def post_ledger(self, request: LedgerPost) -> dict[str, Any]:
        created_at = now()
        candidate = {
            "transaction_id": request.transaction_id,
            "actor": request.actor,
            "narration": request.narration,
            "amount_micros": exact_micros(request.amount),
            "currency": "SYN",
            "debit_account": request.debit_account,
            "credit_account": request.credit_account,
            "created_at": created_at,
        }
        try:
            with self.services.store.transaction() as connection:
                existing = [
                    row_dict(row)
                    for row in connection.execute(
                        "SELECT * FROM ledger_transactions ORDER BY created_at, transaction_id"
                    )
                ]
                entry_count = self.services.ledger.validate((*existing, candidate))
                connection.execute(
                    "INSERT INTO ledger_transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(candidate.values()),
                )
        except sqlite3.IntegrityError as error:
            raise HTTPException(
                status_code=409, detail="ledger transaction conflicts"
            ) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {**candidate, "entry_count": entry_count, "balanced": True}

    def ledger(self) -> dict[str, Any]:
        with self.services.store.read() as connection:
            rows = [
                row_dict(row)
                for row in connection.execute(
                    "SELECT * FROM ledger_transactions ORDER BY created_at, transaction_id"
                )
            ]
        return {
            "transactions": rows,
            "entry_count": self.services.ledger.validate(rows),
            "balanced": True,
            "engine": "beancount",
        }

    def publish(self, request: PublicationPost) -> dict[str, Any]:
        created_at = now()
        digest = body_digest(request.body)
        try:
            with self.services.store.transaction() as connection:
                connection.execute(
                    "INSERT INTO publications VALUES (?, ?, ?, ?, ?, ?, 'published', ?, NULL)",
                    (
                        request.publication_id,
                        request.author,
                        request.subject,
                        request.body,
                        digest,
                        request.reputation_delta,
                        created_at,
                    ),
                )
                connection.execute(
                    "INSERT INTO reputations(subject, score, updated_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(subject) DO UPDATE SET "
                    "score=reputations.score + excluded.score, updated_at=excluded.updated_at",
                    (request.subject, request.reputation_delta, created_at),
                )
                score = connection.execute(
                    "SELECT score FROM reputations WHERE subject=?", (request.subject,)
                ).fetchone()["score"]
        except sqlite3.IntegrityError as error:
            raise HTTPException(
                status_code=409, detail="publication conflicts"
            ) from error
        return {
            "publication_id": request.publication_id,
            "body_digest": digest,
            "status": "published",
            "reputation_score": score,
            "created_at": created_at,
        }

    def remove_publication(self, publication_id: str) -> dict[str, Any]:
        removed_at = now()
        with self.services.store.transaction() as connection:
            publication = connection.execute(
                "SELECT * FROM publications WHERE publication_id=?", (publication_id,)
            ).fetchone()
            if publication is None:
                raise HTTPException(status_code=404, detail="publication not found")
            if publication["status"] != "published":
                raise HTTPException(
                    status_code=409, detail="publication already removed"
                )
            connection.execute(
                "UPDATE publications SET status='removed', removed_at=? WHERE publication_id=?",
                (removed_at, publication_id),
            )
            connection.execute(
                "UPDATE reputations SET score=score-?, updated_at=? WHERE subject=?",
                (publication["reputation_delta"], removed_at, publication["subject"]),
            )
            score = connection.execute(
                "SELECT score FROM reputations WHERE subject=?",
                (publication["subject"],),
            ).fetchone()["score"]
        return {
            "publication_id": publication_id,
            "status": "removed",
            "reputation_score": score,
            "removed_at": removed_at,
        }

    def publications(self, active_only: bool) -> dict[str, Any]:
        with self.services.store.read() as connection:
            if active_only:
                cursor = connection.execute(
                    "SELECT * FROM publications WHERE status='published' "
                    "ORDER BY created_at, publication_id"
                )
            else:
                cursor = connection.execute(
                    "SELECT * FROM publications ORDER BY created_at, publication_id"
                )
            rows = [row_dict(row) for row in cursor]
        return {"publications": rows, "record_count": len(rows)}

    def reputation(self, subject: str) -> dict[str, Any]:
        with self.services.store.read() as connection:
            record = connection.execute(
                "SELECT * FROM reputations WHERE subject=?", (subject,)
            ).fetchone()
        if record is None:
            raise HTTPException(status_code=404, detail="reputation subject not found")
        return row_dict(record)

    def persist_allocation(self, request: AllocationRequest) -> dict[str, Any]:
        result = self.services.models.allocate(
            request.income, request.need_score, request.prior_service
        )
        created_at = now()
        try:
            with self.services.store.transaction() as connection:
                connection.execute(
                    "INSERT INTO allocation_decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        request.decision_id,
                        request.subject_id,
                        request.group_name,
                        request.income,
                        request.need_score,
                        request.prior_service,
                        request.expected_label,
                        int(result.approved),
                        result.probability,
                        result.model_digest,
                        created_at,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise HTTPException(
                status_code=409, detail="allocation decision conflicts"
            ) from error
        return {
            "decision_id": request.decision_id,
            "subject_id": request.subject_id,
            "approved": result.approved,
            "probability": result.probability,
            "model_digest": result.model_digest,
            "created_at": created_at,
        }

    def allocate_seeded_cohort(self) -> dict[str, Any]:
        with self.services.store.read() as connection:
            population = [
                row_dict(row)
                for row in connection.execute(
                    "SELECT * FROM allocation_population ORDER BY subject_id"
                )
            ]
            existing = {
                row["decision_id"]: row_dict(row)
                for row in connection.execute(
                    "SELECT * FROM allocation_decisions WHERE decision_id LIKE 'seed-%'"
                )
            }
        decisions = []
        for row in population:
            decision_id = f"seed-{row['subject_id']}"
            if decision_id in existing:
                decision = existing[decision_id]
                if not self._seed_decision_matches(decision, row):
                    raise HTTPException(
                        status_code=409, detail="allocation decision conflicts"
                    )
                decisions.append(decision)
                continue
            decisions.append(
                self.persist_allocation(
                    AllocationRequest(
                        decision_id=decision_id,
                        **row,
                    )
                )
            )
        return {"decisions": decisions, "record_count": len(decisions)}

    @staticmethod
    def _seed_decision_matches(
        decision: dict[str, Any], population: dict[str, Any]
    ) -> bool:
        return (
            decision.get("subject_id") == population.get("subject_id")
            and decision.get("group_name") == population.get("group_name")
            and abs(float(decision.get("income", -1)) - float(population.get("income", -2))) <= 1e-12
            and abs(float(decision.get("need_score", -1)) - float(population.get("need_score", -2))) <= 1e-12
            and abs(float(decision.get("prior_service", -1)) - float(population.get("prior_service", -2))) <= 1e-12
            and int(decision.get("expected_label", -1)) == int(population.get("expected_label", -2))
        )

    def allocation_fairness(self) -> dict[str, Any]:
        with self.services.store.read() as connection:
            rows = [
                row_dict(row)
                for row in connection.execute(
                    "SELECT * FROM allocation_decisions ORDER BY created_at, decision_id"
                )
            ]
        try:
            return self.services.models.fairness(rows)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    def simulate_user(self, request: UserSimulationRequest) -> dict[str, Any]:
        result = self.services.models.classify_safety(request.message)
        action = "contained" if result.label == "unsafe" else "delivered"
        created_at = now()
        try:
            with self.services.store.transaction() as connection:
                connection.execute(
                    "INSERT INTO user_simulations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        request.simulation_id,
                        request.user_id,
                        request.message,
                        result.label,
                        result.unsafe_probability,
                        action,
                        result.model_digest,
                        created_at,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise HTTPException(
                status_code=409, detail="user simulation conflicts"
            ) from error
        return {
            "simulation_id": request.simulation_id,
            "safety_label": result.label,
            "unsafe_probability": result.unsafe_probability,
            "action": action,
            "classifier_digest": result.model_digest,
            "created_at": created_at,
        }

    def put_budget(self, actor: str, request: BudgetRequest) -> dict[str, Any]:
        updated_at = now()
        with self.services.store.transaction() as connection:
            spent = connection.execute(
                "SELECT spent_microunits FROM budgets WHERE actor=?", (actor,)
            ).fetchone()
            spent_value = int(spent["spent_microunits"]) if spent is not None else 0
            if spent_value > request.limit_microunits:
                raise HTTPException(
                    status_code=409, detail="new limit is below current spend"
                )
            connection.execute(
                "INSERT INTO budgets VALUES (?, ?, ?, ?) "
                "ON CONFLICT(actor) DO UPDATE SET limit_microunits=excluded.limit_microunits, "
                "updated_at=excluded.updated_at",
                (actor, request.limit_microunits, spent_value, updated_at),
            )
        return {
            "actor": actor,
            "limit_microunits": request.limit_microunits,
            "spent_microunits": spent_value,
            "remaining_microunits": request.limit_microunits - spent_value,
            "updated_at": updated_at,
        }

    def meter_cost(self, request: CostEventRequest) -> dict[str, Any]:
        cost = self.services.cost_rates.calculate(
            request.input_tokens, request.output_tokens, request.compute_ms
        )
        created_at = now()
        try:
            with self.services.store.transaction() as connection:
                budget = connection.execute(
                    "SELECT * FROM budgets WHERE actor=?", (request.actor,)
                ).fetchone()
                if budget is None:
                    raise HTTPException(
                        status_code=404, detail="synthetic budget not found"
                    )
                next_spend = int(budget["spent_microunits"]) + cost
                if next_spend > int(budget["limit_microunits"]):
                    raise HTTPException(
                        status_code=409, detail="synthetic budget exceeded"
                    )
                connection.execute(
                    "INSERT INTO cost_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        request.event_id,
                        request.actor,
                        request.producer_id,
                        request.input_tokens,
                        request.output_tokens,
                        request.compute_ms,
                        cost,
                        created_at,
                    ),
                )
                connection.execute(
                    "UPDATE budgets SET spent_microunits=?, updated_at=? WHERE actor=?",
                    (next_spend, created_at, request.actor),
                )
        except sqlite3.IntegrityError as error:
            raise HTTPException(
                status_code=409, detail="cost event conflicts"
            ) from error
        return {
            "event_id": request.event_id,
            "synthetic_cost_microunits": cost,
            "spent_microunits": next_spend,
            "remaining_microunits": int(budget["limit_microunits"]) - next_spend,
            "created_at": created_at,
        }

    def get_budget(self, actor: str) -> dict[str, Any]:
        with self.services.store.read() as connection:
            record = connection.execute(
                "SELECT * FROM budgets WHERE actor=?", (actor,)
            ).fetchone()
        if record is None:
            raise HTTPException(status_code=404, detail="synthetic budget not found")
        result = row_dict(record)
        result["remaining_microunits"] = (
            result["limit_microunits"] - result["spent_microunits"]
        )
        return result

    def put_availability_target(
        self, target_id: str, request: AvailabilityTargetRequest
    ) -> dict[str, Any]:
        if target_id != request.target_id:
            raise HTTPException(status_code=422, detail="target id mismatch")
        created_at = now()
        with self.services.store.transaction() as connection:
            connection.execute(
                "INSERT INTO availability_targets VALUES (?, ?, ?, ?, ?, 0, ?) "
                "ON CONFLICT(target_id) DO UPDATE SET name=excluded.name, "
                "probe_url=excluded.probe_url, recovery_url=excluded.recovery_url, "
                "recovery_after=excluded.recovery_after, consecutive_failures=0",
                (
                    target_id,
                    request.name,
                    request.probe_url,
                    request.recovery_url or None,
                    request.recovery_after,
                    created_at,
                ),
            )
        return {
            "target_id": target_id,
            "probe_url": request.probe_url,
            "recovery_url": request.recovery_url or None,
            "recovery_after": request.recovery_after,
            "created_at": created_at,
        }

    def availability_history(self, target_id: str) -> dict[str, Any]:
        with self.services.store.read() as connection:
            target = connection.execute(
                "SELECT * FROM availability_targets WHERE target_id=?", (target_id,)
            ).fetchone()
            samples = [
                row_dict(row)
                for row in connection.execute(
                    "SELECT * FROM availability_samples WHERE target_id=? ORDER BY occurred_at, sample_id",
                    (target_id,),
                )
            ]
            recoveries = [
                row_dict(row)
                for row in connection.execute(
                    "SELECT * FROM recovery_events WHERE target_id=? ORDER BY occurred_at, recovery_id",
                    (target_id,),
                )
            ]
        if target is None:
            raise HTTPException(status_code=404, detail="availability target not found")
        return {
            "target": row_dict(target),
            "samples": samples,
            "recoveries": recoveries,
        }


def create_app(
    data_root: Path | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    root = data_root or Path(
        os.environ.get(
            "PLATFORM_IMPACT_DATA_ROOT", "/var/lib/keplerops-platform-impact"
        )
    )
    services = PlatformServices(root, transport)
    operations = ImpactOperations(services)
    application = FastAPI(title="KeplerOps Contained Impact Platform", version="1.0.0")
    application.state.services = services

    def require_admin(
        x_platform_admin_token: Annotated[str | None, Header()] = None,
    ) -> None:
        expected = os.environ.get(
            "PLATFORM_IMPACT_ADMIN_TOKEN", "platform-impact-admin-synthetic"
        )
        if not x_platform_admin_token or not hmac.compare_digest(
            x_platform_admin_token, expected
        ):
            raise HTTPException(
                status_code=401, detail="operator authorization required"
            )

    @application.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/readyz", responses=READY_RESPONSES)
    def readiness() -> dict[str, Any]:
        if not services.ready():
            raise HTTPException(status_code=503, detail="platform is not ready")
        return {
            "status": "ready",
            "schema_version": "1",
            "allocation_model_digest": services.models.allocation_digest,
            "safety_classifier_digest": services.models.safety_digest,
        }

    @application.post(
        "/v1/admin/reset",
        dependencies=[Depends(require_admin)],
        responses=AUTH_RESPONSES,
    )
    def reset() -> dict[str, str]:
        services.store.reset()
        return {"status": "reset", "seed_timestamp": SEED_TIMESTAMP}

    @application.post(
        "/v1/ledger/transactions", status_code=201, responses=LEDGER_RESPONSES
    )
    def post_ledger(request: LedgerPost) -> dict[str, Any]:
        return operations.post_ledger(request)

    @application.get("/v1/ledger")
    def ledger() -> dict[str, Any]:
        return operations.ledger()

    @application.post(
        "/v1/publications", status_code=201, responses=PUBLICATION_RESPONSES
    )
    def publish(request: PublicationPost) -> dict[str, Any]:
        return operations.publish(request)

    @application.delete(
        "/v1/publications/{publication_id}", responses=PUBLICATION_RESPONSES
    )
    def remove_publication(publication_id: Identifier) -> dict[str, Any]:
        return operations.remove_publication(publication_id)

    @application.get("/v1/publications")
    def publications(
        active_only: Annotated[bool, Query()] = True,
    ) -> dict[str, Any]:
        return operations.publications(active_only)

    @application.get(
        "/v1/reputation/{subject}",
        responses={404: {"description": "The reputation subject does not exist"}},
    )
    def reputation(subject: Identifier) -> dict[str, Any]:
        return operations.reputation(subject)

    @application.post(
        "/v1/allocations",
        status_code=201,
        responses={409: ALLOCATION_RESPONSES[409]},
    )
    def allocate(request: AllocationRequest) -> dict[str, Any]:
        return operations.persist_allocation(request)

    @application.post(
        "/v1/allocations/seeded-cohort",
        dependencies=[Depends(require_admin)],
        responses={
            401: AUTH_RESPONSES[401],
            409: ALLOCATION_RESPONSES[409],
        },
    )
    def allocate_seeded_cohort() -> dict[str, Any]:
        return operations.allocate_seeded_cohort()

    @application.get(
        "/v1/allocations/fairness",
        responses={409: ALLOCATION_RESPONSES[409]},
    )
    def allocation_fairness() -> dict[str, Any]:
        return operations.allocation_fairness()

    @application.post(
        "/v1/users/simulations",
        status_code=201,
        responses={409: ALLOCATION_RESPONSES[409]},
    )
    def simulate_user(request: UserSimulationRequest) -> dict[str, Any]:
        return operations.simulate_user(request)

    @application.put(
        "/v1/budgets/{actor}",
        dependencies=[Depends(require_admin)],
        responses={
            401: AUTH_RESPONSES[401],
            404: BUDGET_RESPONSES[404],
            409: BUDGET_RESPONSES[409],
        },
    )
    def put_budget(actor: Identifier, request: BudgetRequest) -> dict[str, Any]:
        return operations.put_budget(actor, request)

    @application.post(
        "/v1/cost/events",
        status_code=201,
        responses={
            404: BUDGET_RESPONSES[404],
            409: BUDGET_RESPONSES[409],
        },
    )
    def meter_cost(request: CostEventRequest) -> dict[str, Any]:
        return operations.meter_cost(request)

    @application.get("/v1/budgets/{actor}", responses={404: BUDGET_RESPONSES[404]})
    def get_budget(actor: Identifier) -> dict[str, Any]:
        return operations.get_budget(actor)

    @application.put(
        "/v1/availability/targets/{target_id}",
        dependencies=[Depends(require_admin)],
        responses=AVAILABILITY_RESPONSES,
    )
    def put_availability_target(
        target_id: Identifier, request: AvailabilityTargetRequest
    ) -> dict[str, Any]:
        return operations.put_availability_target(target_id, request)

    @application.post(
        "/v1/availability/targets/{target_id}/sample",
        dependencies=[Depends(require_admin)],
        responses=AVAILABILITY_RESPONSES,
    )
    async def sample_availability(target_id: Identifier) -> dict[str, Any]:
        return await services.probe(target_id)

    @application.get(
        "/v1/availability/targets/{target_id}/history",
        responses={404: {"description": "The availability target does not exist"}},
    )
    def availability_history(target_id: Identifier) -> dict[str, Any]:
        return operations.availability_history(target_id)

    return application


app = create_app()
