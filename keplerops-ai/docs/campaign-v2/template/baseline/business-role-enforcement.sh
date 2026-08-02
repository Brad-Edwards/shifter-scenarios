#!/usr/bin/env bash
set -Eeuo pipefail

readonly WORKSTATION=keplerops-participant-workstation-runtime

if [[ $(docker inspect --format '{{.State.Running}}' "${WORKSTATION}" 2>/dev/null) != true ]]; then
  printf 'participant workstation is not running: %s\n' "${WORKSTATION}" >&2
  exit 1
fi

docker exec --interactive \
  --user kasm-user \
  --env HOME=/home/kasm-user \
  --env PYTHONDONTWRITEBYTECODE=1 \
  "${WORKSTATION}" python3 - <<'PY'
from __future__ import annotations

import html
import http.cookiejar
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any


RANGE_CA = "/usr/local/share/ca-certificates/keplerops-range-root.crt"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class Form(HTMLParser):
    def __init__(
        self,
        *,
        form_id: str | None = None,
        action_contains: str | None = None,
    ) -> None:
        super().__init__()
        self.form_id = form_id
        self.action_contains = action_contains
        self.action: str | None = None
        self.fields: dict[str, str] = {}
        self._selected = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = dict(attrs)
        if tag == "form" and self.action is None:
            action = html.unescape(values.get("action") or "")
            matches_id = self.form_id is None or values.get("id") == self.form_id
            matches_action = (
                self.action_contains is None or self.action_contains in action
            )
            if matches_id and matches_action:
                self.action = action
                self._selected = True
            return
        if tag == "input" and self._selected:
            name = values.get("name")
            if name:
                self.fields[name] = values.get("value") or ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._selected:
            self._selected = False


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.hrefs.append(html.unescape(href))


def fail(message: str) -> None:
    raise RuntimeError(message)


def browser() -> urllib.request.OpenerDirector:
    context = ssl.create_default_context(cafile=RANGE_CA)
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        urllib.request.HTTPSHandler(context=context),
    )
    opener.addheaders = [
        ("User-Agent", USER_AGENT),
        ("Accept-Language", "en-US,en;q=0.9"),
    ]
    return opener


def request(
    opener: urllib.request.OpenerDirector,
    target: str | urllib.request.Request,
) -> tuple[int, str, str]:
    try:
        with opener.open(target, timeout=60) as response:
            return (
                response.status,
                response.geturl(),
                response.read().decode("utf-8", errors="replace"),
            )
    except urllib.error.HTTPError as error:
        return (
            error.code,
            error.geturl(),
            error.read().decode("utf-8", errors="replace"),
        )


def form_post(
    opener: urllib.request.OpenerDirector,
    url: str,
    fields: dict[str, str],
    *,
    origin: str | None = None,
    referer: str | None = None,
) -> tuple[int, str, str]:
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if origin:
        headers["Origin"] = origin
    if referer:
        headers["Referer"] = referer
    return request(
        opener,
        urllib.request.Request(
            url,
            data=urllib.parse.urlencode(fields).encode(),
            headers=headers,
            method="POST",
        ),
    )


def json_call(
    opener: urllib.request.OpenerDirector,
    url: str,
    payload: dict[str, Any],
    *,
    origin: str,
    referer: str,
    method: str = "POST",
) -> tuple[int, str, dict[str, Any]]:
    status, response_url, body = request(
        opener,
        urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": origin,
                "Referer": referer,
            },
            method=method,
        ),
    )
    try:
        decoded = json.loads(body)
    except json.JSONDecodeError as error:
        fail(
            f"browser JSON response was invalid: HTTP {status} at {response_url}: "
            f"{body[:300]!r}; {error}"
        )
    if not isinstance(decoded, dict):
        fail(f"browser JSON response was not an object at {response_url}")
    return status, response_url, decoded


