#!/usr/bin/env python3
"""Generate per-range credential seeds for the KeplerOps phase.

Derives all per-range values from a single seed string using HMAC-SHA256 so
that each range is internally consistent but credentials captured from one
range cannot be replayed on another.

Usage:
    python3 provision-seed.py --seed SEED_STRING [--output-dir DIR]

The seed string must be unique per range. The recommended format is:
    cinder-keplerops-RANGEID-YYYY-MM-DD

Output files (written to --output-dir, default: the assets/opening/k-support/
and assets/opening/k-dev/ directories relative to this script):
    support-service.json    Updated with seed-derived session IDs
    seed-manifest.json      Operator-only record of derived values (not shipped)

Do not ship seed-manifest.json to participants.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_SUPPORT_CONFIG = REPO / "cinder-typhoon" / "assets" / "keplerops" / "opening" / "k-support" / "support-service.json"
DEFAULT_OUTPUT = REPO / "cinder-typhoon" / "assets" / "keplerops" / "opening" / "k-support"


def derive(seed: str, purpose: str, length: int = 8) -> str:
    """Derive a short identifier from the seed for a named purpose."""
    key = seed.encode()
    msg = purpose.encode()
    digest = hmac.new(key, msg, hashlib.sha256).hexdigest()
    # Use URL-safe characters from the digest for session-style identifiers.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
    result = []
    for i in range(0, length * 2, 2):
        result.append(alphabet[int(digest[i:i+2], 16) % len(alphabet)])
    return "".join(result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True, help="Unique seed string for this range")
    parser.add_argument("--output-dir", type=pathlib.Path, default=DEFAULT_OUTPUT,
                        help="Directory to write updated support-service.json")
    parser.add_argument("--support-config", type=pathlib.Path, default=DEFAULT_SUPPORT_CONFIG,
                        help="Input support-service.json to update")
    args = parser.parse_args()

    if len(args.seed) < 8:
        print("error: seed must be at least 8 characters", file=sys.stderr)
        return 2

    # Derive per-range credential values.
    rowan_suffix = derive(args.seed, "keplerops.support.rowan-session")
    talia_suffix = derive(args.seed, "keplerops.support.talia-session")
    git_secret = hmac.new(args.seed.encode(), b"keplerops.git.rowan-secret", hashlib.sha256).hexdigest()[:24]

    rowan_session_id = f"ksess_rowan_2841_{rowan_suffix}"
    talia_session_id = f"ksess_talia_review_{talia_suffix}"

    # Update support-service.json.
    config = json.loads(args.support_config.read_text())
    config["reviewer_session_id"] = talia_session_id
    if config.get("sessions"):
        config["sessions"][0]["session_id"] = rowan_session_id
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_config = args.output_dir / "support-service.json"
    out_config.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")

    # Write operator-only seed manifest.
    manifest = {
        "schema": "fieldkest.seed-manifest/v1",
        "seed": args.seed,
        "derived": {
            "support.rowan_session_id": rowan_session_id,
            "support.talia_session_id": talia_session_id,
            "git.rowan_secret": git_secret,
        },
        "note": "Operator-only. Do not ship to participants or embed in range images.",
    }
    manifest_path = args.output_dir / "seed-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    print(f"Wrote {out_config}")
    print(f"Wrote {manifest_path} (operator-only, do not ship)")
    print(f"  support.rowan_session_id: {rowan_session_id}")
    print(f"  support.talia_session_id: {talia_session_id}")
    print(f"  git.rowan_secret: {git_secret[:8]}... (use to rebuild opening archive)")
    print("Run build_archives.py after updating k-dev/git-credentials with the new secret.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
