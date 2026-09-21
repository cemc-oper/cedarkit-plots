"""The D04 logical content model and minimal XY renderer.

The legacy template implementation remains in :mod:`.panel` and
:mod:`.chart`.  ``Panel`` below is a small compatibility facade: a new
``Panel()`` owns logical configuration and content until ``render()``, while
``Panel(domain=...)`` delegates to the legacy implementation used by the
pre-D04 API.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import cartopy.crs as ccrs
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
from matplotlib.artist import Artist
from matplotlib.figure import Figure
import numpy as np
import xarray as xr

from cedarkit.plots.config import (
    UNSET,
    AxisSpec,
    ChartSpec,
    ConfigError,
    DecorationSpec,
    LayoutSpec,
    SubplotSpec,
    Theme,
    merge_config,
    resolve_config,
    validate_config,
)
from cedarkit.plots.errors import ClosedError, ContentError, RenderError, RenderRequiredError
from cedarkit.plots.style import BarbStyle, ContourStyle, Style


def _content_error(message: str, *, code: str = "invalid_content", path: tuple[str, ...] = ()) -> None:
    raise ContentError(message, code=code, path=path)


def _closed_error() -> None:
    raise ClosedError("Panel is closed")


def _check_id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        _content_error(f"{name} must be a non-empty string without whitespace", code="invalid_id")
    return value


def _copy_style(style: Style) -> Style:
    if not isinstance(style, Style):
        _content_error("style must be a Style instance", code="invalid_style")
    try:
        return copy.deepcopy(style)
    except Exception as exc:  # pragma: no cover - defensive for third-party styles
        raise ContentError("style could not be snapshotted", code="invalid_style") from exc


def _check_crs(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, ccrs.CRS):
        _content_error("data_crs must be a Cartopy CRS or None", code="invalid_crs")
    return copy.deepcopy(value)


def _normalise_targets(value: Any) -> str | tuple[str, ...]:
    if isinstance(value, str):
        if value == "all" or value:
            return value
        _content_error("subplots cannot be an empty string", code="invalid_target")
    if isinstance(value, (list, tuple)):
        if not value:
            _content_error("subplots must contain at least one target", code="invalid_target")
        result = tuple(_check_id(item, "subplot target") for item in value)
        if "all" in result:
            _content_error("'all' cannot be combined with named subplot targets", code="invalid_target")
        return result
    _content_error("subplots must be a subplot ID, 'all', or a tuple/list of IDs", code="invalid_target")


def _validate_zorder(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        _content_error("zorder must be a finite number", code="invalid_zorder")
    return float(value)


def _validate_data(method: str, data: Any) -> None:
    if method in {"contourf", "contour"}:
        if not isinstance(data, xr.DataArray):
            _content_error(f"{method} data must be an xarray.DataArray", code="invalid_data")
    else:
        if (
            not isinstance(data, tuple)
            or len(data) != 2
            or not all(isinstance(item, xr.DataArray) for item in data)
        ):
            _content_error("barbs data must be a strict (u, v) DataArray tuple", code="invalid_data")


def _layer_targets(layer: "PlotLayer", spec: ChartSpec) -> tuple[str, ...]:
    subplots = spec.subplots
    enabled = tuple(key for key, value in subplots.items() if value.enabled)
    value = layer.subplots
    if value == "all":
        return enabled
    if isinstance(value, str):
        targets = (value,)
    else:
        targets = value
    missing = tuple(target for target in targets if target not in subplots or not subplots[target].enabled)
    if missing:
        _content_error(
            f"layer {layer.id!r} targets missing or disabled subplots {missing!r}",
            code="missing_target",
            path=("charts", layer.chart.id, "subplots"),
        )
    return tuple(targets)


@dataclass(frozen=True, slots=True)
class LayerResult:
    """Read-only result values for one logical layer and one target subplot."""

    artists: tuple[Artist, ...]
    mappable: Any
    generation: int


class Subplot:
    """A successful-render subplot result."""

    def __init__(self, chart: "Chart", subplot_id: str, ax: Any, generation: int) -> None:
        self._chart = chart
        self._id = subplot_id
        self._ax = ax
        self._generation = generation

    @property
    def id(self) -> str:
        return self._id

    @property
    def chart(self) -> "Chart":
        return self._chart

    @property
    def ax(self) -> Any:
        self._chart._ensure_current_results()
        return self._ax

    @property
    def generation(self) -> int:
        return self._generation


class MapSubplot(Subplot):
    """Reserved runtime subtype for D06 map rendering."""

    def __init__(self, chart: "Chart", subplot_id: str, ax: Any, generation: int, domain: Any, map_crs: Any) -> None:
        super().__init__(chart, subplot_id, ax, generation)
        self.domain = domain
        self.map_crs = map_crs


class PlotLayer:
    """Stable logical content handle; drawing is deferred until Panel.render."""

    def __init__(
        self,
        chart: "Chart",
        layer_id: str,
        method: str,
        data: Any,
        style: Style,
        subplots: str | tuple[str, ...],
        data_crs: Any,
        zorder: float,
        vector_basis: str | None,
    ) -> None:
        self._chart = chart
        self._id = layer_id
        self._method = method
        self._data = data
        self._style = _copy_style(style)
        self._subplots = subplots
        self._data_crs = data_crs
        self._zorder = zorder
        self._vector_basis = vector_basis
        self._results: Mapping[str, LayerResult] = MappingProxyType({})
        self._removed = False

    def _ensure_available(self) -> None:
        if self._removed:
            _content_error(f"layer {self._id!r} has been removed", code="removed_layer")
        self._chart._ensure_open()

    @property
    def id(self) -> str:
        return self._id

    @property
    def chart(self) -> "Chart":
        return self._chart

    @property
    def method(self) -> str:
        return self._method

    @property
    def data(self) -> Any:
        self._ensure_available()
        return self._data

    @property
    def style(self) -> Style:
        self._ensure_available()
        return self._style

    @property
    def subplots(self) -> str | tuple[str, ...]:
        self._ensure_available()
        return self._subplots

    @property
    def data_crs(self) -> Any:
        self._ensure_available()
        return self._data_crs

    @property
    def zorder(self) -> float:
        self._ensure_available()
        return self._zorder

    @property
    def vector_basis(self) -> str | None:
        self._ensure_available()
        return self._vector_basis

    @property
    def results(self) -> Mapping[str, LayerResult]:
        self._ensure_available()
        self._chart._ensure_current_results()
        return self._results

    def update(
        self,
        *,
        data: Any = UNSET,
        style: Style | Any = UNSET,
        subplots: Any = UNSET,
        data_crs: Any = UNSET,
        vector_basis: Any = UNSET,
        zorder: Any = UNSET,
    ) -> None:
        self._ensure_available()
        self._chart.panel._update_layer(
            self,
            data=self._data if data is UNSET else data,
            style=self._style if style is UNSET else style,
            subplots=self._subplots if subplots is UNSET else subplots,
            data_crs=self._data_crs if data_crs is UNSET else data_crs,
            vector_basis=self._vector_basis if vector_basis is UNSET else vector_basis,
            zorder=self._zorder if zorder is UNSET else zorder,
        )

    def remove(self) -> None:
        self._ensure_available()
        self._chart.panel._remove_layer(self)

    def _set_results(self, results: Mapping[str, LayerResult]) -> None:
        self._results = MappingProxyType(dict(results))

    def _clear_results(self) -> None:
        self._results = MappingProxyType({})


class Chart:
    """A stable logical Chart owned by a new-API Panel."""

    def __init__(self, panel: "_PanelImpl", chart_id: str, role: str | None = None) -> None:
        self._panel = panel
        self._id = chart_id
        self._role = role
        self._layers: dict[str, PlotLayer] = {}
        self._used_layer_ids: set[str] = set()
        self._next_layer_number = 1
        self._config = ChartSpec()
        self._subplots: Mapping[str, Subplot] = MappingProxyType({})
        self._titles: dict[str, str] = {}
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed or self._panel.closed:
            _closed_error()

    def _ensure_current_results(self) -> None:
        self._ensure_open()
        if self._panel.dirty or not self._subplots:
            raise RenderRequiredError("render is required before reading current results")

    @property
    def id(self) -> str:
        return self._id

    @property
    def role(self) -> str | None:
        return self._role

    @property
    def panel(self) -> "Panel":
        return self._panel.public_panel

    @property
    def layers(self) -> Mapping[str, PlotLayer]:
        self._ensure_open()
        return MappingProxyType(self._layers)

    @property
    def subplots(self) -> Mapping[str, Subplot]:
        self._ensure_current_results()
        return self._subplots

    @property
    def main(self) -> Subplot:
        self._ensure_current_results()
        try:
            return self._subplots["main"]
        except KeyError as exc:
            raise RenderRequiredError("main subplot is not available") from exc

    def configure(
        self,
        *,
        subplots: Any = UNSET,
        theme: Any = UNSET,
        decorations: Any = UNSET,
    ) -> None:
        self._ensure_open()
        patch = ChartSpec(subplots=subplots, theme=theme, decorations=decorations)
        self._panel._configure_chart(self, patch)

    def contourf(
        self,
        data: xr.DataArray,
        *,
        style: ContourStyle,
        id: str | None = None,
        subplots: Any = "main",
        data_crs: Any = None,
        zorder: float = 1,
    ) -> PlotLayer:
        return self._add_layer("contourf", data, style, id, subplots, data_crs, zorder, None)

    def contour(
        self,
        data: xr.DataArray,
        *,
        style: ContourStyle,
        id: str | None = None,
        subplots: Any = "main",
        data_crs: Any = None,
        zorder: float = 2,
    ) -> PlotLayer:
        return self._add_layer("contour", data, style, id, subplots, data_crs, zorder, None)

    def barbs(
        self,
        u: xr.DataArray,
        v: xr.DataArray,
        *,
        style: BarbStyle,
        id: str | None = None,
        subplots: Any = "main",
        data_crs: Any = None,
        vector_basis: str = "grid",
        zorder: float = 3,
    ) -> PlotLayer:
        return self._add_layer("barbs", (u, v), style, id, subplots, data_crs, zorder, vector_basis)

    def _add_layer(
        self,
        method: str,
        data: Any,
        style: Style,
        layer_id: str | None,
        subplots: Any,
        data_crs: Any,
        zorder: float,
        vector_basis: str | None,
    ) -> PlotLayer:
        self._ensure_open()
        if layer_id is None:
            while f"plot_{self._next_layer_number}" in self._used_layer_ids:
                self._next_layer_number += 1
            layer_id = f"plot_{self._next_layer_number}"
            self._next_layer_number += 1
        _check_id(layer_id, "layer id")
        if layer_id in self._used_layer_ids:
            _content_error(f"duplicate or reused layer id {layer_id!r}", code="duplicate_id")
        _validate_data(method, data)
        targets = _normalise_targets(subplots)
        crs = _check_crs(data_crs)
        if method != "barbs" and vector_basis is not None:
            _content_error("vector_basis only applies to barbs", code="invalid_vector_basis")
        if method == "barbs" and vector_basis not in {"grid", "earth"}:
            _content_error("vector_basis must be grid or earth", code="invalid_vector_basis")
        layer = PlotLayer(self, layer_id, method, data, style, targets, crs, _validate_zorder(zorder), vector_basis)
        self._panel._add_layer(layer)
        self._used_layer_ids.add(layer_id)
        return layer

    def set_title(self, text: str | None, *, id: str = "title") -> None:
        self._ensure_open()
        self._panel._set_title(self, text, id=id)

    def _set_subplots(self, subplots: Mapping[str, Subplot]) -> None:
        self._subplots = MappingProxyType(dict(subplots))

    def _close(self) -> None:
        self._closed = True
        for layer in self._layers.values():
            layer._clear_results()
            layer._data = None
            layer._style = None
        self._subplots = MappingProxyType({})
        self._layers.clear()


class _PanelImpl:
    """Implementation behind the public compatibility facade."""

    def __init__(
        self,
        public_panel: "Panel",
        *,
        template: Any = None,
        layout: Any = UNSET,
        theme: Any = UNSET,
        chart_defaults: Any = UNSET,
        chart_rules: Any = UNSET,
        chart_configs: Any = UNSET,
        decorations: Any = UNSET,
        rows: Any = UNSET,
        columns: Any = UNSET,
    ) -> None:
        if template is not None:
            raise ConfigError("templates are not implemented until D08", code="template_unavailable")
        if layout is UNSET:
            layout = LayoutSpec()
        if rows is not UNSET or columns is not UNSET:
            if layout is not UNSET and isinstance(layout, LayoutSpec):
                if rows is not UNSET and layout.rows is not UNSET:
                    raise ConfigError("rows is duplicated in layout and shortcut", code="duplicate_config")
                if columns is not UNSET and layout.columns is not UNSET:
                    raise ConfigError("columns is duplicated in layout and shortcut", code="duplicate_config")
            shortcut = LayoutSpec(
                rows=rows if rows is not UNSET else UNSET,
                columns=columns if columns is not UNSET else UNSET,
            )
            layout = merge_config(layout, shortcut)
        self.public_panel = public_panel
        self._layout = layout
        self._theme = theme
        self._chart_defaults = chart_defaults
        self._chart_rules = chart_rules
        self._chart_configs: dict[str, ChartSpec] = {} if chart_configs is UNSET else dict(chart_configs)
        self._decorations = decorations
        self._charts: dict[str, Chart] = {}
        self._used_chart_ids: set[str] = set()
        self._next_chart_number = 1
        self._fig: Figure | None = None
        self._revision = 0
        self._rendered_revision: int | None = None
        self._generation = 0
        self._closed = False
        self._force_failed = False

    def _ensure_open(self) -> None:
        if self._closed:
            _closed_error()

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def rendered_revision(self) -> int | None:
        return self._rendered_revision

    @property
    def dirty(self) -> bool:
        return self._rendered_revision != self._revision or self._force_failed

    @property
    def fig(self) -> Figure | None:
        self._ensure_open()
        return self._fig

    @property
    def charts(self) -> Mapping[str, Chart]:
        self._ensure_open()
        return MappingProxyType(self._charts)

    @property
    def effective_config(self):
        self._ensure_open()
        return self._resolve()

    def _declarations(self, extra: tuple[str, str | None] | None = None) -> dict[str, dict[str, str | None]]:
        result = {chart_id: {"role": chart.role} for chart_id, chart in self._charts.items()}
        if extra is not None:
            result[extra[0]] = {"role": extra[1]}
        return result

    def _resolve(
        self,
        *,
        layout: Any = UNSET,
        theme: Any = UNSET,
        chart_defaults: Any = UNSET,
        chart_rules: Any = UNSET,
        chart_configs: Any = UNSET,
        decorations: Any = UNSET,
        declarations: Any = UNSET,
        complete: bool = False,
    ):
        return resolve_config(
            layout=self._layout if layout is UNSET else layout,
            theme=self._theme if theme is UNSET else theme,
            chart_defaults=self._chart_defaults if chart_defaults is UNSET else chart_defaults,
            chart_rules=self._chart_rules if chart_rules is UNSET else chart_rules,
            chart_configs=self._chart_configs if chart_configs is UNSET else chart_configs,
            decorations=self._decorations if decorations is UNSET else decorations,
            charts=self._declarations() if declarations is UNSET else declarations,
            complete=complete,
        )

    def _commit(self, *, layout: Any, theme: Any, chart_defaults: Any, chart_rules: Any, chart_configs: Any, decorations: Any) -> None:
        self._layout = layout
        self._theme = theme
        self._chart_defaults = chart_defaults
        self._chart_rules = chart_rules
        self._chart_configs = dict(chart_configs)
        self._decorations = decorations
        self._revision += 1
        self._force_failed = False

    def add_chart(
        self,
        *,
        id: str | None = None,
        role: str | None = None,
        row: Any = UNSET,
        column: Any = UNSET,
        rowspan: int = 1,
        colspan: int = 1,
    ) -> Chart:
        self._ensure_open()
        if id is None:
            while f"chart_{self._next_chart_number}" in self._used_chart_ids:
                self._next_chart_number += 1
            id = f"chart_{self._next_chart_number}"
            self._next_chart_number += 1
        _check_id(id, "chart id")
        if id in self._used_chart_ids:
            raise ConfigError(f"duplicate or reused Chart id {id!r}", code="duplicate_id")
        if role is not None:
            _check_id(role, "role")
        if (row is UNSET) != (column is UNSET):
            raise ConfigError("row and column must be supplied together", code="invalid_position")
        candidate_layout = self._layout
        if row is not UNSET:
            from cedarkit.plots.config import Cell

            candidate_layout = merge_config(
                candidate_layout,
                LayoutSpec(placements={id: Cell(row=row, column=column, rowspan=rowspan, colspan=colspan)}),
            )
        elif rowspan != 1 or colspan != 1:
            raise ConfigError("rowspan/colspan require row and column", code="invalid_position")
        self._resolve(layout=candidate_layout, declarations=self._declarations((id, role)))
        chart = Chart(self, id, role)
        self._charts[id] = chart
        self._used_chart_ids.add(id)
        self._layout = candidate_layout
        self._revision += 1
        return chart

    def configure(
        self,
        *,
        layout: Any = UNSET,
        theme: Any = UNSET,
        chart_defaults: Any = UNSET,
        chart_rules: Any = UNSET,
        decorations: Any = UNSET,
    ) -> None:
        self._ensure_open()
        candidate_layout = merge_config(self._layout, layout) if layout is not UNSET else self._layout
        candidate_theme = merge_config(self._theme, theme) if theme is not UNSET else self._theme
        candidate_defaults = merge_config(self._chart_defaults, chart_defaults) if chart_defaults is not UNSET else self._chart_defaults
        candidate_rules = self._chart_rules if chart_rules is UNSET else tuple(chart_rules)
        candidate_decorations = merge_config(self._decorations, decorations) if decorations is not UNSET else self._decorations
        effective = self._resolve(
            layout=candidate_layout, theme=candidate_theme,
            chart_defaults=candidate_defaults, chart_rules=candidate_rules,
            decorations=candidate_decorations,
        )
        for chart in self._charts.values():
            self._validate_chart_layers(chart, effective)
        self._commit(
            layout=candidate_layout, theme=candidate_theme,
            chart_defaults=candidate_defaults, chart_rules=candidate_rules,
            chart_configs=self._chart_configs, decorations=candidate_decorations,
        )

    def _configure_chart(self, chart: Chart, patch: ChartSpec) -> None:
        self._ensure_open()
        current = self._chart_configs.get(chart.id, ChartSpec())
        candidate_config = merge_config(current, patch)
        candidate_configs = dict(self._chart_configs)
        candidate_configs[chart.id] = candidate_config
        effective = self._resolve(chart_configs=candidate_configs)
        self._validate_chart_layers(chart, effective)
        self._chart_configs = candidate_configs
        chart._config = candidate_config
        self._revision += 1

    def _validate_chart_layers(self, chart: Chart, effective: Any) -> None:
        spec = effective.charts.get(chart.id)
        if spec is None:
            return
        for layer in chart._layers.values():
            self._validate_layer_against_spec(layer, spec)

    def _validate_layer_against_spec(self, layer: PlotLayer, spec: ChartSpec) -> tuple[str, ...]:
        targets = _layer_targets(layer, spec)
        for target in targets:
            subplot = spec.subplots[target]
            if subplot.kind == "xy" and layer.data_crs is not None:
                _content_error(
                    f"map data layer {layer.id!r} cannot target XY subplot {target!r}",
                    code="method_target_mismatch",
                )
            if subplot.kind == "map" and layer.data_crs is None:
                _content_error(
                    f"XY data layer {layer.id!r} cannot target map subplot {target!r}",
                    code="method_target_mismatch",
                )
        return targets

    def _add_layer(self, layer: PlotLayer) -> None:
        self._ensure_open()
        effective = self._resolve()
        spec = effective.charts[layer.chart.id]
        self._validate_layer_against_spec(layer, spec)
        if layer.id in layer.chart._layers or layer.id in layer.chart._used_layer_ids:
            _content_error(f"duplicate or reused layer id {layer.id!r}", code="duplicate_id")
        layer.chart._layers[layer.id] = layer
        self._revision += 1

    def _update_layer(self, layer: PlotLayer, *, data: Any, style: Style, subplots: Any, data_crs: Any, vector_basis: Any, zorder: Any) -> None:
        self._ensure_open()
        _validate_data(layer.method, data)
        targets = _normalise_targets(subplots)
        crs = _check_crs(data_crs)
        if layer.method != "barbs" and vector_basis is not None:
            _content_error("vector_basis only applies to barbs", code="invalid_vector_basis")
        if layer.method == "barbs" and vector_basis not in {"grid", "earth"}:
            _content_error("vector_basis must be grid or earth", code="invalid_vector_basis")
        new_zorder = _validate_zorder(zorder)
        new_style = _copy_style(style)
        candidate = PlotLayer(layer.chart, layer.id, layer.method, data, new_style, targets, crs, new_zorder, vector_basis)
        effective = self._resolve()
        self._validate_layer_against_spec(candidate, effective.charts[layer.chart.id])
        layer._data = data
        layer._style = new_style
        layer._subplots = targets
        layer._data_crs = crs
        layer._zorder = new_zorder
        layer._vector_basis = vector_basis
        layer._clear_results()
        self._revision += 1

    def _remove_layer(self, layer: PlotLayer) -> None:
        self._ensure_open()
        chart = layer.chart
        if layer.id not in chart._layers:
            _content_error(f"layer {layer.id!r} is not registered", code="removed_layer")
        del chart._layers[layer.id]
        layer._removed = True
        layer._clear_results()
        layer._data = None
        layer._style = None
        self._revision += 1

    def _set_title(self, owner: Chart | None, text: str | None, *, id: str) -> None:
        self._ensure_open()
        _check_id(id, "title id")
        if text is not None and not isinstance(text, str):
            _content_error("title text must be a string or None", code="invalid_title")
        target = self._titles_for(owner)
        if text is None:
            target.pop(id, None)
        else:
            target[id] = text
        self._revision += 1

    def _titles_for(self, owner: Chart | None) -> dict[str, str]:
        if owner is None:
            if not hasattr(self, "_panel_titles"):
                self._panel_titles: dict[str, str] = {}
            return self._panel_titles
        return owner._titles

    def validate(self, *, complete: bool = False):
        self._ensure_open()
        config = self._resolve(complete=complete)
        validate_config(config, complete=complete)
        return config.pending

    def render(self, *, force: bool = False) -> Figure:
        self._ensure_open()
        if not force and not self.dirty and self._fig is not None:
            return self._fig
        effective = self._resolve(complete=True)
        if len(self._charts) > 1 or effective.layout.rows != 1 or effective.layout.columns != 1:
            raise ConfigError("D04 renderer supports one Chart in a 1x1 layout", code="layout_unavailable")
        generation = self._generation + 1
        temporary: Figure | None = None
        try:
            temporary = plt.figure(
                figsize=effective.layout.figsize,
                dpi=effective.layout.dpi,
                facecolor=effective.theme.figure_facecolor,
            )
            temporary.subplots_adjust(
                left=effective.layout.margins[0],
                right=1 - effective.layout.margins[1],
                bottom=effective.layout.margins[2],
                top=1 - effective.layout.margins[3],
                wspace=effective.layout.wspace,
                hspace=effective.layout.hspace,
            )
            rendered_subplots: dict[Chart, Mapping[str, Subplot]] = {}
            rendered_results: dict[PlotLayer, Mapping[str, LayerResult]] = {}
            for chart in self._charts.values():
                spec = effective.charts[chart.id]
                main_spec = spec.subplots["main"]
                if main_spec.kind != "xy":
                    raise ConfigError("D04 only renders XY main subplots", code="subplot_unavailable")
                left, bottom, width, height = main_spec.position.bounds
                ax = temporary.add_axes((left, bottom, width, height))
                ax.set_facecolor(effective.theme.axes_facecolor)
                ax.tick_params(labelsize=effective.theme.tick_fontsize)
                runtime_subplot = Subplot(chart, "main", ax, generation)
                rendered_subplots[chart] = {"main": runtime_subplot}
                if chart._titles:
                    # The default title is the first registered title; D07
                    # will expand this to configured title scopes.
                    ax.set_title(next(reversed(chart._titles.values())), fontsize=effective.theme.title_fontsize, color=effective.theme.text_color)
                for layer in sorted(chart._layers.values(), key=lambda item: item.zorder):
                    targets = self._validate_layer_against_spec(layer, spec)
                    layer_results: dict[str, LayerResult] = {}
                    for target in targets:
                        if target != "main":
                            raise ConfigError("D04 renderer only supports main XY", code="subplot_unavailable")
                        artist, mappable = _draw_layer(ax, layer)
                        layer_results[target] = LayerResult(
                            artists=(artist,), mappable=mappable, generation=generation,
                        )
                    rendered_results[layer] = layer_results
                if hasattr(self, "_panel_titles") and self._panel_titles:
                    temporary.suptitle(
                        next(reversed(self._panel_titles.values())),
                        fontsize=effective.theme.title_fontsize,
                        color=effective.theme.text_color,
                    )
            temporary.canvas.draw()
        except (ConfigError, ContentError):
            if temporary is not None:
                plt.close(temporary)
            self._force_failed = force
            raise
        except Exception as exc:
            if temporary is not None:
                plt.close(temporary)
            self._force_failed = force
            raise RenderError("XY rendering failed", stage="draw", cause=exc) from exc
        old_fig = self._fig
        self._fig = temporary
        self._generation = generation
        self._rendered_revision = self._revision
        self._force_failed = False
        for chart, subplots in rendered_subplots.items():
            chart._set_subplots(subplots)
        for layer, results in rendered_results.items():
            layer._set_results(results)
        if old_fig is not None:
            plt.close(old_fig)
        return temporary

    def save(
        self,
        path: str | Path,
        *,
        dpi: float | None = None,
        format: str | None = None,
        bbox_inches: str | None = "tight",
        transparent: bool = False,
    ) -> None:
        self._ensure_open()
        if not isinstance(path, (str, Path)):
            raise TypeError("path must be a string or Path")
        if format is not None and not isinstance(format, str):
            raise TypeError("format must be a string or None")
        if bbox_inches not in (None, "tight"):
            raise ValueError("bbox_inches must be None or 'tight'")
        if not isinstance(transparent, bool):
            raise TypeError("transparent must be bool")
        if dpi is not None and (isinstance(dpi, bool) or not isinstance(dpi, (int, float)) or not math.isfinite(float(dpi)) or dpi <= 0):
            raise ValueError("dpi must be a finite positive number")
        figure = self.render()
        figure.savefig(path, dpi=dpi, format=format, bbox_inches=bbox_inches, transparent=transparent)

    def show(self, *, block: bool | None = None) -> None:
        self._ensure_open()
        if block is not None and not isinstance(block, bool):
            raise TypeError("block must be bool or None")
        self.render()
        plt.show(block=block)

    def close(self) -> None:
        if self._closed:
            return
        if self._fig is not None:
            plt.close(self._fig)
        self._fig = None
        for chart in self._charts.values():
            chart._close()
        self._charts.clear()
        self._closed = True

    def __enter__(self) -> "_PanelImpl":
        self._ensure_open()
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        self.close()
        return False


def _field_xy(data: xr.DataArray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = np.asarray(data.values)
    if values.ndim != 2:
        _content_error("contour data must be two-dimensional", code="invalid_data")
    y_name, x_name = data.dims[-2], data.dims[-1]
    y = np.asarray(data.coords[y_name].values if y_name in data.coords else np.arange(values.shape[-2]))
    x = np.asarray(data.coords[x_name].values if x_name in data.coords else np.arange(values.shape[-1]))
    if x.ndim != 1 or y.ndim != 1:
        _content_error("contour coordinates must be one-dimensional", code="invalid_data")
    return x, y, values


def _draw_layer(ax: Any, layer: PlotLayer) -> tuple[Artist, Any]:
    data = layer.data
    style = layer.style
    if layer.method in {"contourf", "contour"}:
        x, y, values = _field_xy(data)
        kwargs: dict[str, Any] = {"zorder": layer.zorder}
        if style.levels is not None:
            kwargs["levels"] = style.levels
        if style.linewidths is not None:
            kwargs["linewidths"] = style.linewidths
        if style.linestyles is not None:
            kwargs["linestyles"] = style.linestyles
        colors = style.colors
        if layer.method == "contourf":
            if isinstance(colors, (str, mcolors.Colormap)):
                kwargs["cmap"] = colors
            elif colors is not None:
                kwargs["colors"] = colors
            result = ax.contourf(x, y, values, **kwargs)
            return result, result
        if isinstance(colors, mcolors.Colormap):
            colors = [colors(index) for index in range(colors.N)]
        if colors is not None:
            kwargs["colors"] = colors
        result = ax.contour(x, y, values, **kwargs)
        return result, result
    u, v = data
    x, y, u_values = _field_xy(u)
    _, _, v_values = _field_xy(v)
    if u_values.shape != v_values.shape:
        _content_error("barb components must have matching shapes", code="invalid_data")
    xx, yy = np.meshgrid(x, y)
    result = ax.barbs(
        xx, yy, u_values, v_values,
        length=style.length, linewidth=style.linewidth, pivot=style.pivot,
        barbcolor=style.barbcolor, flagcolor=style.flagcolor,
        barb_increments=style.barb_increments, zorder=layer.zorder,
    )
    return result, None


class Panel:
    """Public Panel facade supporting both D04 and the legacy domain API."""

    def __init__(
        self,
        *,
        template: Any = None,
        layout: Any = UNSET,
        theme: Any = UNSET,
        chart_defaults: Any = UNSET,
        chart_rules: Any = UNSET,
        decorations: Any = UNSET,
        rows: Any = UNSET,
        columns: Any = UNSET,
        domain: Any = UNSET,
        schema: Any = None,
    ) -> None:
        if domain is not UNSET:
            from .panel import Panel as LegacyPanel

            self._legacy = LegacyPanel(domain=domain, schema=schema)
            self._impl = None
        else:
            if schema is not None:
                raise TypeError("schema is only valid with the legacy domain API")
            self._legacy = None
            self._impl = _PanelImpl(
                self, template=template, layout=layout, theme=theme,
                chart_defaults=chart_defaults, chart_rules=chart_rules,
                decorations=decorations, rows=rows, columns=columns,
            )

    def _target(self) -> Any:
        return self._legacy if self._legacy is not None else self._impl

    def __getattr__(self, name: str) -> Any:
        target = object.__getattribute__(self, "_target")()
        return getattr(target, name)

    def __enter__(self) -> "Panel":
        target = self._target()
        target.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        return self._target().__exit__(exc_type, exc_value, traceback)

    def add_chart(
        self,
        *,
        id: str | None = None,
        role: str | None = None,
        row: Any = UNSET,
        column: Any = UNSET,
        rowspan: int = 1,
        colspan: int = 1,
        domain: Any = UNSET,
    ) -> Any:
        target = self._target()
        if self._legacy is not None:
            if domain is UNSET:
                raise TypeError("legacy add_chart requires domain")
            return target.add_chart(domain=domain)
        if domain is not UNSET:
            raise TypeError("domain is only valid with the legacy Panel constructor")
        return target.add_chart(id=id, role=role, row=row, column=column, rowspan=rowspan, colspan=colspan)

    def configure(self, *, layout: Any = UNSET, theme: Any = UNSET, chart_defaults: Any = UNSET, chart_rules: Any = UNSET, decorations: Any = UNSET) -> None:
        if self._legacy is not None:
            raise ConfigError("configure is unavailable for the legacy domain API", code="legacy_api")
        return self._impl.configure(layout=layout, theme=theme, chart_defaults=chart_defaults, chart_rules=chart_rules, decorations=decorations)

    def render(self, *, force: bool = False) -> Figure:
        if self._legacy is not None:
            return self._legacy.fig
        return self._impl.render(force=force)

    def save(self, path: Any, *, dpi: Any = None, format: Any = None, bbox_inches: Any = "tight", transparent: bool = False) -> None:
        if self._legacy is not None:
            return self._legacy.save(path, dpi=dpi, format=format, bbox_inches=bbox_inches, transparent=transparent)
        return self._impl.save(path, dpi=dpi, format=format, bbox_inches=bbox_inches, transparent=transparent)

    def show(self, *, block: bool | None = None) -> None:
        if self._legacy is not None:
            return self._legacy.show()
        return self._impl.show(block=block)

    def close(self) -> None:
        if self._legacy is not None:
            if self._legacy._fig is not None:
                plt.close(self._legacy._fig)
            return
        return self._impl.close()

    def validate(self, *, complete: bool = False):
        if self._legacy is not None:
            raise ConfigError("validate is unavailable for the legacy domain API", code="legacy_api")
        return self._impl.validate(complete=complete)

    def set_title(
        self,
        text: Any = UNSET,
        *,
        id: str = "title",
        graph_name: Any = UNSET,
        system_name: Any = UNSET,
        start_time: Any = UNSET,
        forecast_time: Any = UNSET,
    ) -> None:
        if self._legacy is not None:
            if text is not UNSET:
                raise TypeError("legacy set_title does not accept text")
            return self._legacy.set_title(
                graph_name=graph_name,
                system_name=system_name,
                start_time=start_time,
                forecast_time=forecast_time,
            )
        if text is UNSET:
            raise TypeError("new set_title requires text")
        return self._impl._set_title(None, text, id=id)

    @property
    def charts(self) -> Mapping[str, Chart]:
        if self._legacy is not None:
            return self._legacy.charts
        return self._impl.charts

    @property
    def fig(self) -> Figure | None:
        if self._legacy is not None:
            return self._legacy.fig
        return self._impl.fig

    @property
    def revision(self) -> int:
        if self._legacy is not None:
            raise ConfigError("revision is unavailable for the legacy domain API", code="legacy_api")
        return self._impl.revision

    @property
    def rendered_revision(self) -> int | None:
        if self._legacy is not None:
            raise ConfigError("rendered_revision is unavailable for the legacy domain API", code="legacy_api")
        return self._impl.rendered_revision

    @property
    def dirty(self) -> bool:
        if self._legacy is not None:
            return self._legacy._fig is None
        return self._impl.dirty

    @property
    def closed(self) -> bool:
        if self._legacy is not None:
            return False
        return self._impl.closed

    @property
    def effective_config(self):
        if self._legacy is not None:
            raise ConfigError("effective_config is unavailable for the legacy domain API", code="legacy_api")
        return self._impl.effective_config


__all__ = ["Chart", "LayerResult", "MapSubplot", "Panel", "PlotLayer", "Subplot"]
