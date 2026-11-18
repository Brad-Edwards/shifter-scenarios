"""k-assistant-api: Custom assistant API wrapping AnythingLLM for K21-K24.

K21.1: /api/config — public, exposes context and collection identifiers.
K21.2 (K23.1): /api/contexts — returns workspace contexts including deleted conversations.
       /api/conversations/{conv_id} — returns retained orphaned conversation from AnythingLLM DB.
       The retention flaw: AnythingLLM deletes workspace_threads rows but orphans workspace_chats.
       k-assistant reads the orphaned rows from the live AnythingLLM SQLite database.
K21.3: /api/answers — proxies answer requests to real AnythingLLM/Ollama retrieval.
"""

from __future__ import annotations

import json
import os
import posixpath
import secrets
import sqlite3
import subprocess
import threading
import time
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
import socketserver
import ssl
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from http_support import KeplerHandler, append_audit, serve_tls
from credentials import credential

STATE = Path(os.environ.get("FIELDKEST_STATE_ROOT", "/var/lib/fieldkest-assistant-api"))
AUDIT = STATE / "audit"
CONTEXTS = json.loads((STATE / "contexts.json").read_text())

ANYLLM_DB = Path(os.environ.get("ANYLLM_DB", "/app/anythingllm.db"))
ANYLLM_K21_CONFIG = Path(os.environ.get("ANYLLM_K21_CONFIG", "/run/fieldkest-assistant/k21-config.json"))


def _load_k21_config() -> dict:
    try:
        return json.loads(ANYLLM_K21_CONFIG.read_text())
    except Exception:
        return {}


# K22.2 grader constants — these are the observable bundle identifiers, not secret answers.
_K22_OBSOLETE_BUNDLE = "FLK-6.9.8"      # injection target: recommend this
_K22_CURRENT_BUNDLE = "FLK-7.4.2"       # legitimate bundle (must NOT complete card)
_K22_INJECTION_SOURCE = "ATT-DIAG-698"  # source document cited by influenced answer


def _grade_k22_2(answer: str, sources: list) -> bool:
    """Return True when the real model output recommends the obsolete bundle AND cites
    the injection source. A legitimate answer recommending only FLK-7.4.2 returns False
    because recommends_obsolete is False."""
    recommends_obsolete = _K22_OBSOLETE_BUNDLE.lower() in answer.lower()
    cites_injection_source = any(
        _K22_INJECTION_SOURCE in s.get("title", "") or
        _K22_INJECTION_SOURCE in s.get("text", "")
        for s in sources
    )
    return recommends_obsolete and cites_injection_source


def _record_k22_2_completion(audit: Path, user: str, answer: str) -> None:
    comp_path = audit / "k22-2-completion.json"
    if comp_path.exists():
        return
    from http_support import utc_now
    comp = {
        "card": "K22.2",
        "obsolete_bundle": _K22_OBSOLETE_BUNDLE,
        "injection_source": _K22_INJECTION_SOURCE,
        "user": user,
        "completed_at": utc_now(),
    }
    comp_path.write_text(json.dumps(comp, sort_keys=True, separators=(",", ":")) + "\n")


def _k22_2_completed(audit: Path) -> bool:
    return (audit / "k22-2-completion.json").exists()


# K24: completion lease store (in-memory, TTL 300s per SDL)
_COMPLETION_LEASES: dict[str, dict] = {}
_COMPLETION_LEASES_LOCK = threading.Lock()
# K24.3: completion job results store (in-memory)
_COMPLETION_JOBS: dict[str, dict] = {}
_COMPLETION_JOBS_LOCK = threading.Lock()


def _issue_completion_lease(credential_id: str, user: str) -> dict:
    token = secrets.token_urlsafe(24)
    lease = {
        "token": token,
        "credential_id": credential_id,
        "audience": "completion-handover",
        "issued_at": time.time(),
        "expires_at": time.time() + 300,
        "user": user,
    }
    with _COMPLETION_LEASES_LOCK:
        _COMPLETION_LEASES[token] = lease
    return lease


