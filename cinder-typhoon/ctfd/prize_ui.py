"""Render Cinder Typhoon prize views over the authenticated claim service."""

from __future__ import annotations

import html
import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]


def _load_claims() -> Any:
    path = ROOT / "ctfd" / "prize_claims.py"
    name = "cinder_prize_claims_ui"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


prize_claims = _load_claims()
AuthenticatedEventStaff = prize_claims.AuthenticatedEventStaff
AuthenticatedParticipant = prize_claims.AuthenticatedParticipant
PrizeClaimService = prize_claims.PrizeClaimService
build_claim_config = prize_claims.build_claim_config


class PrizeUIError(ValueError):
    """A prize page cannot be rendered without weakening its trust boundary."""


def _text(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _csrf(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise PrizeUIError("a bounded integration CSRF token is required")
    return value


def _request_id(value: Any) -> str:
    if not isinstance(value, str):
        raise PrizeUIError("an integration request UUID is required")
    try:
        return str(UUID(value))
    except (AttributeError, ValueError) as error:
        raise PrizeUIError("an integration request UUID is required") from error


class PrizeEventUI:
    """Thin HTML adapter; authentication and HTTP controls stay upstream."""

    def __init__(self, service: Any) -> None:
        required = ("participant_prize", "dashboard", "claim")
        if not all(callable(getattr(service, name, None)) for name in required):
            raise PrizeUIError("a prize claim service is required")
        self.service = service

    def participant_page(
        self,
        context: AuthenticatedParticipant,
        *,
        issue_code: bool = False,
        now: datetime | str | None = None,
    ) -> str:
        """Render only the authenticated participant's current prize."""

        view = self.service.participant_prize(
            context,
            issue_code=issue_code,
            now=now,
        )
        claim_block = ""
        if view["claim_code"] is not None:
            claim_block = (
                '<section aria-labelledby="claim-code-heading">'
                '<h2 id="claim-code-heading">Claim code</h2>'
                f'<output id="claim-code">{_text(view["claim_code"])}</output>'
                f'<div id="claim-qr" data-qr-payload="{_text(view["qr_payload"])}" '
                'aria-label="Claim QR payload"></div>'
                f'<p>Expires <time datetime="{_text(view["expires_at"])}">'
                f"{_text(view['expires_at'])}</time></p></section>"
            )
        claimed_block = ""
        if view["claim_status"] == "claimed":
            claimed_block = (
                f"<p>Pack <strong>{_text(view['pack_number'])}</strong> collected "
                f'<time datetime="{_text(view["claimed_at"])}">'
                f"{_text(view['claimed_at'])}</time>.</p>"
            )
        return (
            '<main data-contract="cinder-typhoon.participant-prize-ui/v1">'
            "<h1>Your event prize</h1>"
            f'<p class="award-name">{_text(view["award_name"])}</p>'
            f'<p class="claim-status">Status: {_text(view["claim_status"])}</p>'
            f"{claimed_block}{claim_block}</main>"
        )

    def operator_page(
        self,
        staff: AuthenticatedEventStaff,
        *,
        csrf_token: str,
        request_id: str,
    ) -> str:
        """Render the authorized 50-slot dashboard and claim form."""

        csrf_token = _csrf(csrf_token)
        request_id = _request_id(request_id)
        dashboard = self.service.dashboard(staff)
        rows = []
        for row in dashboard["slots"]:
            rows.append(
                "<tr>"
                f'<th scope="row">{_text(row["slot_id"])}</th>'
                f"<td>{_text(row['award_name'])}</td>"
                f"<td>{_text(row['trigger_status'])}</td>"
                f"<td>{_text(row['trigger'])}</td>"
                f"<td>{_text(row['selected_alias'])}</td>"
                f"<td>{_text(row['notification_state'])}</td>"
                f"<td>{_text(row['pack_number'])}</td>"
                f"<td>{_text(row['claimed_at'])}</td>"
                f"<td>{_text(row['allocation_state'])}</td>"
                "</tr>"
            )
        errors = "".join(f"<li>{_text(error)}</li>" for error in dashboard["errors"])
        return (
            '<main data-contract="cinder-typhoon.prize-operator-ui/v1">'
            "<h1>Event prize handover</h1>"
            f'<ul id="fail-closed-errors">{errors}</ul>'
            '<form method="post" action="/event-staff/prizes/claim">'
            f'<input type="hidden" name="csrf_token" value="{_text(csrf_token)}">'
            '<label>Claim code <input name="claim_code" required autocomplete="off"></label>'
            '<label>Pack number <input name="pack_number" type="number" min="1" '
            'max="50" required></label>'
            f'<input type="hidden" name="request_id" value="{_text(request_id)}">'
            '<button type="submit">Confirm handover</button></form>'
            "<table><caption>All 50 prize slots</caption><thead><tr>"
            '<th scope="col">Slot</th><th scope="col">Award</th>'
            '<th scope="col">Trigger status</th><th scope="col">Trigger</th>'
            '<th scope="col">Selected alias</th><th scope="col">Notification</th>'
            '<th scope="col">Pack</th><th scope="col">Claimed</th>'
            f'<th scope="col">Allocation</th></tr></thead><tbody>{"".join(rows)}'
            "</tbody></table></main>"
        )

    def claim_receipt(
        self,
        staff: AuthenticatedEventStaff,
        *,
        claim_code: str,
        pack_number: int,
        request_id: str,
        now: datetime | str | None = None,
    ) -> str:
        """Apply one atomic claim and render its staff confirmation."""

        receipt = self.service.claim(
            staff,
            claim_code=claim_code,
            pack_number=pack_number,
            request_id=request_id,
            now=now,
        )
        return (
            '<main data-contract="cinder-typhoon.prize-claim-ui-receipt/v1">'
            "<h1>Prize handover recorded</h1>"
            f'<p class="participant-alias">{_text(receipt["participant_alias"])}</p>'
            f'<p class="award-name">{_text(receipt["award_name"])}</p>'
            f"<p>Pack <strong>{_text(receipt['pack_number'])}</strong></p>"
            f'<time datetime="{_text(receipt["claimed_at"])}">'
            f"{_text(receipt['claimed_at'])}</time></main>"
        )


__all__ = [
    "AuthenticatedEventStaff",
    "AuthenticatedParticipant",
    "PrizeClaimService",
    "PrizeEventUI",
    "PrizeUIError",
    "build_claim_config",
]
