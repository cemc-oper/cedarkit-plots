"""Load only the new workflow schema; no migration or implicit version routing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .schema import Recipe


class RecipeLoadError(ValueError):
    pass


class _UniqueKeysLoader(yaml.SafeLoader):
    pass


def _mapping(loader: _UniqueKeysLoader, node: yaml.MappingNode) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str):
            raise RecipeLoadError(f"YAML mapping key must be a string at line {key_node.start_mark.line + 1}")
        if key in result:
            raise RecipeLoadError(f"duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_UniqueKeysLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


@dataclass(frozen=True)
class LoadedRecipe:
    recipe: Recipe
    origin: str


def load_recipe(source: str | Path | dict[str, Any], *, origin: str | None = None) -> LoadedRecipe:
    """Validate a v3 mapping, YAML text, or existing path without reading data fields."""
    if isinstance(source, dict):
        raw, source_origin = source, origin or "<memory>"
    else:
        source_text = str(source)
        source_origin = origin or "<stdin>"
        try:
            is_path = isinstance(source, Path) or ("\n" not in source_text and "\r" not in source_text and Path(source_text).is_file())
        except OSError:
            is_path = False
        if is_path:
            source_origin = str(source)
            try:
                source_text = Path(source).read_text(encoding="utf-8")
            except OSError as exc:
                raise RecipeLoadError(f"{source_origin}: cannot read recipe: {exc}") from exc
        try:
            raw = yaml.load(source_text, Loader=_UniqueKeysLoader)
        except yaml.YAMLError as exc:
            raise RecipeLoadError(f"{source_origin}: invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise RecipeLoadError(f"{source_origin}: recipe must be a mapping")
    if raw.get("api_version") != "cedarkit.plots/v3":
        raise RecipeLoadError(f"{source_origin}: unsupported api_version {raw.get('api_version')!r}; expected 'cedarkit.plots/v3'")
    try:
        return LoadedRecipe(Recipe.model_validate(raw), source_origin)
    except ValidationError as exc:
        raise RecipeLoadError(f"{source_origin}: recipe validation failed: {exc}") from exc
