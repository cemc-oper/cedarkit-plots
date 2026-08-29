"""Public immutable plot-plan representation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from .issues import PlanIssue
from .nodes import PlanNode, RequestKey


def _json_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_value(value[key]) for key in sorted(value, key=str)}
    return value


def _request_dict(key: RequestKey) -> dict[str, Any]:
    query = key.query
    return {"provider_slot": key.provider_slot, "cardinality": key.cardinality,
            "time_binding": _json_value(key.time_binding.__dict__),
            "query": _json_value({"parameter": query.parameter, "level_type": query.level_type,
                                  "level": query.level, "step_type": query.step_type,
                                  "time_range": query.time_range, "member": query.member,
                                  "extra": query.extra})}


@dataclass(frozen=True)
class PlotPlan:
    recipe_identity: str
    recipe_version: str
    compiler_version: str
    descriptor_identity: str
    context: Mapping[str, Any]
    nodes: tuple[PlanNode, ...]
    outputs: Mapping[str, str]
    layers: tuple[Mapping[str, Any], ...]
    issues: tuple[PlanIssue, ...]
    executable_node_ids: tuple[str, ...]

    @property
    def read_count(self) -> int:
        return sum(node.kind == "read" for node in self.nodes if node.id in self.executable_node_ids)

    def consumers(self, node_id: str) -> tuple[str, ...]:
        """Return stable binding names directly served by a plan node."""
        for node in self.nodes:
            if node.id == node_id:
                return tuple(sorted(node.bindings))
        raise KeyError(f"unknown plan node {node_id!r}")

    def summary(self) -> str:
        text = (f"PlotPlan(recipe={self.recipe_identity!r}, nodes={len(self.nodes)}, "
                f"executable={len(self.executable_node_ids)}, reads={self.read_count}, "
                f"issues={len(self.issues)})")
        return text[:2000]

    def __repr__(self) -> str:
        return self.summary()

    def to_dict(self) -> dict[str, Any]:
        nodes = []
        for node in self.nodes:
            item = {"id": node.id, "kind": node.kind, "dependencies": list(node.dependencies),
                    "origin": node.origin, "bindings": list(node.bindings), "args": _json_value(node.args),
                    "kwargs": _json_value(dict(node.kwargs)), "descriptor": node.descriptor,
                    "output_count": node.output_count, "pure": node.pure, "reusable": node.reusable}
            if node.request:
                item["request"] = _request_dict(node.request)
            nodes.append(item)
        return {"plan_schema_version": 1, "recipe": {"identity": self.recipe_identity,
                "api_version": self.recipe_version}, "compiler_version": self.compiler_version,
                "descriptor_identity": self.descriptor_identity, "context": _json_value(self.context),
                "nodes": nodes, "outputs": dict(sorted(self.outputs.items())), "layers": [_json_value(x) for x in self.layers],
                "issues": [issue.__dict__ for issue in self.issues],
                "executable_node_ids": list(self.executable_node_ids)}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def execute(self, provider: Any, **kwargs: Any) -> Any:
        from .executor import execute_plan
        return execute_plan(self, provider, **kwargs)

    def check_available(self, provider: Any | None = None) -> Any:
        from .availability import check_available
        return check_available(self, provider)
