"""Bounded, duplicate-key-safe readers for Polaris pack contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


MAX_SOURCE_BYTES = 2 * 1024 * 1024


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects ambiguous duplicate mapping keys."""


def _construct_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError("contract source contains a duplicate key")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load one contained contract source without following its final symlink."""

    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError("contract source must be a regular file")
    if source.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("contract source exceeds the bounded read limit")
    with source.open(encoding="utf-8") as handle:
        data = yaml.load(handle, Loader=UniqueKeyLoader)
    if not isinstance(data, dict):
        raise ValueError("contract source root must be a mapping")
    return data


__all__ = ["MAX_SOURCE_BYTES", "load_yaml"]
