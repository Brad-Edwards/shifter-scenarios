"""Check private creation and repeat application of the dev-only desktop login."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).parent / 'guest/fieldlink-desktop-login.py'
SPEC = importlib.util.spec_from_file_location('desktop_login', SCRIPT)
assert SPEC is not None and SPEC.loader is not None
LOGIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LOGIN)


class DevelopmentDesktopLoginTests(unittest.TestCase):
    def test_create_private_login_then_reapply_same_login(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'operator'
            with patch.object(LOGIN, 'Path', return_value=directory), \
                 patch.object(LOGIN.os, 'geteuid', return_value=0), \
                 patch.object(LOGIN.socket, 'gethostname', return_value='cinder-fieldlink-dev'), \
                 patch.object(LOGIN.secrets, 'token_urlsafe', return_value='dev-only-test-value') as generate, \
                 patch.object(LOGIN.subprocess, 'run') as apply:
                # CI can run as a normal user; model the owner check without
                # changing any real file ownership.
                real_stat = Path.stat

                def root_owner(path, *args, **kwargs):
                    result = real_stat(path, *args, **kwargs)
                    return type('PrivateStat', (), {'st_uid': 0, 'st_mode': result.st_mode})()

                with patch.object(Path, 'stat', root_owner):
                    LOGIN.main()
                    LOGIN.main()
                path = directory / 'development-desktop-login.json'
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(json.loads(path.read_text())['username'], 'rowan')
                generate.assert_called_once_with(24)
                self.assertEqual(apply.call_count, 2)
                self.assertEqual(apply.call_args_list[0], apply.call_args_list[1])
                self.assertEqual(apply.call_args.kwargs['input'], 'rowan:dev-only-test-value\n')


if __name__ == '__main__':
    unittest.main()
