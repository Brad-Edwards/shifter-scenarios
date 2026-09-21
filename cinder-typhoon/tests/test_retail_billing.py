"""Pytest wrapper for the retail billing content validator."""
from pathlib import Path

import yaml
from validate_retail_billing import check_retail_billing


def test_retail_billing_content():
    root = Path(__file__).resolve().parents[1] / "assets/narrative"
    author = root / "authoring"
    check_retail_billing(
        root,
        yaml.safe_load((author / "workforce.yaml").read_text())["employees"],
        yaml.safe_load((author / "people.yaml").read_text()),
        yaml.safe_load((author / "mail-retail-billing.yaml").read_text())["messages"],
        yaml.safe_load((author / "documents-retail-billing.yaml").read_text())["documents"],
    )