def submit_keycloak_credentials(
    opener: urllib.request.OpenerDirector,
    login_url: str,
    login_page: str,
    username: str,
    password: str,
) -> tuple[int, str, str]:
    login_form = Form(form_id="kc-form-login")
    login_form.feed(login_page)
    if not login_form.action:
        fail(f"Keycloak login form was absent at {login_url}")
    fields = dict(login_form.fields)
    fields.update(
        {"username": username, "password": password, "credentialId": ""}
    )
    return form_post(
        opener,
        urllib.parse.urljoin(login_url, login_form.action),
        fields,
        origin="https://id.keplerops.lab",
        referer=login_url,
    )


def ghost_login(email: str, password: str) -> urllib.request.OpenerDirector:
    origin = "https://status.keplerops.lab"
    opener = browser()
    status, url, body = request(
        opener,
        urllib.request.Request(
            f"{origin}/ghost/api/admin/session/",
            data=json.dumps({"username": email, "password": password}).encode(),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": origin,
                "Referer": f"{origin}/ghost/",
            },
            method="POST",
        ),
    )
    if status != 201:
        fail(
            f"Ghost browser login failed for {email}: HTTP {status} at {url}: "
            f"{body[:300]!r}"
        )
    return opener


def ghost_self(opener: urllib.request.OpenerDirector) -> dict[str, Any]:
    origin = "https://status.keplerops.lab"
    status, url, body = request(
        opener,
        urllib.request.Request(
            f"{origin}/ghost/api/admin/users/me/?include=roles",
            headers={
                "Accept": "application/json",
                "Accept-Version": "v5.0",
                "Origin": origin,
                "Referer": f"{origin}/ghost/",
            },
        ),
    )
    try:
        decoded = json.loads(body)
        user = decoded["users"][0]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
        fail(f"Ghost current-user response was invalid: HTTP {status} at {url}: {error}")
    if status != 200 or not isinstance(user, dict):
        fail(f"Ghost current-user lookup failed: HTTP {status} at {url}")
    return user


def assert_ghost() -> None:
    owner = ghost_self(
        ghost_login(
            "communications@keplerops.lab",
            "Gv7!qL2@nP9#xR4%wT8&mK3",
        )
    )
    editor = ghost_self(
        ghost_login(
            "comms.publisher@keplerops.lab",
            "KeplerV2-Training-Comms",
        )
    )

    owner_roles = {role.get("name") for role in owner.get("roles", [])}
    editor_roles = {role.get("name") for role in editor.get("roles", [])}
    if (
        owner.get("email") != "communications@keplerops.lab"
        or owner.get("name") != "Range Administrator"
        or owner_roles != {"Owner"}
    ):
        fail(f"Ghost owner identity or native role was wrong: roles={owner_roles!r}")
    if (
        editor.get("email") != "comms.publisher@keplerops.lab"
        or editor.get("name") != "Samira Okafor"
        or editor_roles != {"Editor"}
    ):
        fail(f"Ghost editor identity or native role was wrong: roles={editor_roles!r}")

    status, url, rss = request(browser(), "https://status.keplerops.lab/rss/")
    if status != 200:
        fail(f"Ghost public RSS failed: HTTP {status} at {url}")
    try:
        root = ET.fromstring(rss)
    except ET.ParseError as error:
        fail(f"Ghost public RSS was invalid XML: {error}")
    creators = {
        (item.findtext("title") or "").strip(): (
            item.findtext("{http://purl.org/dc/elements/1.1/}creator") or ""
        ).strip()
        for item in root.findall("./channel/item")
    }
    expected = {
        "Operational Baseline": owner["name"],
        "Communications Maintenance Window": editor["name"],
    }
    for title, creator in expected.items():
        if creators.get(title) != creator:
            fail(
                f"Ghost public ownership mismatch for {title!r}: "
                f"expected {creator!r}, got {creators.get(title)!r}"
            )
    print("PASS Ghost browser sessions expose native Owner/Editor roles and public ownership")


