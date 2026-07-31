from __future__ import annotations

from domain import EvidenceEvent
from domain import SessionClaims
from domain import issue_penr1_receipt
from domain import verify_penr1_receipt
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _database, _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import CONFIG, ERROR_RESPONSES, NOT_FOUND, PROOF_CONTRACT_UNAVAILABLE, SHA256_PREFIX, _regular_owner_file
from keplerops_runtime.foundation.contracts import _flag_contracts, _oracle_contract, _realized_challenge_contracts
from keplerops_runtime.foundation.telemetry import _observe
from keplerops_runtime.proof import ReceiptVerificationRequest
from pathlib import Path
from typing import Annotated
import hashlib
import hmac
import json
import time

router = APIRouter()


@router.post("/v1/receipts/{flag_id}", responses=ERROR_RESPONSES)
def receipt(flag_id: str, session: Annotated[SessionClaims, Depends(_session)]) -> dict[str, str]:
    _require_role("proof")
    generation = _require_ready()
    contracts = _flag_contracts()
    if flag_id not in contracts:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    contract = contracts[flag_id]
    if not isinstance(contract, dict):
        raise HTTPException(status_code=503, detail=PROOF_CONTRACT_UNAVAILABLE)
    oracle = _oracle_contract()
    signing_key_file = CONFIG.get("signing_key_file")
    if not isinstance(signing_key_file, str):
        raise HTTPException(status_code=503, detail="receipt unavailable")
    signing_key = _regular_owner_file(Path(signing_key_file))
    now = int(time.time())
    with _database() as connection:
        rows = connection.execute(
            "SELECT evidence_id FROM evidence WHERE range_instance=? AND participant=? "
            "AND reset_generation=? AND expires_at>=?",
            (session.range_instance, session.participant, generation, now),
        ).fetchall()
        recorded = {row[0] for row in rows}
        if contract.get("outcome") == "ai-capstone" and contract.get("evidence") == "ev-capstone-receipt":
            prerequisite = set(oracle.required_evidence("ai-capstone")) - {"ev-capstone-receipt"}
            if prerequisite <= recorded:
                digest = SHA256_PREFIX + hmac.new(
                    signing_key,
                    f"{session.range_instance}:{session.participant}:{generation}:ai-capstone".encode(),
                    hashlib.sha256,
                ).hexdigest()
                derived = EvidenceEvent.from_mapping(
                    {
                        "actor_role": "proof-service",
                        "asset_id": "telemetry-proof-01",
                        "digest": digest,
                        "event_kind": "objective_verdict",
                        "object_id": "ai-capstone",
                        "outcome_id": "ai-capstone",
                        "participant": session.participant,
                        "range_instance": session.range_instance,
                        "record_count": len(recorded),
                        "status": "passed",
                        "timestamp": now,
                    },
                    safe_fields=set(CONFIG["safe_fields"]),
                )
                evidence_id, expires_at = oracle.qualify_event(
                    derived,
                    producer_asset="telemetry-proof-01",
                    submitted_generation=generation,
                    current_generation=generation,
                    now=now,
                )
                connection.execute(
                    "INSERT OR REPLACE INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        session.range_instance,
                        session.participant,
                        "ai-capstone",
                        evidence_id,
                        generation,
                        "telemetry-proof-01",
                        now,
                        expires_at,
                        json.dumps(derived.values, separators=(",", ":"), sort_keys=True),
                    ),
                )
                recorded.add(evidence_id)
    realized = _realized_challenge_contracts()
    realized_by_flag = {row["flag_id"]: row for row in realized.values()}
    if flag_id in realized_by_flag:
        challenge = realized_by_flag[flag_id]
        prerequisite_evidence = {
            contracts[realized[prerequisite]["flag_id"]]["evidence"]
            for prerequisite in challenge["prerequisites"]
        }
        satisfied = (
            contract.get("evidence") in recorded
            and prerequisite_evidence <= recorded
        )
    else:
        satisfied = oracle.satisfied(contract.get("outcome"), recorded)
    if not satisfied:
        raise HTTPException(status_code=409, detail="objective not satisfied")
    token = issue_penr1_receipt(
        contract=contract,
        binding={
            "range_instance": session.range_instance,
            "participant": session.participant,
            "reset_generation": generation,
        },
        signing_key=signing_key,
        now=now,
        ttl_seconds=900,
    )
    _observe(
        session,
        event_name="receipt.issued",
        outcome_id=str(contract["outcome"]),
        status="passed",
        record_count=1,
    )
    return {"receipt": token}

@router.post("/v1/receipts/{flag_id}/verify", responses=ERROR_RESPONSES)
def verify_submitted_receipt(
    flag_id: str,
    request: ReceiptVerificationRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, bool]:
    _require_role("proof")
    generation = _require_ready()
    contracts = _flag_contracts()
    signing_key_file = CONFIG.get("signing_key_file")
    if flag_id not in contracts:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    contract = contracts[flag_id]
    if not isinstance(contract, dict) or not isinstance(signing_key_file, str):
        raise HTTPException(status_code=503, detail="receipt unavailable")
    valid = verify_penr1_receipt(
        token=request.receipt,
        contract=contract,
        binding={
            "range_instance": session.range_instance,
            "participant": session.participant,
            "reset_generation": generation,
        },
        verification_key=_regular_owner_file(Path(signing_key_file)),
        now=int(time.time()),
    )
    return {"valid": valid}
