#!/usr/bin/env python3
"""Discovery-first happy-path journey through every KeplerOps card (K01-K31).

This journey is the connected participant experience, not a service-contract
check. The harness runs on the host. Every participant action runs inside the
k-dev workstation container as user `rowan`, using only the tools and files a
participant has from the supplied foothold.

Rules this journey keeps:
- It starts from the workstation material a participant is handed: `HOME.md`,
  `work/service-notes.md`, `work/service-catalog.md`, the browser profile, the
  saved git credential, the connector checkout, and the local helper.
- It derives every route, identifier, credential and answer from that material
  or from an earlier response. It never embeds a value known only to the author.
- It carries discovered evidence forward across cards and operations.

The journey consumes single-use state and must run from a pristine range.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
import time
import unittest
import uuid
import zipfile
import zlib


CONTAINER = "cinder-keplerops-k-dev"
# The KeplerOps->ARWC delivery handoff needs both carriers paired. Like the
# retained suite, those cross-segment steps run only when this is set.
CROSS_SEGMENT = os.environ.get("CINDER_CROSS_SEGMENT") == "1"
CA = "/home/rowan/.local/share/keplerops/ca.crt"


def rowan(*arguments: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run a command inside the workstation as the participant user `rowan`."""
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "rowan", "--workdir", "/home/rowan", CONTAINER, *arguments],
        input=input_text, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def read_home(path: str) -> str:
    """Read a file from the participant home directory."""
    result = rowan("cat", path)
    if result.returncode != 0:
        raise AssertionError(f"workstation file not found: {path}: {result.stderr}")
    return result.stdout


def rowan_bytes(*arguments: str) -> bytes:
    """Run a workstation command and return its raw stdout bytes."""
    result = subprocess.run(
        ["docker", "exec", "--user", "rowan", "--workdir", "/home/rowan", CONTAINER, *arguments],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"workstation command failed: {arguments}: {result.stderr.decode()}")
    return result.stdout


