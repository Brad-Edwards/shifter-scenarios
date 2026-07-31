"""Deterministically reset durable context adapter state."""

from __future__ import annotations

import argparse
from pathlib import Path

from store import StateStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", type=Path, required=True)
    args = parser.parse_args()
    store = StateStore(args.state_root)
    store.reset()
    print('{"cursor":0,"event_count":0,"status":"reset"}')


if __name__ == "__main__":
    main()
