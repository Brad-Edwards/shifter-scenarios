"""Startup and ordinary authorization checks for the genuine support integration."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

RUNTIME = Path(__file__).resolve().parents[1] / 'build/keplerops/runtime'


class SupportPlatformTests(unittest.TestCase):
    def test_startup_and_operator_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            credentials = Path(directory) / 'credentials.json'
            credentials.write_text(json.dumps({
                'schema': 'fieldkest.runtime-credentials/v1',
                'credentials': {name: str(index) * 40 for index, name in enumerate((
                    'support_rowan_session', 'support_reviewer_session', 'support_delivery_token', 'assistant_tool_session'), 1)},
            }))
            result = subprocess.run(
                ['python3', '-c', '''
from email.message import Message
from support import SupportHandler
handler = object.__new__(SupportHandler)
handler.headers = Message()
assert not handler._authorized()
handler.headers['Authorization'] = 'Bearer ' + '1' * 40
assert handler._authorized() and handler.principal == 'rowan.ito'
handler.headers.replace_header('Authorization', 'Bearer wrong')
assert not handler._authorized()
handler.headers.replace_header('Authorization', 'Bearer ' + '4' * 40)
assert handler._authorized() and handler.principal == 'svc-fieldlink-assistant'
responses = []
handler.send_json = lambda status, value: responses.append(status)
handler.do_POST()
assert responses == [403]
'''], cwd=RUNTIME,
                env={**os.environ, 'FIELDKEST_CREDENTIALS_FILE': str(credentials)},
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
