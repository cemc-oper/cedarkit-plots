"""Compile v3 recipes from declarations and catalog metadata only."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from typing import Any, Mapping

import pandas as pd
from reki import resolve_parameter

from ...ops import OpRegistry
from ...units import canonical_unit, conversion_rule
from ..metadata import format_value
from ..recipe import LoadedRecipe, Recipe
from .model import FieldRequest, PlanIssue, PlanNode, RecipeCompileError, WorkflowPlan

_QUERY_FIELDS = {"level_type", "level", "step_type", "time_range", "member"}
_FIRST_SURFACE_TYPES = {100: "isobaricInhPa", 103: "heightAboveGround"}


def _normalize_field_level(level: Mapping[str, Any]) -> dict[str, Any]:
    """Bind catalog surface selectors to searchable reki query fields."""
    result = dict(level)
    first = result.pop("first_level", None)
    first_type = result.pop("first_level_type", None)
    second = result.pop("second_level", None)
    second_type = result.pop("second_level_type", None)
    if first is not None:
        if "level" in result and result["level"] != first:
            raise ValueError("level and first_level disagree")
        result["level"] = first
    if first_type is not None:
        result["typeOfFirstFixedSurface"] = first_type
        inferred = _FIRST_SURFACE_TYPES.get(int(first_type))
        if inferred is not None:
            if second is not None and int(first_type) == 103:
                inferred = "heightAboveGroundLayer"
            if "level_type" in result and result["level_type"] != inferred:
                raise ValueError("level_type and first_level_type disagree")
            result["level_type"] = inferred
    if second_type is not None:
        result["typeOfSecondFixedSurface"] = second_type
    if second is not None:
        result["scaledValueOfSecondFixedSurface"] = second
    return result


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"non-serializable plan value {type(value).__name__}")


def _stable_id(kind: str, payload: Any) -> str:
    encoded = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return f"{kind}:{hashlib.sha256(encoded).hexdigest()[:16]}"


def _time(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, pd.Timedelta) or (isinstance(value, str) and re.fullmatch(r"[+-]?\d+(?:\.\d+)?[A-Za-z]+", value)):
        return pd.Timedelta(value).isoformat()
    stamp = pd.Timestamp(value)
    stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
    return stamp.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class CompileContext:
    start_time: Any = None
    forecast_time: Any = None
    params: Mapping[str, Any] | None = None
    provider_slot: str = "default"
    cardinality: str = "one"
    strict: bool = False

    def __post_init__(self) -> None:
        if not self.provider_slot or self.cardinality not in {"one", "first", "all"}:
            raise ValueError("invalid provider_slot or cardinality")
        object.__setattr__(self, "params", dict(self.params or {}))


class _Compiler:
    def __init__(self, recipe: Recipe, context: CompileContext, registry: OpRegistry, origin: str):
        self.recipe, self.context, self.registry, self.origin = recipe, context, registry, origin
        self.params = self._params()
        self.nodes: dict[str, PlanNode] = {}
        self.bindings: dict[str, str] = {}
        self.slots: dict[str, int] = {}
        self.building: list[str] = []
        self.done: set[str] = set()
        self.owners = {name: name for name in recipe.spec.data}
        for name, item in recipe.spec.data.items():
            if item.compute:
                for alias in item.compute.outputs:
                    self.owners[alias] = name

    def error(self, message: str, code: str, *, binding: str | None = None,
              node_id: str | None = None) -> RecipeCompileError:
        return RecipeCompileError(f"product={self.recipe.metadata.name}: {message}", origin=self.origin,
                                  code=code, binding=binding, node_id=node_id)

    def _params(self) -> dict[str, Any]:
        supplied = self.context.params or {}
        unknown = set(supplied) - set(self.recipe.spec.params)
        if unknown:
            raise self.error(f"unknown params {sorted(unknown)}", "unknown_param")
        values = {}
        for name, spec in self.recipe.spec.params.items():
            if name not in supplied and spec.required:
                raise self.error(f"missing required param {name!r}", "missing_param")
            value = supplied.get(name, spec.default)
            if value is not None:
                try:
                    if spec.type == "timedelta":
                        value = pd.Timedelta(value)
                    elif spec.type == "bool":
                        if isinstance(value, str) and value.lower() in {"true", "false"}:
                            value = value.lower() == "true"
                        elif not isinstance(value, bool):
                            raise ValueError("bool must be true or false")
                    elif spec.type in {"str", "int", "float", "bool"}:
                        value = {"str": str, "int": int, "float": float}[spec.type](value)
                except (TypeError, ValueError) as exc:
                    raise self.error(f"invalid param {name!r}: {exc}", "invalid_param") from exc
            if spec.type == "enum" and value not in (spec.values or ()):
                raise self.error(f"invalid enum param {name!r}", "invalid_param")
            values[name] = value
        return values

    def expand(self, value: Any, path: str) -> Any:
        try:
            return format_value(value, params=self.params, metadata=self.recipe.metadata.model_dump(),
                                context=self._context_values(), path=path)
        except ValueError as exc:
            raise self.error(str(exc), "template") from exc

    def _context_values(self) -> dict[str, Any]:
        values = {"start_time": _time(self.context.start_time), "forecast_time": _time(self.context.forecast_time),
                  "provider_slot": self.context.provider_slot, "cardinality": self.context.cardinality}
        if self.context.forecast_time is not None:
            try:
                forecast = pd.Timedelta(self.context.forecast_time)
            except (TypeError, ValueError):
                pass
            else:
                values["forecast_hour"] = f"{int(forecast / pd.Timedelta(hours=1)):03d}"
                if self.params.get("interval") is not None:
                    previous = forecast - pd.Timedelta(self.params["interval"])
                    values["previous_forecast_hour"] = f"{int(previous / pd.Timedelta(hours=1)):03d}"
        return values

    def _content(self):
        content = self.recipe.spec.content
        def titles(items, path):
            return tuple(title.model_copy(update={"text": str(self.expand(title.text, f"{path}.{title.id}.text")).strip()})
                         for title in items)
        def colorbars(items, path):
            return tuple(bar.model_copy(update={"label": str(self.expand(bar.label, f"{path}.{bar.id}.label"))})
                         if bar.label is not None else bar for bar in items)
        charts = tuple(chart.model_copy(update={
            "plots": tuple(plot.model_copy(update={"style": str(self.expand(
                plot.style, f"spec.content.charts.{chart.id}.plots.{plot.id}.style"))})
                           for plot in chart.plots),
            "titles": titles(chart.titles, f"spec.content.charts.{chart.id}.titles"),
            "colorbars": colorbars(chart.colorbars, f"spec.content.charts.{chart.id}.colorbars")})
                       for chart in content.charts)
        return content.model_copy(update={"charts": charts, "titles": titles(content.titles, "spec.content.titles"),
                                  "colorbars": colorbars(content.colorbars, "spec.content.colorbars")})

    def add(self, kind: str, payload: Any, dependencies: tuple[str, ...], origin: str,
            bindings: tuple[str, ...], **kwargs: Any) -> str:
        node_id = _stable_id(kind, payload)
        if node_id in self.nodes:
            raise self.error(f"node ID collision at {origin}", "node_collision", node_id=node_id)
        self.nodes[node_id] = PlanNode(node_id, kind, dependencies, origin, bindings, **kwargs)
        return node_id

    def read(self, parameter: str, level: Mapping[str, Any], binding: str, origin: str,
             *, forecast_time: str | None = None) -> str:
        try:
            expanded = _normalize_field_level(self.expand(level, origin))
        except (TypeError, ValueError) as exc:
            raise self.error(f"invalid field level at {origin}: {exc}", "field_query", binding=binding) from exc
        extra = {key: value for key, value in expanded.items() if key not in _QUERY_FIELDS}
        standard = {key: value for key, value in expanded.items() if key in _QUERY_FIELDS}
        try:
            resolved = resolve_parameter(parameter, extra=extra or None, **standard)
        except Exception as exc:
            raise self.error(f"cannot resolve field {parameter!r} at {origin}: {exc}", "field_query", binding=binding) from exc
        parameter_id = resolved.record.parameter_id
        if not parameter_id:
            raise self.error(f"field {parameter!r} has no stable parameter ID", "parameter_id", binding=binding)
        key = FieldRequest(self.context.provider_slot, parameter_id, resolved.query,
                           _time(self.context.start_time), forecast_time if forecast_time is not None else _time(self.context.forecast_time),
                           self.context.cardinality)
        query = resolved.query
        payload = {"slot": key.provider_slot, "parameter": key.parameter_id,
                   "query": {field: getattr(query, field) for field in ("parameter", "level_type", "level", "step_type", "time_range", "member", "extra")},
                   "start": key.start_time, "forecast": key.forecast_time, "cardinality": key.cardinality}
        node_id = _stable_id("read", payload)
        if node_id in self.nodes:
            node = self.nodes[node_id]
            self.nodes[node_id] = replace(node, bindings=tuple(sorted(set(node.bindings) | {binding})),
                                          origin=min(node.origin, origin))
        else:
            self.nodes[node_id] = PlanNode(node_id, "read", (), origin, (binding,), request=key)
        return node_id

    def descriptor(self, name: str, kind: str, inputs: int, outputs: int, binding: str):
        try:
            descriptor = self.registry.get(name)
        except KeyError as exc:
            raise self.error(str(exc), "unknown_op", binding=binding) from exc
        if descriptor.kind != kind or descriptor.input_count != inputs or descriptor.output_count != outputs:
            raise self.error(f"op {name!r} requires {descriptor.kind} {descriptor.input_count} input(s) / {descriptor.output_count} output(s); got {kind} {inputs} / {outputs}",
                             "op_signature", binding=binding)
        return descriptor

    def reference(self, name: str, owner: str) -> str:
        target = self.owners.get(name)
        if target is None:
            raise self.error(f"unknown data reference {name!r}", "unknown_reference", binding=owner)
        self.build(target)
        return self.bindings[name]

    def build(self, name: str) -> None:
        if name in self.done:
            return
        if name in self.building:
            cycle = self.building[self.building.index(name):] + [name]
            raise self.error("dependency cycle: " + " -> ".join(cycle), "cycle", binding=name)
        self.building.append(name)
        item = self.recipe.spec.data[name]
        origin = f"spec.data.{name}"
        if item.field:
            current = self.read(item.field.parameter, item.field.level, name, origin + ".field")
            self.bindings[name], self.slots[name] = current, 0
        else:
            op = item.compute
            assert op is not None
            aliases = op.outputs or (name,)
            descriptor = self.descriptor(op.op, "compute", len(op.inputs), len(aliases), name)
            dependencies = tuple(self.reference(source, name) for source in op.inputs)
            args = self.expand(op.args, origin + ".compute.args")
            kwargs = self.expand(op.kwargs, origin + ".compute.kwargs")
            current = self.add("compute", (name, op.op, dependencies, args, kwargs), dependencies,
                               origin + ".compute", tuple(sorted(set((name, *aliases)))),
                               input_slots=tuple(self.slots[source] for source in op.inputs),
                               descriptor=op.op, args=args, kwargs=tuple(sorted(kwargs.items())),
                               output_count=descriptor.output_count, pure=descriptor.pure, reusable=descriptor.reusable)
            for index, alias in enumerate(aliases):
                self.bindings[alias], self.slots[alias] = current, index
            self.bindings[name], self.slots[name] = current, 0
            if len(aliases) > 1 and (item.transforms or item.units):
                raise self.error("multi-output data cannot apply one transform/units to all outputs", "multi_output_transform", binding=name)
        for index, transform in enumerate(item.transforms):
            descriptor = self.descriptor(transform.op, "transform", 1, 1, name)
            args = self.expand(transform.args, origin + f".transforms.{index}.args")
            kwargs = self.expand(transform.kwargs, origin + f".transforms.{index}.kwargs")
            for repeat in range(transform.repeat):
                if transform.op == "time_diff":
                    if len(args) != 1 or kwargs:
                        raise self.error("time_diff needs one interval argument", "planner", binding=name)
                    try:
                        interval = pd.Timedelta(args[0])
                        raw_forecast = self.context.forecast_time
                        duration = isinstance(raw_forecast, pd.Timedelta) or (
                            isinstance(raw_forecast, str) and re.fullmatch(r"[+-]?\d+(?:\.\d+)?[A-Za-z]+", raw_forecast))
                        forecast = pd.Timedelta(raw_forecast) if duration else pd.Timestamp(raw_forecast)
                    except (TypeError, ValueError) as exc:
                        raise self.error(f"time_diff needs forecast time and interval: {exc}", "planner", binding=name) from exc
                    if interval <= pd.Timedelta(0) or (duration and forecast < interval):
                        raise self.error("time_diff interval must be positive and within forecast", "planner", binding=name)
                    if not duration and self.context.start_time is not None and forecast - pd.Timestamp(self.context.start_time) < interval:
                        raise self.error("time_diff interval exceeds elapsed forecast time", "planner", binding=name)
                    ancestor = self._read_ancestor(current)
                    if ancestor is None or ancestor.request is None:
                        raise self.error("time_diff needs a field read ancestor", "planner", binding=name)
                    request = ancestor.request
                    query = request.query
                    previous_level = {field: getattr(query, field) for field in _QUERY_FIELDS
                                      if getattr(query, field) is not None}
                    previous_level.update(query.extra)
                    previous = self.read(request.parameter_id, previous_level, f"{name}@-{interval}", origin + f".transforms.{index}.planner",
                                         forecast_time=_time(forecast - interval))
                    dependencies = (current, previous)
                else:
                    if descriptor.planner is not None:
                        raise self.error(f"planner for {transform.op!r} is unsupported by workflow compiler", "planner", binding=name)
                    dependencies = (current,)
                current = self.add("transform", (name, index, repeat, transform.op, dependencies, args, kwargs),
                                   dependencies, origin + f".transforms.{index}", (name,), descriptor=transform.op,
                                   args=() if transform.op == "time_diff" else args,
                                   kwargs=(("accumulation_hours", float(interval / pd.Timedelta(hours=1))),)
                                   if transform.op == "time_diff" else tuple(sorted(kwargs.items())), pure=descriptor.pure,
                                   reusable=descriptor.reusable)
            self.bindings[name] = current
        if item.units is not None or item.source_units is not None or item.temperature_kind is not None:
            try:
                target = canonical_unit(item.units) if item.units is not None else None
                declared_source = item.source_units
                catalog_source = resolve_parameter(item.field.parameter).record.unit if item.field and not item.transforms else None
                if declared_source is not None and catalog_source is not None and canonical_unit(declared_source) != canonical_unit(catalog_source):
                    raise ValueError(f"source_units {declared_source!r} contradict catalog units {catalog_source!r}")
                if declared_source is None and item.field and not item.transforms:
                    declared_source = catalog_source
                source = canonical_unit(declared_source) if declared_source is not None else None
                if source is not None:
                    conversion_rule(source, target or source, temperature_kind=item.temperature_kind,
                                    source_from="explicit" if item.source_units is not None else "metadata")
            except ValueError as exc:
                raise self.error(f"invalid unit declaration: {exc}", "units", binding=name) from exc
            current = self.add("convert_units", (name, target, current), (current,), origin + ".units", (name,),
                               kwargs=(("source_units", source), ("temperature_kind", item.temperature_kind),
                                       ("units", target)))
            self.bindings[name] = current
        if item.compute and len(item.compute.outputs) == 1:
            self.bindings[item.compute.outputs[0]] = current
        self.building.pop()
        self.done.add(name)

    def _read_ancestor(self, node_id: str) -> PlanNode | None:
        node = self.nodes[node_id]
        if node.kind == "read":
            return node
        for dependency in node.dependencies:
            found = self._read_ancestor(dependency)
            if found:
                return found
        return None

    def compile(self) -> WorkflowPlan:
        for name in sorted(self.recipe.spec.data):
            self.build(name)
        used = set()
        for chart in self.recipe.spec.content.charts:
            for plot in chart.plots:
                refs = (plot.field,) if plot.field else (plot.vector.u, plot.vector.v)
                for ref in refs:
                    used.add(self.bindings[ref])
        live = set(used)
        todo = list(used)
        while todo:
            for dependency in self.nodes[todo.pop()].dependencies:
                if dependency not in live:
                    live.add(dependency)
                    todo.append(dependency)
        dead = tuple(PlanIssue("dead_node", f"unused binding(s) {node.bindings!r}", node.origin, node.id,
                                node.bindings[0] if node.bindings else None)
                     for node in sorted(self.nodes.values(), key=lambda item: item.id) if node.id not in live)
        if dead and self.context.strict:
            raise self.error(f"dead nodes found: {len(dead)}", "dead_node", node_id=dead[0].node_id)
        pending = set(live)
        ordered: list[PlanNode] = []
        while pending:
            ready = sorted((self.nodes[node_id] for node_id in pending
                            if all(dep not in pending for dep in self.nodes[node_id].dependencies)), key=lambda node: node.id)
            if not ready:
                raise self.error("node dependency cycle", "cycle", node_id=min(pending))
            for node in ready:
                ordered.append(node)
                pending.remove(node.id)
        batches: dict[tuple[str, str | None, str | None, str], list[str]] = {}
        for node in ordered:
            if node.request:
                key = node.request
                batches.setdefault((key.provider_slot, key.start_time, key.forecast_time, key.cardinality), []).append(node.id)
        context = {**self._context_values(), "params": self.params}
        return WorkflowPlan.create(recipe_identity=self.recipe.metadata.name,
            descriptor_identity=self.registry.manifest()["identity"], context=context,
            nodes=tuple(ordered), outputs={name: node_id for name, node_id in self.bindings.items() if node_id in live},
            output_slots={name: self.slots[name] for name, node_id in self.bindings.items() if node_id in live},
            content=self._content(), display=self.recipe.spec.display.model_copy(deep=True),
            issues=dead, read_batches=tuple(tuple(batches[key]) for key in sorted(batches, key=str)))


def compile_recipe(recipe: Recipe | LoadedRecipe, context: CompileContext | None = None, *,
                   registry: OpRegistry | None = None, origin: str | None = None) -> WorkflowPlan:
    """Compile only declarations and catalog metadata; never query field values."""
    if isinstance(recipe, LoadedRecipe):
        origin = origin or recipe.origin
        recipe = recipe.recipe
    return _Compiler(recipe, context or CompileContext(), registry or OpRegistry.builtins(),
                     origin or "<memory>").compile()
