#!/usr/bin/env python3
"""Launch the pinned client using guest-local, rotating broker access only."""

from __future__ import annotations

import json
import os
import pwd
import sys
from pathlib import Path

VERSION = "2.1.108"
PACKAGE = Path("/usr/local/lib/node_modules/@anthropic-ai/claude-code")
CONFIG = Path("/opt/polaris/model-client")


def launch_command(config: dict, arguments: list[str], environment: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    env = {
        key: value
        for key, value in environment.items()
        if not key.startswith(("AWS_", "GOOGLE_", "GCLOUD_", "ANTHROPIC_", "CLAUDE_"))
        and key not in {"NODE_OPTIONS", "NODE_EXTRA_CA_CERTS", "NODE_TLS_REJECT_UNAUTHORIZED"}
        and not key.lower().endswith("_proxy")
    }
    env.update(
        {
            "ANTHROPIC_BASE_URL": config["broker_url"],
            "ANTHROPIC_MODEL": config["main_model"],
            "ANTHROPIC_SMALL_FAST_MODEL": config["small_model"],
            "ANTHROPIC_DEFAULT_SONNET_MODEL": config["main_model"],
            "ANTHROPIC_DEFAULT_OPUS_MODEL": config["main_model"],
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": config["small_model"],
            "NODE_EXTRA_CA_CERTS": str(CONFIG / "ca.pem"),
            # Keep Claude's mutable first-run state out of the baked home and
            # match the isolated config directory used by the wire test.
            "CLAUDE_CONFIG_DIR": "/tmp/polaris-claude-config",
            "CLAUDE_CODE_API_KEY_HELPER_TTL_MS": "1000",
            "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_NON_ESSENTIAL_MODEL_CALLS": "1",
            "CLAUDE_CODE_EFFORT_LEVEL": "unset",
            "DISABLE_INTERLEAVED_THINKING": "1",
            "DISABLE_PROMPT_CACHING": "1",
            "MAX_THINKING_TOKENS": "0",
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(config["max_output_tokens"]),
        }
    )
    return [
        "/usr/bin/node",
        "--require",
        str(CONFIG / "client-compat.cjs"),
        str(PACKAGE / "cli.js"),
        "--settings",
        str(CONFIG / "settings.json"),
        *arguments,
    ], env


def main() -> int:
    try:
        if json.loads((PACKAGE / "package.json").read_text())["version"] != VERSION:
            raise ValueError
        config = json.loads((CONFIG / "client.json").read_text())
        environment = dict(os.environ)
        environment["HOME"] = pwd.getpwuid(os.geteuid()).pw_dir
        argv, env = launch_command(config, sys.argv[1:], environment)
        os.execve(argv[0], argv, env)
    except Exception:
        print("Model client unavailable", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
