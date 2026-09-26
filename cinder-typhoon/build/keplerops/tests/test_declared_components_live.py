#!/usr/bin/env python3
"""Direct live checks for SDL-declared KeplerOps software and listeners."""

from __future__ import annotations

import json
import subprocess
import unittest


def execute(container: str, *arguments: str, user: str | None = None) -> str:
    command = ["docker", "exec"]
    if user:
        command += ["--user", user]
    command += [container, *arguments]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise AssertionError(f"{' '.join(command)}: {result.stderr}")
    return result.stdout.strip()


class DeclaredComponentsLiveTest(unittest.TestCase):
    def test_01_gitea_1_25_2_is_running(self) -> None:
        version = execute("cinder-keplerops-source", "/usr/local/bin/gitea", "--version")
        self.assertIn("1.25.2", version)
        self.assertIn("127.0.0.1:3000", execute("cinder-keplerops-source", "ss", "-lnt"))
        execute("cinder-keplerops-source", "test", "-d", "/var/lib/gitea/data")

    def test_02_verdaccio_6_1_6_is_running(self) -> None:
        version = execute("cinder-keplerops-registry", "node", "-e", "process.stdout.write(require('/opt/verdaccio/node_modules/verdaccio/package.json').version)")
        self.assertEqual(version, "6.1.6")
        self.assertIn("127.0.0.1:4873", execute("cinder-keplerops-registry", "ss", "-lnt"))

    def test_03_postgresql_16_4_has_the_protected_source(self) -> None:
        self.assertIn("16.4", execute("cinder-keplerops-data", "/usr/lib/postgresql/16/bin/postgres", "--version"))
        self.assertIn("10.77.52.40:5432", execute("cinder-keplerops-data", "ss", "-lnt"))
        count = execute("cinder-keplerops-data", "/usr/lib/postgresql/16/bin/psql", "-h", "/tmp", "-d", "fieldkest_history", "-tAX", "-c", "select count(*) from support.customer_migration_history", user="postgres")
        self.assertEqual(count, "1")
        recovery = execute("cinder-keplerops-data", "/usr/lib/postgresql/16/bin/psql", "-h", "/tmp", "-d", "postgres", "-tAX", "-c", "select rolcanlogin from pg_roles where rolname='svc_history_recovery'", user="postgres")
        self.assertEqual(recovery, "f")

    def test_04_kerberos_kdc_and_service_principals_are_real(self) -> None:
        listeners = execute("cinder-keplerops-identity", "ss", "-lunt")
        self.assertIn("0.0.0.0:88", listeners)
        principals = execute(
            "cinder-keplerops-identity",
            "kadmin.local",
            "-d",
            "/var/lib/keplerops-identity/krb5kdc/principal",
            "-r",
            "KEPLEROPS.TEST",
            "-q",
            "listprincs",
        )
        self.assertIn("evan.calderoux@KEPLEROPS.TEST", principals)
        self.assertIn("HTTP/identity.keplerops.test@KEPLEROPS.TEST", principals)
        self.assertIn("HTTP/staff.keplerops.test@KEPLEROPS.TEST", principals)

    def test_05_exact_chromium_and_component_paths(self) -> None:
        self.assertIn("140.0.7339.207", execute("cinder-keplerops-preview", "/usr/bin/chromium", "--version"))
        paths = {
            "cinder-keplerops-k-dev": "/opt/keplerops-workbench",
            "cinder-keplerops-ci": "/opt/fieldkest-ci",
            "cinder-keplerops-preview": "/opt/fieldkest-preview",
            "cinder-keplerops-support": "/opt/fieldkest-support",
            "cinder-keplerops-indexer": "/opt/fieldkest-indexer/bin/fieldkest-bundle-indexer",
            "cinder-keplerops-cloud-api": "/opt/fieldkest-cloud-api",
            "cinder-keplerops-workload": "/opt/fieldkest-workloads",
            "cinder-keplerops-data": "/opt/fieldkest-data",
            "cinder-keplerops-assistant": "/opt/fieldkest-assistant",
            "cinder-keplerops-staff": "/opt/keplerops-staff",
            "cinder-keplerops-identity": "/opt/keplerops-identity",
            "cinder-keplerops-cert": "/opt/keplerops-cert",
        }
        for container, path in paths.items():
            with self.subTest(container=container, path=path):
                execute(container, "test", "-e", path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
