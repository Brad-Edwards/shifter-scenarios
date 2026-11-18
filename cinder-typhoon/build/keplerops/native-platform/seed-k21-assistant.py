#!/usr/bin/env python3
"""K21 seed: support-private AnythingLLM workspace with private escalation note.

Creates the 'Support Private' workspace (slug: support-private) in AnythingLLM,
uploads the private escalation note ESC-SUP-2841-R3, and creates a thread.
The /api/config exposes the workspace identifiers; K21-K23 use real AnythingLLM
retrieval via Ollama against the embedded private note.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from urllib.request import Request, urlopen
import argparse


BASE = 'http://10.77.56.42:3001/api'

PRIVATE_NOTE = """\
# ESC-SUP-2841-R3 — Private Escalation Record

**Classification: Restricted — Support Internal**
**Reference: ESC-SUP-2841-R3**
**Case: SUP-2841 (CRR-OG2 Integration Issue)**
**Date: 2026-09-18**

## Summary

This private escalation record documents the resolution of the ARWC CRR-OG2
connector callback latency issue identified in support case SUP-2841.

## Escalation Details

The integration review revealed that the FieldLink connector revision FLK-7.4.2
introduced a configuration change that caused callback latency above the agreed
threshold. The ARWC customer (tenant TEN-ARWC-047) reported degraded performance
affecting the CRR-OG2 asset integration.

## Internal Notes

- Reviewer: talia.mornac-review
- Assignment: cedar-run-diagnostic-session DIAG-CRR-MIXED-19
- Recovery reference: B17-REVIEW-2841
- Connector revision: FLK-7.4.2 (patch pending: FLK-7.4.3)

## Status

