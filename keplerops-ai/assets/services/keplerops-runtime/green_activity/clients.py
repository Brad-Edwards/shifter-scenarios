"""Least-privileged clients for ordinary green workforce reads."""

from __future__ import annotations

import imaplib
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml

from .actions import GreenActionExecutor, GreenActionObservation

WORKHUB_ACTION = "participant.action-contract.activity.green-workhub-ticket-triage"
MAIL_ACTION = "participant.action-contract.activity.green-mail-thread-review"
NOTEBOOK_ACTION = "participant.action-contract.activity.green-notebook-evaluation-check"
REGISTRY_ACTION = "participant.action-contract.activity.green-mlflow-model-review"
INFERENCE_ACTION = "participant.action-contract.activity.green-inference-smoke-request"
METADATA_IDENTITY_URL = (
    "http://metadata.google.internal/computeMetadata/v1/"
    "instance/service-accounts/default/identity"
)


@dataclass(frozen=True)
class GreenServiceConfig:
    workhub_url: str
    mail_host: str
    registry_url: str
    model_url: str
    model_identity_audience: str
    jupyter_token_file: Path
    notebook_url: str = "https://notebook-runner-01.keplerops.lab:8888"
    ca_file: Path = Path("/run/tls/combined-ca.crt")
    workhub_username: str = "ml.engineer"
    workhub_password: str = "KeplerOps-Engineer-355!"  # NOSONAR - synthetic range credential
    mail_username: str = "researcher@keplerops.test"
    mail_password: str = "Researcher-Mail-2026!"  # NOSONAR - synthetic range credential

    @classmethod
    def from_runtime_config(
        cls,
        path: Path,
        *,
        jupyter_token_file: Path = Path("/run/keplerops/jupyter-token"),
    ) -> GreenServiceConfig:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("green runtime config must be a mapping")
        required = (
            "workhub_url",
            "mail_host",
            "registry_url",
            "model_url",
            "model_identity_audience",
        )
        values = {key: payload.get(key) for key in required}
        if any(not isinstance(value, str) or not value for value in values.values()):
            raise ValueError("green runtime config is missing a required service endpoint")
        return cls(
            **values,
            jupyter_token_file=jupyter_token_file,
        )


