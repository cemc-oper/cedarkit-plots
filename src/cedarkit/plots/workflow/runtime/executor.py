"""Run a compiled DAG with execution-local, materialized xarray values."""

from __future__ import annotations

import inspect
from typing import Any

import xarray as xr

from ...ops import OpRegistry
from ...ops.descriptor import OpRuntimeContext
from ...units import canonical_unit, prepare_field
from ..plan.model import BoundFieldRequest, PlanNode, WorkflowPlan
from .model import NodeTrace, PlanExecutionError, WorkflowResult


def _owned(value: Any) -> xr.DataArray:
    if not isinstance(value, xr.DataArray):
        raise TypeError(f"workflow data must be xarray.DataArray, got {type(value).__name__}")
    return value.copy(deep=True).load()


def _input(value: Any, slot: int) -> xr.DataArray:
    if isinstance(value, tuple):
        return _owned(value[slot])
    if slot:
        raise IndexError(f"single-output node has no slot {slot}")
    return _owned(value)


def _operation(node: PlanNode, inputs: list[xr.DataArray], registry: OpRegistry,
               plan: WorkflowPlan) -> Any:
    descriptor = registry.get(node.descriptor)
    kwargs = dict(node.kwargs)
    signature = inspect.signature(descriptor.callable)
    if "context" in signature.parameters or any(parameter.kind == parameter.VAR_KEYWORD
                                                  for parameter in signature.parameters.values()):
        kwargs["context"] = OpRuntimeContext(plan.recipe_identity, node.id, plan.context)
    return descriptor.callable(*inputs, *node.args, **kwargs)


def execute_plan(plan: WorkflowPlan, provider: Any, *, registry: OpRegistry | None = None) -> WorkflowResult:
    """Fetch, compute, and prepare values once; never create a Figure or Panel."""
    active_registry = registry or OpRegistry.builtins()
    if active_registry.manifest()["identity"] != plan.descriptor_identity:
        raise ValueError(f"product={plan.recipe_identity}: op registry differs from compiled plan")
    nodes = {node.id: node for node in plan.nodes}
    values: dict[str, Any] = {}
    trace: list[NodeTrace] = []

    def failure(node: PlanNode, message: str, cause: Exception) -> PlanExecutionError:
        failed = NodeTrace(node.id, node.kind, "error", node.origin)
        return PlanExecutionError(node.id, plan.recipe_identity, node.origin, f"{message}: {cause}",
                                  trace=(*trace, failed), cause=cause)

    for batch in plan.read_batches:
        requests = tuple(BoundFieldRequest(node_id, nodes[node_id].request, nodes[node_id].origin)
                         for node_id in batch)
        try:
            if hasattr(provider, "fetch_many"):
                fetched = tuple(provider.fetch_many(requests))
                if len(fetched) != len(requests):
                    raise ValueError(f"provider returned {len(fetched)} values for {len(requests)} requests")
            else:
                fetched = tuple(provider.fetch(request) for request in requests)
            for request, value in zip(requests, fetched):
                node = nodes[request.node_id]
                try:
                    values[node.id] = _owned(value)
                except Exception as exc:
                    raise failure(node, "invalid field value", exc) from exc
                trace.append(NodeTrace(node.id, "read", "ok", node.origin))
        except PlanExecutionError:
            raise
        except Exception as exc:
            raise failure(nodes[batch[0]], "provider fetch failed", exc) from exc

    for node in plan.nodes:
        if node.kind == "read":
            continue
        try:
            slots = node.input_slots or (0,) * len(node.dependencies)
            inputs = [_input(values[dependency], slot) for dependency, slot in zip(node.dependencies, slots)]
            if node.kind == "convert_units":
                options = dict(node.kwargs)
                output = prepare_field(inputs[0], units=options["units"],
                                       source_units=options["source_units"],
                                       temperature_kind=options["temperature_kind"]).field
            else:
                if node.descriptor == "time_diff":
                    first_unit, second_unit = (item.attrs.get("units") for item in inputs)
                    if (first_unit is not None and second_unit is not None
                            and canonical_unit(first_unit) != canonical_unit(second_unit)):
                        raise ValueError(f"time_diff source units differ: {first_unit!r} and {second_unit!r}")
                output = _operation(node, inputs, active_registry, plan)
            if node.output_count == 1:
                values[node.id] = _owned(output)
            else:
                produced = tuple(output)
                if len(produced) != node.output_count:
                    raise ValueError(f"operation returned {len(produced)} outputs; expected {node.output_count}")
                values[node.id] = tuple(_owned(item) for item in produced)
            trace.append(NodeTrace(node.id, node.kind, "ok", node.origin))
        except Exception as exc:
            raise failure(node, "operation failed", exc) from exc

    outputs = {name: _input(values[node_id], plan.output_slots[name])
               for name, node_id in plan.outputs.items()}
    return WorkflowResult.create(plan.recipe_identity, values, outputs, plan.content,
                                 plan.display, tuple(trace), plan.issues)
