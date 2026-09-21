"""Pytest wrapper for the laboratory and quality content validator."""
from pathlib import Path

import yaml

from validate_laboratory_quality import check_laboratory_quality


def test_laboratory_quality_content():
    root = Path(__file__).resolve().parents[1] / "assets/narrative"
    author = root / "authoring"
    check_laboratory_quality(
        root,
        yaml.safe_load((author / "workforce.yaml").read_text())["employees"],
        yaml.safe_load((author / "mail-laboratory-quality.yaml").read_text())["messages"],
        yaml.safe_load((author / "documents-laboratory-quality.yaml").read_text())["documents"],
        yaml.safe_load((author / "calendars-laboratory-quality.yaml").read_text())["events"],
    )
