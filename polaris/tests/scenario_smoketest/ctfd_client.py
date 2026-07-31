"""Pack-local access to the hardened CTFd REST client.

The optional smoketest readback and the reference loader intentionally share
one network/auth implementation so HTTPS, redirect, response-bound, and
redacted-error policy cannot drift between them.
"""

from __future__ import annotations

import sys
from pathlib import Path


_PACK_ROOT = Path(__file__).resolve().parents[2]
if str(_PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACK_ROOT))

from ctfd.common import CtfdClient  # noqa: E402


__all__ = ["CtfdClient"]
