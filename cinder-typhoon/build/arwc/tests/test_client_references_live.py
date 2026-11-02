#!/usr/bin/env python3
"""Verify the participant can crawl every ARWC client-reference document."""

from __future__ import annotations

import json
import subprocess
import unittest


CONTAINER = "cinder-arwc-connector"
EXPECTED_REFERENCES = {
    "https://customer-handover.arwc.test:8443/.well-known/arwc-client",
    "https://business-workplace.arwc.test/.well-known/arwc-client",
    "https://planning-data.arwc.test/.well-known/arwc-client",
    "https://corporate-identity.arwc.test/.well-known/arwc-client",
    "https://retained-archive.arwc.test/.well-known/arwc-client",
    "https://contractor-portal.arwc.test/.well-known/arwc-client",
    "https://field-gateway.arwc.test/.well-known/arwc-client",
    "https://maintenance-review.arwc.test/.well-known/arwc-client",
    "https://process-view.arwc.test/.well-known/arwc-client",
}


def inside(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CONTAINER, *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def get_json(url: str) -> dict[str, object]:
    script = r'''
import json,ssl,sys,urllib.request
context=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
response=urllib.request.urlopen(sys.argv[1],context=context,timeout=10)
print(response.status)
print(response.read().decode())
'''
    completed = inside("python3", "-c", script, url)
    if completed.returncode:
        raise AssertionError(f"GET {url} failed: {completed.stderr}")
    status, payload = completed.stdout.split("\n", 1)
    if int(status) != 200:
        raise AssertionError(f"GET {url} returned {status}")
    result = json.loads(payload)
    if not isinstance(result, dict):
        raise AssertionError(f"GET {url} did not return an object")
    return result


class ClientReferenceGraphLive(unittest.TestCase):
    def test_transition_reaches_every_published_client_document(self) -> None:
        transition_result = inside(
            "cat", "/var/lib/fieldlink-connector/handover/customer-transition.json",
        )
        self.assertEqual(transition_result.returncode, 0, transition_result.stderr)
        transition = json.loads(transition_result.stdout)
        queue = [transition["client_reference"]]
        visited: set[str] = set()
        routes: dict[str, dict[str, str]] = {}

        while queue:
            url = queue.pop(0)
            if url in visited:
                continue
            document = get_json(url)
            self.assertEqual(document.get("schema"), "arwc.client-documents/v1")
            self.assertIsInstance(document.get("service"), str)
            published = document.get("routes")
            self.assertIsInstance(published, list)
            self.assertTrue(published)
            for route in published:
                self.assertIsInstance(route, dict)
                self.assertEqual(set(route), {"key", "method", "template"})
                key = route["key"]
                self.assertNotIn(key, routes)
                routes[key] = route
            related = document.get("related")
            self.assertIsInstance(related, list)
            queue.extend(link for link in related if link not in visited)
            visited.add(url)

        self.assertEqual(visited, EXPECTED_REFERENCES)
        self.assertEqual(
            routes["process.signature-program-reproduction"],
            {
                "key": "process.signature-program-reproduction",
                "method": "POST",
                "template": "https://process-view.arwc.test/api/signature-programs/current/reproductions",
            },
        )
        self.assertEqual(
            routes["process.reporting-checkpoint-submit"],
            {
                "key": "process.reporting-checkpoint-submit",
                "method": "POST",
                "template": "https://process-view.arwc.test/api/reporting-checkpoints/current",
            },
        )
        templates = {route["template"] for route in routes.values()}
        self.assertNotIn("https://process-view.arwc.test/api/integrity-verifier", templates)
        self.assertNotIn("https://planning-data.arwc.test/api/reporting-checkpoints/current", templates)


if __name__ == "__main__":
    unittest.main(verbosity=2)
