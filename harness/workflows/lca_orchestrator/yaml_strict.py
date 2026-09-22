"""Strict YAML helpers: SafeLoader with duplicate-key rejection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class _DuplicateKeySafeLoader(yaml.SafeLoader):
    pass


def _construct_mapping_no_duplicates(
    loader: yaml.SafeLoader, node: yaml.nodes.MappingNode, deep: bool = False
) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            mark = getattr(key_node, "start_mark", None)
            where = ""
            if mark is not None and getattr(mark, "name", None):
                where = f" in {mark.name}"
            raise ValueError(f"duplicate YAML mapping key {key!r}{where}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_DuplicateKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_no_duplicates,
)


def load_yaml_strict(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    try:
        return yaml.load(text, Loader=_DuplicateKeySafeLoader)
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: invalid YAML: {exc}") from exc