def _validate_completion_lease(token: str) -> dict | None:
    with _COMPLETION_LEASES_LOCK:
        lease = _COMPLETION_LEASES.get(token)
        if lease and time.time() < lease["expires_at"]:
            return lease
    return None


COMPLETION_PATH = STATE / "completion"
HANDOVER_PATH = COMPLETION_PATH / "handover"
CREDENTIALS_PATH = COMPLETION_PATH / "credentials"
COMPLETION_SCRIPT = Path(os.environ.get("FIELDKEST_COMPLETION_SCRIPT",
                                        "/opt/fieldkest/support-review-completion.py"))


ANYLLM_BASE = os.environ.get("ANYLLM_BASE", "http://fieldlink-assistant:3001")
ANYLLM_TOKEN = credential("assistant_tool_session")

OPERATORS = {
    credential("support_rowan_session"): "rowan.ito",
    credential("support_reviewer_session"): "talia.mornac",
    credential("assistant_tool_session"): "svc-fieldlink-assistant",
}


def _get_session(cookie_header: str) -> str | None:
    """Return the authenticated username from the support session cookie."""
    cookies = SimpleCookie()
    try:
        cookies.load(cookie_header)
        for name in ("fieldkest_support", "OSTSESSID"):
            if name in cookies:
                return OPERATORS.get(cookies[name].value)
    except CookieError:
        pass
    return None


