"""Real OCI Distribution client and signed reputation-aware image resolver."""

from __future__ import annotations

import base64
import hashlib
import json
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urljoin, urlparse

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from policy import DeploymentPolicy
from security import read_secret, require_digest, require_repository, require_request_id
from store import StateStore, canonical


MANIFEST_ACCEPT = ", ".join(
    (
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
    )
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _registry_tls_context(ca_path: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.load_verify_locations(cafile=str(ca_path))
    return context


def _is_registry_root_challenge(response: httpx.Response) -> bool:
    authenticate = response.headers.get("www-authenticate", "")
    distribution = response.headers.get("docker-distribution-api-version", "")
    return (
        response.status_code == 401
        and (
            authenticate.lower().startswith("bearer ")
            and distribution.lower().startswith("registry/2")
            or response.text == "authGroup.Verify\n"
        )
    )


class OciRegistry:
    """OCI client compatible with the Gitea 1.24.x container registry."""

    def __init__(
        self,
        policy: DeploymentPolicy,
        token_path: Path,
        ca_path: Path,
        store: StateStore,
    ) -> None:
        self.policy = policy
        self.store = store
        self.client = httpx.Client(
            base_url=policy.registry_url + "/",
            auth=(policy.registry_username, read_secret(token_path)),
            timeout=httpx.Timeout(20.0),
            follow_redirects=False,
            verify=_registry_tls_context(ca_path),
            headers={"User-Agent": "keplerops-platform-deployment/1"},
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        accept: str | None = None,
        allow_registry_challenge: bool = False,
    ) -> httpx.Response:
        request_content = {
            "method": method,
            "path": path,
            "params": params or {},
            "accept": accept,
        }
        started = time.monotonic()
        response: httpx.Response | None = None
        try:
            response = self.client.request(
                method,
                path,
                params=params,
                headers={"Accept": accept} if accept else None,
            )
            if len(response.content) > 4_194_304:
                raise RuntimeError("registry response exceeds the 4 MiB evidence bound")
            if not (
                allow_registry_challenge and _is_registry_root_challenge(response)
            ):
                response.raise_for_status()
            response_content = {
                "status_code": response.status_code,
                "headers": {
                    key.lower(): value for key, value in response.headers.items()
                },
                "content_base64": base64.b64encode(response.content).decode(),
                "content_text": response.text,
            }
            self.store.record_event(
                "platform_deployment.registry_exchange",
                "oci",
                "succeeded",
                None,
                request_content,
                response_content,
                (time.monotonic() - started) * 1000,
            )
            return response
        except Exception as exc:
            result: dict[str, Any] = {
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            if response is not None:
                result["status_code"] = response.status_code
                result["headers"] = {
                    key.lower(): value for key, value in response.headers.items()
                }
                result["content_base64"] = base64.b64encode(response.content).decode()
                result["content_text"] = response.text
            self.store.record_event(
                "platform_deployment.registry_exchange",
                "oci",
                "failed",
                None,
                request_content,
                result,
                (time.monotonic() - started) * 1000,
            )
            raise

    def probe(self) -> dict[str, Any]:
        response = self._request("GET", "v2/", allow_registry_challenge=True)
        if _is_registry_root_challenge(response):
            return {
                "status": "ready",
                "distribution_api_version": response.headers.get(
                    "docker-distribution-api-version"
                ),
                "authentication": "registry-root-challenge",
            }
        return {
            "status": "ready",
            "distribution_api_version": response.headers.get(
                "docker-distribution-api-version"
            ),
            "authentication": "authenticated",
        }

    def tags(self, repository: str) -> list[str]:
        require_repository(repository)
        tags: set[str] = set()
        params: dict[str, str] | None = {"n": "100"}
        path = f"v2/{repository}/tags/list"
        for _ in range(100):
            response = self._request("GET", path, params=params)
            payload = response.json()
            if payload.get("name") != repository or not isinstance(
                payload.get("tags"), (list, type(None))
            ):
                raise RuntimeError("registry returned a malformed tag listing")
            values = payload.get("tags") or []
            if any(
                not isinstance(tag, str) or not tag or len(tag) > 128 for tag in values
            ):
                raise RuntimeError("registry returned an invalid tag")
            tags.update(values)
            link = response.headers.get("link")
            if not link:
                return sorted(tags)
            target = link.split(";", 1)[0].strip().strip("<>")
            query = parse_qs(urlparse(urljoin(str(response.request.url), target)).query)
            last = query.get("last", [None])[0]
            if not isinstance(last, str) or not last:
                raise RuntimeError("registry pagination link omitted last")
            params = {"n": "100", "last": last}
        raise RuntimeError("registry tag pagination exceeded 100 pages")

    def manifest(self, repository: str, reference: str) -> dict[str, Any]:
        path = f"v2/{repository}/manifests/{quote(reference, safe='')}"
        head = self._request("HEAD", path, accept=MANIFEST_ACCEPT)
        expected = require_digest(head.headers.get("docker-content-digest", ""))
        response = self._request("GET", path, accept=MANIFEST_ACCEPT)
        delivered = require_digest(response.headers.get("docker-content-digest", ""))
        calculated = "sha256:" + hashlib.sha256(response.content).hexdigest()
        if expected != delivered or calculated != delivered:
            raise RuntimeError(
                "registry manifest digest did not match the delivered bytes"
            )
        json.loads(response.content)
        return {
            "reference": reference,
            "digest": delivered,
            "media_type": response.headers.get("content-type", "").split(";", 1)[0],
            "size": len(response.content),
        }


class ReputationResolver:
    def __init__(
        self,
        policy: DeploymentPolicy,
        registry: OciRegistry,
        key_path: Path,
        store: StateStore,
    ) -> None:
        self.policy = policy
        self.registry = registry
        self.store = store
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise RuntimeError(
                "reputation signing key must be an Ed25519 PKCS8 private key"
            )
        self.key = key
        self.public_key = key.public_key()
        encoded = self.public_key.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.fingerprint = "sha256:" + hashlib.sha256(encoded).hexdigest()

    def record(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = require_request_id(request["request_id"])
        repository = require_repository(request["repository"])
        digest = require_digest(request["digest"])
        if repository not in self.policy.repositories:
            raise ValueError("repository is not allowlisted by the realization policy")
        score = request["score"]
        if (
            isinstance(score, bool)
            or not isinstance(score, int)
            or not -100 <= score <= 100
        ):
            raise ValueError("score must be an integer from -100 through 100")
        producer, rationale = request["producer"], request["rationale"]
        if not isinstance(producer, str) or not producer or len(producer) > 128:
            raise ValueError("producer is invalid")
        if not isinstance(rationale, str) or not rationale or len(rationale) > 4096:
            raise ValueError("rationale is invalid")
        existing = self.store.begin_request(request_id, "reputation", request)
        if existing is not None:
            return existing
        recorded = self.store.reputation_event(request_id)
        if recorded is not None:
            self.store.finish_request(request_id, recorded)
            return recorded
        event = {
            "schema_version": 1,
            "event_id": request_id,
            "repository": repository,
            "digest": digest,
            "score": score,
            "producer": producer,
            "rationale": rationale,
            "observed_at": _utc_now(),
        }
        signature = base64.b64encode(self.key.sign(canonical(event).encode())).decode()
        self.store.add_reputation(event, signature, self.fingerprint)
        result = {
            "event": event,
            "signature": signature,
            "public_key_fingerprint": self.fingerprint,
        }
        self.store.finish_request(request_id, result)
        self.store.record_event(
            "platform_deployment.reputation_recorded",
            "reputation",
            "succeeded",
            request_id,
            request,
            result,
            0.0,
        )
        return result

    def _scores(self, repository: str) -> dict[str, int]:
        scores: dict[str, int] = {}
        for record in self.store.reputation(repository):
            if record["public_key_fingerprint"] != self.fingerprint:
                raise RuntimeError("stored reputation event has an unknown signing key")
            signature = base64.b64decode(record["signature"], validate=True)
            self.public_key.verify(signature, canonical(record["event"]).encode())
            digest = require_digest(record["event"]["digest"])
            scores[digest] = scores.get(digest, 0) + int(record["event"]["score"])
        return scores

    def resolve(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = require_request_id(request["request_id"])
        repository = require_repository(request["repository"])
        if repository not in self.policy.repositories:
            raise ValueError("repository is not allowlisted by the realization policy")
        existing = self.store.begin_request(request_id, "resolve", request)
        if existing is not None:
            return existing
        self.registry.probe()
        candidates = [
            self.registry.manifest(repository, tag)
            for tag in self.registry.tags(repository)
        ]
        if not candidates:
            raise RuntimeError("repository has no resolvable tags")
        scores = self._scores(repository)
        ranked = sorted(
            candidates,
            key=lambda item: (
                -scores.get(item["digest"], 0),
                item["digest"],
                item["reference"],
            ),
        )
        selected = ranked[0]
        result = {
            "request_id": request_id,
            "repository": repository,
            "selected_tag": selected["reference"],
            "selected_digest": selected["digest"],
            "immutable_reference": f"{self.policy.registry_url.removeprefix('https://')}/{repository}@{selected['digest']}",
            "reputation_score": scores.get(selected["digest"], 0),
            "candidates": [
                {**item, "reputation_score": scores.get(item["digest"], 0)}
                for item in ranked
            ],
            "selection_rule": "score-desc,digest-asc,tag-asc",
        }
        self.store.finish_request(request_id, result)
        self.store.record_event(
            "platform_deployment.image_resolved",
            "resolver",
            "succeeded",
            request_id,
            request,
            result,
            0.0,
        )
        return result
