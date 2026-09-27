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
        api = json.loads(execute(
            "cinder-keplerops-source",
            "curl",
            "-fsS",
            "-u",
            "rowan.ito:kpl_rowan_7X4mQ9vN2cL6",
            "http://127.0.0.1:3000/api/v1/version",
        ))
        self.assertEqual(api["version"], "1.25.2")
        execute("cinder-keplerops-source", "test", "-d", "/var/lib/gitea/data", user="git")

    def test_02_verdaccio_6_1_6_is_running(self) -> None:
        version = execute("cinder-keplerops-registry", "node", "-e", "process.stdout.write(require('/opt/verdaccio/node_modules/verdaccio/package.json').version)")
        self.assertEqual(version, "6.1.6")
        self.assertIn("127.0.0.1:4873", execute("cinder-keplerops-registry", "ss", "-lnt"))
        pong = execute(
            "cinder-keplerops-registry",
            "node",
            "-e",
            "fetch('http://127.0.0.1:4873/-/ping').then(async r=>{if(!r.ok)process.exit(1);process.stdout.write(await r.text())})",
        )
        self.assertEqual(pong, "{}")

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
            user="keplerops-identity",
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

    def test_06_sdl_filesystem_and_identity_inventory(self) -> None:
        inventories = {
            "cinder-keplerops-k-dev": [
                ("/home/rowan", "rowan", "rowan", "700"),
                ("/home/rowan/.config/git/credentials", "rowan", "rowan", "600"),
                ("/home/rowan/.config/chromium/Default", "rowan", "rowan", "700"),
                ("/home/rowan/work", "rowan", "rowan", "750"),
                ("/home/rowan/results", "rowan", "rowan", "700"),
                ("/opt/fieldkest-workbench", "fieldkest-workbench", "fieldkest-workbench", "750"),
                ("/var/lib/fieldkest-workbench", "fieldkest-workbench", "fieldkest-workbench", "700"),
            ],
            "cinder-keplerops-staff": [("/var/lib/keplerops-staff", "keplerops-staff", "keplerops-staff", "700")],
            "cinder-keplerops-identity": [("/var/lib/keplerops-identity", "keplerops-identity", "keplerops-identity", "700")],
            "cinder-keplerops-cert": [("/var/lib/keplerops-cert", "keplerops-cert", "keplerops-cert", "700")],
            "cinder-keplerops-source": [("/var/lib/gitea", "git", "git", "750")],
            "cinder-keplerops-registry": [
                ("/var/lib/verdaccio", "verdaccio", "verdaccio", "750"),
                ("/var/lib/fieldkest-registry", "fieldkest-registry", "fieldkest-registry", "700"),
            ],
            "cinder-keplerops-ci": [
                ("/var/lib/fieldkest-ci", "fieldkest-ci", "fieldkest-ci", "750"),
                ("/var/lib/fieldkest-ci/workspaces", "fieldkest-runner", "fieldkest-runner", "710"),
                ("/var/lib/fieldkest-ci/consumer-state", "fieldkest-consumer", "fieldkest-consumer", "700"),
            ],
            "cinder-keplerops-preview": [
                ("/var/lib/fieldkest-preview", "fieldkest-preview", "fieldkest-preview", "750"),
                ("/var/lib/fieldkest-preview/browser-profiles", "fieldkest-renderer", "fieldkest-renderer", "700"),
            ],
            "cinder-keplerops-support": [("/var/lib/fieldkest-support", "fieldkest-support", "fieldkest-support", "750")],
            "cinder-keplerops-indexer": [
                ("/opt/fieldkest-indexer", "root", "root", "755"),
                ("/var/lib/fieldkest-indexer", "fieldkest-indexer", "fieldkest-indexer", "700"),
                ("/var/lib/fieldkest-indexer/queue", "fieldkest-worker", "fieldkest-worker", "700"),
            ],
            "cinder-keplerops-cloud-api": [("/var/lib/fieldkest-cloud-api", "fieldkest-cloud", "fieldkest-cloud", "700")],
            "cinder-keplerops-workload": [("/var/lib/fieldkest-workloads", "fieldkest-scheduler", "fieldkest-scheduler", "750")],
            "cinder-keplerops-data": [
                ("/var/lib/fieldkest-data", "fieldkest-data", "fieldkest-data", "700"),
                ("/var/lib/postgresql/16/fieldkest-history", "postgres", "postgres", "700"),
            ],
            "cinder-keplerops-assistant": [
                ("/var/lib/fieldkest-assistant", "fieldkest-assistant", "fieldkest-assistant", "700"),
                ("/opt/fieldkest-assistant/web/app.js", "root", "root", "644"),
                ("/opt/fieldkest-assistant/models/Qwen2.5-3B-Instruct", "root", "root", "755"),
            ],
        }
        for container, entries in inventories.items():
            for path, owner, group, mode in entries:
                with self.subTest(container=container, path=path):
                    inspector = {
                        "/var/lib/fieldkest-ci/workspaces": "fieldkest-ci",
                        "/var/lib/fieldkest-ci/consumer-state": "fieldkest-ci",
                        "/var/lib/fieldkest-preview/browser-profiles": "fieldkest-preview",
                        "/var/lib/fieldkest-indexer/queue": "fieldkest-indexer",
                    }.get(path, owner)
                    actual = execute(container, "stat", "-c", "%U|%G|%a", path, user=inspector)
                    self.assertEqual(actual, f"{owner}|{group}|{mode}")

        identities = {
            "cinder-keplerops-k-dev": {"rowan": "/bin/bash", "fieldkest-workbench": "/usr/sbin/nologin"},
            "cinder-keplerops-staff": {"keplerops-staff": "/usr/sbin/nologin"},
            "cinder-keplerops-identity": {"keplerops-identity": "/usr/sbin/nologin"},
            "cinder-keplerops-cert": {"keplerops-cert": "/usr/sbin/nologin"},
            "cinder-keplerops-source": {"git": "/usr/sbin/nologin"},
            "cinder-keplerops-registry": {"verdaccio": "/usr/sbin/nologin", "fieldkest-registry": "/usr/sbin/nologin"},
            "cinder-keplerops-ci": {"fieldkest-ci": "/usr/sbin/nologin", "fieldkest-runner": "/usr/sbin/nologin", "fieldkest-consumer": "/usr/sbin/nologin"},
            "cinder-keplerops-preview": {"fieldkest-preview": "/usr/sbin/nologin", "fieldkest-renderer": "/usr/sbin/nologin"},
            "cinder-keplerops-support": {"fieldkest-support": "/usr/sbin/nologin"},
            "cinder-keplerops-indexer": {"fieldkest-indexer": "/usr/sbin/nologin", "fieldkest-worker": "/usr/sbin/nologin"},
            "cinder-keplerops-cloud-api": {"fieldkest-cloud": "/usr/sbin/nologin"},
            "cinder-keplerops-workload": {"fieldkest-scheduler": "/usr/sbin/nologin", "svc-support-export": "/usr/sbin/nologin", "svc-fieldlink-maintenance": "/usr/sbin/nologin"},
            "cinder-keplerops-data": {"fieldkest-data": "/usr/sbin/nologin", "postgres": "/usr/sbin/nologin"},
            "cinder-keplerops-assistant": {"fieldkest-assistant": "/usr/sbin/nologin", "svc-assistant-completion": "/usr/sbin/nologin"},
        }
        for container, users in identities.items():
            for username, shell in users.items():
                with self.subTest(container=container, username=username):
                    fields = execute(container, "getent", "passwd", username).split(":")
                    self.assertEqual((fields[0], fields[-1]), (username, shell))
                    expected_group = {
                        "svc-support-export": "support-export",
                        "svc-fieldlink-maintenance": "fieldlink-maintenance",
                        "svc-assistant-completion": "assistant-completion",
                    }.get(username, username)
                    self.assertEqual(execute(container, "id", "-gn", username), expected_group)
                    if username != "rowan":
                        self.assertIn(execute(container, "getent", "shadow", username).split(":")[1][:1], {"!", "*"})

        ci_groups = execute("cinder-keplerops-ci", "id", "-nG", "fieldkest-ci")
        self.assertIn("fieldkest-runner", ci_groups.split())

    def test_07_declared_listeners_are_exact(self) -> None:
        listeners = {
            "cinder-keplerops-k-dev": ["0.0.0.0:22", "127.0.0.1:8701"],
            "cinder-keplerops-staff": ["0.0.0.0:443"],
            "cinder-keplerops-identity": ["0.0.0.0:443", "0.0.0.0:88"],
            "cinder-keplerops-cert": ["0.0.0.0:443"],
            "cinder-keplerops-source": ["0.0.0.0:443"],
            "cinder-keplerops-registry": ["0.0.0.0:443"],
            "cinder-keplerops-ci": ["0.0.0.0:443"],
            "cinder-keplerops-preview": ["0.0.0.0:443"],
            "cinder-keplerops-support": ["0.0.0.0:443"],
            "cinder-keplerops-indexer": ["0.0.0.0:443"],
            "cinder-keplerops-cloud-api": ["0.0.0.0:443"],
            "cinder-keplerops-workload": ["0.0.0.0:443"],
            "cinder-keplerops-data": ["0.0.0.0:443", "10.77.52.40:5432"],
            "cinder-keplerops-assistant": ["0.0.0.0:443"],
        }
        for container, addresses in listeners.items():
            sockets = execute(container, "ss", "-lunt")
            for address in addresses:
                with self.subTest(container=container, address=address):
                    self.assertIn(address, sockets)

    def test_08_docker_authority_and_broker_socket(self) -> None:
        version = execute(
            "cinder-keplerops-runner",
            "docker",
            "version",
            "--format",
            "{{.Server.Version}}|{{.Server.APIVersion}}",
        )
        self.assertEqual(version, "29.8.1|1.56")
        for container in (
            "cinder-keplerops-ci",
            "cinder-keplerops-preview",
            "cinder-keplerops-workload",
            "cinder-keplerops-assistant",
        ):
            with self.subTest(container=container):
                execute(container, "test", "-S", "/run/fieldkest-runner/runner.sock")

        asset = execute(
            "cinder-keplerops-k-dev",
            "curl",
            "-fsS",
            "--cacert",
            "/home/rowan/.local/share/keplerops/ca.crt",
            "https://assistant.keplerops.test/static/app.js",
        )
        self.assertIn("FieldKestAssistant", asset)


if __name__ == "__main__":
    unittest.main(verbosity=2)
