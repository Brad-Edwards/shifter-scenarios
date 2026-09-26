#!/usr/bin/env python3
"""Operator-side black-box checks for the KeplerOps opening slice."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import textwrap
import unittest


CONTAINER = "cinder-keplerops-k-dev"
CA = "/home/rowan/.local/share/keplerops/ca.crt"
USER = "rowan.ito:kpl_rowan_7X4mQ9vN2cL6"


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
            "https://source.keplerops.test/api/fieldkest/handovers/current", expected=401
        )
        self.assertEqual(anonymous["error"], "authentication_required")
        handover = curl_json(
            "https://source.keplerops.test/api/fieldkest/handovers/current", "-u", USER
        )
        self.assertEqual((handover["handover_id"], handover["revision"]), ("HND-FLK-2026-09", 12))
        rowan("git", "-C", "work/fieldlink-connector", "fetch", "origin", "--tags")
        fixture = rowan(
            "git", "-C", "work/fieldlink-connector", "show",
            "fk-test-6d1e9f7:fixtures/report-crr-og2.json",
        ).stdout
        self.assertEqual(json.loads(fixture)["report_id"], "RPT-CRR-OG2-BASELINE")
        push = rowan("git", "-C", "work/fieldlink-connector", "push", "--dry-run", "origin", "HEAD:main", check=False)
        self.assertNotEqual(push.returncode, 0)

    def test_02_retained_browser_conversation(self) -> None:
        history = rowan(
            "sqlite3", ".config/chromium/Default/History", "select url from urls where id=1;"
        ).stdout.strip()
        self.assertEqual(history, "https://support.keplerops.test/conversations/SUP-2841")
        cookie = rowan(
            "sqlite3", ".config/chromium/Default/Cookies",
            "select value from cookies where name='fieldkest_support';",
        ).stdout.strip()
        conversation = curl_json(
            "https://support.keplerops.test/api/conversations/SUP-2841",
            "-H", f"Cookie: fieldkest_support={cookie}",
        )
        self.assertEqual((conversation["conversation_id"], conversation["revision"]), ("SUP-2841", 7))
        denied = curl_json(
            "https://support.keplerops.test/api/conversations/SUP-2841",
            "-H", "Cookie: fieldkest_support=wrong", expected=403,
        )
        self.assertEqual(denied["error"], "session_denied")

    def test_03_review_export_and_inspection(self) -> None:
        self.assertFalse(rowan("test", "-e", "work/fieldlink-connector/fieldlink-7.4.2-review.md", check=False).returncode == 0)
        review = rowan("cat", "work/review-exports/fieldlink-7.4.2-review.md").stdout
        self.assertIn("REL-FLK-7.4.2-09", review)
        self.assertIn("REV-231", review)
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

    def test_04_ci_importer_boundary(self) -> None:
        log = rowan(
            "curl", "-sS", "--fail", "--cacert", CA, "-u", USER,
            "https://ci.keplerops.test/api/runs/BLD-1842/log",
        ).stdout
        self.assertIn("fk-test-6d1e9f7", log)
        normal = curl_json(
            "https://ci.keplerops.test/api/reviews/import", "-u", USER,
            "-H", "Content-Type: application/json", "--data-binary",
            '{"schema":"fieldkest.review-import/v1","run_id":"BLD-1842","object":"inputs/report-request.json"}',
            expected=201,
        )
        self.assertEqual(normal["resolved_object"], "inputs/report-request.json")
        crossed = curl_json(
            "https://ci.keplerops.test/api/reviews/import", "-u", USER,
            "-H", "Content-Type: application/json", "--data-binary",
            '{"schema":"fieldkest.review-import/v1","run_id":"BLD-1842","object":"inputs/%2e%2e/reviews/REVNOTE-1842.json"}',
            expected=201,
        )
        self.assertEqual(crossed["object"]["review_id"], "REVNOTE-1842")
        denied = curl_json(
            "https://ci.keplerops.test/api/reviews/import", "-u", USER,
            "-H", "Content-Type: application/json", "--data-binary",
            '{"schema":"fieldkest.review-import/v1","run_id":"BLD-1842","object":"inputs/%2e%2e/%2e%2e/etc/passwd"}',
            expected=422,
        )
        self.assertEqual(denied["error"], "object_outside_repository")

    def test_05_isolated_changed_report_and_support_handover(self) -> None:
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
import base64, io, json, pathlib, subprocess, zipfile
root = pathlib.Path('/home/rowan')
fixture = subprocess.check_output(['git','-C',str(root/'work/fieldlink-connector'),'show','fk-test-6d1e9f7:fixtures/report-crr-og2.json'])
buffer = io.BytesIO()
with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
    archive.writestr('provider.py', PROVIDER)
    archive.writestr('fixture.json', fixture)
request = {'template':'report-consumer-v2','input':{'archive_base64':base64.b64encode(buffer.getvalue()).decode()}}
(root/'results/report-job-request.json').write_text(json.dumps(request))
""".replace("PROVIDER", repr(provider))
        rowan("python3", "-c", preparation)
        submitted = curl_json(
            "https://ci.keplerops.test/api/jobs", "-u", USER,
            "-H", "Content-Type: application/json", "--data-binary", "@results/report-job-request.json",
            expected=202,
        )
        result = curl_json(f"https://ci.keplerops.test/api/jobs/{submitted['job_id']}", "-u", USER)
        self.assertEqual(result["state"], "success")
        self.assertEqual(result["report"]["assessment"]["rating"], "action-required")
        cookie = rowan("sqlite3", ".config/chromium/Default/Cookies", "select value from cookies where name='fieldkest_support';").stdout.strip()
        handover = curl_json(
            "https://support.keplerops.test/api/handovers/current",
            "-H", f"Cookie: fieldkest_support={cookie}",
        )
        self.assertEqual(handover["job_id"], submitted["job_id"])
        self.assertEqual(handover["report_sha256"], result["report_sha256"])

    def test_06_staged_callback_reconstruction(self) -> None:
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

    def test_07_no_participant_egress_or_author_material(self) -> None:
        outbound = rowan("curl", "-sS", "--max-time", "2", "https://example.com", check=False)
        self.assertNotEqual(outbound.returncode, 0)
        self.assertNotEqual(rowan("test", "-e", "/opt/tests", check=False).returncode, 0)
        self.assertNotEqual(rowan("test", "-r", "/opt/fieldkest-workbench/config/opening.json", check=False).returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

