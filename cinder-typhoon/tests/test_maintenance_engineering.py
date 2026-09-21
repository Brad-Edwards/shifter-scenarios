"""Pytest wrapper for the maintenance and engineering content validator."""
from pathlib import Path

import yaml

from validate_maintenance_engineering import check_maintenance_engineering


def test_maintenance_engineering_content():
    root = Path(__file__).resolve().parents[1] / "assets/narrative"
    author = root / "authoring"
    check_maintenance_engineering(
        root,
        yaml.safe_load((author / "workforce.yaml").read_text())["employees"],
        yaml.safe_load((author / "mail-maintenance-engineering.yaml").read_text())["messages"],
        yaml.safe_load((author / "documents-maintenance-engineering.yaml").read_text())["documents"],
        yaml.safe_load((author / "calendars-maintenance-engineering.yaml").read_text())["events"],
    )
