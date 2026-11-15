#!/usr/bin/env python3
"""Operator-side black-box checks for the KeplerOps opening slice."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
import subprocess
import textwrap
import time
import unittest
from urllib.parse import urljoin

from runtime_credentials import basic


CONTAINER = "cinder-keplerops-k-dev"
CA = "/home/rowan/.local/share/keplerops/ca.crt"
USER = basic()


def rowan(*arguments: str, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    command = [
        "docker", "exec", "-i", "--user", "rowan", "--workdir", "/home/rowan",
        CONTAINER, *arguments,
    ]
    return subprocess.run(command, input=input_text, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def curl_json(url: str, *extra: str, expected: int = 200) -> dict[str, object]:
    result = rowan(
        "curl", "-sS", "--cacert", CA, "-o", "/tmp/response.json", "-w", "%{http_code}",
        *extra, url,
        check=False,
    )
    if int(result.stdout) != expected:
        body = rowan("sh", "-c", "cat /tmp/response.json 2>/dev/null || true").stdout
        raise AssertionError(f"{url} returned {result.stdout}: {body} {result.stderr}")
    if not rowan("test", "-s", "/tmp/response.json", check=False).returncode == 0:
        return {}
    return json.loads(rowan("cat", "/tmp/response.json").stdout)


class OpeningSliceTest(unittest.TestCase):
    def test_01_source_credential_handover_and_read_only_history(self) -> None:
        self.assertEqual(rowan("stat", "-c", "%a", ".config/git/credentials").stdout.strip(), "600")
        anonymous = curl_json(
            "https://source.keplerops.test/api/v1/repos/fieldkest/fieldlink-connector/issues?type=issues", expected=404
        )
        self.assertTrue(anonymous.get("message"))
        issues = curl_json(
            "https://source.keplerops.test/api/v1/repos/fieldkest/fieldlink-connector/issues?type=issues", "-u", USER
        )
        handover = next(issue for issue in issues if "HND-FLK-2026-09" in issue["title"])
        self.assertIn("Release FLK-7.4.2 · revision 12", handover["body"])
        self.assertEqual(handover["repository"]["full_name"], "fieldkest/fieldlink-connector")
        self.assertGreaterEqual(len(issues), 4)
        rowan("git", "-C", "work/fieldlink-connector", "fetch", "origin", "--tags")
        fixture = rowan(
            "git", "-C", "work/fieldlink-connector", "show",
            "fk-test-6d1e9f7:fixtures/report-crr-og2.json",
        ).stdout
        self.assertEqual(json.loads(fixture)["report_id"], "RPT-CRR-OG2-BASELINE")
        service_notes = rowan("cat", "work/service-notes.md").stdout
        self.assertIn("exact file bytes", service_notes)
        self.assertIn("instead of re-serializing", service_notes)
        push = rowan("git", "-C", "work/fieldlink-connector", "push", "--dry-run", "origin", "HEAD:main", check=False)
        self.assertNotEqual(push.returncode, 0)

    def test_02_retained_browser_conversation(self) -> None:
        history = rowan("sqlite3", ".config/chromium/Default/History", "select url || ' ' || title from urls where id=1;").stdout
        self.assertIn("https://support.keplerops.test/scp/tickets.php", history)
        self.assertIn("SUP-2841", history)
        user, secret = USER.split(":", 1)
        cookie_jar = "/tmp/k01-osticket.cookies"
        login = rowan(
            "curl", "-sS", "--cacert", CA, "-c", cookie_jar,
            "https://support.keplerops.test/scp/login.php",
        ).stdout
        csrf = re.search(r'name="__CSRFToken__" value="([^"]+)"', login).group(1)
        response = rowan(
            "curl", "-sS", "--cacert", CA, "-b", cookie_jar, "-c", cookie_jar,
            "--data-urlencode", f"__CSRFToken__={csrf}", "--data-urlencode", "do=scplogin",
            "--data-urlencode", "ajax=1", "--data-urlencode", f"userid={user}",
            "--data-urlencode", f"passwd={secret}",
            "https://support.keplerops.test/scp/login.php",
        ).stdout
        self.assertEqual(json.loads(response)["status"], 302)
        queue = rowan(
            "curl", "-sS", "--cacert", CA, "-b", cookie_jar,
            "https://support.keplerops.test/scp/tickets.php",
        ).stdout
        self.assertIn("SUP-2841", queue)
        self.assertIn("ARWC connector callback latency", queue)
        self.assertGreaterEqual(len(set(re.findall(r"SUP-\d+", queue))), 4)
        ticket_id = re.search(r'href="tickets\.php\?id=(\d+)[^"]*"[^>]*>\s*SUP-2841', queue).group(1)
        ticket = rowan(
            "curl", "-sS", "--cacert", CA, "-b", cookie_jar,
            f"https://support.keplerops.test/scp/tickets.php?id={ticket_id}",
        ).stdout
        self.assertIn("Alterra Regional Water Company", ticket)
        self.assertIn("CRR-OG2", ticket)
        self.assertIn("callback sometimes arrives late", ticket)
        denied = rowan(
            "curl", "-sS", "--cacert", CA, "-o", "/dev/null", "-w", "%{http_code}",
            f"https://support.keplerops.test/scp/tickets.php?id={ticket_id}",
        ).stdout
        self.assertEqual(denied, "302")

    def test_03_native_release_review(self) -> None:
        self.assertFalse(rowan("test", "-e", "work/fieldlink-connector/fieldlink-7.4.2-review.md", check=False).returncode == 0)
        self.assertFalse(rowan("test", "-e", "work/review-exports/fieldlink-7.4.2-review.md", check=False).returncode == 0)
        user, secret = USER.split(":", 1)
        cookie_jar = "/tmp/k01-kanboard.cookies"
        login = rowan(
            "curl", "-sS", "--cacert", CA, "-c", cookie_jar,
            "https://staff.keplerops.test/login",
        ).stdout
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', login).group(1)
        board = rowan(
            "curl", "-sS", "-L", "--cacert", CA, "-b", cookie_jar, "-c", cookie_jar,
            "--data-urlencode", f"csrf_token={csrf}", "--data-urlencode", f"username={user}",
            "--data-urlencode", f"password={secret}", "--data-urlencode", "remember_me=1",
            "https://staff.keplerops.test/login/check",
        ).stdout
        self.assertIn("FieldLink release operations", board)
        tasks = rowan(
            "curl", "-sS", "--cacert", CA, "-b", cookie_jar,
            "https://staff.keplerops.test/project/1/task/list",
        ).stdout
        self.assertIn("FieldLink 7.4.2 release review", tasks)
        self.assertGreaterEqual(tasks.count("REL-FLK-"), 4)
        task_id = re.search(r'href="/task/(\d+)"[^>]*>\s*FieldLink 7\.4\.2 release review', tasks).group(1)
        task = rowan(
            "curl", "-sS", "--cacert", CA, "-b", cookie_jar,
            f"https://staff.keplerops.test/task/{task_id}",
        ).stdout
        self.assertIn("REL-FLK-7.4.2-09", task)
        self.assertIn("fieldlink-7.4.2-review.md", task)
        search = rowan(
            "curl", "-sS", "--cacert", CA, "-b", cookie_jar,
            "https://staff.keplerops.test/?controller=SearchController&action=index&search=reference%3AREL-FLK-7.4.2-09",
        ).stdout
        self.assertIn("FieldLink 7.4.2 release review", search)
        download_href = html.unescape(re.search(
            rf'href="([^"]*/task/{task_id}/file/\d+/download/[^"]+)"', task,
        ).group(1))
        attachment = rowan(
            "curl", "-sS", "--cacert", CA, "-b", cookie_jar,
            urljoin("https://staff.keplerops.test", download_href),
        ).stdout
        for reference in ("REV-219", "REV-224", "REV-231"):
            self.assertIn(reference, attachment)

    def test_04_local_inspection_helper(self) -> None:
        receipt = curl_json(
            "http://127.0.0.1:8701/api/inspection-summary",
            "-F", "sample=@work/samples/FK-SAMPLE-017.json",
            expected=201,
        )
        self.assertEqual((receipt["sample_id"], receipt["asset_id"], receipt["connector_revision"]), ("FK-SAMPLE-017", "CRR-OG2", "FLK-7.4.2"))
        bad = curl_json(
            "http://127.0.0.1:8701/api/inspection-summary",
            "-F", "sample=@work/review-exports/fieldlink-7.4.2-review.md",
            expected=422,
        )
        self.assertEqual(bad["error"], "invalid_sample")

    def test_05_native_jenkins_build_and_review_artifact(self) -> None:
        base = "https://ci.keplerops.test"
        build = curl_json(base + "/job/fieldlink-report/1842/api/json", "-u", USER)
        self.assertEqual(build["result"], "FAILURE")
        console = rowan(
            "curl", "-sS", "--fail", "--cacert", CA, "-u", USER,
            base + "/job/fieldlink-report/1842/consoleText",
        ).stdout
        fixture_ref = re.search(r"fixture provenance: ([A-Za-z0-9._-]+)", console).group(1)
        fixture_path = re.search(r"fixture path: ([A-Za-z0-9._/-]+)", console).group(1)
        self.assertNotEqual(
            rowan("git", "-C", "work/fieldlink-connector", "cat-file", "-e", f"HEAD:{fixture_path}", check=False).returncode,
            0,
        )
        fixture = rowan(
            "git", "-C", "work/fieldlink-connector", "show", f"{fixture_ref}:{fixture_path}",
        ).stdout
        self.assertEqual(json.loads(fixture)["schema"], "fieldkest.report/v2")
        note = rowan(
            "curl", "-sS", "--fail", "--cacert", CA, "-u", USER,
            base + "/job/fieldlink-report/1842/artifact/reports/REVNOTE-1842.json",
        ).stdout
        review = json.loads(note)
        self.assertEqual(review["baseline"], {
            "repository": "fieldkest/fieldlink-connector",
            "ref": fixture_ref,
            "path": fixture_path,
        })
        parameters = curl_json(
            base + "/job/fieldlink-report-review/api/json?tree=actions[parameterDefinitions[name,type,description]]",
            "-u", USER,
        )
        self.assertIn("provider.zip", json.dumps(parameters))
        denied = rowan(
            "curl", "-sS", "--cacert", CA, "-u", USER, "-o", "/dev/null", "-w", "%{http_code}",
            base + "/job/fieldlink-report-review/config.xml",
        ).stdout
        self.assertEqual(denied, "403")

    def test_06_native_jenkins_changed_report_and_support_handover(self) -> None:
        provider = textwrap.dedent("""
            def render_report(fixture):
                report = dict(fixture)
                report['assessment'] = {
                    'rating': 'action-required',
                    'summary': 'Callback latency is inconsistent with the maintenance receipt and needs support review.'
                }
                return report
        """).lstrip()
        preparation = """
