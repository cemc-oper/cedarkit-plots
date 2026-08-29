"""Execution of a compiled :class:`PlotPlan`, with no recipe interpretation."""

from __future__ import annotations

from collections import defaultdict
import inspect
from typing import Any

from ..ops import OpRegistry
from ..ops.descriptor import OpRuntimeContext
from .provider import BoundFieldRequest
from .result import NodeTrace, PlanResult


class PlanExecutionError(RuntimeError):
    def __init__(self, node_id: str, message: str, cause: Exception | None = None):
        self.node_id, self.cause = node_id, cause
        super().__init__(f"plan node {node_id}: {message}")


def _requests(plan: Any) -> list[BoundFieldRequest]:
    return [BoundFieldRequest(node.id, node.request, node.origin) for node in plan.nodes if node.kind == "read" and node.request]


def _fetch_reads(plan: Any, provider: Any) -> dict[str, Any]:
    requests = _requests(plan)
    values: dict[str, Any] = {}
    groups: dict[tuple[str, object], list[BoundFieldRequest]] = defaultdict(list)
    for request in requests:
        groups[(request.key.provider_slot, request.key.time_binding)].append(request)
    for group in groups.values():
        try:
            if hasattr(provider, "fetch_many"):
                result = list(provider.fetch_many(tuple(group)))
                if len(result) != len(group):
                    raise PlanExecutionError(group[0].node_id, f"provider returned {len(result)} results for {len(group)} requests")
                values.update({request.node_id: item for request, item in zip(group, result)})
            else:
                for request in group:
                    values[request.node_id] = provider.fetch(request)
        except PlanExecutionError:
            raise
        except Exception as exc:
            raise PlanExecutionError(group[0].node_id, "provider fetch failed", exc) from exc
    return values


def execute_plan(plan: Any, provider: Any, *, registry: OpRegistry | None = None) -> PlanResult:
    """Execute immutable ``plan`` with execution-local values only."""
    registry = registry or OpRegistry.builtins()
    values = _fetch_reads(plan, provider)
    trace: list[NodeTrace] = [NodeTrace(node_id, "read", "ok") for node_id in values]
    for node in plan.nodes:
        if node.kind == "read":
            continue
        try:
            inputs = [values[dep] for dep in node.dependencies]
            if node.kind == "convert_units":
                value = inputs[0] * node.args[0] + node.args[1]
                if hasattr(value, "attrs"):
                    value = value.copy()
                    value.attrs = dict(value.attrs)
                    value.attrs["units"] = node.kwargs[0][1]
            else:
                descriptor = registry.get(node.descriptor)
                context = OpRuntimeContext(plan.recipe_identity, node.id, plan.context)
                kwargs = dict(node.kwargs)
                signature = inspect.signature(descriptor.callable)
                if "context" in signature.parameters or any(param.kind == param.VAR_KEYWORD for param in signature.parameters.values()):
                    kwargs["context"] = context
                value = descriptor.callable(*inputs, *node.args, **kwargs)
            if node.output_count == 1:
                values[node.id] = value
            else:
                result = tuple(value)
                if len(result) != node.output_count:
                    raise ValueError(f"op returned {len(result)} values, expected {node.output_count}")
                values[node.id] = result
            trace.append(NodeTrace(node.id, node.kind, "ok"))
        except Exception as exc:
            raise PlanExecutionError(node.id, "operation failed", exc) from exc
    nodes = {node.id: node for node in plan.nodes}

    def output_value(name: str, node_id: str) -> Any:
        """Resolve a public binding to its declared operation output slot."""
        node = nodes[node_id]
        value = values[node_id]
        if node.output_count == 1 or name not in node.bindings:
            return value
        try:
            return value[node.bindings.index(name)]
        except ValueError as exc:  # Defensive: compiler owns this invariant.
            raise PlanExecutionError(node_id, f"output {name!r} has no declared slot") from exc

    outputs = {name: output_value(name, node_id) for name, node_id in plan.outputs.items()}
    layers = tuple({**layer, "value": outputs.get(layer.get("field"))} for layer in plan.layers)
    return PlanResult.create(values, outputs, layers, tuple(trace))
