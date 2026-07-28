"""Offline reset entrypoint for the durable model state mount."""

from __future__ import annotations

import argparse
from pathlib import Path

from app import PlatformML


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", type=Path, required=True)
    args = parser.parse_args()
    platform = PlatformML(args.state_root)
    inventory = platform.retrain(reset_events=True)
    print(inventory["model_set_digest"])


if __name__ == "__main__":
    main()
