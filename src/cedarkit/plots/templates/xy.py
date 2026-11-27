"""Configuration-only presets for ordinary XY and time-profile plots."""

from __future__ import annotations

from collections.abc import Sequence
from math import ceil
from typing import Any

import numpy as np
import pandas as pd

from cedarkit.plots.config import (
    AxisSpec,
    DecorationSpec,
    GridlineSpec,
    LayoutSpec,
    Rect,
    SubplotSpec,
    TextPosition,
    Theme,
    TimeStepFormatter,
    TitleSpec,
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
    xlabel: str | None = None,
    ylabel: str | None = None,
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
        xlabel=xlabel,
        ylabel=ylabel,
        invert_y=invert_y,
        xformatter=xformatter,
        yformatter=yformatter,
        gridlines=gridlines,
    )
    return ChartTemplate(
        subplots={
            "main": SubplotSpec(
                kind="xy",
                position=Rect(space="chart", bounds=(.06, .07, .88, .85)),
                axis=axis,
                aspect=aspect,
            ),
        },
    )


def xy(**kwargs: Any) -> PanelTemplate:
    """Return a one-Chart Panel preset for :func:`xy_chart`."""

    return PanelTemplate(
        layout=LayoutSpec(rows=1, columns=1, figsize=(8.8, 5.8), expected_charts=1),
        theme=Theme(),
        chart_defaults=xy_chart(**kwargs),
        decorations=DecorationSpec(),
    )


def time_profile_chart(
    steps: Sequence[float],
    levels: Sequence[float],
    start_time: Any,
) -> ChartTemplate:
    """Lay out forecast time in UTC and pressure decreasing upwards."""

    steps = _sequence(steps, "steps")
    levels = _sequence(levels, "levels")
    start = pd.Timestamp(start_time)
    if pd.isna(start):
        raise ConfigError("start_time must be a valid timestamp", code="invalid_template", path=("start_time",))
    start = start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")
    first, last = min(steps), max(steps)
    span = last - first
    frequency = pd.Timedelta(hours=max(12, 12 * ceil(span / 120)))
    begin = start + pd.Timedelta(hours=first)
    end = start + pd.Timedelta(hours=last)
    regular = (pd.date_range(begin.ceil(frequency), end.floor(frequency), freq=frequency) - start)
    # The endpoint labels include dates and need more horizontal space.
    gap = min(6, span / 14)
    xticks = tuple(sorted({first, last, *(
        step for step in regular / pd.Timedelta(hours=1) if first + gap < step < last - gap
    )}))
    low, high = min(levels), max(levels)
    chart = xy_chart(
        xlim=(first, last) if first != last else None,
        ylim=(low, high) if low != high else None,
        xticks=xticks,
        yticks=levels,
        xlabel="Valid time (UTC)",
        ylabel="Pressure (hPa)",
        invert_y=True,
        xformatter=TimeStepFormatter(start_time=start, last_step=last),
        gridlines=GridlineSpec(color="#75808a", linewidth=.35, alpha=.4),
    )
    return ChartTemplate(
        subplots=chart.subplots,
        decorations=DecorationSpec(titles={
            "title": TitleSpec(position=TextPosition(space="subplot", xy=(0, 1.025), ha="left", va="bottom")),
            "init": TitleSpec(position=TextPosition(space="subplot", xy=(1, 1.025), ha="right", va="bottom"), fontsize=10),
        }),
    )


def time_profile(
    steps: Sequence[float],
    levels: Sequence[float],
    start_time: Any,
) -> PanelTemplate:
    """Return a one-Chart Panel preset for :func:`time_profile_chart`."""

    return PanelTemplate(
        layout=LayoutSpec(rows=1, columns=1, figsize=(9.4, 5.8), expected_charts=1),
        theme=Theme(),
        chart_defaults=time_profile_chart(steps, levels, start_time),
        decorations=DecorationSpec(),
    )


__all__ = ["time_profile", "time_profile_chart", "xy", "xy_chart"]
