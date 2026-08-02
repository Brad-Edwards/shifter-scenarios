#!/usr/bin/env bash
set -Eeuo pipefail

readonly WORKSTATION=keplerops-participant-workstation-runtime

if [[ $(docker inspect --format '{{.State.Running}}' "$WORKSTATION" 2>/dev/null) != true ]]; then
  printf 'participant workstation is not running: %s\n' "$WORKSTATION" >&2
  exit 1
fi

docker exec --interactive \
  --user kasm-user \
  --env HOME=/home/kasm-user \
  "$WORKSTATION" python3 - <<'PY'
from __future__ import annotations

import html
import http.cookiejar
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser


RANGE_CA = "/usr/local/share/ca-certificates/keplerops-range-root.crt"


class Form(HTMLParser):
    def __init__(self, *, form_id: str | None = None, action_suffix: str | None = None) -> None:
        super().__init__()
        self.form_id = form_id
        self.action_suffix = action_suffix
        self.action: str | None = None
        self.fields: dict[str, str] = {}
        self._selected = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = dict(attrs)
        if tag == "form" and self.action is None:
            action = values.get("action") or ""
            matches_id = self.form_id is None or values.get("id") == self.form_id
            matches_action = self.action_suffix is None or action.endswith(self.action_suffix)
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


class Meta(HTMLParser):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.content: str | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = dict(attrs)
        if tag == "meta" and values.get("name") == self.name:
            self.content = values.get("content")


def browser() -> urllib.request.OpenerDirector:
    cookies = http.cookiejar.CookieJar()
    context = ssl.create_default_context(cafile=RANGE_CA)
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookies),
        urllib.request.HTTPSHandler(context=context),
    )


def read(
    opener: urllib.request.OpenerDirector,
    request: str | urllib.request.Request,
) -> tuple[int, str, str]:
    try:
        with opener.open(request, timeout=60) as response:
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


