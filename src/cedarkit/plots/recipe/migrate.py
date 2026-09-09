"""Pure v1-to-v2 normalization and stable YAML serialization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .schema_v2 import RecipeV2


@dataclass(frozen=True)
class MigrationIssue:
    code: str
    message: str
    path: str = ""
    severity: str = "warning"


@dataclass(frozen=True)
class MigrationResult:
    recipe: RecipeV2
    issues: tuple[MigrationIssue, ...] = ()
    migrated: bool = True


def _identity(origin: str | Path | None, name: str | None) -> tuple[str, list[MigrationIssue]]:
    if name:
        return name, []
    if origin and str(origin) not in {"<memory>", "<stdin>"}:
        stem = Path(origin).with_suffix("").as_posix().replace("/", ".")
        parts = [part for part in stem.split(".") if part and part not in {"recipe", "recipes", "cedar_graph", "cedar-graph"}]
        candidate = ".".join(parts[-3:])
        if candidate and all(part.replace("-", "a").replace("_", "a").isalnum() for part in candidate.split(".")):
            return candidate.lower(), []
    return "migration.unresolved", [MigrationIssue("unresolved_identity", "no stable identity; supply --name")]


def _template(value: Any) -> Any:
    if isinstance(value, str):
        # v1 accepted {interval}; preserve explicit modern namespaces.
        import re
        return re.sub(r"\{([A-Za-z][A-Za-z0-9_-]*)\}", r"{params.\1}", value)
    if isinstance(value, list):
        return [_template(item) for item in value]
    if isinstance(value, dict):
        return {key: _template(item) for key, item in value.items()}
    return value


def migrate_recipe(raw: dict[str, Any] | RecipeV2, *, origin: str | Path | None = None,
                   name: str | None = None) -> MigrationResult:
    """Normalize a parsed v1 document to v2 without I/O or registry access."""
    if isinstance(raw, RecipeV2):
        return MigrationResult(raw, migrated=False)
    if raw.get("api_version") == "cedarkit.plots/v2":
        return MigrationResult(RecipeV2.model_validate(raw), migrated=False)
    identity, issues = _identity(origin, name)
    spec = {key: _template(raw[key]) for key in ("params", "domain", "data", "layers", "title", "colorbar") if key in raw}
    for data_key, entry in spec.get("data", {}).items():
        if "field" in entry and isinstance(entry["field"], str):
            entry["field"] = {"parameter": entry["field"]}
        if "level" in entry and entry.get("field"):
            entry["field"]["level"] = entry.pop("level")
        if any(op.get("op") == "style_units" for op in entry.get("transforms", [])):
            entry["legacy_unit_compatibility"] = True
            issues.append(MigrationIssue("legacy_style_units", "legacy style_units retained", f"spec.data.{data_key}"))
    for layer in spec.get("layers", []):
        # v1 used ``style: {select: {by, cases}}``; v2 makes the selector
        # itself the style value and retains exactly the same semantics.
        if isinstance(layer.get("style"), dict) and set(layer["style"]) == {"select"}:
            layer["style"] = layer["style"]["select"]
    document = {"api_version": "cedarkit.plots/v2", "kind": "PlotRecipe",
                "metadata": {"name": identity, "title": raw.get("name"),
                             "annotations": {"cedarkit.plots/migrated-from": "v1"}},
                "spec": spec}
    return MigrationResult(RecipeV2.model_validate(document), tuple(issues))


def dump_recipe(recipe: RecipeV2) -> str:
    """Produce deterministic, safe YAML (comments are intentionally not retained)."""
    return yaml.safe_dump(recipe.model_dump(mode="json", exclude_none=True), sort_keys=True,
                          allow_unicode=True, default_flow_style=False)
