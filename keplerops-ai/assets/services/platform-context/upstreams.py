"""Real WorkHub and Keycloak HTTP API adapters."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

import httpx
import urllib3
from dulwich import porcelain
from dulwich.objects import Blob
from security import read_secret, validate_range_url

SHA256_PREFIX = "sha256:"


def _body(response: httpx.Response) -> dict[str, Any]:
    if not response.content:
        return {"status_code": response.status_code}
    try:
        parsed = response.json()
    except json.JSONDecodeError:
        parsed = {"text": response.text}
    return {"status_code": response.status_code, "body": parsed}


class WorkHubClient:
    def __init__(
        self,
        *,
        gitea_url: str,
        redmine_url: str,
        gitea_token_path: Path,
        redmine_key_path: Path,
        ca_file: str | None,
        owner: str,
        repository: str,
        branch: str,
        project: str,
    ) -> None:
        self.gitea_url = validate_range_url(gitea_url)
        self.redmine_url = validate_range_url(redmine_url)
        self.gitea_token_path = gitea_token_path
        self.redmine_key_path = redmine_key_path
        self.verify: bool | str = ca_file if ca_file else True
        self.owner = owner
        self.repository = repository
        self.branch = branch
        self.project = project

    def _gitea_headers(self) -> dict[str, str]:
        return {"Authorization": f"token {read_secret(self.gitea_token_path)}"}

    def _redmine_headers(self) -> dict[str, str]:
        return {"X-Redmine-API-Key": read_secret(self.redmine_key_path)}

    @staticmethod
    def _branch_missing(response: httpx.Response) -> bool:
        if response.status_code != 404:
            return False
        try:
            message = str(response.json().get("message", ""))
        except json.JSONDecodeError:
            return False
        return message.startswith("branch does not exist")

    def _git_remote(self) -> str:
        api_suffix = "/api/v1"
        if not self.gitea_url.endswith(api_suffix):
            raise RuntimeError("Gitea API URL does not end in /api/v1")
        return (
            f"{self.gitea_url.removesuffix(api_suffix)}/"
            f"{quote(self.owner, safe='')}/{quote(self.repository, safe='')}.git"
        )

    def _git_pool(self) -> urllib3.PoolManager:
        if isinstance(self.verify, str):
            return urllib3.PoolManager(
                cert_reqs="CERT_REQUIRED",
                ca_certs=self.verify,
            )
        return urllib3.PoolManager(cert_reqs="CERT_REQUIRED")

    def _change_artifact_through_git(
        self,
        path: str,
        content: bytes | None,
        message: str,
    ) -> tuple[str, str | None]:
        relative = PurePosixPath(path)
        if (
            relative.is_absolute()
            or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            raise ValueError("artifact path must be a normalized relative path")

        token = read_secret(self.gitea_token_path)
        remote = self._git_remote()
        pool = self._git_pool()
        output = io.BytesIO()
        with tempfile.TemporaryDirectory(prefix="keplerops-context-git-") as directory:
            repository = porcelain.clone(
                remote,
                directory,
                checkout=True,
                branch=self.branch,
                username=self.owner,
                password=token,
                pool_manager=pool,
                errstream=output,
            )
            target = Path(directory).joinpath(*relative.parts)
            if not target.resolve().is_relative_to(Path(directory).resolve()):
                raise ValueError("artifact path escaped the repository")
            if target.is_symlink():
                raise ValueError("artifact path must not be a symbolic link")
            if content is None:
                porcelain.remove(repository, paths=[relative.as_posix()])
                content_sha = None
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                # Path is normalized, symlink-free, and confined to this clone.
                target.write_bytes(content)  # NOSONAR
                porcelain.add(repository, paths=[relative.as_posix()])
                content_sha = Blob.from_string(content).id.decode("ascii")
            identity = b"KeplerOps Context <platform-context@keplerops.test>"
            commit_sha = porcelain.commit(
                repository,
                message=message.encode("utf-8"),
                author=identity,
                committer=identity,
            ).decode("ascii")
            porcelain.push(
                repository,
                remote_location=remote,
                refspecs=f"HEAD:refs/heads/{self.branch}",
                username=self.owner,
                password=token,
                pool_manager=pool,
                outstream=output,
                errstream=output,
            )
        return commit_sha, content_sha

    def put_artifact(self, path: str, content: bytes, message: str) -> dict[str, Any]:
        encoded_path = "/".join(quote(part, safe="") for part in path.split("/"))
        endpoint = (
            f"{self.gitea_url}/repos/{quote(self.owner, safe='')}/"
            f"{quote(self.repository, safe='')}/contents/{encoded_path}"
        )
        headers = self._gitea_headers()
        with httpx.Client(
            verify=self.verify, timeout=httpx.Timeout(15.0, connect=3.0)
        ) as client:
            existing = client.get(
                endpoint, headers=headers, params={"ref": self.branch}
            )
            if existing.status_code not in {200, 404}:
                existing.raise_for_status()
            body: dict[str, Any] = {
                "branch": self.branch,
                "content": base64.b64encode(content).decode("ascii"),
                "message": message,
            }
            operation = "created"
            if existing.status_code == 200:
                body["sha"] = existing.json()["sha"]
                operation = "updated"
            method = "POST" if existing.status_code == 404 else "PUT"
            response = client.request(method, endpoint, headers=headers, json=body)
            if self._branch_missing(response):
                commit_sha, content_sha = self._change_artifact_through_git(
                    path, content, message
                )
                readback = client.get(
                    endpoint, headers=headers, params={"ref": self.branch}
                )
                readback.raise_for_status()
                observed = base64.b64decode(
                    readback.json()["content"], validate=True
                )
                if observed != content:
                    raise RuntimeError("Git artifact readback did not match")
                result = _body(readback)
                result["status_code"] = 201 if operation == "created" else 200
                result["body"] = {
                    "content": {
                        "sha": content_sha,
                        "path": path,
                    },
                    "commit": {"sha": commit_sha},
                }
                result["transport"] = "git-fallback"
            else:
                response.raise_for_status()
                result = _body(response)
        result.update(
            {
                "operation": operation,
                "path": path,
                "content_base64": body["content"],
                "content_digest": SHA256_PREFIX + hashlib.sha256(content).hexdigest(),
            }
        )
        return result

    def delete_artifact(self, path: str, message: str) -> dict[str, Any]:
        encoded_path = "/".join(quote(part, safe="") for part in path.split("/"))
        endpoint = (
            f"{self.gitea_url}/repos/{quote(self.owner, safe='')}/"
            f"{quote(self.repository, safe='')}/contents/{encoded_path}"
        )
        headers = self._gitea_headers()
        with httpx.Client(
            verify=self.verify, timeout=httpx.Timeout(15.0, connect=3.0)
        ) as client:
            existing = client.get(
                endpoint, headers=headers, params={"ref": self.branch}
            )
            if existing.status_code == 404:
                return {"status_code": 404, "operation": "already-absent", "path": path}
            existing.raise_for_status()
            response = client.request(
                "DELETE",
                endpoint,
                headers=headers,
                json={
                    "branch": self.branch,
                    "message": message,
                    "sha": existing.json()["sha"],
                },
            )
            if self._branch_missing(response):
                commit_sha, _content_sha = self._change_artifact_through_git(
                    path, None, message
                )
                readback = client.get(
                    endpoint, headers=headers, params={"ref": self.branch}
                )
                if readback.status_code != 404:
                    raise RuntimeError("deleted Git artifact remained readable")
                result = {
                    "status_code": 200,
                    "body": {"commit": {"sha": commit_sha}},
                    "transport": "git-fallback",
                }
            else:
                response.raise_for_status()
                result = _body(response)
        result.update({"operation": "deleted", "path": path})
        return result

    def create_conversation(self, subject: str, content: str) -> dict[str, Any]:
        request = {
            "issue": {
                "project_id": self.project,
                "subject": subject,
                "description": content,
            }
        }
        with httpx.Client(
            verify=self.verify, timeout=httpx.Timeout(15.0, connect=3.0)
        ) as client:
            response = client.post(
                f"{self.redmine_url}/issues.json",
                headers=self._redmine_headers(),
                json=request,
            )
            response.raise_for_status()
        result = _body(response)
        result["submitted"] = request
        return result

    def update_conversation(self, issue_id: int, content: str) -> dict[str, Any]:
        request = {"issue": {"notes": content}}
        with httpx.Client(
            verify=self.verify, timeout=httpx.Timeout(15.0, connect=3.0)
        ) as client:
            response = client.put(
                f"{self.redmine_url}/issues/{issue_id}.json",
                headers=self._redmine_headers(),
                json=request,
            )
            response.raise_for_status()
        result = _body(response)
        result["submitted"] = request
        return result


class KeycloakClient:
    def __init__(
        self,
        *,
        base_url: str,
        admin_realm: str,
        target_realm: str,
        client_id: str,
        client_secret_path: Path,
        ca_file: str | None,
    ) -> None:
        self.base_url = validate_range_url(base_url)
        self.admin_realm = admin_realm
        self.target_realm = target_realm
        self.client_id = client_id
        self.client_secret_path = client_secret_path
        self.verify: bool | str = ca_file if ca_file else True

    def _token(self, client: httpx.Client) -> str:
        response = client.post(
            f"{self.base_url}/realms/{quote(self.admin_realm, safe='')}/protocol/openid-connect/token",
            auth=(self.client_id, read_secret(self.client_secret_path)),
            data={"grant_type": "client_credentials"},
        )
        response.raise_for_status()
        return str(response.json()["access_token"])

    def _user(self, client: httpx.Client, token: str, username: str) -> dict[str, Any]:
        response = client.get(
            f"{self.base_url}/admin/realms/{quote(self.target_realm, safe='')}/users",
            headers={"Authorization": f"Bearer {token}"},
            params={"username": username, "exact": "true", "max": 2},
        )
        response.raise_for_status()
        matches = [row for row in response.json() if row.get("username") == username]
        if len(matches) != 1:
            raise LookupError(f"Keycloak user {username} was not uniquely resolved")
        return matches[0]

    def reset_password(
        self, username: str, password: str, temporary: bool
    ) -> dict[str, Any]:
        with httpx.Client(
            verify=self.verify, timeout=httpx.Timeout(15.0, connect=3.0)
        ) as client:
            token = self._token(client)
            user = self._user(client, token, username)
            response = client.put(
                f"{self.base_url}/admin/realms/{quote(self.target_realm, safe='')}/users/"
                f"{quote(user['id'], safe='')}/reset-password",
                headers={"Authorization": f"Bearer {token}"},
                json={"type": "password", "value": password, "temporary": temporary},
            )
            response.raise_for_status()
        return {
            "status_code": response.status_code,
            "username": username,
            "user_id": user["id"],
            "temporary": temporary,
            "credential_digest": SHA256_PREFIX
            + hashlib.sha256(password.encode("utf-8")).hexdigest(),
        }

    def sessions(self, username: str) -> dict[str, Any]:
        with httpx.Client(
            verify=self.verify, timeout=httpx.Timeout(15.0, connect=3.0)
        ) as client:
            token = self._token(client)
            user = self._user(client, token, username)
            response = client.get(
                f"{self.base_url}/admin/realms/{quote(self.target_realm, safe='')}/users/"
                f"{quote(user['id'], safe='')}/sessions",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
        sessions = response.json()
        return {
            "status_code": response.status_code,
            "username": username,
            "user_id": user["id"],
            "session_count": len(sessions),
            "sessions": sessions,
        }

    def logout(self, username: str) -> dict[str, Any]:
        with httpx.Client(
            verify=self.verify, timeout=httpx.Timeout(15.0, connect=3.0)
        ) as client:
            token = self._token(client)
            user = self._user(client, token, username)
            response = client.post(
                f"{self.base_url}/admin/realms/{quote(self.target_realm, safe='')}/users/"
                f"{quote(user['id'], safe='')}/logout",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
        return {
            "status_code": response.status_code,
            "username": username,
            "user_id": user["id"],
            "operation": "all-user-sessions-logged-out",
        }

    def rotate_client_secret(self, client_id: str) -> dict[str, Any]:
        with httpx.Client(
            verify=self.verify, timeout=httpx.Timeout(15.0, connect=3.0)
        ) as client:
            token = self._token(client)
            headers = {"Authorization": f"Bearer {token}"}
            found = client.get(
                f"{self.base_url}/admin/realms/{quote(self.target_realm, safe='')}/clients",
                headers=headers,
                params={"clientId": client_id, "max": 2},
            )
            found.raise_for_status()
            matches = [row for row in found.json() if row.get("clientId") == client_id]
            if len(matches) != 1:
                raise LookupError(
                    f"Keycloak client {client_id} was not uniquely resolved"
                )
            response = client.post(
                f"{self.base_url}/admin/realms/{quote(self.target_realm, safe='')}/clients/"
                f"{quote(matches[0]['id'], safe='')}/client-secret",
                headers=headers,
            )
            response.raise_for_status()
        secret = str(response.json()["value"])
        return {
            "status_code": response.status_code,
            "client_id": client_id,
            "client_uuid": matches[0]["id"],
            "client_secret": secret,
            "credential_digest": SHA256_PREFIX
            + hashlib.sha256(secret.encode("utf-8")).hexdigest(),
        }
