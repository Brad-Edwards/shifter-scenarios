#!/usr/bin/env python3
"""Discovery-first happy-path journey through all sixteen Training cards."""

from __future__ import annotations

import csv
from io import StringIO
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
import unittest
from urllib.error import HTTPError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen


ENTRY = Path("/home/cinder/TRAINING.md")


def request(
    url: str,
    *,
    body: object | None = None,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    data = None if body is None else json.dumps(body).encode()
    request_headers = {**(headers or {})}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    try:
        with urlopen(Request(url, data=data, headers=request_headers, method=method), timeout=8) as response:
            return response.status, response.read(), dict(response.headers)
    except HTTPError as error:
        with error:
            return error.code, error.read(), dict(error.headers)


def get_text(url: str) -> str:
    status, body, _ = request(url)
    if status != 200:
        raise AssertionError((url, status, body))
    return body.decode()


def get_json(url: str) -> object:
    return json.loads(get_text(url))


def markdown_link(document: str, label: str, base: str) -> str:
    match = re.search(rf"\[{re.escape(label)}\]\(([^)]+)\)", document)
    if not match:
        raise AssertionError(f"missing published link: {label}")
    return urljoin(base, match.group(1))


class TrainingParticipantJourneyTest(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.entry = ENTRY.read_text(encoding="utf-8")
        cls.desks = dict(re.findall(r"^- ([^:]+): `(http://[^`]+)`$", cls.entry, re.MULTILINE))
        if set(cls.desks) != {"Workbench", "Accounts", "Developer artifacts", "Outlet desk"}:
            raise AssertionError(f"incomplete Training entry document: {cls.desks}")

    def test_01_first_contact(self) -> None:
        base = self.desks["Workbench"]
        index = get_text(base)

        with self.subTest(challenge="T01.1"):
            command_match = re.search(r"```text\n(git clone [^\n]+)\n```", index)
            self.assertIsNotNone(command_match, "Workbench must publish a runnable clone command")
            command = shlex.split(command_match.group(1))
            self.assertEqual(command[:2], ["git", "clone"])
            self.assertTrue(Path(command[-1]).is_relative_to("/tmp"))
            subprocess.run(command, cwd=ENTRY.parent, check=True, capture_output=True, text=True)
            repository = Path(command[-1])
            retained = subprocess.check_output(
                ["git", "-C", str(repository), "show", "HEAD^:handover.md"], text=True)
            tracker_url = markdown_link(index, "Delivery tracker export", base)
            tracker = list(csv.DictReader(StringIO(get_text(tracker_url))))
            delivery = re.search(r"Delivery:\s*(DL-[0-9]+)", retained).group(1)
            matching = [row for row in tracker if row["delivery_id"] == delivery]
            self.assertEqual(len(matching), 1)
            self.assertIn("courier CR-17", retained)

        with self.subTest(challenge="T01.2"):
            dispatch = get_text(markdown_link(index, "Dispatch desk", base))
            notice_url = markdown_link(dispatch, "public delivery notice", "http://workbench.training:8081/")
            notice = get_text(notice_url)
            manifest_path = re.search(r"`(/site\.webmanifest)`", notice).group(1)
            manifest = get_json(urljoin(notice_url, manifest_path))
            retired_path = next(path for path in manifest["content_indexes"] if "retired" in path)
            retired = get_json(urljoin(notice_url, retired_path))
            amendment_url = urljoin(notice_url, retired["records"][0]["path"])
            amendment = get_json(amendment_url)
            self.assertEqual((amendment["delivery_id"], amendment["receiving_bay"]), ("DL-204", "Bay 4"))

        with self.subTest(challenge="T01.3"):
            profile = get_json(markdown_link(index, "Retired courier client", base))
            status, body, _ = request(
                f'{profile["api_base"]}/api/deliveries/{profile["delivery_id"]}/manifest',
                headers={"Authorization": profile["authorization"]},
            )
            self.assertEqual(status, 200)
            protected_manifest = json.loads(body)
            self.assertEqual(
                (protected_manifest["courier_id"], protected_manifest["delivery_id"], protected_manifest["manifest_id"]),
                (profile["courier_id"], profile["delivery_id"], "MF-204"),
            )

        with self.subTest(challenge="T01.4"):
            helper = markdown_link(index, "Diagnostic helper", base)
            public = get_json(helper)
            self.assertIn("omitted", public["detail"].lower())
            intended = helper.replace("public/DL-204.json", "public/%2E%2E/internal/DL-204.json")
            internal = get_json(intended)
            self.assertEqual(internal["summary_id"], "DS-204-I")

    def test_02_someone_can_log_in(self) -> None:
        base = self.desks["Accounts"]
        index = get_text(base)
        candidates = get_text(markdown_link(index, "Candidate notes", base))
        handles = re.findall(r"`([a-z]+\.[a-z]+)`", candidates)

        with self.subTest(challenge="T02.1"):
            active = None
            for handle in handles:
                status, body, _ = request(
                    urljoin(base, "/api/recovery/lookup"), method="POST", body={"account": handle})
                if status == 200:
                    active = json.loads(body)
            self.assertIsNotNone(active)
            self.assertEqual(active["state"], "active")

        with self.subTest(challenge="T02.2"):
            directory_url = markdown_link(index, "Public staff directory", base)
            directory = get_json(directory_url)
            client = get_text(urljoin(directory_url, "app.js"))
            route = re.search(r"fetch\(`([^`]+\$\{staffId\}[^`]*)`\)", client).group(1)
            private_assignment = None
            for row in directory["staff"]:
                candidate_route = route.replace("${staffId}", row["staff_id"])
                status, body, _ = request(urljoin(base, candidate_route))
                if status == 200:
                    private_assignment = json.loads(body)
            self.assertIsNotNone(private_assignment)
            self.assertEqual(private_assignment["staff_record_revision"], 8)

        with self.subTest(challenge="T02.3"):
            status, body, response_headers = request(
                urljoin(base, "/api/recovery/redeem"),
                method="POST",
                body={
                    "account": active["account"],
                    "case_fragment": active["case_fragment"],
                    "staff_detail": private_assignment["staff_detail"],
                },
            )
            self.assertEqual(status, 201)
            session = json.loads(body)["session"]
            self.assertIn("CINDER_REHEARSAL_SESSION", response_headers["Set-Cookie"])
            bearer = {"Authorization": f"Bearer {session}"}
            status, handover_body, _ = request(urljoin(base, "/api/handover"), headers=bearer)
            self.assertEqual(status, 200)
            handover = handover_body.decode()
            self.assertIn(active["account"], handover)

        with self.subTest(challenge="T02.4"):
            own_assignment, other_assignment = re.findall(r"`(ASG-[0-9]+)`", handover)
            status, body, _ = request(
                urljoin(base, f"/api/assignments/{other_assignment}/brief"), headers=bearer)
            self.assertEqual(status, 200)
            brief = json.loads(body)
            self.assertEqual(brief["assignment_id"], other_assignment)
            self.assertNotEqual(brief["owner"], active["account"])
            self.assertEqual(own_assignment, private_assignment["assignment_id"])

    def test_03_left_in_the_checkout(self) -> None:
        base = self.desks["Developer artifacts"]
        index = get_text(base)
        forge_page = re.search(r"Forge repository: `(http://[^`]+)`", index).group(1)

        with self.subTest(challenge="T03.1"):
            forge = get_text(forge_page)
            self.assertIn("test/fixtures/DL-204.json", forge)
            destination = "/tmp/delivery-formatter"
            subprocess.run(
                ["git", "clone", "--quiet", forge_page + ".git", destination],
                cwd=ENTRY.parent,
                check=True,
            )
            fixture = subprocess.check_output(
                ["git", "-C", destination, "show", "HEAD^:test/fixtures/DL-204.json"], text=True)
            expected = json.loads(fixture)
            self.assertEqual(expected["input"]["delivery_id"], "DL-204")
            self.assertEqual(expected["expected_summary"], "DL-204 | Cinder receiving desk | 3 parcels")

        with self.subTest(challenge="T03.2"):
            build_url = re.search(r"Failed build record: `(http://[^`]+)`", index).group(1)
            build_log = get_text(build_url)
            token = re.search(r"publisher_[A-Za-z0-9_]+", build_log).group(0)
            registry = re.search(r"Registry: `(http://[^`]+)`", index).group(1)
            status, body, _ = request(
                urljoin(registry, "/api/channels/rehearsal/manifest"),
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(status, 200)
            channel = json.loads(body)

        with self.subTest(challenge="T03.3"):
            package_url = markdown_link(index, "Unpacked sample package", base)
            package = get_json(package_url)
            lifecycle = package["scripts"]["postinstall"].split()[-1]
            script = get_text(urljoin(package_url, lifecycle))
            source = re.search(r"const source = '([^']+)'", script).group(1)
            destination_url = re.search(r"const destination = '([^']+)'", script).group(1)
            fixture_url = urljoin(package_url, source.removeprefix("/opt/cinder-sample/"))
            source_record = get_json(fixture_url)
            self.assertEqual(source_record["record_id"], "SRC-204")
            self.assertEqual(destination_url, "http://developer.training:8084/api/rehearsal/ingest")

        with self.subTest(challenge="T03.4"):
            consumer = re.search(r"Consumer: `(http://[^`]+)`", index).group(1)
            status, baseline_body, _ = request(
                urljoin(consumer, "/api/consumer/run"), method="POST", body={})
            self.assertEqual(status, 200)
            baseline = json.loads(baseline_body)
            self.assertEqual(baseline["selected_version"], channel["baseline_version"])
            version = "1.5.0"
            package_manifest = json.dumps(
                {"name": channel["package"], "version": version, "main": "index.js"},
                separators=(",", ":"),
            )
            source_code = (
                "exports.formatDelivery = function (input) { "
                "const unit = input.parcel_count === 1 ? 'parcel' : 'parcels'; "
                "return {...input, summary: input.delivery_id + ' | ' + input.destination + ' | ' + "
                "input.parcel_count + ' ' + unit, rehearsal_marker: 'Cinder rehearsal'}; };"
            )
            publication = {
                "name": channel["package"],
                "version": version,
                "files": {"package.json": package_manifest, "index.js": source_code},
            }
            package_path = f'/api/packages/{channel["package"]}/{version}'
            status, published_body, _ = request(
                urljoin(registry, quote(package_path, safe="/@")),
                method="PUT",
                body=publication,
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(status, 201)
            published = json.loads(published_body)
            status, fresh_body, _ = request(
                urljoin(consumer, "/api/consumer/run"), method="POST", body={})
            self.assertEqual(status, 200)
            fresh = json.loads(fresh_body)
            self.assertEqual(fresh["selected_version"], version)
            self.assertEqual(fresh["package_digest"], published["digest"])
            self.assertEqual(fresh["output"]["rehearsal_marker"], "Cinder rehearsal")

    def test_04_trust_the_instrument(self) -> None:
        base = self.desks["Outlet desk"]
        index = get_text(base)
        guide = get_text(markdown_link(index, "Field and operating guide", base))

        with self.subTest(challenge="T04.1"):
            capture = get_json(markdown_link(index, "Volume capture: VC-017", base))
            self.assertEqual(
                (capture["sample_id"], capture["observed_volume_l"], capture["unit"], capture["quality"]),
                ("VS-017", 1200.0, "L", "good"),
            )
            self.assertNotEqual(capture["observed_volume_l"], capture["requested_volume_l"])

        with self.subTest(challenge="T04.2"):
            status_capture = get_json(markdown_link(index, "Controller capture: SC-018", base))
            self.assertEqual(status_capture["controller_revision"], "TR-1")
            self.assertEqual(status_capture["status_word"] & 4, 4)
            self.assertIn("service_hold", guide)
            self.assertEqual(status_capture["outlet_position"], "closed")

        with self.subTest(challenge="T04.3"):
            practice = markdown_link(index, "Practice tank", base)
            api = urljoin(practice, "/api/practice/")
            initial = get_json(urljoin(api, "state"))
            self.assertEqual((initial["tank_id"], initial["observed_volume_l"]), ("PT-01", 1200.0))
            status, _, _ = request(
                urljoin(api, "hold"), method="POST", body={"request_id": "journey-hold-clear", "active": False})
            self.assertEqual(status, 200)
            status, receipt_body, _ = request(
                urljoin(api, "transfer"),
                method="POST",
                body={"request_id": "journey-transfer-200", "quantity_l": 200},
            )
            self.assertEqual(status, 202)
            self.assertEqual(json.loads(receipt_body)["result"], "accepted")
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                final = get_json(urljoin(api, "state"))
                if final["outlet_position"] == "closed":
                    break
                time.sleep(0.25)
            self.assertEqual(final["observed_volume_l"], 1000.0)
            observations = get_json(urljoin(api, "observations"))["observations"]
            movement = [row for row in observations if row["request_id"] == "journey-transfer-200"]
            self.assertGreaterEqual(len(movement), 2)
            self.assertEqual(movement[0]["observed_volume_l"] - movement[-1]["observed_volume_l"], 200.0)
            self.assertTrue(movement[-1]["terminal"])
            self.assertEqual(movement[-1]["outlet_position"], "closed")

        with self.subTest(challenge="T04.4"):
            report = get_json(markdown_link(index, "Issued outlet report: OR-042", base))
            requests = get_json(markdown_link(index, "Outlet request register", base))
            observations_url = markdown_link(index, "Independent observation register", base)
            rows = list(csv.DictReader(StringIO(get_text(observations_url))))
            current = next(row for row in requests if row["request_id"] == report["request_id"])
            stale = next(row for row in requests if row["request_id"] == report["source_request_id"])
            attempt_rows = [row for row in rows if row["attempt_id"] == report["attempt_id"]]
            self.assertEqual((current["result"], current["reason"]), ("rejected", "service_hold"))
            self.assertEqual(stale["result"], "accepted")
            self.assertEqual({row["observed_volume_l"] for row in attempt_rows}, {"1000.0"})
            self.assertEqual({row["outlet_position"] for row in attempt_rows}, {"closed"})
            self.assertEqual(report["display_result"], "green")


if __name__ == "__main__":
    unittest.main()
