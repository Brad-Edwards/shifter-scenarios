"""Authenticated edge procurement, inventory, capability, and attestation API."""

import json
import os
import secrets
import sqlite3
import uuid
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from edge_state import (
    EVENT_SCHEMA_VERSION,
    SCHEMA_VERSION,
    EdgeStore,
    canonical_json,
    now,
)


DEFAULT_ADMIN_TOKEN = "keplerops-edge-registry-admin"
ADMIN_HEADER = "X-Edge-Registry-Token"
IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9._-]{2,63}$"
MAX_CONTENT_BYTES = 65_536
UNAUTHORIZED_RESPONSE = {"description": "Missing or invalid edge registry credential"}
NOT_FOUND_RESPONSE = {
    "description": "Requested procurement or device record was not found"
}
CONFLICT_RESPONSE = {
    "description": "Requested transition conflicts with registry state"
}
PAYLOAD_TOO_LARGE_RESPONSE = {
    "description": "Structured content exceeds the bounded size"
}
SERVICE_UNAVAILABLE_RESPONSE = {"description": "Edge registry state is unavailable"}
UNKNOWN_PROCUREMENT_ORDER = "unknown procurement order"
ORDER_TRANSITIONS = {
    "requested": {"approved", "cancelled"},
    "approved": {"ordered", "cancelled"},
    "ordered": {"received", "cancelled"},
    "received": set(),
    "cancelled": set(),
}


