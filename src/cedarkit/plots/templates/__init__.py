"""Immutable presentation presets for the D08 plotting API.

Templates are configuration values only.  They do not own Charts, layers,
Matplotlib objects, callbacks, or any other rendering state.  The core
renderer receives the ordinary ``LayoutSpec``/``ChartSpec`` values produced
by these wrappers through :class:`~cedarkit.plots.config.resolve_config`.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from cedarkit.plots.config import (
    RESET,
    UNSET,
    ChartRule,
    ChartSpec,
    DecorationSpec,
    LayoutSpec,
    Theme,
)
from cedarkit.plots.errors import ConfigError


def _contains_reset(value: Any) -> bool:
    if value is RESET:
        return True
    if isinstance(value, Mapping):
        return any(_contains_reset(key) or _contains_reset(item) for key, item in value.items())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_reset(item) for item in value)
    if dataclasses.is_dataclass(value):
        return any(_contains_reset(getattr(value, field.name)) for field in dataclasses.fields(value))
    return False


def _reject_reset(value: Any) -> None:
    if _contains_reset(value):
        raise ConfigError(
            "RESET is only valid for user configuration patches, not templates",
            code="invalid_template",
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class ChartTemplate(ChartSpec):
    """A reusable Chart-scoped presentation configuration."""

    def __post_init__(self) -> None:
        ChartSpec.__post_init__(self)
        _reject_reset(self)

    def to_chart_spec(self) -> ChartSpec:
        """Return an ordinary ``ChartSpec`` without creating runtime state."""

        return ChartSpec(
            subplots=self.subplots,
            theme=self.theme,
            decorations=self.decorations,
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class PanelTemplate:
    """A reusable Panel-scoped presentation configuration."""

    layout: LayoutSpec | Any = UNSET
    theme: Theme | Any = UNSET
    chart_defaults: ChartTemplate | ChartSpec | Any = UNSET
    chart_rules: Sequence[ChartRule] | Any = UNSET
    decorations: DecorationSpec | Any = UNSET

    def __post_init__(self) -> None:
        _reject_reset(self)
        if self.layout is not UNSET and not isinstance(self.layout, LayoutSpec):
            raise ConfigError("PanelTemplate.layout must be LayoutSpec", code="invalid_template")
        if self.theme is not UNSET and not isinstance(self.theme, Theme):
            raise ConfigError("PanelTemplate.theme must be Theme", code="invalid_template")
        if self.decorations is not UNSET and not isinstance(self.decorations, DecorationSpec):
            raise ConfigError(
                "PanelTemplate.decorations must be DecorationSpec",
                code="invalid_template",
            )
        defaults = self.chart_defaults
        if isinstance(defaults, ChartTemplate):
            defaults = defaults.to_chart_spec()
        elif defaults is not UNSET and not isinstance(defaults, ChartSpec):
            raise ConfigError(
                "PanelTemplate.chart_defaults must be ChartTemplate or ChartSpec",
                code="invalid_template",
            )
        if defaults is not self.chart_defaults:
            object.__setattr__(self, "chart_defaults", defaults)
        if self.chart_rules is not UNSET:
            if isinstance(self.chart_rules, (str, bytes)) or not isinstance(self.chart_rules, Sequence):
                raise ConfigError(
                    "PanelTemplate.chart_rules must be a sequence",
                    code="invalid_template",
                )
            rules = tuple(self.chart_rules)
            if any(not isinstance(rule, ChartRule) for rule in rules):
                raise ConfigError(
                    "PanelTemplate.chart_rules must contain ChartRule values",
                    code="invalid_template",
                )
            object.__setattr__(self, "chart_rules", rules)


from .east_asia import east_asia, east_asia_chart
from .ens_cn import ens_cn, ens_cn_chart, ens_cn_layout


__all__ = [
    "ChartTemplate",
    "PanelTemplate",
    "east_asia",
    "east_asia_chart",
    "ens_cn",
    "ens_cn_chart",
    "ens_cn_layout",
]
