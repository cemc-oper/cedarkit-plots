"""Configuration-only presets for ordinary XY and time-profile plots."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from cedarkit.plots.config import (
    AxisSpec,
    DecorationSpec,
    GridlineSpec,
    LayoutSpec,
    SubplotSpec,
    Theme,
    TimeStepFormatter,
)
from cedarkit.plots.errors import ConfigError

from . import ChartTemplate, PanelTemplate


def _sequence(value: Any, name: str, *, allow_empty: bool = False) -> tuple[float, ...]:
    if isinstance(value, (str, bytes)):
        raise ConfigError(
            f"{name} must be a numeric sequence",
            code="invalid_template",
            path=(name,),
        )
    try:
        values = tuple(value)
    except TypeError as exc:
        raise ConfigError(
            f"{name} must be a numeric sequence",
            code="invalid_template",
            path=(name,),
        ) from exc
    if not values and not allow_empty:
        raise ConfigError(
            f"{name} must not be empty",
            code="invalid_template",
            path=(name,),
        )
    try:
        result = tuple(float(item) for item in values)
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            f"{name} must be a numeric sequence",
            code="invalid_template",
            path=(name,),
        ) from exc
    if not np.all(np.isfinite(result)):
        raise ConfigError(
            f"{name} must contain finite values",
            code="invalid_template",
            path=(name,),
        )
    return result


def xy_chart(
    *,
    xlim: Sequence[float] | None = None,
    ylim: Sequence[float] | None = None,
    xticks: Sequence[float] | None = None,
    yticks: Sequence[float] | None = None,
    invert_y: bool = False,
    xformatter: str | TimeStepFormatter | None = None,
    yformatter: str | TimeStepFormatter | None = None,
    gridlines: GridlineSpec | None = None,
    aspect: str | float = "auto",
) -> ChartTemplate:
    """Return a normal XY ``ChartTemplate`` without map configuration."""

    if not isinstance(invert_y, bool):
        raise ConfigError(
            "invert_y must be bool",
            code="invalid_template",
            path=("invert_y",),
        )
    if gridlines is not None and not isinstance(gridlines, GridlineSpec):
        raise ConfigError(
            "gridlines must be GridlineSpec or None",
            code="invalid_template",
            path=("gridlines",),
        )
    normalized_xlim = None if xlim is None else _sequence(xlim, "xlim")
    normalized_ylim = None if ylim is None else _sequence(ylim, "ylim")
    if normalized_xlim is not None and len(normalized_xlim) != 2:
        raise ConfigError("xlim must contain two values", code="invalid_template", path=("xlim",))
    if normalized_ylim is not None and len(normalized_ylim) != 2:
        raise ConfigError("ylim must contain two values", code="invalid_template", path=("ylim",))
    normalized_xticks = None if xticks is None else _sequence(xticks, "xticks", allow_empty=True)
    normalized_yticks = None if yticks is None else _sequence(yticks, "yticks", allow_empty=True)
    axis = AxisSpec(
        xlim=normalized_xlim,
        ylim=normalized_ylim,
        xticks=normalized_xticks,
        yticks=normalized_yticks,
        invert_y=invert_y,
        xformatter=xformatter,
        yformatter=yformatter,
        gridlines=gridlines,
    )
    return ChartTemplate(
        subplots={
            "main": SubplotSpec(
                kind="xy",
                axis=axis,
                aspect=aspect,
            ),
        },
    )


def xy(**kwargs: Any) -> PanelTemplate:
    """Return a one-Chart Panel preset for :func:`xy_chart`."""

    return PanelTemplate(
        layout=LayoutSpec(rows=1, columns=1, expected_charts=1),
        theme=Theme(),
        chart_defaults=xy_chart(**kwargs),
        decorations=DecorationSpec(),
    )


def time_profile_chart(
    steps: Sequence[float],
    levels: Sequence[float],
    start_time: Any,
) -> ChartTemplate:
    """Return the D01 time-step/level XY configuration.

    Tick labels retain the old behavior: every 00Z tick includes the day and
    month, and the final step additionally includes the year.
    """

    steps = _sequence(steps, "steps")
    levels = _sequence(levels, "levels")
    xticks = tuple(float(value) for value in np.arange(0, steps[-1] + 1, 12))
    return xy_chart(
        xticks=xticks,
        yticks=levels,
        xformatter=TimeStepFormatter(start_time=start_time, last_step=steps[-1]),
    )


def time_profile(
    steps: Sequence[float],
    levels: Sequence[float],
    start_time: Any,
) -> PanelTemplate:
    """Return a one-Chart Panel preset for :func:`time_profile_chart`."""

    return PanelTemplate(
        layout=LayoutSpec(rows=1, columns=1, expected_charts=1),
        theme=Theme(),
        chart_defaults=time_profile_chart(steps, levels, start_time),
        decorations=DecorationSpec(),
    )


__all__ = ["time_profile", "time_profile_chart", "xy", "xy_chart"]
