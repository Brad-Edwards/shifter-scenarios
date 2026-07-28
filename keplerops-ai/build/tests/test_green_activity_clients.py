from __future__ import annotations

import json
import sys
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PACK_ROOT / "assets/services/keplerops-runtime"
sys.path.insert(0, str(RUNTIME_ROOT))

import httpx
from green_activity.clients import GreenServiceClients, GreenServiceConfig


def _response(request: httpx.Request) -> httpx.Response:
    routes = {
        ("GET", "https://repo-ticket-01.keplerops.lab/git/api/v1/user/repos"): [
            {"full_name": "ml.engineer/model-release"}
        ],
        ("GET", "https://notebook-runner-01.keplerops.lab:8888/api/status"): {
            "connections": 1,
        },
        (
            "GET",
            "http://model-registry-01.keplerops.lab:9000/api/2.0/mlflow/registered-models/search",
        ): {"registered_models": [{"name": "keplerops-teacher"}]},
        (
            "GET",
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity",
        ): "header.payload.signature",
        ("POST", "https://keplerops-model.example/v1/chat/completions"): {
            "choices": [{"message": {"content": "ready"}}],
            "usage": {"total_tokens": 19},
        },
    }
    key = (request.method, str(request.url.copy_with(query=None)))
    payload = routes[key]
    headers = {"Metadata-Flavor": "Google"} if "metadata.google.internal" in str(request.url) else {}
    return httpx.Response(
        200,
        headers=headers,
        content=payload if isinstance(payload, str) else json.dumps(payload),
        request=request,
    )


class FakeImap:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def login(self, username: str, password: str):
        assert username == "researcher@keplerops.test"
        assert password == "Researcher-Mail-2026!"
        return "OK", []

    def select(self, mailbox: str, readonly: bool = False):
        assert (mailbox, readonly) == ("INBOX", True)
        return "OK", [b"7"]

    def search(self, *_args):
        return "OK", [b"1 2 3 4 5 6 7"]


def test_green_service_config_uses_combined_internal_and_public_trust() -> None:
    config = GreenServiceConfig(
        workhub_url="https://workhub.example",
        mail_host="mail.example",
        registry_url="https://registry.example",
        model_url="https://model.example",
        model_identity_audience="https://model.example",
        jupyter_token_file=Path("/tmp/jupyter-token"),
    )

    assert config.ca_file == Path("/run/tls/combined-ca.crt")


def test_real_service_handlers_use_bounded_authenticated_product_reads(tmp_path: Path) -> None:
    token = tmp_path / "jupyter-token"
    token.write_text("synthetic-jupyter-token\n", encoding="utf-8")
    config = GreenServiceConfig(
        workhub_url="https://repo-ticket-01.keplerops.lab",
        mail_host="mail-server-01.keplerops.lab",
        notebook_url="https://notebook-runner-01.keplerops.lab:8888",
        registry_url="http://model-registry-01.keplerops.lab:9000",
        model_url="https://keplerops-model.example",
        model_identity_audience="https://keplerops-model.example",
        jupyter_token_file=token,
        ca_file=Path("/etc/ssl/certs/ca-certificates.crt"),
    )
    with httpx.Client(transport=httpx.MockTransport(_response)) as client:
        services = GreenServiceClients(
            config,
            http_client=client,
            imap_factory=lambda *_args, **_kwargs: FakeImap(),
        )
        executor = services.executor()
        observations = {
            action: executor.execute(action)
            for action in sorted(executor.action_addresses)
        }

    assert {item.status for item in observations.values()} == {"succeeded"}
    assert observations[
        "participant.action-contract.activity.green-inference-smoke-request"
    ].measurements == {"inference_tokens": 19}
    assert all(len(item.observation) <= 256 for item in observations.values())
    assert all(len(item.evidence_refs) == 1 for item in observations.values())


def test_config_loads_only_green_runtime_inputs(tmp_path: Path) -> None:
    config_file = tmp_path / "runtime.yaml"
    config_file.write_text(
        """
workhub_url: https://repo-ticket-01.keplerops.lab
mail_host: mail-server-01.keplerops.lab
registry_url: http://model-registry-01.keplerops.lab:9000
model_url: https://keplerops-model.example
model_identity_audience: https://keplerops-model.example
""",
        encoding="utf-8",
    )

    config = GreenServiceConfig.from_runtime_config(
        config_file,
        jupyter_token_file=tmp_path / "token",
    )

    assert config.notebook_url == "https://notebook-runner-01.keplerops.lab:8888"
    assert not hasattr(config, "proof_url")
    assert not hasattr(config, "signing_key_file")
