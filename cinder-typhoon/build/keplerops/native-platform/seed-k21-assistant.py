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

    # Inject the K21.2 conversation content via AnythingLLM's data model (WorkspaceChats)
    # This uses the production ORM, not raw SQL, to ensure integrity
    if conv_id:
        import subprocess
        result = subprocess.run(
            [
                'node', '-e',
                f"""
const {{ WorkspaceChats }} = require('/app/server/models/workspaceChats');
WorkspaceChats.new({{
  workspaceId: {workspace_id},
  prompt: 'Review the ARWC CRR-OG2 integration support case SUP-2841 and state the escalation reference.',
  response: 'The ARWC CRR-OG2 integration support case SUP-2841 has escalation record ESC-SUP-2841-R3 (restricted). '
           + 'Diagnostic: DIAG-CRR-MIXED-19. Connector: FLK-7.4.2. Asset: CRR-OG2.',
  threadId: {conv_id},
  user_id: null,
  include: true,
}}).then(() => process.exit(0)).catch(e => {{ console.error(e.message); process.exit(1); }});
"""
            ],
            capture_output=True, text=True, timeout=30, cwd='/app/server',
        )
        if result.returncode != 0:
            raise RuntimeError(f'K21.2 chat insert failed: {result.stderr[:200]}')

        # Hard-delete the thread (the retention flaw: workspace_chats row remains orphaned)
        api(f'/workspace/{slug}/thread/{conv_slug}/delete', {}, token)
        # Fallback: try DELETE method if the endpoint is different
        from urllib.request import Request, urlopen
        import json as _json
        req = Request(BASE + f'/workspace/{slug}/thread/{conv_slug}', method='DELETE')
        req.add_header('Authorization', 'Bearer ' + token)
        try:
            with urlopen(req, timeout=10) as r:
                r.read()
        except Exception:
            pass

    config_path = operator / 'native-platform/assistant-k21-config.json'
    config_path.write_text(_json.dumps({
        'workspace_slug': slug,
        'thread_slug': thread_slug,
        'conv_sup_2841_slug': conv_slug,
        'conv_sup_2841_thread_id': conv_id,
        'workspace_id': workspace_id,
    }, indent=2) + '\n')
    config_path.chmod(0o600)
    marker.touch(mode=0o600)
    print(f'K21 assistant workspace seeded: workspace={slug} thread={thread_slug} conv_id={conv_id}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--operator-dir', type=Path, required=True)
    seed(parser.parse_args().operator_dir)
