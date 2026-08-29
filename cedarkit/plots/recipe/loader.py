"""Safe version routing for recipe documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .migrate import MigrationIssue, migrate_recipe
from .schema_v2 import RecipeV2


class RecipeLoadError(ValueError):
    pass


class UnsupportedRecipeVersionError(RecipeLoadError):
    def __init__(self, path: str, received: object, supported: tuple[str, ...] = ("cedarkit.plots/v2",)):
        self.path, self.received, self.supported = path, received, supported
        super().__init__(f"{path}: unsupported recipe api_version {received!r}; supported: {', '.join(supported)}")


@dataclass(frozen=True)
class LoadedRecipe:
    recipe: RecipeV2
    origin: str
    source_version: int
    issues: tuple[MigrationIssue, ...] = ()


def _parse(text: str, origin: str) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f" line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise RecipeLoadError(f"{origin}: invalid YAML{location}: {exc}") from exc
    if not isinstance(raw, dict):
        raise RecipeLoadError(f"{origin}: recipe document must be a YAML mapping")
    return raw


def load_recipe(source: str | Path | dict[str, Any], *, origin: str | None = None,
                name: str | None = None) -> LoadedRecipe:
    """Load either a file, YAML text, or parsed mapping through one entry point."""
    if isinstance(source, dict):
        raw, source_origin = source, origin or "<memory>"
    else:
        path = Path(source)
        if path.exists():
            source_origin = str(path)
            try:
                raw = _parse(path.read_text(encoding="utf-8"), source_origin)
            except OSError as exc:
                raise RecipeLoadError(f"{source_origin}: cannot read file: {exc}") from exc
        else:
            source_origin = origin or "<stdin>"
            raw = _parse(str(source), source_origin)
    has_version, has_kind = "api_version" in raw, "kind" in raw
    if has_version != has_kind:
        raise RecipeLoadError(f"{source_origin}: partial v2 envelope requires api_version and kind")
    try:
        if has_version:
            if raw["api_version"] != "cedarkit.plots/v2":
                raise UnsupportedRecipeVersionError(source_origin, raw["api_version"])
            if raw["kind"] != "PlotRecipe":
                raise RecipeLoadError(f"{source_origin}: invalid recipe kind {raw['kind']!r}")
            return LoadedRecipe(RecipeV2.model_validate(raw), source_origin, 2)
        result = migrate_recipe(raw, origin=source_origin, name=name)
        return LoadedRecipe(result.recipe, source_origin, 1, result.issues)
    except ValidationError as exc:
        raise RecipeLoadError(f"{source_origin}: recipe validation failed: {exc}") from exc
