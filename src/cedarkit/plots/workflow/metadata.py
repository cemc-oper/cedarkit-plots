"""Value-only formatting for workflow declarations and presentation text."""

from __future__ import annotations

import re
from typing import Any, Mapping

_VARIABLE = re.compile(r"\{(params|metadata|context)\.([A-Za-z][A-Za-z0-9_-]*)\}")


def format_value(value: Any, *, params: Mapping[str, Any], metadata: Mapping[str, Any],
                 context: Mapping[str, Any], path: str) -> Any:
    """Resolve declared placeholders while retaining types for whole values."""
    if isinstance(value, Mapping):
        return {key: format_value(item, params=params, metadata=metadata, context=context,
                                  path=f"{path}.{key}") for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(format_value(item, params=params, metadata=metadata, context=context,
                                  path=f"{path}.{index}") for index, item in enumerate(value))
    if not isinstance(value, str):
        return value
    matches = list(_VARIABLE.finditer(value))
    if not matches:
        if "{" in value or "}" in value:
            raise ValueError(f"invalid placeholder at {path}: {value!r}")
        return value
    namespaces = {"params": params, "metadata": metadata, "context": context}

    def lookup(match: re.Match[str]) -> Any:
        namespace, key = match.groups()
        if key not in namespaces[namespace]:
            raise ValueError(f"unknown placeholder {namespace}.{key} at {path}")
        return namespaces[namespace][key]

    if len(matches) == 1 and matches[0].span() == (0, len(value)):
        return lookup(matches[0])
    result = _VARIABLE.sub(lambda match: str(lookup(match)), value)
    if "{" in result or "}" in result:
        raise ValueError(f"invalid placeholder at {path}: {value!r}")
    return result