def oidc_login(
    start_url: str, username: str, password: str
) -> tuple[urllib.request.OpenerDirector, int, str, str]:
    opener = browser()
    status, login_url, login_page = read(opener, start_url)
    if status != 200:
        raise RuntimeError(f"OIDC login did not reach Keycloak: HTTP {status} at {login_url}")

    form = Form(form_id="kc-form-login")
    form.feed(login_page)
    if not form.action:
        raise RuntimeError(f"Keycloak login form was not present at {login_url}")

    action = urllib.parse.urljoin(login_url, html.unescape(form.action))
    body = urllib.parse.urlencode(
        {"username": username, "password": password, "credentialId": ""}
    ).encode()
    request = urllib.request.Request(
        action,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    status, url, body = read(opener, request)
    return opener, status, url, body


def zammad_saml_login(
    username: str, password: str
) -> tuple[urllib.request.OpenerDirector, int, str, str]:
    opener = browser()
    status, base_url, page = read(opener, "https://support.keplerops.lab")
    if status != 200:
        raise RuntimeError(f"Zammad login page failed: HTTP {status} at {base_url}")
    token = Meta("csrf-token")
    token.feed(page)
    if not token.content:
        raise RuntimeError("Zammad login page did not publish its CSRF token")
    request = urllib.request.Request(
        "https://support.keplerops.lab/auth/saml",
        data=urllib.parse.urlencode({"authenticity_token": token.content}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    status, login_url, login_page = read(opener, request)
    if status != 200:
        raise RuntimeError(f"Zammad SAML did not reach Keycloak: HTTP {status} at {login_url}")
    form = Form(form_id="kc-form-login")
    form.feed(login_page)
    if not form.action:
        raise RuntimeError(f"Keycloak SAML login form was not present at {login_url}")
    request = urllib.request.Request(
        urllib.parse.urljoin(login_url, html.unescape(form.action)),
        data=urllib.parse.urlencode(
            {"username": username, "password": password, "credentialId": ""}
        ).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    status, url, body = read(opener, request)
    return opener, status, url, body


def redmine_login(username: str, password: str) -> tuple[int, str, str]:
    opener = browser()
    status, login_url, login_page = read(opener, "https://workhub.keplerops.lab/login")
    if status != 200:
        raise RuntimeError(f"Redmine login page failed: HTTP {status} at {login_url}")

    form = Form(action_suffix="/login")
    form.feed(login_page)
    if not form.action:
        raise RuntimeError("Redmine login form was not present")
    fields = dict(form.fields)
    fields.update({"username": username, "password": password, "login": "Login"})
    request = urllib.request.Request(
        urllib.parse.urljoin(login_url, html.unescape(form.action)),
        data=urllib.parse.urlencode(fields).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return read(opener, request)


_, status, url, body = oidc_login(
    "https://notebooks.keplerops.lab/hub/oauth_login?next=%2Fhub%2Fhome",
    "ml.engineer",
    "KeplerV2-Training-MLEngineer",
)
if status != 200 or "notebooks.keplerops.lab/hub/" not in url:
    raise RuntimeError(f"allowed evaluator failed JupyterHub login: HTTP {status} at {url}")
if "Log in to continue" in body or "Forbidden" in body:
    raise RuntimeError("allowed evaluator remained at a JupyterHub login or denial page")
print("PASS ml.engineer entered JupyterHub through Keycloak")

_, status, url, body = oidc_login(
    "https://notebooks.keplerops.lab/hub/oauth_login?next=%2Fhub%2Fhome",
    "data.annotator",
    "KeplerV2-Training-Annotator",
)
if status != 403 or ("not allowed" not in body.lower() and "forbidden" not in body.lower()):
    raise RuntimeError(f"adjacent role was not denied by JupyterHub: HTTP {status} at {url}")
print("PASS data.annotator authenticated but was denied JupyterHub")

_, status, url, body = oidc_login(
    "https://git.keplerops.lab/user/oauth2/keplerops",
    "ml.engineer",
    "KeplerV2-Training-MLEngineer",
)
if status != 200 or "git.keplerops.lab" not in url or "ml.engineer" not in body:
    raise RuntimeError(f"allowed researcher failed Forgejo OIDC login: HTTP {status} at {url}")
print("PASS ml.engineer entered Forgejo through Keycloak")

_, status, url, body = oidc_login(
    "https://git.keplerops.lab/user/oauth2/keplerops",
    "data.annotator",
    "KeplerV2-Training-Annotator",
)
if (
    status < 400
    and "required claim" not in body.lower()
    and "access denied" not in body.lower()
    and "account is suspended" not in body.lower()
):
    title_start = body.lower().find("<title>")
    title_end = body.lower().find("</title>", title_start)
    title = body[title_start + 7 : title_end].strip() if title_start >= 0 else "missing title"
    raise RuntimeError(
        f"adjacent role was not denied by Forgejo: HTTP {status} at {url}; title={title!r}"
    )
print("PASS data.annotator authenticated but was denied Forgejo")

status, url, body = redmine_login("ml.engineer", "KeplerV2-Training-MLEngineer")
if status != 200 or url.endswith("/login") or "Logged in as" not in body:
    raise RuntimeError(f"allowed researcher failed Redmine AD login: HTTP {status} at {url}")
print("PASS ml.engineer entered Redmine with Active Directory credentials")

status, url, body = redmine_login("support.analyst", "KeplerV2-Training-Support")
if status != 200 or not url.endswith("/login") or "Invalid user or password" not in body:
    raise RuntimeError(f"adjacent role was not denied by Redmine LDAP filter: HTTP {status} at {url}")
print("PASS support.analyst was denied Redmine by its directory resource boundary")

_, status, url, body = oidc_login(
    "https://files.keplerops.lab/apps/user_oidc/login/1",
    "reviewer",
    "KeplerV2-Training-Reviewer",
)
if (
    status != 200
    or "files.keplerops.lab" not in url
    or "Log in" in body
    or "Code login error" in body
    or "invalid_scope" in body
):
    raise RuntimeError(f"allowed reviewer failed Nextcloud OIDC login: HTTP {status} at {url}")
print("PASS reviewer entered Nextcloud through Keycloak")

_, status, url, body = oidc_login(
    "https://files.keplerops.lab/apps/user_oidc/login/1",
    "release.engineer",
    "KeplerV2-Training-Release",
)
if status < 400 and "not allowed" not in body.lower() and "error" not in body.lower():
    raise RuntimeError(f"adjacent role was not denied by Nextcloud: HTTP {status} at {url}")
print("PASS release.engineer was denied by the Nextcloud Orion group boundary")

_, status, url, body = oidc_login(
    "https://airflow.keplerops.lab/auth/login/keycloak",
    "ml.engineer",
    "KeplerV2-Training-MLEngineer",
)
if status != 200 or "airflow.keplerops.lab" not in url or "ml.engineer" not in body:
    raise RuntimeError(f"allowed runner failed Airflow OIDC login: HTTP {status} at {url}")
print("PASS ml.engineer entered Airflow through Keycloak")

_, status, url, body = oidc_login(
    "https://airflow.keplerops.lab/auth/login/keycloak",
    "data.annotator",
    "KeplerV2-Training-Annotator",
)
if status < 400 and "invalid login" not in body.lower() and "access denied" not in body.lower():
    raise RuntimeError(f"adjacent role was not denied by Airflow: HTTP {status} at {url}")
print("PASS data.annotator authenticated but was denied Airflow")

grafana, status, url, body = oidc_login(
    "https://grafana.keplerops.lab/login/generic_oauth",
    "platform.operator",
    "KeplerV2-Training-Platform",
)
if status != 200 or "grafana.keplerops.lab" not in url:
    raise RuntimeError(f"platform operator failed Grafana OIDC login: HTTP {status} at {url}")
status, url, body = read(grafana, "https://grafana.keplerops.lab/api/user/orgs")
organizations = json.loads(body) if status == 200 else []
if not any(org.get("role") == "Editor" for org in organizations):
    raise RuntimeError(
        f"Grafana did not assign native Editor role: HTTP {status} at {url}; "
        f"response={body[:500]!r}"
    )
print("PASS platform.operator received Grafana Editor through strict group mapping")

_, status, url, body = oidc_login(
    "https://grafana.keplerops.lab/login/generic_oauth",
    "ml.engineer",
    "KeplerV2-Training-MLEngineer",
)
if status < 400 and "role" not in body.lower() and "access denied" not in body.lower():
    raise RuntimeError(f"unmapped role was not denied by Grafana: HTTP {status} at {url}")
print("PASS ml.engineer was denied by Grafana strict role mapping")

harbor, status, url, body = oidc_login(
    "https://registry.keplerops.lab/c/oidc/login",
    "reviewer",
    "KeplerV2-Training-Reviewer",
)
if status != 200 or "registry.keplerops.lab" not in url:
    raise RuntimeError(f"reviewer failed Harbor OIDC login: HTTP {status} at {url}")
status, url, body = read(harbor, "https://registry.keplerops.lab/api/v2.0/projects/orion-build")
if status != 200 or json.loads(body).get("name") != "orion-build":
    raise RuntimeError(f"Harbor reviewer could not read private Orion project: HTTP {status} at {url}")
print("PASS reviewer received Harbor Guest on the private Orion project")

harbor, status, url, body = oidc_login(
    "https://registry.keplerops.lab/c/oidc/login",
    "data.annotator",
    "KeplerV2-Training-Annotator",
)
if status != 200 or "registry.keplerops.lab" not in url:
    raise RuntimeError(f"adjacent user failed Harbor OIDC authentication: HTTP {status} at {url}")
status, url, body = read(harbor, "https://registry.keplerops.lab/api/v2.0/projects/orion-build")
if status not in (403, 404):
    raise RuntimeError(f"adjacent role accessed private Harbor project: HTTP {status} at {url}")
print("PASS data.annotator authenticated to Harbor but could not read the private Orion project")

zammad, status, url, body = zammad_saml_login(
    "support.analyst", "KeplerV2-Training-Support"
)
if status != 200 or "support.keplerops.lab" not in url:
    raise RuntimeError(f"support analyst failed Zammad SAML login: HTTP {status} at {url}")
status, url, body = read(zammad, "https://support.keplerops.lab/api/v1/tickets")
if status != 200 or not body.lstrip().startswith("["):
    raise RuntimeError(f"Zammad agent could not list tickets: HTTP {status} at {url}")
print("PASS support.analyst entered Zammad through SAML with native Agent access")

zammad, status, url, body = zammad_saml_login(
    "comms.publisher", "KeplerV2-Training-Comms"
)
if status != 200 or "support.keplerops.lab" not in url:
    raise RuntimeError(f"communications user failed Zammad SAML login: HTTP {status} at {url}")
status, url, body = read(zammad, "https://support.keplerops.lab/api/v1/tickets")
if status != 403:
    raise RuntimeError(f"Zammad customer accessed agent ticket listing: HTTP {status} at {url}")
print("PASS comms.publisher authenticated to Zammad but was denied agent ticket access")
PY

printf 'identity role-enforcement acceptance passed from the participant network\n'
