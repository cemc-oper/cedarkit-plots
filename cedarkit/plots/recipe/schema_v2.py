"""Strict public schema for ``cedarkit.plots/v2`` recipe documents."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_NAME = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MetadataSpec(StrictModel):
    name: str
    title: str | None = None
    description: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def stable_name(cls, value: str) -> str:
        if not _NAME.fullmatch(value):
            raise ValueError("must be a stable dotted identity")
        return value

    @field_validator("annotations")
    @classmethod
    def annotation_namespaces(cls, value: dict[str, str]) -> dict[str, str]:
        if any("/" not in key for key in value):
            raise ValueError("annotation keys must contain a namespace slash")
        return value


class ParamSpecV2(StrictModel):
    type: Literal["str", "int", "float", "bool", "timedelta", "enum"] = "str"
    required: bool = False
    default: Any | None = None
    values: list[str | int | float | bool] | None = None

    @model_validator(mode="after")
    def valid_contract(self) -> "ParamSpecV2":
        if self.required and self.default is not None:
            raise ValueError("a required param cannot have a default")
        if self.type == "enum" and (not self.values or len(set(map(str, self.values))) != len(self.values)):
            raise ValueError("enum params require non-empty unique values")
        if self.type != "enum" and self.values is not None:
            raise ValueError("values is only valid for enum params")
        return self


class FieldSpecV2(StrictModel):
    parameter: str
    level: dict[str, Any] | None = None

    @field_validator("parameter")
    @classmethod
    def parameter_id(cls, value: str) -> str:
        if not value or "{" in value:
            raise ValueError("field parameter must be a non-template identifier")
        return value


class OpSpecV2(StrictModel):
    op: str
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    repeat: int = 1

    @field_validator("op")
    @classmethod
    def op_name(cls, value: str) -> str:
        if not _NAME.fullmatch(value):
            raise ValueError("must be a stable op name")
        return value

    @field_validator("repeat")
    @classmethod
    def positive_repeat(cls, value: int) -> int:
        if value < 1:
            raise ValueError("repeat must be >= 1")
        return value


class ComputeSpecV2(OpSpecV2):
    inputs: list[str]
    outputs: list[str] | None = None

    @field_validator("inputs")
    @classmethod
    def inputs_present(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("compute op requires at least one input")
        return value


class DataSpecV2(StrictModel):
    field: FieldSpecV2 | None = None
    compute: ComputeSpecV2 | None = None
    units: str | None = None
    transforms: list[OpSpecV2] = Field(default_factory=list)
    legacy_unit_compatibility: bool = False

    @model_validator(mode="after")
    def source_exactly_once(self) -> "DataSpecV2":
        if (self.field is None) == (self.compute is None):
            raise ValueError("data entry needs exactly one of 'field' or 'compute'")
        return self


class VectorSpecV2(StrictModel):
    u: str
    v: str


class StyleSelectV2(StrictModel):
    by: str
    cases: dict[str, str]

    @model_validator(mode="after")
    def else_case(self) -> "StyleSelectV2":
        if "else" not in self.cases:
            raise ValueError("select cases must include an 'else' branch")
        return self


class LayerSpecV2(StrictModel):
    field: str | None = None
    vector: VectorSpecV2 | None = None
    style: str | StyleSelectV2
    layer: list[int] | None = None

    @model_validator(mode="after")
    def one_reference(self) -> "LayerSpecV2":
        if (self.field is None) == (self.vector is None):
            raise ValueError("layer needs exactly one of 'field' or 'vector'")
        return self


class DomainSpecV2(StrictModel):
    default: str
    area: str


class TitleSpecV2(StrictModel):
    graph_name: str
    area_prefix: bool = False


class ColorbarSpecV2(StrictModel):
    layer: int | list[int]


class RecipeSpecV2(StrictModel):
    params: dict[str, ParamSpecV2] = Field(default_factory=dict)
    domain: DomainSpecV2
    data: dict[str, DataSpecV2]
    layers: list[LayerSpecV2]
    title: TitleSpecV2
    colorbar: ColorbarSpecV2 | None = None

    @model_validator(mode="after")
    def references(self) -> "RecipeSpecV2":
        if not self.data or not self.layers:
            raise ValueError("data and layers must not be empty")
        names = set(self.data)
        for entry in self.data.values():
            if entry.compute:
                for key in entry.compute.inputs:
                    if key not in names:
                        raise ValueError(f"compute references unknown input {key!r}")
                names.update(entry.compute.outputs or [])
        for layer in self.layers:
            refs = [layer.field] if layer.field else [layer.vector.u, layer.vector.v]  # type: ignore[union-attr]
            if any(ref not in names for ref in refs):
                raise ValueError("layer references unknown data entry")
        return self


class RecipeV2(StrictModel):
    api_version: Literal["cedarkit.plots/v2"]
    kind: Literal["PlotRecipe"]
    metadata: MetadataSpec
    spec: RecipeSpecV2
