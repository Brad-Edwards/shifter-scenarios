"""Golden-range acceptance for Cinder's native Shifter event delivery.

This file is copied into the current Shifter platform test tree by
``check-golden-gcp.sh``. It intentionally depends on Shifter's real pytest
fixtures and is not part of this repository's local unit-test collection.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone

from ctf.content_bundle import parse_ctf_content_bundle
from ctf.enums import EventStatus, ParticipantStatus
from ctf.models import CTFChallenge, CTFEvent, CTFParticipant
from ctf.services.content_hydration import hydrate_event_ctf_content
from ctf.services.content_resolution import HydrationSourceEvidence, ResolvedCtfContent
from ctf.services.submission import submit_flag
from management.services import set_active_ctf_event
from shared.principal_port import principal_for_user
from tests.ctf._api_flow_helpers import call_json
from tests.ctf.conftest import individual_event_scope


def _bundle_path() -> Path:
    value = os.environ.get("CINDER_EVENT_BUNDLE", "")
    if not value:
        raise RuntimeError("CINDER_EVENT_BUNDLE is required")
    return Path(value)


@pytest.mark.django_db
def test_cinder_native_import_participant_api_and_score(
    organizer_user,
    participant_user,
    authenticated_participant_client,
    monkeypatch,
) -> None:
    raw = _bundle_path().read_bytes()
    payload = json.loads(raw)
    bundle = parse_ctf_content_bundle(raw)
    digest = hashlib.sha256(raw).hexdigest()
    resolved = ResolvedCtfContent(
        bundle=bundle,
        evidence=HydrationSourceEvidence(
            reference_contract="shifter-ctf-content-references/v1",
            declared_digest=f"sha256:{digest}",
            object_key_fingerprint=hashlib.sha256(b"cinder-golden-bundle").hexdigest(),
            object_identity_fingerprint=digest,
            object_size_bytes=len(raw),
        ),
    )
    now = timezone.now()
    event = CTFEvent.objects.create(
        name="Cinder delivery golden acceptance",
        created_by=organizer_user,
        **individual_event_scope(organizer_user),
        status=EventStatus.DRAFT.value,
        event_start=now - timedelta(minutes=5),
        event_end=now + timedelta(hours=1),
        scenario_id="cinder-typhoon",
    )

    result = hydrate_event_ctf_content(event.pk, resolved, actor_id=organizer_user.pk)
    assert result.created is True
    assert result.challenge_count == 240
    assert result.flag_count == 240
    assert result.hint_count == 720
    assert result.prerequisite_count == 0

    imported = list(CTFChallenge.objects.filter(event=event).order_by("order"))
    expected = payload["challenges"]
    assert [(row.source_id, row.name, row.points) for row in imported] == [
        (row["id"], row["name"], row["points"]) for row in expected
    ]
    assert sum(row.points for row in imported) == 39_200

    event.status = EventStatus.ACTIVE.value
    event.save(update_fields=["status"])
    participant = CTFParticipant.objects.create(
        event=event,
        user=participant_user,
        principal_uuid=principal_for_user(participant_user).uuid,
        email=participant_user.email,
        name="Cinder Golden Participant",
        status=ParticipantStatus.ACTIVE.value,
        registered_at=now,
    )
    set_active_ctf_event(participant_user, event.pk)

    response = call_json(authenticated_participant_client, "get", "api_participant_challenges")
    assert response.status_code == 200
    displayed = response.json()
    assert {row["name"]: row["points"] for row in displayed} == {
        row["name"]: row["points"] for row in expected
    }
    assert len(displayed) == 240
    assert sum(row["points"] for row in displayed) == 39_200
    assert all("flags" not in row and "solution" not in row for row in displayed)

    scorer_requests = []

    class GoldenResponse:
        status = 200

        @staticmethod
        def read(_limit: int) -> bytes:
            return b'{"valid": true}'

    class GoldenConnection:
        def request(self, method, path, body=None, headers=None) -> None:
            scorer_requests.append((method, path, body, headers))

        @staticmethod
        def getresponse() -> GoldenResponse:
            return GoldenResponse()

        @staticmethod
        def close() -> None:
            return None

    monkeypatch.setattr(
        "ctf.validators.socket.getaddrinfo",
        lambda *_args, **_kwargs: [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("93.184.216.34", 443),
            )
        ],
    )
    monkeypatch.setattr(
        "ctf.validators._build_https_connection",
        lambda **_kwargs: GoldenConnection(),
    )
    challenge = imported[0]
    submission = submit_flag(participant.pk, challenge.pk, "golden-range-evidence")
    assert submission.is_correct is True
    assert submission.points_awarded == challenge.points
    assert len(scorer_requests) == 1
    method, path, body, headers = scorer_requests[0]
    assert method == "POST"
    assert path == "/v1/objectives/t01.1/verify"
    assert json.loads(body) == {
        "flag": "golden-range-evidence",
        "challenge_id": str(challenge.pk),
    }
    expected_revision = payload["challenges"][0]["flags"][0]["headers"][
        "X-Cinder-Catalog-Revision"
    ]
    assert headers["X-Cinder-Catalog-Revision"] == expected_revision
    participant.refresh_from_db()
    assert participant.cached_score == challenge.points
    assert participant.cached_solve_count == 1

    response = call_json(authenticated_participant_client, "get", "api_participant_challenges")
    assert response.status_code == 200
    solved = {row["name"]: row["solved"] for row in response.json()}
    assert solved[challenge.name] is True