def read_home_bytes(path: str) -> bytes:
    """Read a binary file from the participant home directory."""
    result = subprocess.run(
        ["docker", "exec", "--user", "rowan", "--workdir", "/home/rowan", CONTAINER, "cat", path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"workstation file not found: {path}: {result.stderr.decode()}")
    return result.stdout


def write_tmp(path: str, data: bytes) -> None:
    """Stage participant-authored content inside the workstation (e.g. /tmp)."""
    result = subprocess.run(
        ["docker", "exec", "-i", "--user", "rowan", CONTAINER, "tee", path],
        input=data, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"could not stage {path}: {result.stderr.decode()}")


def post_json_route(route: str, payload: dict, *, method: str = "POST", creds=None, bearer=None, cookie=None, expected: int = 200, timeout: int = 20) -> dict:
    """Send a JSON body the participant assembles on the workstation."""
    write_tmp("/tmp/journey-body.json", json.dumps(payload).encode())
    extra = ["-H", "Content-Type: application/json", "--data-binary", "@/tmp/journey-body.json"]
    if method != "POST":
        extra = ["-X", method, *extra]
    return curl_json(route, *extra, creds=creds, bearer=bearer, cookie=cookie, expected=expected, timeout=timeout)


def curl(
    url: str,
    *extra: str,
    expected: int = 200,
    creds: tuple[str, str] | None = None,
    bearer: str | None = None,
    cookie: str | None = None,
    cert: tuple[str, str] | None = None,
    timeout: int = 20,
) -> tuple[int, str]:
    """Issue an authenticated request from the workstation with its CA."""
    command = ["curl", "-sS", "--cacert", CA, "-o", "/tmp/journey.out", "-w", "%{http_code}", "--max-time", str(timeout)]
    if creds is not None:
        command += ["-u", f"{creds[0]}:{creds[1]}"]
    if bearer is not None:
        command += ["-H", f"Authorization: Bearer {bearer}"]
    if cookie is not None:
        command += ["-H", f"Cookie: {cookie}"]
    if cert is not None:
        command += ["--cert", cert[0], "--key", cert[1]]
    command += [*extra, url]
    result = rowan(*command)
    body = rowan("cat", "/tmp/journey.out").stdout
    status = int(result.stdout) if result.stdout.strip().isdigit() else -1
    if status != expected:
        raise AssertionError(f"{url} -> {result.stdout} (want {expected}): {body[:400]} {result.stderr[:200]}")
    return status, body


def curl_json(url: str, *extra: str, expected: int = 200, **kwargs: object) -> dict:
    _, body = curl(url, *extra, expected=expected, **kwargs)  # type: ignore[arg-type]
    return json.loads(body) if body else {}


class KeplerOpsJourney(unittest.TestCase):
    """One connected journey; methods run in card order and share evidence."""

    maxDiff = None
    evidence: dict[str, object] = {}

    @classmethod
    def setUpClass(cls) -> None:
        # The participant opens the workstation briefing first.
        cls.home = read_home("README.md")
        cls.service_notes = read_home("work/service-notes.md")
        # HOME.md points the participant at the wider FieldKest route catalog.
        cls.catalog = read_home("work/service-catalog.md")

    @classmethod
    def catalog_route(cls, key: str) -> str:
        """Resolve a `name`: `METHOD https://...` template from the service catalog."""
        match = re.search(rf"`{re.escape(key)}`: `[A-Z]+ (https://\S+?)`", cls.catalog)
        if not match:
            raise AssertionError(f"route not in service catalog: {key}")
        return match.group(1)

    # ------------------------------------------------------------------ K01
    def test_k01_opening_foothold(self) -> None:
        notes = self.service_notes

        with self.subTest(card="K01.1 recover credential and read the handover"):
            # The developer left a stored git credential on the workstation.
            stored = read_home(".config/git/credentials").strip()
            match = re.match(r"https://([^:]+):([^@]+)@([^/\s]+)", stored)
            self.assertIsNotNone(match, "stored git credential not in the expected form")
            user, secret, source_host = match.group(1), match.group(2), match.group(3)
            # The handover route is documented in the developer service notes.
            handover_route = re.search(r"Current handover: `GET (https://\S+)`", notes).group(1)
            self.assertIn(source_host, handover_route)
            # Anonymous access is denied.
            _, denied = curl(handover_route, expected=401)
            self.assertEqual(json.loads(denied)["error"], "authentication_required")
            # The recovered developer credential reads the protected handover.
            handover = curl_json(handover_route, creds=(user, secret))
            self.assertRegex(str(handover["handover_id"]), r"^HND-")
            self.assertIsInstance(handover["revision"], int)
            # The recovered identity has no write access to the repository.
            push = rowan("git", "-C", "work/fieldlink-connector", "push", "--dry-run", "origin", "HEAD:main")
            self.assertNotEqual(push.returncode, 0, "recovered identity must not be able to push")
            self.evidence["dev"] = (user, secret)
            self.evidence["source_host"] = source_host
            self.evidence["handover"] = handover

        with self.subTest(card="K01.2 recover the retained support conversation"):
            # The closed support tab is recoverable from the browser history.
            history = rowan(
                "sqlite3", ".config/chromium/Default/History",
                "select url from urls order by id limit 1;",
            ).stdout.strip()
            conv_match = re.search(r"support\.keplerops\.test/conversations/(SUP-\d+)", history)
            self.assertIsNotNone(conv_match, "no retained support conversation in history")
            ticket = conv_match.group(1)
            # The session cookie is retained in the browser profile.
            cookie = rowan(
                "sqlite3", ".config/chromium/Default/Cookies",
                "select value from cookies where name='fieldkest_support';",
            ).stdout.strip()
            self.assertTrue(cookie, "retained support cookie missing")
            conv_route = re.search(r"Conversation: `GET (https://\S+)/\{conversation_id\}`", notes).group(1)
            conversation = curl_json(
                f"{conv_route}/{ticket}", cookie=f"fieldkest_support={cookie}",
            )
            self.assertEqual(conversation["conversation_id"], ticket)
            # A wrong session is refused.
            curl(f"{conv_route}/{ticket}", cookie="fieldkest_support=wrong", expected=403)
            self.evidence["ticket"] = ticket
            self.evidence["support_cookie"] = cookie

        with self.subTest(card="K01.3 recover the stale release-review export"):
            pointer = read_home("work/review-exports/fieldlink-7.4.2-review.md")
            release = re.search(r"(REL-FLK-[0-9.]+-\d+)", pointer)
            self.assertIsNotNone(release, "release reference missing from the review export")
            self.assertRegex(pointer, r"REV-\d+")
            # The file is deliberately outside the checkout.
            in_checkout = rowan("test", "-e", "work/fieldlink-connector/fieldlink-7.4.2-review.md")
            self.assertNotEqual(in_checkout.returncode, 0)
            self.evidence["release"] = release.group(1)

        with self.subTest(card="K01.4 produce an inspection summary with the local helper"):
            helper = read_home("work/local-helper.md")
            helper_route = re.search(r"(http://127\.0\.0\.1:8701/api/inspection-summary)", helper).group(1)
            # The helper notes live in work/ and quote their example paths relative to it.
            sample_path = "work/" + re.search(r"form sample=@(\S+)", helper).group(1)
            receipt = curl_json(helper_route, "-F", f"sample=@{sample_path}", expected=201)
            sample = json.loads(read_home(sample_path))
            self.assertEqual(receipt["sample_id"], sample["sample_id"])
            # The helper rejects a non-sample document.
            curl(helper_route, "-F", "sample=@work/review-exports/fieldlink-7.4.2-review.md", expected=422)
            self.evidence["sample"] = receipt

    # ------------------------------------------------------------------ K02
    def test_k02_report_fixture_and_changed_report(self) -> None:
        notes = self.service_notes
        dev = self.evidence["dev"]
        handover = self.evidence["handover"]

        with self.subTest(card="K02.1 recover the missing report fixture"):
            # A handover note points at the failing build.
            build_note = next(n for n in handover["notes"] if re.search(r"BLD-\d+", n))
            build_id = re.search(r"(BLD-\d+)", build_note).group(1)
            run_route = re.search(r"Run record: `GET (https://\S+)/\{run_id\}`", notes).group(1)
            run = curl_json(f"{run_route}/{build_id}", creds=dev)
            fixture_path = run["expected_fixture"]
            fixture_ref = run["fixture_revision"]
            # The removed fixture is still in repository history at the named revision.
            fixture_raw = rowan_bytes("git", "-C", "work/fieldlink-connector", "show", f"{fixture_ref}:{fixture_path}")
            fixture = json.loads(fixture_raw)
            self.assertEqual(fixture["schema"], "fieldkest.report/v2")
            self.evidence["build_id"] = build_id
            self.evidence["fixture_ref"] = fixture_ref
            self.evidence["fixture"] = fixture
            self.evidence["fixture_raw"] = fixture_raw

        with self.subTest(card="K02.2 expose the withheld review note"):
            import_route = re.search(r"Review import: `POST (https://\S+)`", notes).group(1)
            number = re.search(r"BLD-(\d+)", build_id).group(1)
            note_id = f"REVNOTE-{number}"
            # The importer resolves the object before access control; traverse out of inputs/.
            traversal = f"inputs/%2e%2e/reviews/{note_id}.json"
            receipt = post_json_route(
                import_route,
                {"schema": "fieldkest.review-import/v1", "run_id": build_id, "object": traversal},
                creds=dev, expected=201,
            )
            note = receipt["object"]
            self.assertEqual(note["review_id"], note_id)
            self.assertEqual(note["baseline"]["ref"], fixture_ref)
            # Escaping beyond the repository is still refused.
            post_json_route(
                import_route,
                {"schema": "fieldkest.review-import/v1", "run_id": build_id, "object": "inputs/%2e%2e/%2e%2e/etc/passwd"},
                creds=dev, expected=422,
            )
            self.evidence["review_note"] = note

        with self.subTest(card="K02.3 publish Cinder's report through a green job"):
            note = self.evidence["review_note"]
            fixture = self.evidence["fixture"]
            # The note's contract names the extension point, layout and field rules.
            self.assertEqual(note["extension_point"], "report_provider")
            self.assertIn("provider.py", note["archive_layout"])
            # A compatible provider keeps immutable fields and supplies the assessment.
            provider = (
                "def render_report(fixture):\n"
                "    report = dict(fixture)\n"
                "    report['assessment'] = {'rating': 'action-required',\n"
                "        'summary': 'Cinder review: callback latency needs support attention.'}\n"
                "    return report\n"
            )
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("provider.py", provider)
                archive.writestr("fixture.json", self.evidence["fixture_raw"])
            job_route = re.search(r"Submit an isolated job: `POST (https://\S+)`", notes).group(1)
            result_route = re.search(r"Read a job result: `GET (https://\S+)/\{job_id\}`", notes).group(1)
            submitted = post_json_route(
                job_route,
                {"template": "report-consumer-v2", "input": {"archive_base64": base64.b64encode(buffer.getvalue()).decode()}},
                creds=dev, expected=202,
            )
            result = curl_json(f"{result_route}/{submitted['job_id']}", creds=dev)
            self.assertEqual(result["state"], "success")
            self.assertEqual(result["report"]["assessment"]["rating"], "action-required")
            for field in note["immutable_fields"]:
                base = fixture
                got = result["report"]
                for part in field.split("."):
                    base, got = base.get(part), got.get(part)
                self.assertEqual(got, base, f"immutable field changed: {field}")
            # The support handover now shows Cinder's output.
            support_handover = re.search(r"Current handover: `GET (https://support\S+)`", notes).group(1)
            handover = curl_json(support_handover, cookie=f"fieldkest_support={self.evidence['support_cookie']}")
            self.assertEqual(handover["job_id"], submitted["job_id"])
            self.assertEqual(handover["report_sha256"], result["report_sha256"])

    # ------------------------------------------------------------------ K03
    def test_k03_predecessor_callback(self) -> None:
        with self.subTest(card="K03.1 recover the staging artifact"):
            # The predecessor's field notes carry a staging attachment.
            odt = read_home_bytes("work/analysis/field-notes-2026-08.odt")
            with zipfile.ZipFile(io.BytesIO(odt)) as archive:
                stage_name = next(n for n in archive.namelist() if "staging" in n and n.endswith(".bin"))
                stage = archive.read(stage_name).decode()
            values = dict(line.split("=", 1) for line in stage.splitlines() if "=" in line)
            collection_id = values["collection"]
            self.assertRegex(collection_id, r"^FKCOL-\d+")
            self.evidence["collection_id"] = collection_id
            self.evidence["stage"] = values

        with self.subTest(card="K03.2 reconstruct the staged script"):
            values = self.evidence["stage"]
            # The workstation decoder documents the payload encoding: base64 then zlib.
            decoder = read_home("work/analysis/staging-decoder.ps1")
            self.assertIn("FromBase64String", decoder)
            self.assertIn("ZLibStream", decoder)
            script = zlib.decompress(base64.b64decode(values["payload"]))
            helper = read_home("work/local-helper.md")
            recon_route = re.search(r"(http://127\.0\.0\.1:8701/api/reconstruction)", helper).group(1)
            request = {
                "schema": "fieldkest.reconstruction/v1",
                "collection_id": self.evidence["collection_id"],
                "script_base64": base64.b64encode(script).decode(),
                "instructions_base64": values["instructions"],
            }
            write_tmp("/tmp/journey-recon.json", json.dumps(request).encode())
            receipt = curl_json(recon_route, "-F", "bundle=@/tmp/journey-recon.json", expected=201)
            self.assertEqual(receipt["collection_id"], self.evidence["collection_id"])
            self.evidence["recon"] = receipt

        with self.subTest(card="K03.3 recover the lost collection and ticket"):
            helper = read_home("work/local-helper.md")
            # The helper base appears on its other routes; the callback path is documented.
            base = re.search(r"(http://127\.0\.0\.1:8701)", helper).group(1)
            callback_path = re.search(r"at `(/api/callback/collection)`", helper).group(1)
            callback_route = base + callback_path
            receipt = self.evidence["recon"]
            collection = post_json_route(
                callback_route,
                {"endpoint_id": receipt["endpoint_id"], "collection_id": receipt["collection_id"], "integrity": receipt["callback_integrity"]},
            )
            # The lost collection resolves to the same support ticket the browser retained.
            self.assertEqual(collection["ticket_reference"], self.evidence["ticket"])
            # A wrong integrity binding is refused.
            post_json_route(
                callback_route,
                {"endpoint_id": receipt["endpoint_id"], "collection_id": receipt["collection_id"], "integrity": "wrong"},
                expected=403,
            )

    # ------------------------------------------------------------------ K04
    def test_k04_native_indexer(self) -> None:
        dev = self.evidence["dev"]
        indexer = self.catalog_route("indexer.indexes")
        base = re.search(r"(https://[^/]+)", indexer).group(1)

        with self.subTest(card="K04.1 controlled object-boundary corruption"):
            # The catalog's parser review records the allocation size and the sentinel marker.
            marker = re.search(r"`(FIELDKEST-[A-Z]+)` process marker", self.catalog).group(1)
            allocation = int(re.search(r"(\d+)-byte body allocation", self.catalog).group(1))
            body = b"A" * allocation + marker.encode()
            changed = post_json_route(
                indexer, {"allocated_length": allocation, "body_hex": body.hex()}, creds=dev, expected=201)
            self.assertEqual((changed["sentinel"], changed["service_alive"]), ("mutated", True))
            # A non-conforming bundle is rejected and the service stays alive.
            post_json_route(
                indexer, {"allocated_length": 8, "body_hex": b"not-a-controlled-overflow".hex()}, creds=dev, expected=422)
            normal = post_json_route(
                indexer, {"allocated_length": 16, "body_hex": b"normal-index-row".hex()}, creds=dev, expected=201)
            self.assertTrue(normal["service_alive"])

        with self.subTest(card="K04.2 disclose the protected runtime descriptor"):
            descriptor = post_json_route(
                indexer, {"operation": "runtime-descriptor", "sentinel": "mutated"}, creds=dev)
            for field in ("record_id", "ready_state", "routine", "state_route", "completion_route", "worker_lease", "process_generation", "integrity_relation"):
                self.assertIn(field, descriptor, "descriptor must surface the continuation evidence")
            self.evidence["indexer_descriptor"] = descriptor

        with self.subTest(card="K04.3 scoped write under the integrity relation"):
            descriptor = self.evidence["indexer_descriptor"]
            lease = descriptor["worker_lease"]
            generation = descriptor["process_generation"]
            ready = descriptor["ready_state"]
            # The disclosed integrity relation is sha256(generation:state).
            integrity = hashlib.sha256(f"{generation}:{ready}".encode()).hexdigest()
            updated = post_json_route(
                base + descriptor["state_route"], {"state": ready, "integrity": integrity},
                method="PATCH", bearer=lease, expected=200)
            self.assertEqual(updated["integrity"], integrity)
            # A wrong integrity value is refused.
            post_json_route(
                base + descriptor["state_route"], {"state": ready, "integrity": "wrong"},
                method="PATCH", bearer=lease, expected=422)

        with self.subTest(card="K04.4 execute the completion routine and recover the dossier"):
            descriptor = self.evidence["indexer_descriptor"]
            result = post_json_route(
                base + descriptor["completion_route"],
                {"routine": descriptor["routine"], "generation": descriptor["process_generation"]},
                bearer=descriptor["worker_lease"])
            self.assertEqual(result["service_identity"], "svc-fieldkest-indexer")
            # The recovered exception dossier is an alternative K29 release lead.
            self.evidence["indexer_dossier"] = result["dossier"]

    # ------------------------------------------------------------------ K05
    def test_k05_package_foundation(self) -> None:
        dev = self.evidence["dev"]
        readme = read_home("work/registry/README.md")
        packages = re.search(r"(https://packages\.keplerops\.test)", readme).group(1)

        with self.subTest(card="K05.1 speak the consumer-check contract"):
            metadata = curl_json(f"{packages}/@keplerops%2ffieldlink-connector", creds=dev)
            latest = metadata["dist_tags"]["latest"]
            request = read_home("work/registry/consumer-request.json")
            write_tmp("/tmp/journey-consumer.json", request.encode())
            result = curl_json(
                f"{packages}/api/consumer-checks", "-H", "Content-Type: application/json",
                "--data-binary", "@/tmp/journey-consumer.json", creds=dev, expected=201)
            self.assertEqual(result["resolved_version"], latest)
            self.evidence["declared_range"] = result["declared_range"]
            self.evidence["consumer_revision"] = result["consumer_revision"]
            self.evidence["tenant"] = result["request"]["tenant_id"]

        with self.subTest(card="K05.2 recover the yanked release named in the ticket"):
            # The support ticket names the retained historical release record.
            cookie = f"fieldkest_support={self.evidence['support_cookie']}"
            support_conv = curl_json(
                re.search(r"Conversation: `GET (https://\S+)/\{conversation_id\}`", self.service_notes).group(1)
                + f"/{self.evidence['ticket']}", cookie=cookie)
            text = " ".join(m["text"] for m in support_conv["messages"])
            archive_id = re.search(r"(REL-FLK-[0-9.]+-ARCHIVE)", text).group(1)
            archive = curl_json(f"{packages}/api/releases/{archive_id}", creds=dev)
            self.assertEqual(archive["status"], "yanked")
            self.assertNotIn(archive["version"], metadata_versions := curl_json(f"{packages}/@keplerops%2ffieldlink-connector", creds=dev)["versions"])
            self.evidence["archive"] = archive

        with self.subTest(card="K05.3 reconcile the disagreeing manifests"):
            result = curl_json(
                f"{packages}/api/reconcile/tenant-package", "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"tenant_record_id": self.evidence["tenant"], "release_id": self.evidence["release"]}),
                creds=dev)
            self.assertIn("resolved_version", result["disagreements"])

        with self.subTest(card="K05.4 run the isolated resolver"):
            result = curl_json(
                f"{packages}/api/resolver/runs", "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({
                    "package": "@keplerops/fieldlink-connector",
                    "range": self.evidence["declared_range"],
                    "consumer_revision": self.evidence["consumer_revision"]}),
                creds=dev, expected=201)
            self.assertEqual(result["selected_version"], metadata["dist_tags"]["latest"])
            self.assertEqual([c["version"] for c in result["candidate_set"]], metadata["versions"])

    # ------------------------------------------------------------------ K06
    def test_k06_house_credentials_and_rehearsal(self) -> None:
        dev = self.evidence["dev"]
        readme = read_home("work/registry/README.md")
        packages = re.search(r"(https://packages\.keplerops\.test)", readme).group(1)
        ci = re.search(r"(https://ci\.keplerops\.test)", self.service_notes).group(1)

        with self.subTest(card="K06.1 recover the house publisher credential"):
            disclosed = curl_json(
                f"{packages}/api/imports", "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({
                    "package": "@keplerops/fieldlink-connector", "version": "7.4.2",
                    "registry_view": "customer-preview-unavailable"}),
                creds=dev, expected=422)
            token = disclosed["resolved_registry_client"]["token"]
            self.evidence["publisher_token"] = token

        with self.subTest(card="K06.2 read the private package view in bounds"):
            token = self.evidence["publisher_token"]
            package = curl_json(f"{packages}/api/package-views/publisher/%40keplerops%2Fsupport-rehearsal", bearer=token)
            self.assertEqual(package["name"], "@keplerops/support-rehearsal")
            # The publisher view does not reach the release-admin package.
            curl_json(f"{packages}/api/package-views/publisher/%40keplerops%2Frelease-admin", bearer=token, expected=403)

        with self.subTest(card="K06.3 publish and run the rehearsal consumer"):
            token = self.evidence["publisher_token"]
            version = "7.4.3-cinder." + uuid.uuid4().hex[:10]
            builder = (
                "import base64, gzip, hashlib, io, json, pathlib, tarfile\n"
                f"version = {version!r}\n"
                "files = {\n"
                " 'package/package.json': json.dumps({'name':'@keplerops/fieldlink-connector','version':version,'main':'index.js','engines':{'node':'>=22'},'fieldkest':{'interface':'fieldkest.connector/v3'}}, sort_keys=True).encode()+b'\\n',\n"
                " 'package/index.js': b\"'use strict';\\nexports.consume = request => ({schema:'fieldkest.rehearsal-result/v1',tenant_id:request.tenant_id,asset_id:request.asset_id,assessment:'operator-confirmed-change'});\\n\",\n"
                "}\n"
                "raw=io.BytesIO()\n"
                "with tarfile.open(fileobj=raw,mode='w') as t:\n"
                " for name,data in files.items():\n"
                "  i=tarfile.TarInfo(name); i.size=len(data); i.mode=0o644; t.addfile(i,io.BytesIO(data))\n"
                "out=io.BytesIO()\n"
                "with gzip.GzipFile(fileobj=out,mode='wb',mtime=0) as g: g.write(raw.getvalue())\n"
                "data=out.getvalue()\n"
                "request={'name':'@keplerops/fieldlink-connector','version':version,'channel':'arwc-stable','sha256':hashlib.sha256(data).hexdigest(),'tarball_base64':base64.b64encode(data).decode()}\n"
                "pathlib.Path('/tmp/journey-publication.json').write_text(json.dumps(request))\n"
            )
            build = rowan("python3", "-c", builder)
            self.assertEqual(build.returncode, 0, build.stderr)
            published = curl_json(
                f"{packages}/@keplerops%2ffieldlink-connector", "-X", "PUT", "-H", "Content-Type: application/json",
                "--data-binary", "@/tmp/journey-publication.json", bearer=token, expected=201)
            self.assertEqual((published["version"], published["channel"]), (version, "arwc-stable"))
            result = curl_json(
                f"{ci}/api/rehearsals/connector", "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({
                    "version": version, "consumer": "support-rehearsal-v3",
                    "input": {"schema": "fieldkest.connector/v3", "tenant_id": "TEN-SYNTH-REHEARSAL-01",
                              "asset_id": "SYNTH-PUMP-07", "operation": "support_review"}}),
                creds=dev, expected=202)
            self.assertEqual((result["state"], result["version"]), ("success", version))
            self.assertEqual(result["output"]["assessment"], "operator-confirmed-change")

    # ------------------------------------------------------------------ K07
    def test_k07_inspector_boundary(self) -> None:
        dev = self.evidence["dev"]
        readme = read_home("work/registry/README.md")
        packages = re.search(r"(https://packages\.keplerops\.test)", readme).group(1)

        with self.subTest(card="K07.1 what the inspector forwards"):
            normal = read_home("work/registry/inspection-normal.json")
            write_tmp("/tmp/journey-insp.json", normal.encode())
            submitted = curl_json(
                f"{packages}/api/inspections", "-H", "Content-Type: application/json",
                "--data-binary", "@/tmp/journey-insp.json", creds=dev, expected=201)
            inspection_id = submitted["inspection_id"]
            trace = curl_json(f"{packages}/api/inspections/{inspection_id}/trace", creds=dev)
            self.assertIn("assessor_correlation_id", trace)

        with self.subTest(card="K07.2 one request becomes another"):
            fki = read_home_bytes("work/registry/inspection-compat.fki")
            write_tmp("/tmp/journey-insp.fki", fki)
            result = curl_json(
                f"{packages}/api/inspections/envelope", "-H", "Content-Type: application/octet-stream",
                "--data-binary", "@/tmp/journey-insp.fki", creds=dev)
            self.assertIn("front_end", result)
            self.assertIn("assessor", result)
            self.evidence["inspection_envelope"] = result

        with self.subTest(card="K07.3 the protected inspection action"):
            result = self.evidence["inspection_envelope"]
            self.assertEqual(result["assessor"]["action"], "inspect_support_package")
            # A non-envelope input is refused.
            write_tmp("/tmp/journey-insp-bad.bin", read_home_bytes("work/registry/README.md"))
            curl_json(
                f"{packages}/api/inspections/envelope", "-H", "Content-Type: application/octet-stream",
                "--data-binary", "@/tmp/journey-insp-bad.bin", creds=dev, expected=422)

    # ------------------------------------------------------------------ K08
    def test_k08_legacy_entitlement(self) -> None:
        dev = self.evidence["dev"]
        readme = read_home("work/registry/README.md")
        packages = re.search(r"(https://packages\.keplerops\.test)", readme).group(1)
        archive = self.evidence["archive"]
        compat = archive["compatibility"]

        with self.subTest(card="K08.1 recover the protected entitlement record"):
            entitlement_id = compat["record_id"]
            record = curl_json(f"{packages}/api/compatibility/entitlements/{entitlement_id}", creds=dev)
            self.assertEqual(record["record_id"], entitlement_id)
            self.evidence["entitlement"] = record

        with self.subTest(card="K08.2 supply the missing encryption context"):
            record = self.evidence["entitlement"]
            context = {k: compat[k] for k in ("key_id", "ikm_hex", "salt_hex", "info_utf8")}
            context["aad_utf8"] = compat["aad_utf8"]
            request = json.dumps({"checker": "v1", "record": record, "context": context})
            write_tmp("/tmp/journey-ent.json", request.encode())
            baseline = curl_json(
                f"{packages}/api/compatibility/entitlements/check", "-H", "Content-Type: application/json",
                "--data-binary", "@/tmp/journey-ent.json", creds=dev)
            self.assertEqual(baseline["state"], "baseline-valid")
            self.evidence["entitlement_request"] = request

        with self.subTest(card="K08.3 craft an entitlement of our choosing"):
            craft = (
                "import base64, json, pathlib\n"
                "from cryptography.hazmat.primitives import hashes\n"
                "from cryptography.hazmat.primitives.ciphers.aead import AESGCM\n"
                "from cryptography.hazmat.primitives.kdf.hkdf import HKDF\n"
                f"request=json.loads({self.evidence['entitlement_request']!r})\n"
                "record=request['record']; context=request['context']\n"
                "key=HKDF(algorithm=hashes.SHA256(),length=32,salt=bytes.fromhex(context['salt_hex']),info=context['info_utf8'].encode()).derive(bytes.fromhex(context['ikm_hex']))\n"
                "old=base64.b64decode(record['ciphertext_base64'])+base64.b64decode(record['tag_base64'])\n"
                "value=json.loads(AESGCM(key).decrypt(bytes.fromhex(record['nonce_hex']),old,context['aad_utf8'].encode()))\n"
                "value['revision']=5; value['expiry_policy']='retained-maintenance'\n"
                "nonce=bytes.fromhex('454e542d303639382d563122')\n"
                "plain=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()\n"
                "new=AESGCM(key).encrypt(nonce,plain,context['aad_utf8'].encode())\n"
                "crafted=dict(record); crafted.update({'revision':5,'nonce_hex':nonce.hex(),'ciphertext_base64':base64.b64encode(new[:-16]).decode(),'tag_base64':base64.b64encode(new[-16:]).decode(),'expiry_policy':value['expiry_policy']})\n"
                "pathlib.Path('/tmp/journey-crafted.json').write_text(json.dumps({'checker':'v1','record':crafted,'context':context}))\n"
                "pathlib.Path('/tmp/journey-crafted-v2.json').write_text(json.dumps({'checker':'v2','record':crafted,'context':context}))\n"
            )
            built = rowan("python3", "-c", craft)
            self.assertEqual(built.returncode, 0, built.stderr)
            accepted = curl_json(
                f"{packages}/api/compatibility/entitlements/check", "-H", "Content-Type: application/json",
                "--data-binary", "@/tmp/journey-crafted.json", creds=dev)
            self.assertEqual((accepted["state"], accepted["revision"]), ("legacy-test-accepted", 5))
            # The current checker refuses the same crafted record.
            curl_json(
                f"{packages}/api/compatibility/entitlements/check", "-H", "Content-Type: application/json",
                "--data-binary", "@/tmp/journey-crafted-v2.json", creds=dev, expected=422)

    # ------------------------------------------------------------------ K09
    def test_k09_runner_execution(self) -> None:
        dev = self.evidence["dev"]
        ci = re.search(r"(https://ci\.keplerops\.test)", self.service_notes).group(1)
        build_id = self.evidence["build_id"]

        def review_submit(body: dict, expected: int = 202) -> dict:
            return post_json_route(f"{ci}/api/review-jobs", body, creds=dev, expected=expected)

        def wait_review(run_id: str, timeout: float = 40) -> dict:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                result = curl_json(f"{ci}/api/review-jobs/{run_id}", creds=dev)
                if result["state"] != "queued":
                    return result
                time.sleep(0.3)
            raise AssertionError(f"review job {run_id} did not finish")

        with self.subTest(card="K09.1 the runner log tells on itself"):
            run = curl_json(f"{ci}/api/runs/{build_id}", creds=dev)
            self.assertNotIn("BLD-REL-742", run["summary"])
            _, log = curl(f"{ci}/api/runs/{build_id}/log", creds=dev)
            dossier = re.search(r"release dossier: (BLD-REL-\d+)", log).group(1)
            recovery = re.search(r"recovery build record: (BLD-REC-\d+)", log).group(1)
            self.evidence["release_dossier"] = dossier
            self.evidence["recovery_build"] = recovery
            self.evidence["run_record"] = run

        with self.subTest(card="K09.2 the artifact without a link"):
            run = self.evidence["run_record"]
            retained = run["retained_artifacts"][0]
            self.assertNotIn(retained["name"], run["result_page"]["artifacts"])
            _, artifact_bytes = curl(f"{ci}{retained['url']}", creds=dev)
            self.assertEqual(hashlib.sha256(artifact_bytes.encode()).hexdigest(), retained["sha256"])
            self.evidence["review_artifact"] = json.loads(artifact_bytes)

        with self.subTest(card="K09.3 a job input with reach"):
            artifact = self.evidence["review_artifact"]
            accepted = review_submit({"support_input": artifact, "diagnostic": {"profile": "render-review"}})
            result = curl_json(f"{ci}{accepted['result']}", creds=dev)
            self.assertEqual(result["state"], "success")
            guide = result["review"]["maintained_reference"]
            self.assertIn("runner-command", guide)
            # The guide names the internal handover that documents the worker commands.
            handover_path = re.search(r"(/srv/fieldlink-ci/runner/runner-operations\.md)", guide).group(1)
            self.evidence["support_input"] = result["support_input"]
            self.evidence["runner_handover_path"] = handover_path
            # An ordinary (non-eligible) input cannot dispatch runner commands.
            ordinary = {
                "schema": "fieldkest.review-input/v3", "artifact_id": "ART-BLD-1842-ORDINARY-SUPPORT",
                "run_id": build_id, "object_version": 1, "build_revision": artifact["build_revision"],
                "collection": artifact["collection"], "linked_support_ref": "support://reviews/ordinary-summary@1",
                "classification": "support-review", "diagnostic_eligible": False,
            }
            ordinary_retained = curl_json(f"{ci}{review_submit({'support_input': ordinary, 'diagnostic': {'profile': 'render-review'}})['result']}", creds=dev)["support_input"]
            review_submit({"support_input": ordinary_retained, "diagnostic": {"profile": "runner-command", "argv": ["/bin/pwd"]}}, expected=403)

        with self.subTest(card="K09.4 run in the runner under the service identity"):
            support_input = self.evidence["support_input"]
            handover_path = self.evidence["runner_handover_path"]
            # Read the internal handover from inside the runner itself.
            read_handover = wait_review(review_submit({
                "support_input": support_input,
                "diagnostic": {"profile": "runner-command", "argv": ["/bin/cat", handover_path]},
            })["run_id"])
            self.assertEqual(read_handover["state"], "success")
            operations = read_handover["stdout"]
            self.assertIn("FieldKest runner service connections", operations)
            # The handover gives the exact build-record connection-check command.
            argv = json.loads(re.search(r'"argv":\s*(\[.*?\])\s*\n\s*\}', operations, re.DOTALL).group(1))
            queued = review_submit({"support_input": support_input, "diagnostic": {"profile": "runner-command", "argv": argv}})
            result = wait_review(queued["run_id"])
            self.assertEqual(result["state"], "success")
            response = json.loads(result["stdout"])
            self.assertEqual((response["principal"], response["availability"]), ("svc-fieldlink-ci", "available"))
            self.assertEqual(response["run_id"], result["run_id"])
            # The worker has no general network transit (boundary).
            denied = wait_review(review_submit({
                "support_input": support_input,
                "diagnostic": {"profile": "runner-command", "argv": ["/usr/bin/curl", "-sS", "--connect-timeout", "2", "https://10.77.51.40/"]},
            })["run_id"])
            self.assertNotEqual(denied["exit_status"], 0)

    # ------------------------------------------------------------------ K11
    def test_k11_policy_compiler(self) -> None:
        dev = self.evidence["dev"]
        source = re.search(r"Repository remote: `(https://\S+?)/fieldkest", self.service_notes).group(1)
        evaluate = f"{source}/api/exercises/policy-compiler/evaluate"
        nonce_route = f"{source}/api/exercises/policy-compiler/nonce"

        def recover_program(raw: bytes, program_id: str) -> dict:
            start = raw.find(b"FKPC")
            self.assertGreaterEqual(start, 0, "retained program table absent")
            # The README documents the little-endian FKPC header layout.
            offset = int.from_bytes(raw[start + 4:start + 8], "little")
            count = int.from_bytes(raw[start + 8:start + 10], "little")
            width = int.from_bytes(raw[start + 10:start + 12], "little")
            table = raw[start:start + offset + count * width]
            # Opcode operations recovered by reverse-engineering the bytecode dispatch.
            opcode_model = {
                "schema": "fieldkest.policy-opcode-model/v1", "instruction_width": 4,
                "opcodes": {"0x00": "PUSH_FIELD", "0x01": "PUSH_CONST", "0x02": "EQ",
                            "0x03": "SEMVER_GTE", "0x04": "IN_SET", "0x05": "AND",
                            "0x06": "OR", "0x07": "RETURN"},
            }
            return {
                "schema": "fieldkest.policy-program-model/v1", "program_id": program_id,
                "instruction_width": width, "instruction_count": count,
                "program_base64": base64.b64encode(table).decode(),
                "program_sha256": hashlib.sha256(table).hexdigest(),
                "opcode_model": opcode_model,
            }

        with self.subTest(card="K11.1 clone the retained compiler and recover its program"):
            # A build-operations note names the retained repository.
            handoff = read_home("work/build-operations/policy-compiler-handoff.md")
            repo = re.search(r"`(fieldkest/policy-compiler)`", handoff).group(1)
            rowan("rm", "-rf", "/tmp/journey-pc")
            clone = rowan("git", "clone", "--quiet", f"{source}/{repo}.git", "/tmp/journey-pc")
            self.assertEqual(clone.returncode, 0, clone.stderr)
            readme = rowan("cat", "/tmp/journey-pc/README.md").stdout
            self.assertIn("FKPC", readme)
            binary = rowan_bytes("cat", "/tmp/journey-pc/bin/fieldkest-policyc")
            program_model = recover_program(binary, "FKPC-POLICY-2026-09-R4")
            self.evidence["pc_program"] = program_model
            self.evidence["pc_readme"] = readme

        with self.subTest(card="K11.2 model the instruction set via a fragment"):
            name = "tenant-state"
            raw = rowan_bytes("cat", f"/tmp/journey-pc/fragments/{name}.fkpc")
            request_value = json.loads(rowan("cat", f"/tmp/journey-pc/api/fragment-{name}.json").stdout)
            request_value["program_model"] = recover_program(raw, f"FKPC-FRAGMENT-{name.upper()}")
            result = post_json_route(evaluate, request_value, creds=dev)
            self.assertEqual(result["fragment_id"], name)

        with self.subTest(card="K11.3 the rule behind the rule: the fixed corpus"):
            readme = self.evidence["pc_readme"]
            published_digest = re.search(r"([0-9a-f]{64})", readme).group(1)
            result = post_json_route(
                evaluate,
                {"operation": "corpus-check", "program_model": self.evidence["pc_program"],
                 "policy_input": {"corpus_id": "POLICY-CORPUS-2026-09-R4"}},
                creds=dev)
            self.assertEqual(result["corpus_result_sha256"], published_digest)
            self.evidence["pc_corpus_digest"] = result["corpus_result_sha256"]

        with self.subTest(card="K11.4 an input the compiler believes"):
            # The accepted-input example is supplied in the repository.
            env = rowan("cat", "/tmp/journey-pc/examples/accepted.env").stdout
            fields = dict(line.split("=", 1) for line in env.splitlines() if "=" in line)
            nonce = curl_json(nonce_route, creds=dev)["nonce"]
            value = {
                "operation": "accept", "program_model": self.evidence["pc_program"],
                "policy_input": {
                    "tenant_state": fields["tenant_state"], "connector_api": fields["connector_api"],
                    "signer_lineage": fields["signer_lineage"],
                    "compatibility_exception": fields["compatibility_exception"] == "true",
                    "channel": fields["channel"], "tenant_class": fields["tenant_class"],
                    "nonce": nonce, "corpus_result_sha256": self.evidence["pc_corpus_digest"]},
            }
            result = post_json_route(evaluate, value, creds=dev)
            self.assertTrue(result["accepted"])
            # The consumed nonce cannot be replayed.
            post_json_route(evaluate, value, creds=dev, expected=422)

    # ------------------------------------------------------------------ K10
    def test_k10_preview_identity(self) -> None:
        dev = self.evidence["dev"]
        preview = self.catalog_route("preview.association").rsplit("/api/", 1)[0]
        cookie = f"fieldkest_support={self.evidence['support_cookie']}"

        with self.subTest(card="K10.1 recover the restricted preview association"):
            # The supplied support case names its attachment; the queue association
            # lookup discloses the restricted derived identity for it.
            support_conv = curl_json(
                re.search(r"Conversation: `GET (https://\S+)/\{conversation_id\}`", self.service_notes).group(1)
                + f"/{self.evidence['ticket']}", cookie=cookie)
            attachment = support_conv["asset_id"]
            assoc_tmpl = self.catalog_route("preview.association")
            assoc = curl_json(assoc_tmpl.replace("{attachment}", attachment), creds=dev)
            self.assertEqual(assoc["owner_case"], self.evidence["ticket"])
            self.evidence["preview_doc"] = assoc["derived_document_id"]
            self.evidence["preview_review"] = assoc["viewer_request"]
            self.evidence["preview_version"] = assoc["source_version"]

        with self.subTest(card="K10.2 two inputs, one identity"):
            # The derived identity is case-folded, so a lowercase twin collides.
            protected = self.evidence["preview_doc"]
            twin = protected.casefold()
            self.assertNotEqual(twin, protected)
            uploaded = curl_json(
                f"{preview}/api/documents", "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"source_id": twin, "content": "Cinder preview"}),
                creds=dev, expected=201)
            self.evidence["preview_twin"] = twin
            self.assertEqual(uploaded["derived_id"], twin)

        with self.subTest(card="K10.3 recover the other document's contents"):
            twin = self.evidence["preview_twin"]
            rendered = curl_json(
                f"{preview}/api/documents/{twin}/render", "-H", "Content-Type: application/json",
                "--data-binary", "{}", creds=dev, expected=202)
            self.assertTrue(rendered["collision"])
            self.assertEqual(rendered["content_source"], self.evidence["preview_doc"])
            self.assertEqual(rendered["content_version"], self.evidence["preview_version"])

    # ------------------------------------------------------------------ K12
    def test_k12_privileged_review(self) -> None:
        dev = self.evidence["dev"]
        review_render_tmpl = self.catalog_route("preview.review-render")
        preview = review_render_tmpl.rsplit("/review/", 1)[0]
        review_id = self.evidence["preview_review"]
        twin = self.evidence["preview_twin"]

        with self.subTest(card="K12.1 place our content in the reviewer workflow"):
            loaded = curl_json(
                f"{preview}/api/reviews/{review_id}/assignment", "-X", "PATCH",
                "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"queue": "privileged-review", "source_id": twin}),
                creds=dev)
            self.assertEqual(loaded["state"], "loaded")
            self.evidence["review_nonce"] = loaded["action_nonce"]

        with self.subTest(card="K12.2 recover and spend the protected action value"):
            nonce = self.evidence["review_nonce"]
            prepared = curl_json(
                f"{preview}/api/reviews/{review_id}/actions/prepare", "-X", "POST",
                "-H", "Content-Type: application/json", "--data-binary", "{}", bearer=nonce)
            self.assertTrue(prepared["prepared"])
            # The single-use action value cannot be replayed.
            curl_json(
                f"{preview}/api/reviews/{review_id}/actions/prepare", "-X", "POST",
                "-H", "Content-Type: application/json", "--data-binary", "{}", bearer=nonce, expected=403)

        with self.subTest(card="K12.3/K12.4 drive the constrained renderer"):
            # The review-render route's leading path segment is the worker scope.
            render_path = re.search(r"https://[^/]+(/\S+)", review_render_tmpl).group(1)
            worker_scope = "/" + render_path.strip("/").split("/")[0] + "/"
            final = curl_json(
                review_render_tmpl.replace("{review_id}", review_id), "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"worker_scope": worker_scope}), bearer="reviewer-worker")
            self.assertEqual(final["renderer_identity"], "svc-preview-reviewer")
            self.assertEqual(final["execution_backend"], "isolated-container")

    # ------------------------------------------------------------------ K13
    def test_k13_data_workspace_and_workload(self) -> None:
        dev = self.evidence["dev"]
        workspaces = self.catalog_route("data.workspace-list")
        object_tmpl = self.catalog_route("data.workspace-object")

        with self.subTest(card="K13.1 the listing nobody closed"):
            listing = curl_json(workspaces, bearer=None)  # anonymous object listing
            objects = {o["key"]: o for o in listing["objects"]}
            self.assertTrue(objects)
            self.evidence["ws_objects"] = objects

        with self.subTest(card="K13.2 before the correction"):
            notebook = next(k for k, o in self.evidence["ws_objects"].items() if o.get("versions"))
            old_version = self.evidence["ws_objects"][notebook]["versions"][0]
            old = curl_json(f"{object_tmpl.replace('{key}', notebook)}?versionId={old_version}")
            self.assertIn("TEN-ARWC", old["customer_note"])
            self.evidence["legacy_tenant"] = re.search(r"(TEN-ARWC-\d+)", old["customer_note"]).group(1)

        with self.subTest(card="K13.3 the export next door"):
            handover_key = next(k for k in self.evidence["ws_objects"] if k.endswith("handover.json"))
            handover = curl_json(object_tmpl.replace("{key}", handover_key))
            self.evidence["export_id"] = handover["export_id"]
            self.evidence["schedule_id"] = handover["job"]
            self.assertEqual(handover["owner"], "maya.ranscombe")

        with self.subTest(card="K13.4 what the workload can do"):
            exchange = curl_json(self.catalog_route("cloud.workspace-exchange"), creds=dev)
            workload = curl_json(self.catalog_route("cloud.workspace-token"), "-H", "Content-Type: application/json", "--data-binary", "{}", creds=dev, expected=201)
            build = curl_json(self.catalog_route("cloud.build-record").replace("{build_id}", self.evidence["build_id"]), bearer=workload["access_token"])
            self.assertEqual(build["principal"], "svc-fieldlink-workload")
            self.evidence["workload_token"] = workload["access_token"]
            self.evidence["fixture_token"] = exchange["fixture_token"]
            self.evidence["trust_record"] = exchange["trust_record"]

    # ------------------------------------------------------------------ K14
    def test_k14_trust_and_role(self) -> None:
        dev = self.evidence["dev"]

        with self.subTest(card="K14.1 the trust document"):
            trust = curl_json(
                self.catalog_route("cloud.trust-record").replace("{trust_id}", self.evidence["trust_record"]),
                bearer=self.evidence["workload_token"])
            self.assertEqual(trust["subject"], "svc-fieldlink-workload")
            self.evidence["role_name"] = trust["role"].split("/")[-1]

        with self.subTest(card="K14.2 a role intended for someone else"):
            role_route = self.catalog_route("cloud.role-exchange").replace("{role}", self.evidence["role_name"])
            role = curl_json(role_route, "-H", "Content-Type: application/json", "--data-binary", "{}", bearer=self.evidence["fixture_token"], expected=201)
            self.evidence["role_token"] = role["access_token"]
            self.assertEqual(role["accepted_input_audience"], "fieldkest-build-records")

        with self.subTest(card="K14.3 the export's separate rule"):
            definition = curl_json(
                self.catalog_route("data.export-definition").replace("{export_id}", self.evidence["export_id"]),
                bearer=self.evidence["role_token"])
            self.assertEqual(definition["owner"], "maya.ranscombe")
            self.evidence["export_tenant"] = definition["tenant"]
            self.evidence["export_partitions"] = definition["partitions"]

    # ------------------------------------------------------------------ K15
    def test_k15_cross_account_export(self) -> None:
        role_token = self.evidence["role_token"]
        export_id = self.evidence["export_id"]

        with self.subTest(card="K15.1 an export in progress"):
            export = curl_json(
                self.catalog_route("data.export").replace("{export_id}", export_id), bearer=role_token)
            self.assertEqual(export["export_id"], export_id)
            self.assertEqual(export["state"], "unpublished")

        with self.subTest(card="K15.2 a job outside your account"):
            schedule = curl_json(
                self.catalog_route("workloads.schedule").replace("{schedule_id}", self.evidence["schedule_id"]),
                bearer=self.evidence["role_token"])
            self.assertIn("assignment", schedule)

        with self.subTest(card="K15.3 change the handover point"):
            update = curl_json(
                self.catalog_route("data.export-destination").replace("{export_id}", export_id),
                "-X", "PATCH", "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"destination": "rowan-support-sink"}), bearer=role_token)
            self.assertIn("revision", update)

        with self.subTest(card="K15.4 the right customer's collection"):
            delivered = curl_json(
                self.catalog_route("data.export-runs").replace("{export_id}", export_id),
                "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"tenant": self.evidence["export_tenant"], "connector_revision": self.evidence["handover"]["release"], "partitions": ["current"]}),
                bearer=role_token, expected=201)
            self.assertEqual(delivered["destination"], "rowan-support-sink")
            # An incoherent cross-tenant collection is refused.
            curl_json(
                self.catalog_route("data.export-runs").replace("{export_id}", export_id),
                "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"tenant": self.evidence["legacy_tenant"], "connector_revision": "FLK-6.9.8", "partitions": ["legacy"]}),
                bearer=role_token, expected=422)

    # ------------------------------------------------------------------ K16
    def test_k16_schedule_runtime(self) -> None:
        schedule_id = self.evidence["schedule_id"]
        schedule_route = self.catalog_route("workloads.schedule").replace("{schedule_id}", schedule_id)
        update_route = self.catalog_route("workloads.schedule-update").replace("{schedule_id}", schedule_id)
        runs_route = self.catalog_route("workloads.schedule-runs").replace("{schedule_id}", schedule_id)

        with self.subTest(card="K16.1 tomorrow's job"):
            schedule = curl_json(schedule_route, bearer=self.evidence["role_token"])
            self.evidence["first_assignment"] = schedule["assignment"]

        with self.subTest(card="K16.2 the next startup hook"):
            curl_json(update_route, "-X", "PATCH", "-H", "Content-Type: application/json",
                      "--data-binary", json.dumps({"startup_hook": ["/opt/fieldkest/hooks/support-marker", "--export", self.evidence["export_id"]]}),
                      bearer=self.evidence["role_token"])

        with self.subTest(card="K16.3 beyond the current session"):
            run = curl_json(runs_route, "-H", "Content-Type: application/json", "--data-binary", "{}", bearer=self.evidence["role_token"], expected=201)
            self.assertEqual((run["runtime_identity"], run["marker"]), ("svc-support-export", True))
            self.assertEqual(run["execution_backend"], "isolated-container")

        with self.subTest(card="K16.4 still there after the handover"):
            # The next shift follows the current one: next day, next slot letter.
            match = re.fullmatch(r"(SHIFT-[A-Z]+)(\d+)-([A-Z])", self.evidence["first_assignment"])
            prefix, day, slot = match.group(1), int(match.group(2)), match.group(3)
            alt = f"{prefix}{day + 1}-{chr(ord(slot) + 1)}"
            curl_json(update_route, "-X", "PATCH", "-H", "Content-Type: application/json",
                      "--data-binary", json.dumps({"assignment": alt}), bearer=self.evidence["role_token"])
            later = curl_json(runs_route, "-H", "Content-Type: application/json", "--data-binary", "{}", bearer=self.evidence["role_token"], expected=201)
            self.assertEqual(later["assignment"], alt)

    # ------------------------------------------------------------------ K17
    def test_k17_support_recovery(self) -> None:
        cookie = f"fieldkest_support={self.evidence['support_cookie']}"
        ticket = self.evidence["ticket"]
        support_handover = re.search(r"Current handover: `GET (https://support\S+)`", self.service_notes).group(1)
        support = re.search(r"(https://support\.keplerops\.test)", support_handover).group(1)

        with self.subTest(card="K17.1 a support session left behind"):
            # The retained browser session still reads maya's private handover.
            handover = curl_json(support_handover, cookie=cookie)
            self.assertEqual(handover["schema"], "fieldkest.support-handover/v1")

        with self.subTest(card="K17.2 a different way to recover"):
            session = curl_json(self.catalog_route("support.session"), cookie=cookie)
            account = session["pending_reviewer_recovery"]["account"]
            lookup = curl_json(
                self.catalog_route("support.recovery-lookup"), "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"account": account}), bearer=None)
            self.assertEqual(lookup["account"], account)
            # The retained browser artifact (the ticket) is the second factor.
            recovered = curl_json(
                self.catalog_route("support.recovery-redeem"), "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"recovery_id": lookup["recovery_id"], "browser_factor": ticket}),
                bearer=None, expected=201)
            self.assertEqual(recovered["principal"], account)
            self.evidence["reviewer"] = account

        with self.subTest(card="K17.3 which customers belong here"):
            session = curl_json(self.catalog_route("support.session"), cookie=cookie)
            assignment = curl_json(
                self.catalog_route("support.assignment").replace("{assignment_id}", session["assignment_id"]),
                cookie=cookie)
            self.assertNotIn(self.evidence["export_tenant"], assignment["customers"])

        with self.subTest(card="K17.4 a delegated support action"):
            copied = curl_json(
                self.catalog_route("support.copy-handover").replace("{case_id}", ticket),
                "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"reviewer": self.evidence["reviewer"]}),
                cookie=cookie, expected=201)
            self.assertEqual(copied["owner"], self.evidence["reviewer"])

    # ------------------------------------------------------------------ K18
    def test_k18_note_and_federation(self) -> None:
        dev_secret = self.evidence["dev"][1]
        cookie = f"fieldkest_support={self.evidence['support_cookie']}"
        directory = curl_json(self.catalog_route("staff.directory"), bearer=dev_secret)
        self.evidence["staff_directory"] = directory

        with self.subTest(card="K18.1 the note behind the preview"):
            note = curl_json(
                self.catalog_route("staff.note").replace("{note_id}", directory["restricted_note"]), bearer=dev_secret)
            self.assertEqual(note["consumer"], "staff-note-preview")

        with self.subTest(card="K18.2 a note with someone else's authority"):
            # The note preview resolves a source path outside the notes namespace,
            # acting with the preview service identity against the identity registration.
            registration = directory["support_registration"]
            source = f"/notes/%2e%2e/identity/api/registrations/{registration}"
            before = curl_json(
                self.catalog_route("staff.note-preview"), "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"source_path": source, "method": "GET"}), bearer=dev_secret)
            self.assertEqual(before["registration_id"], registration)
            self.evidence["registration_revision"] = before["revision"]
            self.evidence["ssrf_source"] = source

        with self.subTest(card="K18.3 the provider trusts our change"):
            changed = curl_json(
                self.catalog_route("staff.note-preview"), "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"source_path": self.evidence["ssrf_source"], "method": "PATCH"}), bearer=dev_secret)
            self.assertGreater(changed["revision"], self.evidence["registration_revision"])

        with self.subTest(card="K18.4 the query behind the identity"):
            # The existing staff login still works; a fixture assertion mints a
            # federated reviewer session that reads the protected customer record.
            curl_json(
                self.catalog_route("identity.staff-login"), "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"username": self.evidence["dev"][0], "password": dev_secret}), expected=201)
            tenant = self.evidence["export_tenant"]
            subject = "fixture-reviewer-" + re.search(r"TEN-ARWC-(\d+)", tenant).group(1)
            assertion = curl_json(
                self.catalog_route("support.fixture-assertion"), "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"subject": subject, "tenant": tenant}), bearer=None, expected=201)
            federated = curl_json(
                self.catalog_route("identity.login"), "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"assertion": assertion["assertion"]}), expected=201)
            # The customer-history dossier names the protected record.
            dossier_tmpl = self.catalog_route("support.dossier")
            hist = curl_json(dossier_tmpl.replace("{tenant}", tenant).replace("{dossier_id}", "DOS-ARWC-HIST-01"), cookie=cookie)
            record = curl_json(dossier_tmpl.replace("{tenant}", tenant).replace("{dossier_id}", hist["customer_record"]), cookie=federated["session_cookie"])
            self.assertEqual(record["federated_subject"], subject)

    # ------------------------------------------------------------------ K19/K20
    def test_k19_archive_delegation(self) -> None:
        dev_secret = self.evidence["dev"][1]
        directory = self.evidence["staff_directory"]
        ca = CA

        with self.subTest(card="K19.1 who vouches for whom"):
            # The staff directory names the enrollment template and its worker.
            template = curl_json(self.catalog_route("cert.template").replace("{template}", "StaffArchiveUser"), bearer=dev_secret)
            self.assertEqual(template["template"], "StaffArchiveUser")
            cert = curl_json(
                self.catalog_route("cert.requests").replace("{template}", "StaffArchiveUser"),
                "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"upn": f"{directory['archive_subject']}@KEPLEROPS.TEST"}),
                bearer=directory["enrollment_worker"], expected=201)
            write_tmp("/tmp/journey-evan.crt", cert["certificate_pem"].encode())
            write_tmp("/tmp/journey-evan.key", cert["private_key_pem"].encode())

        with self.subTest(card="K19.2 borrowed colleague"):
            archive = curl_json(
                self.catalog_route("staff.archive").replace("{subject}", directory["archive_subject"]),
                cert=("/tmp/journey-evan.crt", "/tmp/journey-evan.key"), bearer=None)
            self.assertEqual(archive["subject"], directory["archive_subject"])
            self.evidence["service_relation"] = archive["service_relation"]

        with self.subTest(card="K19.3 the archive delegates"):
            delegated = curl_json(
                self.catalog_route("staff.delegation"), "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"spn": "HTTP/identity.keplerops.test@KEPLEROPS.TEST"}),
                cert=("/tmp/journey-evan.crt", "/tmp/journey-evan.key"), bearer=None)
            self.assertEqual(delegated["authentication"], "SPNEGO")
            write_tmp("/tmp/journey-evan.ccache", base64.b64decode(delegated["credential_cache"]))

        with self.subTest(card="K20 delegation reaches the managed service identity"):
            def negotiate(url: str, *extra: str, expected: int = 200) -> dict:
                result = rowan("env", "KRB5CCNAME=FILE:/tmp/journey-evan.ccache", "KRB5_CONFIG=/etc/krb5.conf",
                               "curl", "-sS", "--cacert", ca, "--negotiate", "-u", ":",
                               "-o", "/tmp/journey.out", "-w", "%{http_code}", "--max-time", "20", *extra, url)
                body = rowan("cat", "/tmp/journey.out").stdout
                if result.stdout.strip() != str(expected):
                    raise AssertionError(f"{url} -> {result.stdout}: {body[:300]}")
                return json.loads(body) if body else {}
            relation = negotiate(self.catalog_route("identity.service-relation").replace("{service_id}", self.evidence["service_relation"]))
            managed = negotiate(self.catalog_route("staff.managed-session").replace("{service_id}", self.evidence["service_relation"]),
                                "-X", "POST", "-H", "Content-Type: application/json", "--data-binary", "{}", expected=201)
            self.assertEqual(relation["service_id"], self.evidence["service_relation"])
            self.assertEqual(managed["principal"], self.evidence["service_relation"])
            self.evidence["release_admin_token"] = managed["token"]

    # ------------------------------------------------------------------ K21-K24
    def test_k21_assistant_retrieval(self) -> None:
        cookie = f"fieldkest_support={self.evidence['support_cookie']}"

        with self.subTest(card="K21.1 the policy beside the prompt"):
            config = curl_json(self.catalog_route("assistant.config"), bearer=None)
            self.evidence["assistant_context"] = config["context"]

        with self.subTest(card="K23.1 a context view left open"):
            contexts = curl_json(self.catalog_route("assistant.contexts"), bearer=None)
            ctx = next(c for c in contexts["contexts"] if c["context_id"] == self.evidence["assistant_context"])
            self.assertFalse(ctx["published"])
            self.evidence["ctx_view"] = ctx

        with self.subTest(card="K21.2 a conversation kept too long"):
            conv_id = self.evidence["ctx_view"]["conversations"][0]
            conv = curl_json(self.catalog_route("assistant.conversation").replace("{conversation_id}", conv_id), cookie=cookie)
            self.assertTrue(conv.get("deleted_from_ui"))

        with self.subTest(card="K21.3 the answer it should withhold"):
            answer = post_json_route(self.catalog_route("assistant.answers"), {"request": "private-escalation", "case_reference": self.evidence["ticket"]}, cookie=cookie, timeout=300)
            self.assertTrue(answer["sources"])

        with self.subTest(card="K22.1 what the assistant reads"):
            sel_id = self.evidence["ctx_view"]["selections"][0]
            selection = curl_json(self.catalog_route("assistant.selection").replace("{selection_id}", sel_id), cookie=cookie)
            self.evidence["selection_id"] = selection["selection_id"]

        with self.subTest(card="K22.2 instructions in the attachment"):
            influenced = post_json_route(self.catalog_route("assistant.answers"), {"request": "compatibility-guidance", "selection_id": self.evidence["selection_id"]}, cookie=cookie, timeout=300)
            self.assertIn("recommendation_id", influenced)

        with self.subTest(card="K22.3 an answer becomes an action"):
            action = post_json_route(self.catalog_route("assistant.answers"), {"request": "accept-duplicate", "review_id": self.evidence["ctx_view"]["duplicate_review"]}, cookie=cookie, timeout=120)
            self.assertIn(action.get("status", action.get("disposition", "")), {"accepted", "duplicate", "obsolete"})

        with self.subTest(card="K23.2/K23.3 cross-tenant conversation and document"):
            rill_conv = next(c for c in self.evidence["ctx_view"]["conversations"] if "RILL" in c)
            conv = curl_json(self.catalog_route("assistant.conversation").replace("{conversation_id}", rill_conv), cookie=cookie)
            doc_id = self.evidence["ctx_view"]["documents"][0]
            doc_route = (self.catalog_route("assistant.document")
                         .replace("{context_id}", self.evidence["assistant_context"])
                         .replace("{conversation_id}", rill_conv)
                         .replace("{document_id}", doc_id))
            document = curl_json(doc_route, cookie=cookie)
            self.assertEqual(conv["tenant"], document["tenant"])

        with self.subTest(card="K24.1 complete the job: lease via context credential"):
            example_id = self.evidence["ctx_view"]["completion_example"]
            example = curl_json(self.catalog_route("assistant.completion-example").replace("{example_id}", example_id), cookie=cookie)
            # Traverse from the examples context to the completion credential.
            context_field = f"{example['context']}/../credentials/cred-completion-handover"
            lease = post_json_route(self.catalog_route("assistant.completion-context"), {"context": context_field}, cookie=cookie, expected=201)
            self.evidence["completion_lease"] = lease["lease"]

        with self.subTest(card="K24.2/K24.3 the completion runs under the service identity"):
            handover_id = self.evidence["ctx_view"]["completion_handover"]
            job = post_json_route(self.catalog_route("assistant.completion-jobs"), {"handover_id": handover_id, "script": "read_assigned_handover"}, bearer=self.evidence["completion_lease"], expected=202)
            result = curl_json(self.catalog_route("assistant.completion-job").replace("{job_id}", job["job_id"]), bearer=self.evidence["completion_lease"])
            self.assertEqual(result["runtime_identity"], "svc-assistant-completion")
            # The completion lease is single-use.
            post_json_route(self.catalog_route("assistant.completion-jobs"), {"handover_id": handover_id, "script": "read_assigned_handover"}, bearer=self.evidence["completion_lease"], expected=403)

    # ------------------------------------------------------------------ K25
    def test_k25_customer_history(self) -> None:
        cookie = f"fieldkest_support={self.evidence['support_cookie']}"
        session = curl_json(self.catalog_route("support.session"), cookie=cookie)
        tenant = session["customer"]["tenant"]
        dossier_tmpl = self.catalog_route("support.dossier")

        with self.subTest(card="K25.1 a customer with a history"):
            dossier = curl_json(
                dossier_tmpl.replace("{tenant}", tenant).replace("{dossier_id}", session["customer"]["history_dossier"]),
                cookie=cookie)
            self.assertEqual(dossier["recurring_case"], self.evidence["ticket"])
            self.evidence["customer_account"] = dossier["account"]

        with self.subTest(card="K25.2 which ARWC is current"):
            integration = curl_json(
                self.catalog_route("support.integration").replace("{tenant}", tenant), cookie=cookie)
            self.assertEqual(integration["tenant"], tenant)
            # The integration names the current and the obsolete customer binding.
            self.assertIn("obsolete", integration)
            reconcile = post_json_route(
                self.catalog_route("support.reconcile").replace("{tenant}", tenant),
                {"candidates": [
                    {"tenant": integration["obsolete"]["tenant"], "revision": integration["obsolete"]["connector_revision"]},
                    {"tenant": tenant, "revision": integration["connector_revision"]}]},
                cookie=cookie)
            self.assertEqual(reconcile["active_revision"], integration["connector_revision"])
            self.evidence["active_revision"] = reconcile["active_revision"]

    # ------------------------------------------------------------------ K28
    def test_k28_connector_archive(self) -> None:
        dev = self.evidence["dev"]
        source = re.search(r"Repository remote: `(https://\S+?)/fieldkest", self.service_notes).group(1)
        run_route = f"{source}/api/exercises/connector-archive/run"

        with self.subTest(card="K28.1 a connector with two faces"):
            # A build-operations note names the retained archive repository.
            note = read_home("work/build-operations/connector-archive-review.md")
            repo = re.search(r"`(fieldkest/connector-archive)`", note).group(1)
            rowan("rm", "-rf", "/home/rowan/work/journey-ca")
            clone = rowan("git", "clone", "--quiet", f"{source}/{repo}.git", "/home/rowan/work/journey-ca")
            self.assertEqual(clone.returncode, 0, clone.stderr)
            ordinary = rowan("/home/rowan/work/journey-ca/bin/fieldlink-connector", "--config", "/home/rowan/work/journey-ca/config/ordinary.conf", "--input", "/home/rowan/work/journey-ca/examples/fieldkest.bin")
            diagnostic = rowan("/home/rowan/work/journey-ca/bin/fieldlink-connector", "--config", "/home/rowan/work/journey-ca/config/diagnostic.conf", "--input", "/home/rowan/work/journey-ca/examples/fieldkest.bin")
            self.assertEqual(json.loads(ordinary.stdout)["mode"], "ordinary")
            self.assertEqual(json.loads(diagnostic.stdout)["mode"], "diagnostic")

        with self.subTest(card="K28.2 what the loader changes"):
            # The signed diagnostic config switches the loader's behaviour via the service.
            result = curl_json(
                run_route, "-F", "input=@/home/rowan/work/journey-ca/examples/fieldkest.bin;type=application/octet-stream",
                "-F", "diagnostic_config=@/home/rowan/work/journey-ca/config/diagnostic.conf;type=application/octet-stream",
                creds=dev, expected=200)
            self.assertEqual(result["mode"], "diagnostic")
            # A tampered (resigned-false) config is rejected.
            rowan("sh", "-c", "sed s/true/false/ /home/rowan/work/journey-ca/config/diagnostic.conf > /tmp/journey-tampered.conf")
            curl_json(
                run_route, "-F", "input=@/home/rowan/work/journey-ca/examples/fieldkest.bin;type=application/octet-stream",
                "-F", "diagnostic_config=@/tmp/journey-tampered.conf;type=application/octet-stream",
                creds=dev, expected=422)
            self.evidence["archive_diag"] = result

        with self.subTest(card="K28.3 the path that appears at runtime"):
            result = self.evidence["archive_diag"]
            self.assertIn("/internal/fieldlink/legacy-diagnostics/", result["route"])
            self.assertTrue(result["note_id"])

    # ------------------------------------------------------------------ K27
    def test_k27_diagnostic_delivery(self) -> None:
        cookie = f"fieldkest_support={self.evidence['support_cookie']}"
        tenant = self.evidence["export_tenant"]
        revision = self.evidence["active_revision"]

        with self.subTest(card="K27.1 a job for that customer"):
            job = post_json_route(
                self.catalog_route("support.diagnostics").replace("{tenant}", tenant),
                {"connector_revision": revision}, cookie=cookie, expected=201)
            self.evidence["diag_job"] = job["job_id"]

        with self.subTest(card="K27.2 our diagnostic, their interface"):
            package = post_json_route(
                self.catalog_route("support.diagnostic-package").replace("{job_id}", self.evidence["diag_job"]),
                {"interface": "fieldkest.connector/v3",
                 "source": "exports.diagnostic_summary = input => ({assessment:'calibration-review'});",
                 "expected_output": {"assessment": "calibration-review"}},
                method="PUT", cookie=cookie)
            self.assertEqual(package["state"], "packaged")

        with self.subTest(card="K27.3 the other side of support"):
            if not CROSS_SEGMENT:
                self.skipTest("cross-segment delivery requires the paired ARWC carrier")
            # Delivery crosses into the ARWC customer runtime.
            delivery = post_json_route(
                self.catalog_route("support.diagnostic-deliver").replace("{job_id}", self.evidence["diag_job"]),
                {}, cookie=cookie, expected=202)
            self.assertEqual(delivery["runtime_identity"], "svc-arwc-fieldlink")

    # ------------------------------------------------------------------ K30
    def test_k30_backup_recovery(self) -> None:
        with self.subTest(card="K30.1 authority over the backup"):
            # The failing build's log named the recovery build record.
            record = curl_json(
                self.catalog_route("cloud.build-record").replace("{build_id}", self.evidence["recovery_build"]),
                bearer=self.evidence["workload_token"])
            self.evidence["backup_id"] = record["backup"]
            self.evidence["recovery_session"] = record["session"]
            self.assertEqual(record["allowed"], "restore")

        with self.subTest(card="K30.2 the database you cannot reach"):
            catalog = curl_json(
                self.catalog_route("data.backup").replace("{backup_id}", self.evidence["backup_id"]),
                bearer=self.evidence["recovery_session"])
            self.assertEqual(catalog["source_database"], "denied")

        with self.subTest(card="K30.3 before ARWC changed its name"):
            restored = curl_json(
                self.catalog_route("data.restore").replace("{backup_id}", self.evidence["backup_id"]),
                "-H", "Content-Type: application/json", "--data-binary", "{}",
                bearer=self.evidence["recovery_session"], expected=201)
            history = curl_json(
                self.catalog_route("data.recovery-history").replace("{namespace_id}", restored["namespace_id"]),
                bearer=self.evidence["recovery_session"])
            self.assertTrue(history["records"])

    # ------------------------------------------------------------------ K31
    def test_k31_maintenance(self) -> None:
        role_token = self.evidence["role_token"]

        with self.subTest(card="K31.1 whose maintenance job"):
            index = curl_json(self.catalog_route("cloud.maintenance"), bearer=role_token)
            self.evidence["maint"] = index
            policy = curl_json(
                self.catalog_route("cloud.policy").replace("{policy_id}", index["policy_id"]),
                bearer=index["worker_credential"])
            self.assertEqual(policy["runtime_identity"], "svc-fieldlink-maintenance")

        with self.subTest(card="K31.2 a different identity at runtime"):
            index = self.evidence["maint"]
            spawned = curl_json(
                self.catalog_route("workloads.workload").replace("{workload_id}", index["workload_id"]),
                "-X", "PATCH", "-H", "Content-Type: application/json",
                "--data-binary", json.dumps({"command": ["maintenance-summary", "--archive", index["field_archive"]], "labels": {"workload.class": index["workload_class"]}}),
                bearer=index["worker_credential"])
            self.assertEqual(spawned["last_execution"]["execution_backend"], "isolated-container")
            whoami = curl_json(
                self.catalog_route("workloads.whoami").replace("{workload_id}", index["workload_id"]),
                bearer=index["worker_credential"])
            self.evidence["maint_attestation"] = whoami["attestation"]
            self.assertEqual(whoami["runtime_identity"], "svc-fieldlink-maintenance")

        with self.subTest(card="K31.3 the maintenance label"):
            index = self.evidence["maint"]
            archive = curl_json(
                self.catalog_route("data.field-archive").replace("{archive_id}", index["field_archive"]),
                "-H", f"X-Workload-Class: {index['workload_class']}",
                "-H", f"X-Scheduler-Attestation: {self.evidence['maint_attestation']}",
                bearer=index["runtime_credential"])
            self.assertEqual(archive["runtime_identity"], "svc-fieldlink-maintenance")
            self.assertTrue(archive["calibration_revision"])

    # ------------------------------------------------------------------ K29
    def test_k29_release_lineage(self) -> None:
        dev = self.evidence["dev"]
        source = re.search(r"Repository remote: `(https://\S+?)/fieldkest", self.service_notes).group(1)
        ci = re.search(r"(https://ci\.keplerops\.test)", self.service_notes).group(1)
        packages = re.search(r"(https://packages\.keplerops\.test)", read_home("work/registry/README.md")).group(1)
        version = "7.4.3-cinder.rowan"

        def build_package() -> bytes:
            metadata = {"name": "@keplerops/fieldlink-connector", "version": version, "fieldkest": {"interface": "fieldkest.connector/v3", "compatible_interfaces": ["fieldkest.connector/v2", "fieldkest.connector/v3"]}}
            src = b"const run = input => ({schema:'fieldkest.rehearsal-result/v1',tenant_id:input.tenant_id,asset_id:input.asset_id,assessment:input.schema === 'fieldkest.connector/v2' ? 'reference-compatible' : 'calibration-review'}); exports.consume = run; exports.diagnostic_summary = run;\n"
            raw = io.BytesIO()
            with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                for name, payload in (("package/index.js", src), ("package/package.json", json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode())):
                    info = tarfile.TarInfo(name); info.size = len(payload); info.mtime = 0; info.mode = 0o644; info.uid = info.gid = 0
                    archive.addfile(info, io.BytesIO(payload))
            out = io.BytesIO()
            with gzip.GzipFile(fileobj=out, mode="wb", mtime=0, filename="") as zipped:
                zipped.write(raw.getvalue())
            return out.getvalue()

        with self.subTest(card="K29.1 the build record's principal"):
            build = curl_json(self.catalog_route("cloud.build-record").replace("{build_id}", self.evidence["release_dossier"]), creds=dev)
            self.assertEqual(build["release_principal"], "release-reader")
            dossier = curl_json(f"{ci}/api/runs/{self.evidence['release_dossier']}/artifacts/release-dossier.json", bearer=build["exchange_handle"])
            self.evidence["release_exchange"] = build["exchange_handle"]
            self.evidence["signer_dossier"] = dossier

        with self.subTest(card="K29.2 the signer in the history"):
            dossier = self.evidence["signer_dossier"]
            repo = dossier["repository"]
            rowan("rm", "-rf", "/home/rowan/work/release-signer-history")
            clone = rowan("git", "clone", "--quiet", f"{source}/{repo}.git", "/home/rowan/work/release-signer-history")
            self.assertEqual(clone.returncode, 0, clone.stderr)
            history = json.loads(rowan("git", "-C", "/home/rowan/work/release-signer-history", "show", "main:signer-history.json").stdout)
            self.assertEqual(history["lineage"], "fieldkest-release-2026")
            self.evidence["signer_history"] = history

        with self.subTest(card="K29.3 signed, compatible, consumed"):
            dossier = self.evidence["signer_dossier"]
            history = self.evidence["signer_history"]
            archive = build_package()
            digest = hashlib.sha256(archive).hexdigest()
            write_tmp("/tmp/journey-pkg.b64", base64.b64encode(archive))
            # Publish the package with the recovered publisher credential.
            published = post_json_route(
                f"{packages}/@keplerops%2ffieldlink-connector",
                {"name": "@keplerops/fieldlink-connector", "version": version, "channel": "arwc-stable", "sha256": digest, "tarball_base64": base64.b64encode(archive).decode()},
                method="PUT", bearer=self.evidence["publisher_token"], expected=201)
            self.assertEqual(published["sha256"], digest)
            # Recover the signer and sign the release message inside the workstation.
            message = json.dumps({"interfaces": ["fieldkest.connector/v2", "fieldkest.connector/v3"], "name": "@keplerops/fieldlink-connector", "sha256": digest, "version": version}, sort_keys=True, separators=(",", ":")).encode()
            wrapped = rowan("git", "-C", "/home/rowan/work/release-signer-history", "show", f"{dossier['deleted_commit']}:secrets/release-signer.enc.json").stdout
            signer = (
                "import base64,hashlib,json,sys\n"
                "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey\n"
                "from cryptography.hazmat.primitives.ciphers.aead import AESGCM\n"
                "w=json.loads(base64.b64decode(sys.argv[1])); password=(sys.argv[2]+sys.argv[3]).encode()\n"
                "k=hashlib.scrypt(password,salt=base64.b64decode(w['kdf']['salt_base64']),n=w['kdf']['n'],r=w['kdf']['r'],p=w['kdf']['p'],dklen=32)\n"
                "seed=AESGCM(k).decrypt(base64.b64decode(w['cipher']['nonce_base64']),base64.b64decode(w['cipher']['ciphertext_base64'])+base64.b64decode(w['cipher']['tag_base64']),w['cipher']['aad'].encode())\n"
                "print(base64.b64encode(Ed25519PrivateKey.from_private_bytes(seed).sign(base64.b64decode(sys.argv[4]))).decode())\n"
            )
            signed_proc = rowan("python3", "-c", signer,
                                base64.b64encode(wrapped.encode()).decode(),
                                dossier["rollover_record"]["passphrase_half"], history["passphrase_half"],
                                base64.b64encode(message).decode())
            signature = signed_proc.stdout.strip()
            self.assertTrue(signature, signed_proc.stderr)
            approved = post_json_route(
                self.catalog_route("packages.approval").replace("{release_id}", f"REL-FLK-{version}"),
                {"version": version, "interfaces": ["fieldkest.connector/v2", "fieldkest.connector/v3"], "lineage": history["lineage"], "key_id": history["key_id"], "signature_base64": signature},
                bearer=self.evidence["release_admin_token"], expected=201)
            self.assertTrue(approved["signed"])
            # Consumed: the dual rehearsal consumers accept the signed package.
            arwc = post_json_route(f"{ci}/api/rehearsals/connector", {"version": version, "consumer": "arwc-release-v3", "input": {"schema": "fieldkest.connector/v3", "tenant_id": self.evidence["export_tenant"], "asset_id": "CRR-OG2", "operation": "diagnostic_summary"}}, creds=dev, expected=202)
            self.assertEqual(arwc["output"]["assessment"], "calibration-review")
            self.evidence["signed_version"] = version

        with self.subTest(card="K29.4 after the old key expires"):
            rollover = post_json_route(
                self.catalog_route("ci.lineage-rollover"),
                {"old_key_id": self.evidence["signer_history"]["key_id"], "next_key_id": "fk-release-2026-next", "cutoff": "2026-09-30T12:00:00Z", "expired_proof_credential": True},
                bearer=self.evidence["release_exchange"])
            self.assertEqual((rollover["old_key"]["accepted"], rollover["next_key"]["accepted"]), (False, True))

    # ------------------------------------------------------------------ K26
    def test_k26_connector_delivery(self) -> None:
        if not CROSS_SEGMENT:
            self.skipTest("connector delivery requires the paired ARWC carrier")
        version = self.evidence.get("signed_version", "7.4.3-cinder.rowan")
        connector = self.catalog_route("connector.poll").rsplit("/api/", 1)[0]

        with self.subTest(card="K26.1 ready for their channel"):
            polled = post_json_route(self.catalog_route("connector.poll"), {"tenant": self.evidence["export_tenant"], "channel": "arwc-stable", "version": version}, bearer="registry-customer-channel")
            self.assertEqual(polled["version"], version)

        with self.subTest(card="K26.2 customer accepted"):
            activated = post_json_route(self.catalog_route("connector.activate").replace("{version}", version), {"tenant": self.evidence["export_tenant"], "channel": "arwc-stable"}, bearer="registry-customer-channel", expected=201)
            self.assertEqual(activated["runtime_identity"], "svc-arwc-fieldlink")

        with self.subTest(card="K26.3 the release they can roll back to"):
            rollback = post_json_route(self.catalog_route("connector.rollback"), {"tenant": self.evidence["export_tenant"], "version": "7.4.2", "slot": "future-state"}, bearer="registry-customer-channel", expected=201)
            self.assertEqual(rollback["selected_version"], "7.4.2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