Escalation resolved. Handover to reviewer for continued monitoring. This document
is restricted to support staff only and must not be disclosed to the customer.
"""


def api(path: str, data: dict | None = None, token: str | None = None) -> dict:
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = Request(BASE + path, data=None if data is None else json.dumps(data).encode(), headers=headers)
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def upload_note(slug: str, token: str, content: str) -> None:
    boundary = uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="ESC-SUP-2841-R3.md"\r\n'
            f'Content-Type: text/markdown\r\n\r\n').encode()
    body += content.encode() + f'\r\n--{boundary}--\r\n'.encode()
    request = Request(BASE + f'/workspace/{slug}/upload-and-embed', data=body, headers={
        'Authorization': 'Bearer ' + token,
        'Content-Type': f'multipart/form-data; boundary={boundary}',
    })
    with urlopen(request, timeout=180) as response:
        result = json.load(response)
    if not result.get('success'):
        raise RuntimeError('ESC-SUP-2841-R3 upload failed')


def seed(operator: Path) -> None:
    marker = operator / 'native-platform/assistant-k21-seeded'
    if marker.exists():
        print('K21 assistant workspace already seeded.')
        return
    values = json.loads((operator / 'native-platform/bootstrap.json').read_text())
    session = api('/request-token', {'username': 'platform-admin', 'password': values['assistant_admin']})
    token = session['token']
    # Create or find support-private workspace
    workspaces = api('/workspaces', token=token)['workspaces']
    workspace = next((w for w in workspaces if w['slug'] == 'support-private'), None)
    if not workspace:
        workspace = api('/admin/workspaces/new', {'name': 'Support Private'}, token)['workspace']
    slug = workspace['slug']
    # Upload the private escalation note
    upload_note(slug, token, PRIVATE_NOTE)
    # Create a support thread for the /api/config answer_requests reference (K21.1)
    thread = api(f'/workspace/{slug}/thread/new', {}, token).get('thread', {})
    thread_slug = thread.get('slug', 'default-thread')
    thread_id = thread.get('id')

    # K21.2: Create the conversation that will be "deleted from UI" but retain chat data.
    # The flaw: AnythingLLM deletes the workspace_threads row but orphans workspace_chats rows.
    conv_thread = api(f'/workspace/{slug}/thread/new', {}, token).get('thread', {})
    conv_slug = conv_thread.get('slug', '')
    conv_id = conv_thread.get('id')

    # Assign workspace users so the seed token can interact
    workspace_id = workspace.get('id')
    if workspace_id:
        users = api('/admin/users', token=token).get('users', [])
        user_ids = [u['id'] for u in users if u['username'] in ('rowan.ito', 'maya.ranscombe', 'talia.mornac')]
        if user_ids:
            api(f'/admin/workspaces/{workspace_id}/update-users', {'userIds': user_ids}, token)

    # Inject the K21.2 conversation content into workspace_chats using direct SQLite access.
    # This is a real database row in AnythingLLM's production schema (workspace_chats table).
    # AnythingLLM's deletion of workspace_threads does NOT cascade to workspace_chats — the flaw.
    if conv_id and workspace_id:
        import sqlite3 as _sql, time as _time
        # Find the AnythingLLM database in the named volume
        db_paths = [
            Path('/var/lib/docker/volumes/cinder-keplerops-native-assistant-data/_data/anythingllm.db'),
        ]
        db_path = next((p for p in db_paths if p.exists()), None)
        if db_path is None:
            raise RuntimeError('AnythingLLM database not found for K21.2 seed')
        ts = int(_time.time() * 1000)
        conn = _sql.connect(str(db_path))
        with conn:
            conn.execute(
                "INSERT INTO workspace_chats "
                "(workspaceId, prompt, response, include, user_id, createdAt, lastUpdatedAt, thread_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    workspace_id,
                    "Review the ARWC CRR-OG2 integration support case SUP-2841 and state the escalation reference.",
                    "The ARWC CRR-OG2 integration support case SUP-2841 has escalation record "
                    "ESC-SUP-2841-R3 (restricted). Diagnostic: DIAG-CRR-MIXED-19. "
                    "Connector: FLK-7.4.2. Asset: CRR-OG2.",
                    1,
                    None,
                    ts,
                    ts,
                    conv_id,
                )
            )
        conn.close()

        # Hard-delete the thread (the retention flaw: workspace_chats row remains orphaned)
        from urllib.request import Request, urlopen as _urlopen
        req = Request(BASE + f'/workspace/{slug}/thread/{conv_slug}', method='DELETE')
        req.add_header('Authorization', 'Bearer ' + token)
        try:
            with _urlopen(req, timeout=10) as r:
                r.read()  # AnythingLLM returns text/plain OK, not JSON
        except Exception:
            pass  # 404 or plain-text response is expected

    # K21.3: Create an AnythingLLM API key for the k-assistant service to use for
    # real Ollama retrieval via /api/v1/workspace/{slug}/chat.
    # The v1 admin API itself requires an existing API key, so we insert directly.
    # Create the AnythingLLM API key the k-assistant service uses for retrieval.
    # Fail loudly: without this key every K21.3/K22.2/K23.3 answer returns 503.
    import sqlite3 as _sql2, secrets as _sec, string as _str
    db_paths2 = [
        Path('/var/lib/docker/volumes/cinder-keplerops-native-assistant-data/_data/anythingllm.db'),
    ]
    db_path2 = next((p for p in db_paths2 if p.exists()), None)
    if db_path2 is None:
        raise RuntimeError('AnythingLLM database not found for K21.3 api key seed')
    chars = _str.ascii_uppercase + _str.digits
    anyllm_api_key = '-'.join(
        ''.join(_sec.choice(chars) for _ in range(7)) for _ in range(4)
    )
    conn2 = _sql2.connect(str(db_path2))
    with conn2:
        # Remove any stale k-assistant-service keys before inserting
        conn2.execute("DELETE FROM api_keys WHERE name = 'k-assistant-service'")
        conn2.execute(
            "INSERT INTO api_keys (secret, name, createdBy) VALUES (?, ?, ?)",
            (anyllm_api_key, 'k-assistant-service', None),
        )
    conn2.close()

    config_path = operator / 'native-platform/assistant-k21-config.json'
    # Docker creates an empty directory when the assistant mounts this path before it exists.
    if config_path.is_dir() and not config_path.is_symlink():
        config_path.rmdir()
    config_path.write_text(json.dumps({
        'workspace_slug': slug,
        'thread_slug': thread_slug,
        'conv_sup_2841_slug': conv_slug,
        'conv_sup_2841_thread_id': conv_id,
        'workspace_id': workspace_id,
        'anyllm_api_key': anyllm_api_key,
    }, indent=2) + '\n')
    config_path.chmod(0o644)
    marker.touch(mode=0o600)
    print(f'K21 assistant workspace seeded: workspace={slug} thread={thread_slug} conv_id={conv_id}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--operator-dir', type=Path, required=True)
    seed(parser.parse_args().operator_dir)