def _configured_token(
    *, file_variable: str, value_variable: str, synthetic_default: str
) -> str:
    if file_variable not in os.environ:
        return os.environ.get(value_variable, synthetic_default)
    configured_path = os.environ[file_variable]
    if not configured_path:
        raise RuntimeError(f"{file_variable} must name a readable, non-empty file")
    try:
        value = Path(configured_path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise RuntimeError(
            f"{file_variable} must name a readable, non-empty file"
        ) from error
    if value.endswith("\r\n"):
        value = value[:-2]
    elif value.endswith("\n"):
        value = value[:-1]
    if not value:
        raise RuntimeError(f"{file_variable} must name a readable, non-empty file")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProcurementRequest(StrictModel):
    order_id: str = Field(pattern=IDENTIFIER_PATTERN)
    vendor: str = Field(min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=128)
    quantity: int = Field(ge=1, le=64)
    notes: str = Field(default="", max_length=4096)


class ProcurementTransition(StrictModel):
    state: Literal["approved", "ordered", "received", "cancelled"]


class DeviceEnrollment(StrictModel):
    device_id: str = Field(pattern=IDENTIFIER_PATTERN)
    order_id: str = Field(pattern=IDENTIFIER_PATTERN)
    manufacturer: str = Field(min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=128)
    serial_number: str = Field(min_length=1, max_length=256)
    inventory: dict[str, Any]
    claimed_capabilities: dict[str, Any]
    attestation: dict[str, Any] | None = None


class DeviceObservation(StrictModel):
    inventory: dict[str, Any] | None = None
    claimed_capabilities: dict[str, Any] | None = None
    attestation: dict[str, Any] | None = None
    source: str = Field(min_length=1, max_length=128)


def _bounded_payload(value: Any) -> str:
    serialized = canonical_json(value)
    if len(serialized.encode("utf-8")) > MAX_CONTENT_BYTES:
        raise HTTPException(
            status_code=413, detail="structured content exceeds 65536 bytes"
        )
    return serialized


def _order_response(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _device_response(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["inventory"] = json.loads(result.pop("inventory_json"))
    result["claimed_capabilities"] = json.loads(result.pop("capabilities_json"))
    attestation = result.pop("attestation_json")
    result["attestation"] = json.loads(attestation) if attestation else None
    result["verified"] = False
    return result


def _ready_response(store: EdgeStore) -> dict[str, Any]:
    if not store.ready():
        raise HTTPException(status_code=503, detail="state store is not ready")
    return {
        "status": "ready",
        "schema_version": SCHEMA_VERSION,
        "event_schema_version": EVENT_SCHEMA_VERSION,
        "registered_devices": store.device_count(),
        "verified_physical_accelerators": 0,
        "hardware_constraint": "unsatisfied",
    }


def _reset_response(store: EdgeStore) -> dict[str, Any]:
    store.reset()
    return {
        "status": "reset",
        "registered_devices": 0,
        "verified_physical_accelerators": 0,
        "hardware_constraint": "unsatisfied",
    }


def _create_order(store: EdgeStore, request: ProcurementRequest) -> dict[str, Any]:
    payload = request.model_dump()
    _bounded_payload(payload)
    created_at = now()
    try:
        with store.transaction() as connection:
            connection.execute(
                "INSERT INTO procurement_orders "
                "(order_id, vendor, model, quantity, state, notes, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'requested', ?, ?, ?)",
                (
                    request.order_id,
                    request.vendor,
                    request.model,
                    request.quantity,
                    request.notes,
                    created_at,
                    created_at,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="procurement order already exists"
        ) from exc
    store.event(
        "edge.procurement.requested",
        "edge-registry",
        {"request": payload, "state": "requested"},
        request.order_id,
    )
    row = store.order(request.order_id)
    assert row is not None
    return _order_response(row)


def _transition_order(
    store: EdgeStore, order_id: str, request: ProcurementTransition
) -> dict[str, Any]:
    row = store.order(order_id)
    if row is None:
        raise HTTPException(status_code=404, detail=UNKNOWN_PROCUREMENT_ORDER)
    current = str(row["state"])
    if request.state not in ORDER_TRANSITIONS[current]:
        raise HTTPException(
            status_code=409,
            detail=f"cannot transition procurement order from {current} to {request.state}",
        )
    changed_at = now()
    with store.transaction() as connection:
        connection.execute(
            "UPDATE procurement_orders SET state=?, updated_at=? WHERE order_id=?",
            (request.state, changed_at, order_id),
        )
    store.event(
        "edge.procurement.transitioned",
        "edge-registry",
        {"order_id": order_id, "from_state": current, "to_state": request.state},
        order_id,
    )
    updated = store.order(order_id)
    assert updated is not None
    return _order_response(updated)


def _get_order(store: EdgeStore, order_id: str) -> dict[str, Any]:
    row = store.order(order_id)
    if row is None:
        raise HTTPException(status_code=404, detail=UNKNOWN_PROCUREMENT_ORDER)
    return _order_response(row)


def _enroll_device(store: EdgeStore, request: DeviceEnrollment) -> dict[str, Any]:
    full_request = request.model_dump()
    _bounded_payload(full_request)
    order = store.order(request.order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=UNKNOWN_PROCUREMENT_ORDER)
    if order["state"] != "received":
        raise HTTPException(status_code=409, detail="procurement order is not received")
    if request.manufacturer != order["vendor"] or request.model != order["model"]:
        raise HTTPException(
            status_code=409,
            detail="device manufacturer and model do not match its procurement order",
        )
    created_at = now()
    inventory_json = _bounded_payload(request.inventory)
    capabilities_json = _bounded_payload(request.claimed_capabilities)
    attestation_json = (
        _bounded_payload(request.attestation)
        if request.attestation is not None
        else None
    )
    try:
        with store.transaction() as connection:
            enrolled = connection.execute(
                "SELECT COUNT(*) AS count FROM devices WHERE order_id=?",
                (request.order_id,),
            ).fetchone()
            if int(enrolled["count"]) >= int(order["quantity"]):
                raise HTTPException(
                    status_code=409,
                    detail="procurement order quantity is already fully enrolled",
                )
            connection.execute(
                "INSERT INTO devices "
                "(device_id, order_id, manufacturer, model, serial_number, inventory_json, "
                "capabilities_json, attestation_json, physical_presence_state, "
                "capability_state, attestation_state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'reported_unverified', "
                "'reported_unverified', ?, ?, ?)",
                (
                    request.device_id,
                    request.order_id,
                    request.manufacturer,
                    request.model,
                    request.serial_number,
                    inventory_json,
                    capabilities_json,
                    attestation_json,
                    "received_unverified" if attestation_json else "not_provided",
                    created_at,
                    created_at,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="device identity already exists"
        ) from exc
    store.event(
        "edge.device.enrolled_unverified",
        "edge-registry",
        {
            "request": full_request,
            "physical_presence_state": "reported_unverified",
            "capability_state": "reported_unverified",
            "attestation_state": (
                "received_unverified"
                if request.attestation is not None
                else "not_provided"
            ),
            "verified": False,
        },
        request.device_id,
    )
    row = store.device(request.device_id)
    assert row is not None
    return _device_response(row)


def _record_observation(
    store: EdgeStore, device_id: str, request: DeviceObservation
) -> dict[str, Any]:
    device = store.device(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="unknown device")
    payload = request.model_dump()
    observation_json = _bounded_payload(payload)
    observation_id = f"edge-observation-{uuid.uuid4()}"
    observed_at = now()
    inventory_json = (
        _bounded_payload(request.inventory)
        if request.inventory is not None
        else device["inventory_json"]
    )
    capabilities_json = (
        _bounded_payload(request.claimed_capabilities)
        if request.claimed_capabilities is not None
        else device["capabilities_json"]
    )
    attestation_json = (
        _bounded_payload(request.attestation)
        if request.attestation is not None
        else device["attestation_json"]
    )
    with store.transaction() as connection:
        connection.execute(
            "INSERT INTO device_observations "
            "(observation_id, device_id, observation_json, created_at) VALUES (?, ?, ?, ?)",
            (observation_id, device_id, observation_json, observed_at),
        )
        connection.execute(
            "UPDATE devices SET inventory_json=?, capabilities_json=?, attestation_json=?, "
            "attestation_state=?, updated_at=? WHERE device_id=?",
            (
                inventory_json,
                capabilities_json,
                attestation_json,
                "received_unverified" if attestation_json else "not_provided",
                observed_at,
                device_id,
            ),
        )
    store.event(
        "edge.device.observed_unverified",
        "edge-registry",
        {
            "observation_id": observation_id,
            "device_id": device_id,
            "observation": payload,
            "physical_presence_state": "reported_unverified",
            "capability_state": "reported_unverified",
            "attestation_state": (
                "received_unverified" if attestation_json else "not_provided"
            ),
            "verified": False,
        },
        device_id,
    )
    updated = store.device(device_id)
    assert updated is not None
    return {"observation_id": observation_id, "device": _device_response(updated)}


def _get_device(store: EdgeStore, device_id: str) -> dict[str, Any]:
    row = store.device(device_id)
    if row is None:
        raise HTTPException(status_code=404, detail="unknown device")
    return _device_response(row)


def _events_response(store: EdgeStore, limit: int) -> dict[str, Any]:
    with store.read() as connection:
        rows = connection.execute(
            "SELECT * FROM structured_events ORDER BY occurred_at, event_id LIMIT ?",
            (limit,),
        ).fetchall()
    result = []
    for row in rows:
        event = dict(row)
        event["payload"] = json.loads(event.pop("payload_json"))
        result.append(event)
    return {"schema_version": EVENT_SCHEMA_VERSION, "events": result}


def create_app(data_root: Path | None = None) -> FastAPI:
    root = data_root or Path(
        os.environ.get("EDGE_REGISTRY_DATA_ROOT", "/var/lib/keplerops-edge-registry")
    )
    admin_token = _configured_token(
        file_variable="EDGE_REGISTRY_ADMIN_TOKEN_FILE",
        value_variable="EDGE_REGISTRY_ADMIN_TOKEN",
        synthetic_default=DEFAULT_ADMIN_TOKEN,
    )
    store = EdgeStore(root)
    application = FastAPI(
        title="KeplerOps Edge Procurement and Device Registry",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.store = store

    def require_admin(
        supplied: Annotated[str | None, Header(alias=ADMIN_HEADER)] = None,
    ) -> None:
        if supplied is None or not secrets.compare_digest(supplied, admin_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized"
            )

    AdminAuthorization = Annotated[None, Depends(require_admin)]

    @application.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get(
        "/readyz",
        responses={401: UNAUTHORIZED_RESPONSE, 503: SERVICE_UNAVAILABLE_RESPONSE},
    )
    def ready(_authorized: AdminAuthorization) -> dict[str, Any]:
        return _ready_response(store)

    @application.post("/v1/admin/reset", responses={401: UNAUTHORIZED_RESPONSE})
    def reset(_authorized: AdminAuthorization) -> dict[str, Any]:
        return _reset_response(store)

    @application.post(
        "/v1/procurement/orders",
        status_code=201,
        responses={
            401: UNAUTHORIZED_RESPONSE,
            409: CONFLICT_RESPONSE,
            413: PAYLOAD_TOO_LARGE_RESPONSE,
        },
    )
    def create_order(
        request: ProcurementRequest,
        _authorized: AdminAuthorization,
    ) -> dict[str, Any]:
        return _create_order(store, request)

    @application.post(
        "/v1/procurement/orders/{order_id}/transition",
        responses={
            401: UNAUTHORIZED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            409: CONFLICT_RESPONSE,
        },
    )
    def transition_order(
        order_id: str,
        request: ProcurementTransition,
        _authorized: AdminAuthorization,
    ) -> dict[str, Any]:
        return _transition_order(store, order_id, request)

    @application.get(
        "/v1/procurement/orders/{order_id}",
        responses={401: UNAUTHORIZED_RESPONSE, 404: NOT_FOUND_RESPONSE},
    )
    def get_order(
        order_id: str,
        _authorized: AdminAuthorization,
    ) -> dict[str, Any]:
        return _get_order(store, order_id)

    @application.post(
        "/v1/devices",
        status_code=201,
        responses={
            401: UNAUTHORIZED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            409: CONFLICT_RESPONSE,
            413: PAYLOAD_TOO_LARGE_RESPONSE,
        },
    )
    def enroll_device(
        request: DeviceEnrollment,
        _authorized: AdminAuthorization,
    ) -> dict[str, Any]:
        return _enroll_device(store, request)

    @application.post(
        "/v1/devices/{device_id}/observations",
        status_code=201,
        responses={
            401: UNAUTHORIZED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            413: PAYLOAD_TOO_LARGE_RESPONSE,
        },
    )
    def record_observation(
        device_id: str,
        request: DeviceObservation,
        _authorized: AdminAuthorization,
    ) -> dict[str, Any]:
        return _record_observation(store, device_id, request)

    @application.get(
        "/v1/devices/{device_id}",
        responses={401: UNAUTHORIZED_RESPONSE, 404: NOT_FOUND_RESPONSE},
    )
    def get_device(
        device_id: str,
        _authorized: AdminAuthorization,
    ) -> dict[str, Any]:
        return _get_device(store, device_id)

    @application.get("/v1/events", responses={401: UNAUTHORIZED_RESPONSE})
    def events(
        _authorized: AdminAuthorization,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> dict[str, Any]:
        return _events_response(store, limit)

    return application


app = create_app()
