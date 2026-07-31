"""Recipe YAML schema (pydantic).

A recipe is a declarative plot product definition: which fields to load
(``data``), how to transform them (``transforms`` / ``compute`` ops), how
to draw them (``layers`` with style references), plus ``domain``,
``title``, ``params`` and ``colorbar`` sections.

The schema is a closed vocabulary on purpose (design decision D4): ops
are names resolved against the op registry, never embedded expressions.
Cross-reference checks (unknown op / field / style id) are done by
:class:`~cedarkit.plots.engine.engine.PlotEngine` at load time; this
module only validates structure.
"""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecipeError(ValueError):
    """Raised when a recipe YAML file fails to load or validate."""

    def __init__(self, path: Union[str, Path], message: str):
        self.path = str(path)
        super().__init__(f"{self.path}: {message}")


class TransformSpec(BaseModel):
    """A named transform op applied to a loaded/computed field."""
    model_config = ConfigDict(extra="forbid")

    op: str
    args: List[Any] = Field(default_factory=list)
    kwargs: Dict[str, Any] = Field(default_factory=dict)
    repeat: int = 1

    @model_validator(mode="after")
    def check_repeat(self) -> "TransformSpec":
        if self.repeat < 1:
            raise ValueError("repeat must be >= 1")
        return self


class LevelSpec(BaseModel):
    """Level selection using GRIB2 code table 4.5 numeric level type.

    ``first_level`` may be a ``"{param}"`` template resolved from recipe
    params at load time.
    """
    model_config = ConfigDict(extra="forbid")

    first_level_type: int
    first_level: Union[int, float, str]
    second_level_type: Optional[int] = None
    second_level: Optional[Union[int, float, str]] = None


class ComputeSpec(BaseModel):
    """A named compute op deriving field(s) from other data entries."""
    model_config = ConfigDict(extra="forbid")

    op: str
    inputs: List[str]
    args: List[Any] = Field(default_factory=list)
    kwargs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Optional[List[str]] = None

    @model_validator(mode="after")
    def check_inputs(self) -> "ComputeSpec":
        if not self.inputs:
            raise ValueError("compute op requires at least one input")
        return self


