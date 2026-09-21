"""Pytest wrapper for the purchasing and stores content validator."""
from pathlib import Path

import yaml

from validate_purchasing_stores import check_purchasing_stores


def test_purchasing_stores_content():
    root = Path(__file__).resolve().parents[1] / "assets/narrative"
    author = root / "authoring"
    check_purchasing_stores(
        root,
        yaml.safe_load((author / "workforce.yaml").read_text())["employees"],
        yaml.safe_load((author / "people.yaml").read_text()),
        yaml.safe_load((author / "mail-purchasing-stores.yaml").read_text())["messages"],
        yaml.safe_load((author / "documents-purchasing-stores.yaml").read_text())["documents"],
    )