class GreenServiceClients:
    """Concrete product-interface adapters selected by the compiled policy."""

    def __init__(
        self,
        config: GreenServiceConfig,
        *,
        http_client: httpx.Client | None = None,
        imap_factory: Any = imaplib.IMAP4_SSL,
    ) -> None:
        self._config = config
        self._http = http_client or httpx.Client(
            timeout=10.0,
            verify=str(config.ca_file),
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=1),
        )
        self._imap_factory = imap_factory

    def executor(self) -> GreenActionExecutor:
        return GreenActionExecutor(
            {
                WORKHUB_ACTION: lambda: self._guard("workhub", self.read_workhub),
                MAIL_ACTION: lambda: self._guard("mail", self.read_mail),
                NOTEBOOK_ACTION: lambda: self._guard("notebook", self.read_notebook),
                REGISTRY_ACTION: lambda: self._guard("registry", self.read_registry),
                INFERENCE_ACTION: lambda: self._guard("inference", self.request_inference),
            }
        )

    @staticmethod
    def _guard(label: str, action: Any) -> GreenActionObservation:
        try:
            return action()
        except (httpx.TimeoutException, TimeoutError):
            failure_class = "timeout"
        except (
            httpx.HTTPError,
            imaplib.IMAP4.error,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ):
            failure_class = "target_unavailable"
        return GreenActionObservation(
            status="failed",
            observation=f"{label} service read was unavailable",
            evidence_refs=(f"evidence.green-activity.{label}",),
            failure_class=failure_class,
        )

    @staticmethod
    def _success(label: str, observation: str, **measurements: int) -> GreenActionObservation:
        return GreenActionObservation(
            status="succeeded",
            observation=observation[:256],
            evidence_refs=(f"evidence.green-activity.{label}",),
            measurements=measurements,
        )

    def read_workhub(self) -> GreenActionObservation:
        response = self._http.get(
            f"{self._config.workhub_url.rstrip('/')}/git/api/v1/user/repos",
            params={"limit": 10},
            auth=(self._config.workhub_username, self._config.workhub_password),
        )
        response.raise_for_status()
        repositories = response.json()
        if not isinstance(repositories, list):
            raise TypeError("WorkHub repository response is not a list")
        return self._success("workhub", f"reviewed {min(len(repositories), 10)} WorkHub repositories")

    def read_mail(self) -> GreenActionObservation:
        context = ssl.create_default_context(cafile=str(self._config.ca_file))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        with self._imap_factory(
            self._config.mail_host,
            993,
            ssl_context=context,
            timeout=10,
        ) as mailbox:
            mailbox.login(self._config.mail_username, self._config.mail_password)
            status, _ = mailbox.select("INBOX", readonly=True)
            if status != "OK":
                raise RuntimeError("green mailbox could not be selected")
            status, matches = mailbox.search(None, "ALL")
            if status != "OK":
                raise RuntimeError("green mailbox could not be searched")
            count = len(matches[0].split()) if matches else 0
        return self._success("mail", f"reviewed mailbox status with {count} messages")

    def read_notebook(self) -> GreenActionObservation:
        token = self._config.jupyter_token_file.read_text(encoding="utf-8").strip()
        if not token or len(token) > 4096:
            raise ValueError("Jupyter token is unavailable")
        response = self._http.get(
            f"{self._config.notebook_url.rstrip('/')}/api/status",
            headers={"Authorization": f"token {token}"},
        )
        response.raise_for_status()
        status = response.json()
        if not isinstance(status, dict):
            raise TypeError("Jupyter status response is not an object")
        return self._success("notebook", "reviewed Jupyter evaluation workspace status")

    def read_registry(self) -> GreenActionObservation:
        response = self._http.get(
            f"{self._config.registry_url.rstrip('/')}/api/2.0/mlflow/registered-models/search",
            params={"max_results": 10},
        )
        response.raise_for_status()
        payload = response.json()
        models = payload.get("registered_models", []) if isinstance(payload, dict) else None
        if not isinstance(models, list):
            raise TypeError("MLflow registry response is malformed")
        return self._success("registry", f"reviewed {min(len(models), 10)} registered models")

    def _identity_token(self) -> str:
        response = self._http.get(
            METADATA_IDENTITY_URL,
            headers={"Metadata-Flavor": "Google"},
            params={
                "audience": self._config.model_identity_audience,
                "format": "full",
            },
        )
        response.raise_for_status()
        token = response.text.strip()
        if (
            response.headers.get("metadata-flavor", "").lower() != "google"
            or not token
            or len(token) > 16384
            or token.count(".") != 2
        ):
            raise ValueError("GCE identity response is invalid")
        return token

    def request_inference(self) -> GreenActionObservation:
        response = self._http.post(
            f"{self._config.model_url.rstrip('/')}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._identity_token()}"},
            json={
                "model": "keplerops-teacher",
                "messages": [
                    {
                        "role": "system",
                        "content": "Return only a short service readiness acknowledgement.",
                    },
                    {"role": "user", "content": "Routine internal model smoke check."},
                ],
                "max_tokens": 16,
                "temperature": 0,
            },
        )
        response.raise_for_status()
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
            tokens = payload.get("usage", {}).get("total_tokens", 0)
        except (AttributeError, IndexError, KeyError, TypeError) as exc:
            raise ValueError("model response is malformed") from exc
        if not isinstance(content, str) or not isinstance(tokens, int) or tokens < 0:
            raise ValueError("model response values are invalid")
        return self._success(
            "inference",
            "completed routine shared-model smoke request",
            inference_tokens=tokens,
        )