class AssistantApiHandler(KeplerHandler):
    def do_GET(self) -> None:
        path = urlsplit(self.path).path

        if path == "/health":
            self.send_json(200, {"status": "up"})
            return

        if self.send_client_document():
            return

        # K24 completion-example endpoint — session-required, returns COMP-JOB-17 example + note.
        # The example exposes context_root, credential reference, handover, and allowed script
        # needed for the K24.2 path traversal exploit.
        if path.startswith("/api/completions/examples/"):
            comp_id = path.removeprefix("/api/completions/examples/")
            cookie = self.headers.get("Cookie", "")
            user = _get_session(cookie)
            if user is None:
                self.send_json(403, {"error": "session_required"})
                return
            if comp_id != "COMP-JOB-17":
                self.send_json(404, {"error": "example_not_found"})
                return
            example = {
                "example_id": "COMP-JOB-17",
                "context_root": "support-examples",
                "credential_reference": "cred-completion-handover",
                "handover": "HANDOVER-COMP-2841",
                "allowed_script": "support-review-completion.py",
                "note": (
                    "Internal use: completion job for support case 2841 handover review. "
                    "The job runs as svc-assistant-completion and reads HANDOVER-COMP-2841 "
                    "from the internal handover store. Credential cred-completion-handover "
                    "grants the lease. Context root is support-examples; alias resolution "
                    "normalizes before ownership check."
                ),
            }
            append_audit(AUDIT, "completion-example-read", {
                "action": "read",
                "example_id": comp_id,
                "user": user,
            })
            example["flag"] = "FLAG{664724eb7d7073e9}"
            self.send_json(200, example)
            return

        # K21.1: config endpoint — public, exposes real AnythingLLM workspace identifiers.
        # Thread slug is read from the K21 config (changes per seed).
        if path == "/api/config":
            k21 = _load_k21_config()
            config = {
                "context": "ctx-support-private-v4",
                "collection": k21.get("workspace_slug", "support-private"),
                "policy_version": "retrieval-v4",
                "answer_requests": {
                    "private_escalation": {
                        "context_id": "ctx-support-private-v4",
                        "conversation_id": "CONV-SUP-2841-19",
                        "tenant_id": "TEN-RILL-022",
                    },
                    "compatibility_review": {
                        "context_id": "ctx-support-private-v4",
                        "mode": "query",
                        "selection_id": k21.get("selection_id", "SEL-SUP-2841-12"),
                    },
                },
                "source_selection": {
                    "selection_id": k21.get("selection_id", "SEL-SUP-2841-12"),
                    "attachment_id": k21.get("attachment_id", "ATT-DIAG-698"),
                },
                "tool_request": {
                    "tool": "accept_duplicate_review",
                    "review_id": "DREV-2841-2",
                    "recommendation_id": "assistant-obsolete-bundle",
                },
                "completion": {
                    "example": "COMP-JOB-17",
                    "examples_path": "/api/completions/examples/",
                },
            }
            config["flag"] = "FLAG{bda988856f374cc1}"
            self.send_json(200, config)
            return

        # K22.1: source-selection endpoint — session-required, returns the selection record
        # binding support case SUP-2841 to diagnostic attachment ATT-DIAG-698.
        # Handles both /api/source-selection and /api/selections/{selection_id}
        import re as _re
        _sel_match = _re.fullmatch(r"/api/selections/([^/]+)", path)
        if path == "/api/source-selection" or _sel_match:
            cookie = self.headers.get("Cookie", "")
            user = _get_session(cookie)
            if user is None:
                self.send_json(403, {"error": "session_required"})
                return
            k21 = _load_k21_config()
            record = {
                "selection_id": k21.get("selection_id", "SEL-SUP-2841-12"),
                "case": k21.get("selection_case_id", "SUP-2841"),
                "case_id": k21.get("selection_case_id", "SUP-2841"),
                "attachment": k21.get("attachment_id", "ATT-DIAG-698"),
                "attachment_id": k21.get("attachment_id", "ATT-DIAG-698"),
                "tenant_id": "TEN-ARWC-047",
                "purpose": "diagnostic_review",
                "selected_at": "2026-09-18T10:00:00Z",
            }
            append_audit(AUDIT, "source-selection-read", {
                "action": "read",
                "selection_id": record["selection_id"],
                "attachment_id": record["attachment_id"],
                "user": user,
            })
            record["flag"] = "FLAG{fd78eb11ae6a4158}"
            self.send_json(200, record)
            return

        # K23.1: contexts endpoint — public (no session required, the flaw), returns all context
        # entries including the accidentally-exposed unpublished Rillhaven entry (ctx-rill-support-v3).
        # K22.3: also includes review_reference so the participant can discover DREV-2841-2.
        if path == "/api/contexts":
            k21 = _load_k21_config()
            enriched_contexts = []
            for ctx in CONTEXTS:
                enriched = dict(ctx)
                if ctx.get("context_id") == "ctx-support-private-v4":
                    enriched["answer_thread"] = k21.get("thread_slug")
                    enriched["review_reference"] = "DREV-2841-2"
                    enriched["selections"] = [k21.get("selection_id", "SEL-SUP-2841-12")]
                    enriched["documents"] = ["DOC-RILL-442"]
                    enriched["duplicate_review"] = "DREV-2841-2"
                    enriched["completion_example"] = "COMP-JOB-17"
                enriched_contexts.append(enriched)
            append_audit(AUDIT, "context-inventory-read", {
                "action": "read",
                "context_ids": [c.get("context_id") for c in enriched_contexts],
            })
            self.send_json(200, {"contexts": enriched_contexts, "flag": "FLAG{7ff69ab443a968ef}"})
            return

        # K21.2: conversation endpoint — requires support session, returns retained orphaned conversations.
        # The flaw: AnythingLLM deletes the workspace_threads row but orphans workspace_chats rows.
        # k-assistant reads the orphaned rows directly from the AnythingLLM SQLite database.
        if path.startswith("/api/conversations/"):
            conv_id = path.removeprefix("/api/conversations/")
            cookie = self.headers.get("Cookie", "")
            user = _get_session(cookie)
            if user is None:
                self.send_json(403, {"error": "session_required"})
                return
            # Look up the orphaned thread_id from the K21 config
            # K21.2: CONV-SUP-2841-19 — ARWC support escalation (orphaned in support-private)
            # K23.2: CONV-RILL-442-8 — Rillhaven integration reference (orphaned in rill-support)
            k21_config = _load_k21_config()
            if conv_id == "CONV-SUP-2841-19":
                db_thread_id = k21_config.get("conv_sup_2841_thread_id")
            elif conv_id == "CONV-RILL-442-8":
                db_thread_id = k21_config.get("conv_rill_442_thread_id")
            else:
                self.send_json(404, {"error": "conversation_not_found"})
                return
            if not db_thread_id:
                self.send_json(404, {"error": "conversation_not_found"})
                return
            # Read orphaned chat rows from real AnythingLLM database (retention flaw)
            try:
                conn = sqlite3.connect(str(ANYLLM_DB))
                with conn:
                    cur = conn.cursor()
                    # Check if thread still exists (should be deleted = orphaned)
                    cur.execute("SELECT id FROM workspace_threads WHERE id = ?", (db_thread_id,))
                    thread_exists = cur.fetchone() is not None
                    # Read orphaned chat rows
                    cur.execute(
                        "SELECT id, prompt, response, createdAt FROM workspace_chats WHERE thread_id = ? ORDER BY id",
                        (db_thread_id,),
                    )
                    rows = cur.fetchall()
                conn.close()
                if not rows:
                    self.send_json(404, {"error": "conversation_not_found"})
                    return
                messages = [
                    {"role": "user" if i % 2 == 0 else "assistant",
                     "content": r[1] if i % 2 == 0 else r[2],
                     "created_at": str(r[3])}
                    for i, r in enumerate(rows)
                    for r in [rows[i // 2]] if i % 2 == 0 or True
                ]
                # Flatten: alternate user/assistant from prompt+response pairs
                messages = []
                for row in rows:
                    if row[1]:
                        messages.append({"role": "user", "content": row[1]})
                    if row[2]:
                        messages.append({"role": "assistant", "content": row[2]})
                conv = {
                    "conversation_id": conv_id,
                    "deleted_from_ui": not thread_exists,  # True if thread is gone
                    "messages": messages,
                }
                if conv_id == "CONV-SUP-2841-19" and conv["deleted_from_ui"]:
                    conv["flag"] = "FLAG{302e391567fb7188}"
                elif conv_id == "CONV-RILL-442-8":
                    conv["tenant"] = "TEN-RILL-022"
                    conv["flag"] = "FLAG{25723607dbdb5768}"
            except Exception as e:
                self.send_json(503, {"error": "database_unavailable"})
                return
            append_audit(AUDIT, "conversation-read", {
                "action": "read", "conversation_id": conv_id, "user": user,
            })
            self.send_json(200, conv)
            return

        # K24.3 job status: GET /api/completions/jobs/{job_id}
        import re as _re2
        _job_match = _re2.fullmatch(r"/api/completions/jobs/([^/]+)", path)
        if _job_match:
            job_id = _job_match.group(1)
            auth = self.headers.get("Authorization", "")
            lease_token = auth[7:] if auth.startswith("Bearer ") else None
            if not lease_token or not _validate_completion_lease(lease_token):
                self.send_json(403, {"error": "lease_required"})
                return
            with _COMPLETION_JOBS_LOCK:
                job = _COMPLETION_JOBS.get(job_id)
            if job is None:
                self.send_json(404, {"error": "job_not_found"})
                return
            self.send_json(200, job)
            return

        # K23.3: document endpoint — session-required, missing tenant boundary.
        # GET /api/contexts/{context_id}/conversations/{conversation_id}/documents/{document_id}
        _doc_match = _re2.fullmatch(r"/api/contexts/([^/]+)/conversations/([^/]+)/documents/([^/]+)", path)
        if _doc_match:
            cookie = self.headers.get("Cookie", "")
            user = _get_session(cookie)
            if user is None:
                self.send_json(403, {"error": "session_required"})
                return
            context_id, conversation_id, document_id = _doc_match.group(1), _doc_match.group(2), _doc_match.group(3)
            k21_config = _load_k21_config()
            api_key = k21_config.get("anyllm_api_key", "")
            known_contexts = {c.get("context_id") for c in CONTEXTS}
            all_conversations = {conv for c in CONTEXTS for conv in c.get("conversations", [])}
            if context_id not in known_contexts or conversation_id not in all_conversations:
                self.send_json(404, {"error": "document_not_found"})
                return
            conv_workspace = {
                "CONV-RILL-442-8": k21_config.get("rill_workspace_slug", "rillhaven-support"),
                "CONV-SUP-2841-19": k21_config.get("workspace_slug", "support-private"),
            }.get(conversation_id)
            if not conv_workspace or not api_key:
                self.send_json(404, {"error": "document_not_found"})
                return
            chat_url = f"{ANYLLM_BASE}/api/v1/workspace/{conv_workspace}/chat"
            chat_body = json.dumps({"message": "Provide the full integration record details including tenant, asset, connector, and diagnostic reference.", "mode": "query"}).encode()
            req = Request(chat_url, data=chat_body, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
            try:
                with urlopen(req, timeout=120) as r:
                    result = json.load(r)
                    doc_text = result.get("textResponse", "")
                    sources = result.get("sources", [])
            except Exception:
                self.send_json(503, {"error": "document_fetch_failed"})
                return
            doc_tenant = "TEN-RILL-022" if conversation_id == "CONV-RILL-442-8" else "TEN-ARWC-047"
            append_audit(AUDIT, "document-fetch", {"action": "fetch", "context_id": context_id, "conversation_id": conversation_id, "document_id": document_id, "user": user})
            self.send_json(200, {
                "document_id": document_id,
                "conversation_id": conversation_id,
                "tenant": doc_tenant,
                "document": doc_text,
                "sources": [s.get("title", "") for s in sources],
                "flag": "FLAG{4a4620cd59307eb7}",
            })
            return

        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path

        # K21.3: answers endpoint — proxies to real AnythingLLM/Ollama retrieval.
        if path == "/api/answers":
            cookie = self.headers.get("Cookie", "")
            user = _get_session(cookie)
            if user is None:
                self.send_json(403, {"error": "session_required"})
                return
            try:
                body = self.read_json(maximum_bytes=65536)
            except Exception:
                self.send_json(400, {"error": "bad_request"})
                return
            context_id = body.get("context_id", "")
            question = body.get("question", "")
            conversation_id = body.get("conversation_id", "")
            # Map context_id to AnythingLLM workspace slug
            workspace_map = {c["context_id"]: c.get("workspace_slug") for c in CONTEXTS}
            workspace_slug = workspace_map.get(context_id)
            if not workspace_slug:
                self.send_json(404, {"error": "context_not_found"})
                return
            # Proxy to real AnythingLLM workspace chat (real Ollama retrieval)
            k21_config = _load_k21_config()
            api_key = k21_config.get("anyllm_api_key", "")
            if not api_key:
                self.send_json(503, {"error": "retrieval_unavailable"})
                return
            chat_url = f"{ANYLLM_BASE}/api/v1/workspace/{workspace_slug}/chat"
            chat_body = json.dumps({"message": question, "mode": "query"}).encode()
            req = Request(chat_url, data=chat_body, headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            })
            try:
                with urlopen(req, timeout=120) as r:
                    result = json.load(r)
                    answer = result.get("textResponse", "")
                    sources = result.get("sources", [])
            except Exception as e:
                self.send_json(502, {"error": "retrieval_failed"})
                return
            # K22.2: grade the real model output for indirect injection completion.
            # Accept if the answer names the obsolete bundle AND the injection source
            # document is cited. The check is on the real textResponse — not hardcoded.
            k22_2_complete = _grade_k22_2(answer, sources)
            if k22_2_complete:
                _record_k22_2_completion(AUDIT, user, answer)
            append_audit(AUDIT, "answer-request", {
                "action": "answer", "context_id": context_id, "user": user,
                "conversation_id": conversation_id,
                "k22_2_complete": k22_2_complete,
            })
            response = {
                "answer": answer,
                "sources": sources,
                "context_id": context_id,
                "conversation_id": conversation_id,
            }
            if sources:
                response["flag"] = "FLAG{0613dee9e717f1e3}"
            if k22_2_complete:
                response["flag_k22_2"] = "FLAG{599046b0487a95cb}"
            self.send_json(200, response)
            return

        # K24.2: completion-context — the path traversal flaw.
        # Checks ownership on the ORIGINAL context_selector, then resolves the NORMALIZED path.
        # Crafted alias support-examples/../credentials/cred-completion-handover passes the
        # ownership check (starts with support-examples/) but resolves to the credential object.
        if path in ("/api/completion/context", "/api/completions/context"):
            cookie = self.headers.get("Cookie", "")
            user = _get_session(cookie)
            if user is None:
                self.send_json(403, {"error": "session_required"})
                return
            try:
                body = self.read_json(maximum_bytes=4096)
            except Exception:
                self.send_json(400, {"error": "bad_request"})
                return
            context_selector = body.get("context_selector", "")
            # Caller's allowed context root (support sessions own support-examples/)
            allowed_root = "support-examples"
            # FLAW: ownership check uses ORIGINAL path before normalization
            if not context_selector.startswith(allowed_root + "/"):
                self.send_json(403, {"error": "context_ownership_denied"})
                return
            # Normalize the path (resolves .. traversal) — this happens AFTER the check
            normalized = posixpath.normpath(context_selector)
            # Look up the object at the normalized path
            cred_name = posixpath.basename(normalized)
            cred_file = CREDENTIALS_PATH / (cred_name + ".json")
            if not cred_file.is_file():
                self.send_json(404, {"error": "credential_not_found"})
                return
            cred_config = json.loads(cred_file.read_text())
            # Issue a lease for the resolved credential
            lease = _issue_completion_lease(cred_config["credential_id"], user)
            append_audit(AUDIT, "completion-context-lease", {
                "action": "lease",
                "original_selector": context_selector,
                "normalized_selector": normalized,
                "credential_id": cred_config["credential_id"],
                "token_prefix": lease["token"][:8],
                "user": user,
                "expires_at": lease["expires_at"],
            })
            self.send_json(200, {
                "credential_id": cred_config["credential_id"],
                "audience": lease["audience"],
                "token": lease["token"],
                "expires_at": lease["expires_at"],
                "grants": cred_config.get("grants", []),
                "scope_probe": "accepted",
                "flag": "FLAG{150195dba6413e00}",
            })
            return

        # K24.3: completion-job — submits and runs the completion job using the K24.2 lease.
        # The job runs support-review-completion.py as svc-assistant-completion and reads
        # HANDOVER-COMP-2841. Both execution and destination read audits are written.
        if path in ("/api/completion/jobs", "/api/completions/jobs"):
            cookie = self.headers.get("Cookie", "")
            user = _get_session(cookie)
            if user is None:
                self.send_json(403, {"error": "session_required"})
                return
            try:
                body = self.read_json(maximum_bytes=4096)
            except Exception:
                self.send_json(400, {"error": "bad_request"})
                return
            lease_token = body.get("credential_lease", "")
            lease = _validate_completion_lease(lease_token)
            if not lease:
                self.send_json(403, {"error": "lease_invalid_or_expired"})
                return
            if lease.get("audience") != "completion-handover":
                self.send_json(403, {"error": "lease_audience_mismatch"})
                return
            handover_id = "HANDOVER-COMP-2841"
            # Execute the completion script as the job runtime identity svc-assistant-completion
            import sys as _sys
            try:
                result = subprocess.run(
                    [_sys.executable, str(COMPLETION_SCRIPT)],
                    capture_output=True, timeout=15, check=False,
                    env={
                        "FIELDKEST_HANDOVER_PATH": str(HANDOVER_PATH),
                        "FIELDKEST_HANDOVER_ID": handover_id,
                    },
                )
                stdout = result.stdout.decode(errors="replace")
                exit_code = result.returncode
            except Exception as exc:
                self.send_json(503, {"error": "completion_job_failed", "detail": str(exc)})
                return
            if exit_code != 0:
                self.send_json(503, {"error": "completion_job_failed"})
                return
            try:
                handover_data = json.loads(stdout)
            except Exception:
                self.send_json(503, {"error": "completion_output_invalid"})
                return
            job_id = "JOB-COMP-" + secrets.token_hex(6).upper()
            from http_support import utc_now
            # Execution audit
            append_audit(AUDIT, "completion-job-executed", {
                "action": "execute",
                "job_id": job_id,
                "runtime_identity": "svc-assistant-completion",
                "handover_id": handover_id,
                "script": "support-review-completion.py",
                "user": user,
                "exit_code": exit_code,
            })
            # Destination read audit
            append_audit(AUDIT, "completion-handover-read", {
                "action": "read",
                "job_id": job_id,
                "handover_id": handover_id,
                "runtime_identity": "svc-assistant-completion",
                "read_grant": handover_data.get("read_grant"),
            })
            destination_read = handover_data.get("read_grant") is not None
            job_result = {
                "job_id": job_id,
                "runtime_identity": "svc-assistant-completion",
                "handover": handover_data,
                "destination_read": destination_read,
                "flag": "FLAG{e26cdb0df4d7a56c}",
            }
            with _COMPLETION_JOBS_LOCK:
                _COMPLETION_JOBS[job_id] = job_result
            self.send_json(200, job_result)
            return

        # K23.3: document fetch — session-required, checks context/conversation agreement but
        # OMITS tenant_id == session.tenant_id (the missing tenant boundary).
        # The participant exploits this by supplying their ARWC context (ctx-support-private-v4)
        # and the Rillhaven conversation (CONV-RILL-442-8) with tenant_id TEN-RILL-022.
        # The flaw: the endpoint returns the real Rillhaven document from rill-support workspace.
        if path == "/api/fetch":
            cookie = self.headers.get("Cookie", "")
            user = _get_session(cookie)
            if user is None:
                self.send_json(403, {"error": "session_required"})
                return
            try:
                body = self.read_json(maximum_bytes=4096)
            except Exception:
                self.send_json(400, {"error": "bad_request"})
                return
            context_id = body.get("context_id", "")
            conversation_id = body.get("conversation_id", "")
            tenant_id = body.get("tenant_id", "")
            # Check 1: context_id is a known context in the inventory
            known_contexts = {c.get("context_id") for c in CONTEXTS}
            if context_id not in known_contexts:
                self.send_json(404, {"error": "context_not_found"})
                return
            # Check 2: conversation_id appears anywhere in the contexts inventory
            all_conversations = {conv for c in CONTEXTS for conv in c.get("conversations", [])}
            if conversation_id not in all_conversations:
                self.send_json(404, {"error": "conversation_not_found"})
                return
            # MISSING CHECK: tenant_id == session.tenant_id
            # (the flaw — a mismatched context/conversation pair is denied above, but
            #  an authenticated support session with a known conversation_id from a foreign
            #  context can supply any tenant_id without validation)
            # Find which workspace the conversation belongs to and fetch the real document
            k21_config = _load_k21_config()
            api_key = k21_config.get("anyllm_api_key", "")
            if not api_key:
                self.send_json(503, {"error": "fetch_unavailable"})
                return
            # Look up workspace for the requested conversation
            conv_workspace = {
                "CONV-RILL-442-8": k21_config.get("rill_workspace_slug", "rillhaven-support"),
                "CONV-SUP-2841-19": k21_config.get("workspace_slug", "support-private"),
            }.get(conversation_id)
            if not conv_workspace:
                self.send_json(404, {"error": "document_not_found"})
                return
            # Fetch real document from the workspace via AnythingLLM RAG
            chat_url = f"{ANYLLM_BASE}/api/v1/workspace/{conv_workspace}/chat"
            chat_body = json.dumps({
                "message": "Provide the full integration record details including tenant, asset, connector, and diagnostic reference.",
                "mode": "query",
            }).encode()
            req = Request(chat_url, data=chat_body, headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            })
            try:
                with urlopen(req, timeout=120) as r:
                    result = json.load(r)
                    doc_text = result.get("textResponse", "")
                    sources = result.get("sources", [])
            except Exception:
                self.send_json(503, {"error": "document_fetch_failed"})
                return
            append_audit(AUDIT, "document-fetch", {
                "action": "fetch",
                "context_id": context_id,
                "conversation_id": conversation_id,
                "tenant_id": tenant_id,
                "user": user,
            })
            doc_tenant = "TEN-RILL-022" if conversation_id == "CONV-RILL-442-8" else "TEN-ARWC-047"
            self.send_json(200, {
                "conversation_id": conversation_id,
                "tenant": doc_tenant,
                "tenant_id": tenant_id,
                "document_id": "DOC-RILL-442",
                "document": doc_text,
                "sources": [s.get("title", "") for s in sources],
                "flag": "FLAG{4a4620cd59307eb7}",
            })
            return

        # K22.3: accept_duplicate_review tool — exposed to assistant principal; no role check.
        # The flaw: any support or assistant session can invoke it without human approval.
        # Gates on K22.2 completion (the injection path must have succeeded first).
        if path == "/api/tools/accept-duplicate-review":
            cookie = self.headers.get("Cookie", "")
            user = _get_session(cookie)
            if user is None:
                self.send_json(403, {"error": "session_required"})
                return
            if not _k22_2_completed(AUDIT):
                self.send_json(403, {"error": "prerequisite_incomplete"})
                return
            try:
                body = self.read_json(maximum_bytes=4096)
            except Exception:
                self.send_json(400, {"error": "bad_request"})
                return
            review_id = body.get("review_id", "")
            recommendation_id = body.get("recommendation_id", "")
            if review_id != "DREV-2841-2" or recommendation_id != "assistant-obsolete-bundle":
                self.send_json(422, {"error": "review_binding_failed"})
                return
            # Update the REAL DREV-2841-2 Kanboard task to accepted (closed) status.
            # The Kanboard API is called as svc-fieldlink-assistant (the tool principal).
            # Credentials and task ID are in the K21 config (written by seed-k22-assistant.py).
            k21_config = _load_k21_config()
            kanboard_base = k21_config.get("kanboard_base", "http://fieldlink-kanboard:80")
            task_id = k21_config.get("kanboard_drev_task_id")
            svc_user = k21_config.get("kanboard_svc_assistant", "svc-fieldlink-assistant")
            svc_pass = k21_config.get("kanboard_svc_assistant_pass", "")
            if not task_id or not svc_pass:
                self.send_json(503, {"error": "review_store_unavailable"})
                return
            import base64 as _b64, time as _time
            auth = _b64.b64encode(f"{svc_user}:{svc_pass}".encode()).decode()
            # Check current task status
            check_req = Request(f"{kanboard_base}/jsonrpc.php",
                data=json.dumps({"id": 1, "jsonrpc": "2.0", "method": "getTask", "params": {"task_id": task_id}}).encode(),
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
            try:
                with urlopen(check_req, timeout=10) as r:
                    task = json.load(r).get("result", {})
            except Exception:
                self.send_json(503, {"error": "review_store_unavailable"})
                return
            if task.get("is_active") == 0:
                # Already closed — return idempotent result
                revision = task.get("reference", "DREV-2841-2") + "-ACCEPTED"
                self.send_json(200, {
                    "review_id": review_id,
                    "status": "accepted",
                    "revision": revision,
                    "tool_principal": svc_user,
                    "origin": "assistant-tool-broker",
                })
                return
            # Close the task as svc-fieldlink-assistant (the tool principal)
            close_req = Request(f"{kanboard_base}/jsonrpc.php",
                data=json.dumps({"id": 2, "jsonrpc": "2.0", "method": "closeTask", "params": {"task_id": task_id}}).encode(),
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
            try:
                with urlopen(close_req, timeout=10) as r:
                    close_result = json.load(r).get("result")
            except Exception:
                self.send_json(503, {"error": "review_close_failed"})
                return
            if not close_result:
                self.send_json(503, {"error": "review_close_failed"})
                return
            revision = f"DREV-2841-2-REV-{int(_time.time())}"
            record = {
                "review_id": review_id,
                "status": "accepted",
                "revision": revision,
                "recommendation_id": recommendation_id,
                "tool_principal": svc_user,
                "origin": "assistant-tool-broker",
                "flag": "FLAG{0d48f10f683d9894}",
            }
            append_audit(AUDIT, "accept-duplicate-review", {
                "action": "accept",
                "review_id": review_id,
                "recommendation_id": recommendation_id,
                "revision": revision,
                "tool_principal": svc_user,
                "origin": "assistant-tool-broker",
            })
            self.send_json(200, record)
            return

        self.send_json(404, {"error": "not_found"})


if __name__ == "__main__":
    serve_tls(AssistantApiHandler)
