#!/usr/bin/env python3

import http.cookiejar
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser


BASE_URL = "https://notebook.cinder.lab"
USERNAME = "cinder-field-operator"
PASSWORD = "Cinder-Field-Operator-Notebook-R5w8Nx2k"


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = {}

    def handle_starttag(self, tag, attrs):
        if tag != "input":
            return
        attributes = dict(attrs)
        if "name" in attributes:
            self.values[attributes["name"]] = attributes.get("value", "")


cookies = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cookies),
    urllib.request.HTTPSHandler(context=ssl.create_default_context()),
)


def open_path(path, *, data=None, method=None, headers=None, timeout=15):
    request = urllib.request.Request(
        urllib.parse.urljoin(BASE_URL, path),
        data=data,
        method=method,
        headers=headers or {},
    )
    return opener.open(request, timeout=timeout)


def form_values(response):
    parser = FormParser()
    parser.feed(response.read().decode("utf-8"))
    return parser.values


def xsrf_token():
    candidates = [cookie for cookie in cookies if cookie.name == "_xsrf"]
    if candidates:
        cookie = max(candidates, key=lambda item: len(item.path))
        return urllib.parse.unquote(cookie.value)
    raise RuntimeError("JupyterHub did not issue an XSRF cookie")


login = open_path("/hub/login")
login_values = form_values(login)
login_payload = urllib.parse.urlencode(
    {
        "_xsrf": login_values["_xsrf"],
        "username": USERNAME,
        "password": PASSWORD,
    }
).encode()
login_result = open_path(
    "/hub/login",
    data=login_payload,
    method="POST",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
if "/hub/login" in login_result.geturl():
    raise RuntimeError("JupyterHub participant login was rejected")

spawn = open_path("/hub/spawn")
if "/hub/spawn" in spawn.geturl():
    spawn_values = form_values(spawn)
    spawn_payload = urllib.parse.urlencode(
        {"_xsrf": spawn_values["_xsrf"], "profile": "cpu"}
    ).encode()
    open_path(
        "/hub/spawn",
        data=spawn_payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

api_path = f"/user/{urllib.parse.quote(USERNAME)}/api"
deadline = time.monotonic() + 180
while True:
    try:
        response = open_path(api_path, timeout=10)
        if response.status == 200:
            break
    except (urllib.error.HTTPError, urllib.error.URLError):
        pass
    if time.monotonic() >= deadline:
        raise RuntimeError("participant notebook did not become ready")
    time.sleep(2)

user_base = f"/user/{urllib.parse.quote(USERNAME)}"
open_path(f"{user_base}/lab")
root_contents = json.load(open_path(f"{user_base}/api/contents/"))
root_entries = {entry["name"]: entry for entry in root_contents.get("content", [])}
if "START-HERE.md" in root_entries:
    workspace_prefix = ""
elif root_entries.get("work", {}).get("type") == "directory":
    workspace_prefix = "work/"
else:
    raise RuntimeError("participant notebook does not expose the seeded Cinder workspace")
probe_path = f"{user_base}/api/contents/{workspace_prefix}keplerops-readiness.txt"
probe_value = f"cinder-workspace-{int(time.time())}"
headers = {
    "Content-Type": "application/json",
    "X-XSRFToken": xsrf_token(),
}
payload = json.dumps(
    {"type": "file", "format": "text", "content": probe_value}
).encode()
try:
    open_path(probe_path, data=payload, method="PUT", headers=headers)
except urllib.error.HTTPError as error:
    detail = error.read().decode("utf-8", errors="replace")[:500]
    raise RuntimeError(f"participant notebook write failed ({error.code}): {detail}") from error
stored = json.load(open_path(probe_path))
if stored.get("content") != probe_value:
    raise RuntimeError("participant notebook PVC did not preserve written content")
open_path(probe_path, data=b"", method="DELETE", headers=headers)

print("PASS participant JupyterHub login, CPU workspace, and PVC file roundtrip")
