"""Strict, value-only schema for workflow recipes."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field as PydanticField, field_validator, model_validator

_ID = re.compile(r"^\S+$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _identifier(value: str) -> str:
    if not _ID.fullmatch(value):
        raise ValueError("ID must be non-empty and contain no whitespace")
    return value


class Metadata(StrictModel):
    name: str
    title: str | None = None
    description: str | None = None

    _name = field_validator("name")(_identifier)


class Param(StrictModel):
    type: Literal["str", "int", "float", "bool", "timedelta", "enum"] = "str"
    required: bool = False
    default: Any | None = None
    values: tuple[str | int | float | bool, ...] | None = None

    @model_validator(mode="after")
    def valid_contract(self) -> "Param":
        if self.required and self.default is not None:
            raise ValueError("required param cannot have a default")
        if self.type == "enum" and (not self.values or len(set(map(str, self.values))) != len(self.values)):
            raise ValueError("enum requires non-empty unique values")
        if self.type != "enum" and self.values is not None:
            raise ValueError("values is only valid for enum")
        return self


class Field(StrictModel):
    parameter: str
    level: dict[str, Any] = PydanticField(default_factory=dict)

    _parameter = field_validator("parameter")(_identifier)


class Operation(StrictModel):
    op: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...] = ()
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = PydanticField(default_factory=dict)

    _op = field_validator("op")(_identifier)

    @field_validator("inputs")
    @classmethod
    def nonempty_inputs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("operation needs at least one input")
        return tuple(_identifier(item) for item in value)

    @field_validator("outputs")
    @classmethod
    def valid_outputs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("duplicate compute output ID")
        return tuple(_identifier(item) for item in value)


class Transform(StrictModel):
    op: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = PydanticField(default_factory=dict)
    repeat: int = PydanticField(default=1, ge=1)

    _op = field_validator("op")(_identifier)


class Data(StrictModel):
    field: Field | None = None
    compute: Operation | None = None
    units: str | None = None
    transforms: tuple[Transform, ...] = ()

    @model_validator(mode="after")
    def one_source(self) -> "Data":
        if (self.field is None) == (self.compute is None):
            raise ValueError("data needs exactly one of field or compute")
        return self


class Vector(StrictModel):
    u: str
    v: str

    _u = field_validator("u")(_identifier)
    _v = field_validator("v")(_identifier)


class Plot(StrictModel):
    id: str
    method: Literal["contourf", "contour", "barbs"]
    field: str | None = None
    vector: Vector | None = None
    style: str
    targets: str | tuple[str, ...] = "main"
    zorder: float | None = None

    _id = field_validator("id")(_identifier)
    _style = field_validator("style")(_identifier)

    @field_validator("targets")
    @classmethod
    def valid_targets(cls, value: str | tuple[str, ...]) -> str | tuple[str, ...]:
        if isinstance(value, str):
            return _identifier(value)
        if not value or len(set(value)) != len(value) or any(item == "all" for item in value):
            raise ValueError("fixed targets must be non-empty, unique IDs without all")
        return tuple(_identifier(item) for item in value)

    @model_validator(mode="after")
    def valid_method_and_binding(self) -> "Plot":
        if self.method == "barbs":
            if self.vector is None or self.field is not None:
                raise ValueError("barbs requires vector and forbids field")
        elif self.field is None or self.vector is not None:
            raise ValueError(f"{self.method} requires field and forbids vector")
        if self.field is not None:
            _identifier(self.field)
        return self


class Title(StrictModel):
    id: str
    text: str

    _id = field_validator("id")(_identifier)


class PlotRef(StrictModel):
    chart: str
    plot: str

    _chart = field_validator("chart")(_identifier)
    _plot = field_validator("plot")(_identifier)


class Colorbar(StrictModel):
    id: str
    plots: tuple[PlotRef, ...]
    target: str = "main"
    label: str | None = None

    _id = field_validator("id")(_identifier)
    _target = field_validator("target")(_identifier)

    @field_validator("plots")
    @classmethod
    def nonempty_plots(cls, value: tuple[PlotRef, ...]) -> tuple[PlotRef, ...]:
        if not value or len(set((ref.chart, ref.plot) for ref in value)) != len(value):
            raise ValueError("colorbar needs distinct plot references")
        return value


class Chart(StrictModel):
    id: str
    role: str | None = None
    plots: tuple[Plot, ...]
    titles: tuple[Title, ...] = ()
    colorbars: tuple[Colorbar, ...] = ()

    _id = field_validator("id")(_identifier)

    @field_validator("role")
    @classmethod
    def role_id(cls, value: str | None) -> str | None:
        return _identifier(value) if value is not None else None

    @model_validator(mode="after")
    def unique_content(self) -> "Chart":
        for label, items in (("plot", self.plots), ("title", self.titles), ("colorbar", self.colorbars)):
            ids = [item.id for item in items]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {label} ID in chart {self.id!r}")
        if not self.plots:
            raise ValueError("chart needs at least one plot")
        return self


class Content(StrictModel):
    charts: tuple[Chart, ...]
    titles: tuple[Title, ...] = ()
    colorbars: tuple[Colorbar, ...] = ()


class Display(StrictModel):
    template: str | None = None
    layout: dict[str, Any] = PydanticField(default_factory=dict)
    chart_defaults: dict[str, Any] = PydanticField(default_factory=dict)
    chart_rules: tuple[dict[str, Any], ...] = ()
    charts: dict[str, dict[str, Any]] = PydanticField(default_factory=dict)
    decorations: dict[str, Any] = PydanticField(default_factory=dict)

    @field_validator("template")
    @classmethod
    def template_id(cls, value: str | None) -> str | None:
        return _identifier(value) if value is not None else None


class Spec(StrictModel):
    params: dict[str, Param] = PydanticField(default_factory=dict)
    data: dict[str, Data]
    content: Content
    display: Display = PydanticField(default_factory=Display)

    @model_validator(mode="after")
    def references(self) -> "Spec":
        if not self.data or not self.content.charts:
            raise ValueError("data and content.charts must not be empty")
        for key in self.params:
            _identifier(key)
        for key in self.data:
            _identifier(key)
        available_bindings = set(self.data)
        for key, item in self.data.items():
            if item.compute:
                for output in item.compute.outputs:
                    if output in available_bindings:
                        raise ValueError(f"duplicate data/output ID {output!r}")
                    available_bindings.add(output)
        for key, item in self.data.items():
            if item.compute:
                for source in item.compute.inputs:
                    if source not in available_bindings:
                        raise ValueError(f"data {key!r} references missing input {source!r}")
        charts = {chart.id: chart for chart in self.content.charts}
        if len(charts) != len(self.content.charts):
            raise ValueError("duplicate chart ID")
        for chart in self.content.charts:
            for plot in chart.plots:
                bindings = (plot.field,) if plot.field else (plot.vector.u, plot.vector.v)  # type: ignore[union-attr]
                for binding in bindings:
                    if binding not in available_bindings:
                        raise ValueError(f"chart {chart.id!r} plot {plot.id!r} references missing data {binding!r}")
        for key in self.display.charts:
            if key not in charts:
                raise ValueError(f"display references missing chart {key!r}")
        for label, items in (("title", self.content.titles), ("colorbar", self.content.colorbars)):
            ids = [item.id for item in items]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate panel {label} ID")
        for owner, bars in ((None, self.content.colorbars), *((chart.id, chart.colorbars) for chart in self.content.charts)):
            for bar in bars:
                for ref in bar.plots:
                    referenced_plot = next((plot for plot in charts[ref.chart].plots if plot.id == ref.plot), None) if ref.chart in charts else None
                    if referenced_plot is None:
                        raise ValueError(f"colorbar {bar.id!r} references missing plot ({ref.chart!r}, {ref.plot!r})")
                    if owner is not None and ref.chart != owner:
                        raise ValueError(f"chart colorbar {bar.id!r} cannot reference another chart")
                    if referenced_plot.method == "barbs":
                        raise ValueError(f"colorbar {bar.id!r} cannot reference barbs plot")
        return self


class Recipe(StrictModel):
    api_version: Literal["cedarkit.plots/v3"]
    kind: Literal["PlotRecipe"]
    metadata: Metadata
    spec: Spec