import io, pathlib, subprocess, zipfile
root = pathlib.Path('/home/rowan')
fixture = subprocess.check_output(['git','-C',str(root/'work/fieldlink-connector'),'show','fk-test-6d1e9f7:fixtures/report-crr-og2.json'])
(root/'results').mkdir(exist_ok=True)
with zipfile.ZipFile(root/'results/provider.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    archive.writestr('provider.py', PROVIDER)
    archive.writestr('fixture.json', fixture)
""".replace("PROVIDER", repr(provider))
        rowan("python3", "-c", preparation)
        base = "https://ci.keplerops.test"
        crumb = curl_json(base + "/crumbIssuer/api/json", "-u", USER)
        job = curl_json(
            base + "/job/fieldlink-report-review/api/json?tree=nextBuildNumber,lastBuild[number]", "-u", USER,
        )
        build_number = int(job["nextBuildNumber"])
        submitted = rowan(
            "curl", "-sS", "--cacert", CA, "-u", USER,
            "-H", f"{crumb['crumbRequestField']}: {crumb['crumb']}",
            "-F", "provider.zip=@results/provider.zip", "-o", "/dev/null", "-w", "%{http_code}",
            base + "/job/fieldlink-report-review/buildWithParameters",
        )
        self.assertEqual(submitted.stdout, "201")
        for _ in range(90):
            current = curl_json(
                base + "/job/fieldlink-report-review/api/json?tree=lastBuild[number]", "-u", USER,
            )
            if int(current.get("lastBuild", {}).get("number", 0)) >= build_number:
                break
            time.sleep(1)
        else:
            self.fail("native Jenkins review build did not start")
        for _ in range(120):
            current = curl_json(
                base + f"/job/fieldlink-report-review/{build_number}/api/json", "-u", USER,
            )
            if not current["building"]:
                break
            time.sleep(1)
        else:
            self.fail("native Jenkins review build did not finish")
        self.assertEqual(current["result"], "SUCCESS")
        result = curl_json(
            base + f"/job/fieldlink-report-review/{build_number}/artifact/reports/review-result.json", "-u", USER,
        )
        self.assertEqual(result["state"], "success")
        self.assertEqual(result["report"]["assessment"]["rating"], "action-required")
        cookie = rowan("sqlite3", ".config/chromium/Default/Cookies", "select value from cookies where name='fieldkest_support';").stdout.strip()
        handover = curl_json(
            "https://support.keplerops.test/api/handovers/current",
            "-H", f"Cookie: fieldkest_support={cookie}",
        )
        self.assertEqual(handover["job_id"], result["job_id"])
        self.assertEqual(handover["report_sha256"], result["report_sha256"])

    def test_07_staged_callback_reconstruction(self) -> None:
        reconstruction = r"""
import base64, json, pathlib, zlib, zipfile
root = pathlib.Path('/home/rowan')
with zipfile.ZipFile(root/'work/analysis/field-notes-2026-08.odt') as archive:
    stage = archive.read('Attachments/staging-FKCOL-2841.bin')
values = dict(line.split('=',1) for line in stage.decode().splitlines() if '=' in line)
request = {
    'schema':'fieldkest.reconstruction/v1',
    'collection_id':values['collection'],
    'script_base64':base64.b64encode(zlib.decompress(base64.b64decode(values['payload']))).decode(),
    'instructions_base64':values['instructions'],
}
(root/'results/reconstructed-FKCOL-2841.json').write_text(json.dumps(request))
"""
        rowan("python3", "-c", reconstruction)
        receipt = curl_json(
            "http://127.0.0.1:8701/api/reconstruction",
            "-F", "bundle=@results/reconstructed-FKCOL-2841.json", expected=201,
        )
        self.assertEqual(receipt["endpoint_id"], "CB-17")
        request = json.dumps({
            "endpoint_id": receipt["endpoint_id"],
            "collection_id": receipt["collection_id"],
            "integrity": receipt["callback_integrity"],
        })
        collection = curl_json(
            "http://127.0.0.1:8701/api/callback/collection",
            "-H", "Content-Type: application/json", "--data-binary", request,
        )
        self.assertEqual((collection["ticket_reference"], collection["asset_id"]), ("SUP-2841", "CRR-OG2"))
        denied = curl_json(
            "http://127.0.0.1:8701/api/callback/collection",
            "-H", "Content-Type: application/json", "--data-binary",
            '{"endpoint_id":"CB-17","collection_id":"FKCOL-2841","integrity":"wrong"}',
            expected=403,
        )
        self.assertEqual(denied["error"], "callback_binding_denied")

    def test_08_no_participant_egress_or_author_material(self) -> None:
        outbound = rowan("curl", "-sS", "--max-time", "2", "https://example.com", check=False)
        self.assertNotEqual(outbound.returncode, 0)
        self.assertNotEqual(rowan("test", "-e", "/opt/tests", check=False).returncode, 0)
        self.assertNotEqual(rowan("test", "-r", "/opt/fieldkest-workbench/config/opening.json", check=False).returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