def mautic_saml_login(
    username: str, password: str
) -> urllib.request.OpenerDirector:
    base = "https://advisories.keplerops.lab"
    opener = browser()
    status, request_url, request_page = request(opener, f"{base}/s/saml/login")
    request_form = Form(action_contains="/protocol/saml")
    request_form.feed(request_page)
    if status != 200 or not request_form.action or "SAMLRequest" not in request_form.fields:
        fail(f"Mautic did not produce a SAML request form: HTTP {status} at {request_url}")

    status, login_url, login_page = form_post(
        opener,
        urllib.parse.urljoin(request_url, request_form.action),
        request_form.fields,
        origin=base,
        referer=request_url,
    )
    if status != 200 or urllib.parse.urlsplit(login_url).hostname != "id.keplerops.lab":
        fail(f"Mautic SAML did not reach Keycloak: HTTP {status} at {login_url}")

    status, response_url, response_page = submit_keycloak_credentials(
        opener, login_url, login_page, username, password
    )
    response_form = Form(action_contains="/s/saml/login_check")
    response_form.feed(response_page)
    if not response_form.action or "SAMLResponse" not in response_form.fields:
        fail(
            f"Keycloak did not return the Mautic SAML response form: "
            f"HTTP {status} at {response_url}"
        )
    status, final_url, final_page = form_post(
        opener,
        urllib.parse.urljoin(response_url, response_form.action),
        response_form.fields,
        origin="https://id.keplerops.lab",
        referer=response_url,
    )
    if (
        status != 200
        or urllib.parse.urlsplit(final_url).hostname != "advisories.keplerops.lab"
        or "/s/login" in urllib.parse.urlsplit(final_url).path
        or "Invalid login" in final_page
    ):
        fail(f"Mautic SAML login failed for {username}: HTTP {status} at {final_url}")
    return opener


def assert_mautic() -> None:
    opener = mautic_saml_login(
        "comms.publisher", "KeplerV2-Training-Comms"
    )
    base = "https://advisories.keplerops.lab"

    status, url, account = request(opener, f"{base}/s/account")
    if status != 200 or "comms.publisher" not in account:
        fail(f"Mautic account page did not identify comms.publisher: HTTP {status} at {url}")

    status, url, emails = request(opener, f"{base}/s/emails/1")
    if status != 200 or "Access Denied" in emails:
        fail(f"Mautic Communications role could not read email content: HTTP {status} at {url}")
    status, url, new_email = request(opener, f"{base}/s/emails/new")
    if status != 200 or "Access Denied" in new_email:
        fail(f"Mautic Communications role could not render email creation: HTTP {status} at {url}")

    for denied_path in ("/s/config/edit", "/s/roles/1"):
        status, url, _ = request(opener, f"{base}{denied_path}")
        if status != 403:
            fail(
                f"Mautic Communications role escaped its non-admin boundary at "
                f"{denied_path}: HTTP {status} at {url}"
            )
    print("PASS Mautic SAML grants Communications work and denies native administration")


