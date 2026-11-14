"""Fixed, read-only operating history on the existing corporate HTTPS bridge."""
from __future__ import annotations

import base64
import binascii
import hmac
import json
import logging
import os
import pathlib
import subprocess

PATH = "/api/operating-history"
IDENTITY = pathlib.Path("/tmp/ot-operating-reader.json")
LOG = logging.getLogger(__name__)
QUERY = """SELECT json_build_object(
 'schema','arwc.operating-history/v1',
 'read_at',clock_timestamp(),
 'samples',coalesce(json_agg(samples), '[]'::json))
FROM (
 SELECT asset,source_time,collected_time,ingested_at,tag,value,unit,process_quality,origin
 FROM public.dmz_process_history
 WHERE source_time >= statement_timestamp()-interval '5 minutes'
 ORDER BY source_time DESC,tag LIMIT 900
) samples"""


def authorized(header: str, identity: dict[str, str]) -> bool:
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "basic":
        return False
    try:
        supplied = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        return False
    expected = (identity["username"] + ":" + identity["password"]).encode()
    return hmac.compare_digest(supplied, expected)


def respond(handler) -> None:
    try:
        identity = json.loads(IDENTITY.read_text())
    except (OSError, ValueError):
        handler.send_json(503, {"error": "operating history is not configured"})
        return
    if not authorized(handler.headers.get("Authorization", ""), identity):
        handler.send_response(401)
        handler.send_header("WWW-Authenticate", 'Basic realm="ARWC operating history", charset="UTF-8"')
        handler.send_header("Content-Length", "0")
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        return
    environment = dict(os.environ, PGSERVICE="arwc-operating-history",
                       PGSERVICEFILE="/tmp/ot-pg-service.conf", PGPASSFILE="/tmp/ot-pgpass",
                       PGCONNECT_TIMEOUT="3", PGOPTIONS="-c default_transaction_read_only=on -c statement_timeout=2000")
    try:
        result = subprocess.run(["psql", "--no-psqlrc", "--tuples-only", "--no-align", "--quiet",
            "--set", "ON_ERROR_STOP=1", "--command", QUERY],
            env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=5, check=True)
        payload = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        LOG.error("Operating history query unavailable: type=%s returncode=%s errno=%s",
                  type(error).__name__, getattr(error, "returncode", None), getattr(error, "errno", None))
        handler.send_json(503, {"error": "operating history unavailable"})
        return
    handler.send_json(200, payload)
