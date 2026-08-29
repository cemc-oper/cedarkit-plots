"""Static v2 recipe compiler.  It never accesses a provider or field values."""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

import pandas as pd
from reki import FieldQuery, resolve_parameter

from ..ops import OpRegistry
from ..recipe import LoadedRecipe, RecipeV2
from .issues import PlanIssue, RecipeCompileError
from .nodes import PlanNode, RequestKey, TimeBinding
from .plan import PlotPlan
from .units import conversion

_PLACEHOLDER = re.compile(r"\{(params|metadata)\.([A-Za-z][A-Za-z0-9_-]*)\}")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _time(value: Any) -> str | None:
    if value is None:
        return None
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    else:
        stamp = stamp.tz_convert("UTC")
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
        object.__setattr__(self, "params", _freeze(dict(self.params or {})))
        if not self.provider_slot:
            raise ValueError("provider_slot must not be empty")
        if self.cardinality not in {"one", "first", "all"}:
            raise ValueError("cardinality must be one, first, or all")


def _scalar(value: Any) -> Any:
    if isinstance(value, pd.Timedelta):
        return int(value.value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        raise ValueError("non-finite numbers are not allowed")
    if isinstance(value, Mapping):
        return {str(key): _scalar(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_scalar(item) for item in value]
    return value


class _Compiler:
    def __init__(self, recipe: RecipeV2, context: CompileContext, registry: OpRegistry, origin: str):
        self.recipe, self.context, self.registry, self.origin = recipe, context, registry, origin
        self.params = self._params()
        self.nodes: list[PlanNode] = []
        self.bindings: dict[str, str] = {}
        self.node_dependencies: dict[str, tuple[str, ...]] = {}
        self.declaration: dict[str, int] = {}
        self.issues: list[PlanIssue] = []
        self._reads: dict[str, str] = {}
        self._building: list[str] = []
        self._built: set[str] = set()
        self._aliases: dict[str, str] = {}

    def _params(self) -> Mapping[str, Any]:
        bound: dict[str, Any] = {}
        supplied = self.context.params or {}
        unknown = set(supplied) - set(self.recipe.spec.params)
        if unknown:
            raise RecipeCompileError(f"unknown context params: {sorted(unknown)}", origin=self.origin, code="unknown_param")
        for name, spec in self.recipe.spec.params.items():
            if name in supplied:
                value = supplied[name]
            elif spec.required:
                raise RecipeCompileError(f"missing required param {name!r}", origin=self.origin, code="missing_param")
            else:
                value = spec.default
            if value is not None:
                try:
                    value = {"int": int, "float": float, "str": str, "bool": bool}.get(spec.type, lambda x: x)(value)
                    if spec.type == "timedelta": value = pd.Timedelta(value)
                except (TypeError, ValueError) as exc:
                    raise RecipeCompileError(f"invalid value for param {name!r}: {exc}", origin=self.origin, code="invalid_param") from exc
            if spec.type == "enum" and value not in (spec.values or []):
                raise RecipeCompileError(f"invalid enum value for {name!r}", origin=self.origin, code="invalid_param")
            bound[name] = value
        return MappingProxyType(bound)

    def expand(self, value: Any, *, where: str) -> Any:
        if isinstance(value, list): return [self.expand(item, where=where) for item in value]
        if isinstance(value, Mapping): return {key: self.expand(item, where=where) for key, item in value.items()}
        if not isinstance(value, str): return value
        matches = list(_PLACEHOLDER.finditer(value))
        if not matches:
            if "{" in value or "}" in value:
                raise RecipeCompileError(f"invalid template {value!r} at {where}", origin=self.origin, code="template")
            return value
        if len(matches) == 1 and matches[0].span() == (0, len(value)):
            namespace, key = matches[0].groups()
            values = self.params if namespace == "params" else self.recipe.metadata.model_dump()
            if key not in values:
                raise RecipeCompileError(f"unknown template variable {namespace}.{key}", origin=self.origin, code="template")
            return values[key]
        def replace(match: re.Match[str]) -> str:
            namespace, key = match.groups(); values = self.params if namespace == "params" else self.recipe.metadata.model_dump()
            if key not in values: raise RecipeCompileError(f"unknown template variable {namespace}.{key}", origin=self.origin, code="template")
            return str(values[key])
        return _PLACEHOLDER.sub(replace, value)

    def _query(self, field: Any, path: str) -> FieldQuery:
        level = self.expand(field.level or {}, where=path + ".level")
        try:
            # Preserve legacy GRIB fixed-surface terms as explicit extra values.
            kwargs: dict[str, Any] = {}
            extra: dict[str, Any] = {}
            for key, value in level.items():
                if key in {"level_type", "level", "step_type", "time_range", "member"}: kwargs[key] = value
                else: extra[key] = value
            return resolve_parameter(field.parameter, extra=extra or None, **kwargs).query
        except Exception as exc:
            raise RecipeCompileError(f"cannot resolve field {field.parameter!r}: {exc}", origin=self.origin, code="field_query") from exc

    def _source_unit(self, field: Any) -> str | None:
        """Canonical unit comes from the parameter registry, never a style."""
        return resolve_parameter(field.parameter).record.unit

    def _read(self, query: FieldQuery, binding: str, origin: str, *, time_binding: TimeBinding | None = None) -> str:
        key = RequestKey(self.context.provider_slot, query, time_binding or TimeBinding(_time(self.context.start_time), _time(self.context.forecast_time)), self.context.cardinality)  # type: ignore[arg-type]
        rendered = json.dumps({"slot": key.provider_slot, "cardinality": key.cardinality, "time": key.time_binding.__dict__,
                               "query": _scalar({"parameter": query.parameter, "level_type": query.level_type, "level": query.level, "step_type": query.step_type, "time_range": query.time_range, "member": query.member, "extra": query.extra})}, sort_keys=True, default=str)
        if rendered in self._reads:
            node_id = self._reads[rendered]
            index = next(index for index, node in enumerate(self.nodes) if node.id == node_id)
            old = self.nodes[index]
            self.nodes[index] = replace(old, bindings=tuple(sorted(set(old.bindings) | {binding})),
                                        origin=min(old.origin, origin))
            return node_id
        node = self._node("read", (), origin, (binding,), request=key)
        self._reads[rendered] = node.id
        return node.id

    def _node(self, kind: str, dependencies: tuple[str, ...], origin: str, bindings: tuple[str, ...], **kwargs: Any) -> PlanNode:
        node = PlanNode(id=f"{kind}:pending:{len(self.nodes):04d}", kind=kind, dependencies=dependencies, origin=origin, bindings=bindings, **kwargs)  # type: ignore[arg-type]
        self.nodes.append(node); self.node_dependencies[node.id] = dependencies; self.declaration[node.id] = len(self.nodes)
        return node

    def compile(self) -> PlotPlan:
        # Register output aliases first, then recursively build bindings.  This
        # deliberately makes declaration order irrelevant while retaining a
        # readable cycle path.
        for name, entry in self.recipe.spec.data.items():
            for output in (entry.compute.outputs or [name]) if entry.compute else [name]:
                previous = self._aliases.setdefault(output, name)
                if previous != name:
                    raise RecipeCompileError(f"duplicate output {output!r}", origin=self.origin, code="duplicate_output")
        for name in self.recipe.spec.data:
            self._build(name)
        self._cycle_check()
        layer_outputs = self._layer_outputs()
        live = self._live(layer_outputs)
        dead = [node for node in self.nodes if node.id not in live]
        for node in dead: self.issues.append(PlanIssue("dead_node", f"binding(s) {node.bindings!r} are not consumed", node.origin))
        if dead and self.context.strict: raise RecipeCompileError("dead nodes found", origin=self.origin, code="dead_node")
        ordered = self._topological(live)
        ids = {old.id: f"{old.kind}:{index:04d}" for index, old in enumerate(ordered, 1)}
        normalized = tuple(PlanNode(id=ids[node.id], kind=node.kind, dependencies=tuple(ids[dep] for dep in node.dependencies if dep in ids), origin=node.origin, bindings=node.bindings, args=node.args, kwargs=node.kwargs, descriptor=node.descriptor, output_count=node.output_count, pure=node.pure, reusable=node.reusable, request=node.request) for node in ordered)
        outputs = MappingProxyType({name: ids[node] for name, node in self.bindings.items() if node in ids})
        layers = tuple(_freeze(layer) for layer in self._layer_dicts())
        return PlotPlan(self.recipe.metadata.name, self.recipe.api_version, "cedarkit.plots.compiler/v1", self.registry.manifest()["identity"], MappingProxyType({"start_time": _time(self.context.start_time), "forecast_time": _time(self.context.forecast_time), "params": dict(self.params), "provider_slot": self.context.provider_slot, "cardinality": self.context.cardinality}), normalized, outputs, layers, tuple(self.issues), tuple(node.id for node in normalized))

    def _descriptor(self, name: str, kind: str, inputs: int, path: str):
        try: descriptor = self.registry.get(name)
        except KeyError as exc: raise RecipeCompileError(str(exc), origin=self.origin, code="unknown_op") from exc
        if descriptor.kind != kind: raise RecipeCompileError(f"op {name!r} is {descriptor.kind}, not {kind}", origin=self.origin, code="op_kind")
        if descriptor.input_count != inputs: raise RecipeCompileError(f"op {name!r} requires {descriptor.input_count} inputs, got {inputs}", origin=self.origin, code="input_count")
        return descriptor

    def _build(self, name: str) -> str:
        if name in self._built:
            return self.bindings[name]
        if name in self._building:
            start = self._building.index(name)
            cycle = self._building[start:] + [name]
            raise RecipeCompileError("dependency cycle: " + " -> ".join(cycle), origin=self.origin, code="cycle")
        self._building.append(name)
        entry = self.recipe.spec.data[name]; path = f"spec.data.{name}"
        if entry.field:
            current = self._read(self._query(entry.field, path), name, path + ".field")
        else:
            assert entry.compute
            descriptor = self._descriptor(entry.compute.op, "compute", len(entry.compute.inputs), path + ".compute")
            deps = tuple(self._reference(ref, path + ".compute") for ref in entry.compute.inputs)
            produced = tuple(entry.compute.outputs or [name])
            if len(produced) != descriptor.output_count:
                raise RecipeCompileError(f"op {descriptor.name!r} returns {descriptor.output_count} values, recipe binds {len(produced)}", origin=self.origin, code="output_count")
            current = self._node("compute", deps, path + ".compute", produced, args=tuple(_freeze(self.expand(entry.compute.args, where=path))), kwargs=tuple(sorted((key, _freeze(value)) for key, value in self.expand(entry.compute.kwargs, where=path).items())), descriptor=descriptor.name, output_count=descriptor.output_count, pure=descriptor.pure, reusable=descriptor.reusable).id
            for output in produced: self.bindings[output] = current
        self.bindings[name] = current
        for index, transform in enumerate(entry.transforms):
            descriptor = self._descriptor(transform.op, "transform", 1, f"{path}.transforms.{index}")
            for _ in range(transform.repeat):
                args = tuple(_freeze(self.expand(transform.args, where=path)))
                if descriptor.planner:
                    call = _PlannerCall(current, args, tuple(sorted((key, _freeze(value)) for key, value in self.expand(transform.kwargs, where=path).items())), path + f".transforms.{index}")
                    try:
                        current = descriptor.planner(self, call, self.context)
                    except RecipeCompileError:
                        raise
                    except Exception as exc:
                        raise RecipeCompileError(f"planner for {descriptor.name!r} failed: {exc}", origin=self.origin, code="planner") from exc
                else:
                    current = self._node("transform", (current,), f"{path}.transforms.{index}", (name,), args=args, kwargs=tuple(sorted((key, _freeze(value)) for key, value in self.expand(transform.kwargs, where=path).items())), descriptor=descriptor.name, output_count=1, pure=descriptor.pure, reusable=descriptor.reusable).id
            self.bindings[name] = current
        if entry.units:
            source = self._source_unit(entry.field) if entry.field else None
            if source is None:
                raise RecipeCompileError(f"data {name!r} declares units but has no known source unit", origin=self.origin, code="units")
            try:
                scale, offset, target = conversion(source, entry.units)
            except ValueError as exc:
                raise RecipeCompileError(str(exc), origin=self.origin, code="units") from exc
            if (scale, offset) != (1, 0):
                current = self._node("convert_units", (current,), path + ".units", (name,), args=(scale, offset), kwargs=(("units", target),)).id
                self.bindings[name] = current
        self._building.pop(); self._built.add(name)
        return current

    def time_difference(self, call: Any, interval: Any, context: CompileContext) -> str:
        interval = pd.Timedelta(interval)
        if interval <= pd.Timedelta(0):
            raise RecipeCompileError("time_diff interval must be positive", origin=self.origin, code="planner")
        if context.forecast_time is None:
            raise RecipeCompileError("time_diff requires forecast_time", origin=self.origin, code="planner")
        forecast = pd.Timestamp(context.forecast_time)
        if context.start_time is not None and forecast - pd.Timestamp(context.start_time) < interval:
            raise RecipeCompileError("forecast_time is smaller than time_diff interval", origin=self.origin, code="planner")
        # The planner is deliberately restricted to graph data.  It derives a
        # second request from the input's concrete read; it cannot access a provider.
        source = self._read_ancestor(call.input_id)
        if source is None or source.request is None:
            raise RecipeCompileError("time_diff input has no field read ancestor", origin=self.origin, code="planner")
        earlier_time = _time(forecast - interval)
        key = RequestKey(source.request.provider_slot, source.request.query,
                         TimeBinding(source.request.time_binding.start_time, earlier_time), source.request.cardinality)
        previous = self._read(key.query, f"{source.bindings[0]}@-{interval}", call.origin + ".planner", time_binding=key.time_binding)
        return self._node("transform", (call.input_id, previous), call.origin + ".planner", (), args=(), kwargs=(), descriptor="time_diff", output_count=1, pure=True, reusable=True).id

    def _read_ancestor(self, node_id: str) -> PlanNode | None:
        node = next((item for item in self.nodes if item.id == node_id), None)
        if node is None: return None
        if node.kind == "read": return node
        for dep in node.dependencies:
            found = self._read_ancestor(dep)
            if found: return found
        return None

    def _reference(self, name: str, path: str) -> str:
        owner = self._aliases.get(name)
        if owner is None:
            raise RecipeCompileError(f"unknown input {name!r} at {path}", origin=self.origin, code="unknown_reference")
        self._build(owner)
        return self.bindings[name]

    def _bind(self, name: str, node: str, path: str) -> None:
        self.bindings[name] = node

    def _cycle_check(self) -> None:
        # A direct check over the binding dependency graph yields a readable closed binding path.
        dependencies = {name: [dep for dep, node in self.bindings.items() if node in self.node_dependencies.get(node_id, ())] for name, node_id in self.bindings.items()}
        # Node graph is the source of truth; Kahn below detects all practical cycles.
        try: self._topological(set(node.id for node in self.nodes))
        except RecipeCompileError: raise

    def _topological(self, live: set[str]) -> list[PlanNode]:
        by_id = {node.id: node for node in self.nodes}; indegree = {ident: sum(dep in live for dep in node.dependencies) for ident, node in by_id.items() if ident in live}; reverse: dict[str, list[str]] = defaultdict(list)
        for ident in live:
            for dep in by_id[ident].dependencies:
                if dep in live: reverse[dep].append(ident)
        tie = lambda ident: (by_id[ident].bindings, by_id[ident].kind, by_id[ident].origin, self.declaration[ident])
        ready = sorted((ident for ident, degree in indegree.items() if degree == 0), key=tie)
        result: list[PlanNode] = []
        while ready:
            ident = ready.pop(0); result.append(by_id[ident])
            for child in sorted(reverse[ident], key=lambda item: self.declaration[item]):
                indegree[child] -= 1
                if indegree[child] == 0: ready.append(child)
            ready.sort(key=tie)
        if len(result) != len(live):
            stuck = sorted(ident for ident, degree in indegree.items() if degree)
            raise RecipeCompileError("dependency cycle: " + " -> ".join(stuck + [stuck[0]]), origin=self.origin, code="cycle")
        return result

    def _layer_outputs(self) -> set[str]:
        result: set[str] = set()
        for index, layer in enumerate(self.recipe.spec.layers):
            refs = (layer.field,) if layer.field else (layer.vector.u, layer.vector.v)  # type: ignore[union-attr]
            for ref in refs:
                if ref not in self.bindings: raise RecipeCompileError(f"layer {index} references unknown output {ref!r}", origin=self.origin, code="unknown_reference")
                result.add(self.bindings[ref])
        return result

    def _live(self, outputs: set[str]) -> set[str]:
        by_id = {node.id: node for node in self.nodes}; live, todo = set(outputs), list(outputs)
        while todo:
            node = by_id[todo.pop()]
            for dep in node.dependencies:
                if dep not in live: live.add(dep); todo.append(dep)
        return live

    def _layer_dicts(self) -> list[dict[str, Any]]:
        result = []
        for index, layer in enumerate(self.recipe.spec.layers):
            refs = {"field": layer.field} if layer.field else {"vector": {"u": layer.vector.u, "v": layer.vector.v}}  # type: ignore[union-attr]
            result.append({"index": index, **refs, "style": layer.style.model_dump() if hasattr(layer.style, "model_dump") else layer.style, "layer": layer.layer})
        return result


def compile_recipe(recipe: RecipeV2 | LoadedRecipe, context: CompileContext, *, registry: OpRegistry | None = None, origin: str | None = None) -> PlotPlan:
    """Compile a normalized recipe with no provider I/O."""
    if isinstance(recipe, LoadedRecipe):
        origin = origin or recipe.origin; recipe = recipe.recipe
    return _Compiler(recipe, context, registry or OpRegistry.builtins(), origin or "<memory>").compile()


@dataclass(frozen=True)
class _PlannerCall:
    input_id: str
    args: tuple[Any, ...]
    kwargs: tuple[tuple[str, Any], ...]
    origin: str