def odoo_login(
    username: str, password: str
) -> tuple[urllib.request.OpenerDirector, dict[str, Any]]:
    base = "https://business.keplerops.lab"
    opener = browser()
    status, login_url, login_page = request(opener, f"{base}/web/login?db=business")
    if status != 200:
        fail(f"Odoo login page failed: HTTP {status} at {login_url}")

    links = Links()
    links.feed(login_page)
    provider_url = next(
        (
            urllib.parse.urljoin(login_url, href)
            for href in links.hrefs
            if "id.keplerops.lab" in href
            and "/protocol/openid-connect/auth" in href
        ),
        None,
    )
    if not provider_url:
        fail("Odoo login page did not expose the KeplerOps OIDC provider")

    query = urllib.parse.parse_qs(urllib.parse.urlsplit(provider_url).query)
    required = {
        "client_id": ["odoo"],
        "response_type": ["code"],
        "code_challenge_method": ["S256"],
        "redirect_uri": [f"{base}/auth_oauth/signin"],
    }
    for key, expected in required.items():
        if query.get(key) != expected:
            fail(
                f"Odoo OIDC request had invalid {key}: "
                f"expected {expected!r}, got {query.get(key)!r}"
            )
    challenge = query.get("code_challenge", [""])[0]
    if len(challenge) < 43:
        fail("Odoo OIDC request did not include a viable PKCE challenge")

    status, keycloak_url, keycloak_page = request(opener, provider_url)
    if status != 200 or "id.keplerops.lab" not in keycloak_url:
        fail(f"Odoo OIDC did not reach Keycloak: HTTP {status} at {keycloak_url}")
    status, final_url, final_page = submit_keycloak_credentials(
        opener, keycloak_url, keycloak_page, username, password
    )
    if (
        status != 200
        or urllib.parse.urlsplit(final_url).hostname != "business.keplerops.lab"
        or "oauth_error=" in final_url
        or "Access Denied" in final_page
    ):
        fail(f"Odoo OIDC login failed for {username}: HTTP {status} at {final_url}")

    status, url, rpc = json_call(
        opener,
        f"{base}/web/session/get_session_info",
        {"jsonrpc": "2.0", "method": "call", "params": {}, "id": 1},
        origin=base,
        referer=final_url,
    )
    if status != 200 or rpc.get("error"):
        fail(f"Odoo session lookup failed for {username}: HTTP {status} at {url}")
    session = rpc.get("result")
    if not isinstance(session, dict) or session.get("username") != username:
        actual_username = (
            session.get("username") if isinstance(session, dict) else None
        )
        fail(
            f"Odoo session identity mismatch for {username}: "
            f"{actual_username!r}"
        )
    return opener, session


def odoo_access(
    opener: urllib.request.OpenerDirector,
    model: str,
    operation: str,
    request_id: int,
) -> bool:
    base = "https://business.keplerops.lab"
    status, url, rpc = json_call(
        opener,
        f"{base}/web/dataset/call_kw/{model}/check_access_rights",
        {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": model,
                "method": "check_access_rights",
                "args": [operation],
                "kwargs": {"raise_exception": False},
            },
            "id": request_id,
        },
        origin=base,
        referer=f"{base}/odoo",
    )
    if status != 200 or rpc.get("error"):
        fail(
            f"Odoo browser access probe failed for {operation}: "
            f"HTTP {status} at {url}; error={rpc.get('error')!r}"
        )
    result = rpc.get("result")
    if not isinstance(result, bool):
        fail(f"Odoo browser access probe returned a non-boolean for {operation}")
    return result


def assert_odoo() -> None:
    finance, _ = odoo_login(
        "finance.operator", "KeplerV2-Training-Finance"
    )
    auditor, _ = odoo_login(
        "security.auditor", "KeplerV2-Training-Auditor"
    )

    finance_access = {
        operation: odoo_access(finance, "account.move", operation, index)
        for index, operation in enumerate(("read", "write", "create", "unlink"), 10)
    }
    auditor_access = {
        operation: odoo_access(auditor, "account.move", operation, index)
        for index, operation in enumerate(("read", "write", "create", "unlink"), 20)
    }
    if finance_access != {
        "read": True,
        "write": True,
        "create": True,
        "unlink": True,
    }:
        fail(f"Odoo Finance Operator boundary was wrong: {finance_access!r}")
    if auditor_access != {
        "read": True,
        "write": False,
        "create": False,
        "unlink": False,
    }:
        fail(f"Odoo Finance Auditor boundary was wrong: {auditor_access!r}")
    if odoo_access(finance, "ir.config_parameter", "write", 30):
        fail("Odoo Finance Operator escaped into system configuration")
    if odoo_access(auditor, "ir.config_parameter", "write", 31):
        fail("Odoo Finance Auditor escaped into system configuration")
    print("PASS Odoo OIDC/PKCE preserves native Finance Operator and Auditor boundaries")


if not ssl.create_default_context(cafile=RANGE_CA).get_ca_certs():
    fail(f"participant range CA is invalid or empty: {RANGE_CA}")

assert_ghost()
assert_mautic()
assert_odoo()
PY

printf 'business role-enforcement acceptance passed from the participant network\n'