class DataFieldSpec(BaseModel):
    """One entry of the ``data`` section: a field load or a computation."""
    model_config = ConfigDict(extra="forbid")

    field: Optional[str] = None
    level: Optional[LevelSpec] = None
    compute: Optional[ComputeSpec] = None
    transforms: List[TransformSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_source(self) -> "DataFieldSpec":
        if (self.field is None) == (self.compute is None):
            raise ValueError("data entry needs exactly one of 'field' or 'compute'")
        if self.level is not None and self.field is None:
            raise ValueError("'level' is only valid together with 'field'")
        return self


class StyleSelectSpec(BaseModel):
    """Runtime style variant selection rule.

    ``by`` is a dotted path into the plot metadata (e.g.
    ``start_time.month``); a ``pd.Timedelta`` value is compared as integer
    hours. Case keys are comma-separated value lists; ``else`` is
    required (exhaustiveness, design section 6).
    """
    model_config = ConfigDict(extra="forbid")

    by: str
    cases: Dict[str, str]

    @model_validator(mode="after")
    def check_else(self) -> "StyleSelectSpec":
        if "else" not in self.cases:
            raise ValueError("select cases must include an 'else' branch")
        return self


class StyleSelectHolder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    select: StyleSelectSpec


#: layer style: ``"id"`` / ``"id:variant"`` or a select rule.
StyleSpec = Union[str, StyleSelectHolder]


class VectorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    u: str
    v: str


class LayerSpec(BaseModel):
    """One drawing layer: a scalar field or a u/v vector pair."""
    model_config = ConfigDict(extra="forbid")

    field: Optional[str] = None
    vector: Optional[VectorSpec] = None
    style: StyleSpec
    layer: Optional[List[int]] = None

    @model_validator(mode="after")
    def check_data_ref(self) -> "LayerSpec":
        if (self.field is None) == (self.vector is None):
            raise ValueError("layer needs exactly one of 'field' or 'vector'")
        return self


class DomainSpec(BaseModel):
    """Domain template names; chosen by ``metadata.area_range``."""
    model_config = ConfigDict(extra="forbid")

    default: str
    area: str


class TitleSpec(BaseModel):
    """Graph title template; ``{param}`` placeholders come from metadata.

    ``area_prefix`` prepends ``"{area_name} "`` when an area is set.
    """
    model_config = ConfigDict(extra="forbid")

    graph_name: str
    area_prefix: bool = False


class ColorbarSpec(BaseModel):
    """Which layer styles feed the colorbar (single index or list)."""
    model_config = ConfigDict(extra="forbid")

    layer: Union[int, List[int]]

    @model_validator(mode="after")
    def check_layer(self) -> "ColorbarSpec":
        layers = self.layer if isinstance(self.layer, list) else [self.layer]
        if not layers or any(index < 0 for index in layers):
            raise ValueError("colorbar layer must be a non-negative index (or list)")
        return self

    @property
    def layers(self) -> List[int]:
        return self.layer if isinstance(self.layer, list) else [self.layer]


class ParamSpec(BaseModel):
    """A recipe parameter, exposed on the generated ``PlotMetadata``."""
    model_config = ConfigDict(extra="forbid")

    type: Literal["float", "int", "str", "timedelta"] = "str"
    required: bool = False
    default: Optional[Any] = None

    @model_validator(mode="after")
    def check_required_default(self) -> "ParamSpec":
        if self.required and self.default is not None:
            raise ValueError("a required param cannot have a default")
        return self


class Recipe(BaseModel):
    """A complete plot recipe."""
    model_config = ConfigDict(extra="forbid")

    name: str
    domain: DomainSpec
    params: Dict[str, ParamSpec] = Field(default_factory=dict)
    data: Dict[str, DataFieldSpec]
    layers: List[LayerSpec]
    title: TitleSpec
    colorbar: Optional[ColorbarSpec] = None

    @model_validator(mode="after")
    def check_references(self) -> "Recipe":
        if not self.data:
            raise ValueError("data section must not be empty")
        if not self.layers:
            raise ValueError("layers section must not be empty")
        for key, spec in self.data.items():
            if spec.compute is not None:
                for input_key in spec.compute.inputs:
                    if input_key not in self.data:
                        raise ValueError(
                            f"data entry {key!r} computes from unknown input {input_key!r}"
                        )
                for output_key in spec.compute.outputs or []:
                    if output_key in self.data:
                        raise ValueError(
                            f"compute output {output_key!r} duplicates a data entry"
                        )
        data_keys = set(self.data)
        for spec in self.data.values():
            if spec.compute is not None:
                data_keys.update(spec.compute.outputs or [])
        for index, layer in enumerate(self.layers):
            refs = [layer.field] if layer.field is not None else [layer.vector.u, layer.vector.v]
            for ref in refs:
                if ref not in data_keys:
                    raise ValueError(f"layer {index} references unknown data entry {ref!r}")
        if self.colorbar is not None:
            for layer_index in self.colorbar.layers:
                if layer_index >= len(self.layers):
                    raise ValueError(
                        f"colorbar layer index {layer_index} out of range "
                        f"({len(self.layers)} layers)"
                    )
        return self


def load_recipe_file(path: Union[str, Path]) -> Recipe:
    """
    Load and validate a recipe YAML file.

    Raises
    ------
    RecipeError
        on YAML syntax errors (with line/column) and schema violations,
        always prefixed with the file path.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise RecipeError(path, f"cannot read file: {e}") from e

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        if mark is not None:
            raise RecipeError(path, f"invalid YAML at line {mark.line + 1}, column {mark.column + 1}: {e.problem}") from e
        raise RecipeError(path, f"invalid YAML: {e}") from e

    if not isinstance(raw, dict):
        raise RecipeError(path, "recipe file must contain a YAML mapping")

    try:
        return Recipe.model_validate(raw)
    except ValueError as e:
        raise RecipeError(path, f"recipe validation failed: {e}") from e
