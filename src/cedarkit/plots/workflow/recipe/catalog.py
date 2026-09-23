"""Deterministic discovery of packaged v3 recipe documents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...registry import DuplicateRegistrationError, RegistryProvenance
from .loader import LoadedRecipe, load_recipe


@dataclass(frozen=True)
class RecipeResource:
    name: str
    resource: Any
    provenance: RegistryProvenance

    @property
    def origin(self) -> str:
        distribution = self.provenance.distribution or self.provenance.source
        return f"{distribution}:{self.resource}"


class RecipeCatalog:
    """Index resources by relative dotted name without reading recipe contents."""

    def __init__(self) -> None:
        self._items: dict[str, RecipeResource] = {}

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._items))

    def register_resource(self, name: str, resource: Any, *,
                          provenance: RegistryProvenance | None = None) -> None:
        if not name or any(not part or not part.replace("_", "").replace("-", "").isalnum()
                           for part in name.split(".")):
            raise ValueError(f"invalid recipe ID {name!r}")
        source = provenance or RegistryProvenance()
        if name in self._items:
            old = self._items[name].provenance.public_dict()
            raise DuplicateRegistrationError(
                f"duplicate recipe {name!r}: {old} conflicts with {source.public_dict()}")
        if not resource.is_file():
            raise ValueError(f"recipe resource {resource} is not a file")
        self._items[name] = RecipeResource(name, resource, source)

    def register_root(self, root: Any, *, provenance: RegistryProvenance | None = None) -> None:
        def visit(directory: Any, parts: tuple[str, ...]) -> None:
            for item in sorted(directory.iterdir(), key=lambda value: value.name):
                if item.is_dir():
                    visit(item, (*parts, item.name))
                elif item.is_file() and item.name.lower().endswith((".yaml", ".yml")):
                    self.register_resource(".".join((*parts, item.name.rsplit(".", 1)[0])),
                                           item, provenance=provenance)
        visit(root, ())

    def get(self, name: str) -> RecipeResource:
        try:
            return self._items[name]
        except KeyError as exc:
            raise KeyError(f"unknown recipe {name!r}; registered: {self.names}") from exc

    def load(self, name: str) -> LoadedRecipe:
        item = self.get(name)
        return load_recipe(item.resource.read_text(encoding="utf-8"), origin=item.origin)
