"""Initialize an empty KDC and complete missing declared users without rotation."""

import json
import os
from pathlib import Path
import subprocess


STATE = Path('/var/lib/keplerops-identity')
INPUT = Path('/run/fieldlink/kerberos.json')
REALM = 'KEPLEROPS.TEST'


def run(arguments: list[str], data: str = '') -> None:
    subprocess.run(arguments, input=data, text=True, check=True, timeout=30,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def initialize() -> None:
    database = STATE / 'krb5kdc'
    started = STATE / '.native-initialization-started'
    complete = STATE / '.native-initialization-complete'
    retained = complete.exists() or ((database / 'principal').exists() and not started.exists())
    if not (database / 'principal').exists() and any(database.iterdir()):
        raise RuntimeError('KDC state is incomplete; refusing to overwrite it')
    values = json.loads(INPUT.read_text())
    if not (database / 'principal').exists():
        started.touch(mode=0o600)
        master = values['master']
        run(['kdb5_util', 'create', '-s', '-r', REALM], master + '\n' + master + '\n')
    def principals() -> set[str]:
        return set(subprocess.check_output(['kadmin.local', '-r', REALM, '-q', 'listprincs'],
                                          text=True, stderr=subprocess.DEVNULL, timeout=30).splitlines())
    existing = principals()
    required = {f'{name}@{REALM}' for name in values['users']}
    for principal, password in values['users'].items():
        if f'{principal}@{REALM}' not in existing:
            run(['kadmin.local', '-r', REALM, '-q', f'addprinc {principal}@{REALM}'],
                password + '\n' + password + '\n')
    if retained:
        if not required <= principals():
            raise RuntimeError('Native KDC declared user completion did not finish')
        return
    for service, filename in (('identity', 'identity'), ('staff', 'staff')):
        principal = f'HTTP/{service}.keplerops.test@{REALM}'
        required.add(principal)
        if principal not in existing:
            run(['kadmin.local', '-r', REALM], f'addprinc -randkey {principal}\nquit\n')
        if not (STATE / 'keytabs' / f'{filename}.keytab').exists():
            run(['kadmin.local', '-r', REALM],
                f'ktadd -norandkey -k {STATE}/keytabs/{filename}.keytab {principal}\nquit\n')
    if not required <= principals():
        raise RuntimeError('Native KDC principal initialization did not complete')
    for path in (STATE / 'keytabs').glob('*.keytab'):
        path.chmod(0o600)
    complete.touch(mode=0o600)


if __name__ == '__main__':
    os.umask(0o077)
    initialize()
