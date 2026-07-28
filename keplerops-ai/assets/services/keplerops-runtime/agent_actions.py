"""Pure source-binding rules for loopback agent actions."""

from __future__ import annotations

import re
from urllib.parse import urlparse


PACKAGE_PATH = "/git/api/packages/ml.engineer/generic/keplerops-maintainer/1.0.0/keplerops-maintainer.sh"
WORKHUB_HOST = "repo-ticket-01.keplerops.lab"
CLICK_HOST = "inference-gateway.keplerops.lab"
PACKAGE_URL = f"https://{WORKHUB_HOST}{PACKAGE_PATH}"
CLICK_PATH = re.compile(r"^/public/agent-click/(click-[0-9a-f]{24})$")
WEB_DELIVERY_PATH = re.compile(
    r"^/public/evasion/deliveries/(wex-[0-9a-f]{24})$"
)


def package_url_allowed(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname == WORKHUB_HOST
        and parsed.port is None
        and parsed.path == PACKAGE_PATH
        and not parsed.query
        and not parsed.fragment
    )


def click_trap_id(value: str) -> str | None:
    """Return the canonical trap identifier for the sole allowed click route."""

    parsed = urlparse(value)
    match = CLICK_PATH.fullmatch(parsed.path)
    if (
        parsed.scheme != "https"
        or parsed.hostname != CLICK_HOST
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
        or match is None
    ):
        return None
    return match.group(1)


def click_url_allowed(value: str) -> bool:
    return click_trap_id(value) is not None


def web_delivery_id(value: str) -> str | None:
    """Return the canonical range-local web-delivery identifier."""

    parsed = urlparse(value)
    match = WEB_DELIVERY_PATH.fullmatch(parsed.path)
    if (
        parsed.scheme != "https"
        or parsed.hostname != CLICK_HOST
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
        or match is None
    ):
        return None
    return match.group(1)


__all__ = [
    "PACKAGE_URL",
    "click_trap_id",
    "click_url_allowed",
    "package_url_allowed",
    "web_delivery_id",
]
