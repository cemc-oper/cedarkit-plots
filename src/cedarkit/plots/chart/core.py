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
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any

import cartopy.crs as ccrs
import matplotlib.path as mpath
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
import numpy as np
import xarray as xr

from cedarkit.plots.config import (
    RESET,
    UNSET,
    AxisSpec,
    Cell,
    ChartSpec,
    ColorbarSpec,
    ConfigError,
    DecorationSpec,
    LayoutSpec,
    Rect,
    SubplotSpec,
    TextPosition,
    TimeStepFormatter,
    TitleSpec,
    Theme,
    merge_config,
    _ordered_chart_ids,
    resolve_config,
    validate_config,
)
from cedarkit.plots.errors import ClosedError, ContentError, Issue, RenderError, RenderRequiredError
from cedarkit.plots.painter.component_bindutils import add_map_info_text
from cedarkit.plots.style import BarbStyle, ContourLabelStyle, ContourStyle, LevelStep, Style


def _content_error(message: str, *, code: str = "invalid_content", path: tuple[str, ...] = ()) -> None:
    raise ContentError(message, code=code, path=path)


def _closed_error() -> None:
    raise ClosedError("Panel is closed")


def _check_id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        _content_error(f"{name} must be a non-empty string without whitespace", code="invalid_id")
    return value


def _copy_style(style: Style | str, data: Any = None) -> Style:
    if isinstance(style, str):
        if style == "auto":
            _content_error("core plotting requires an explicit style", code="invalid_style")
        from cedarkit.plots.style import resolve_style
        style = resolve_style(style, data)
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
    enabled = tuple(
        key
        for key, value in sorted(
            subplots.items(),
            key=lambda item: (0 if item[0] == "main" else 1, item[0]),
        )
        if value.enabled
    )
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


@dataclass(frozen=True, slots=True)
class _ColorbarBinding:
    id: str
    owner: "Chart | None"
    layers: tuple["PlotLayer", ...]
    subplots: str
    label: str | None


@dataclass(frozen=True, slots=True)
class _ScaleBinding:
    id: str
    layers: tuple["PlotLayer", ...]


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
        if self._generation != self._chart._panel._generation or self._chart._subplots.get(self._id) is not self:
            raise RenderRequiredError("subplot belongs to a previous render")
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
        self._style = _copy_style(style, data)
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
        # Style values are snapshots.  Return a defensive copy so callers
        # cannot mutate the style used by a later render through the public
        # handle.
        return _copy_style(self._style)

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
        style: ContourStyle | str,
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
        style: ContourStyle | str,
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
        style: BarbStyle | str,
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

    def colorbar(
        self,
        layers: PlotLayer | Sequence[PlotLayer],
        *,
        id: str | None = None,
        subplots: str = "main",
        label: str | None = None,
    ) -> str:
        self._ensure_open()
        return self._panel._register_colorbar(
            self,
            layers,
            id=id,
            subplots=subplots,
            label=label,
        )

    def remove_colorbar(self, id: str) -> None:
        self._ensure_open()
        self._panel._remove_colorbar(id, owner=self)

    def _set_subplots(self, subplots: Mapping[str, Subplot]) -> None:
        self._subplots = MappingProxyType(dict(subplots))

    def _close(self) -> None:
        self._closed = True
        for layer in self._layers.values():
            layer._clear_results()
            layer._data = None
            layer._style = None
        self._subplots = MappingProxyType({})
        self._titles.clear()
        self._layers.clear()


def _validate_panel_template(value: Any) -> Any:
    if value is None:
        return None
    from cedarkit.plots.templates import PanelTemplate

    if not isinstance(value, PanelTemplate):
        raise ConfigError(
            "template must be a PanelTemplate or None",
            code="invalid_template",
        )
    return value


def _merge_template_value(template_value: Any, user_value: Any) -> Any:
    if user_value is UNSET or user_value is RESET:
        return template_value
    if template_value is UNSET:
        return user_value
    return merge_config(template_value, user_value)


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
        self._template = _validate_panel_template(template)
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
        self._panel_titles: dict[str, str] = {}
        self._colorbars: dict[str, _ColorbarBinding] = {}
        self._used_colorbar_ids: set[str] = set()
        self._next_colorbar_number = 1
        self._scales: dict[str, _ScaleBinding] = {}
        self._used_scale_ids: set[str] = set()
        self._next_scale_number = 1
        self._rendered_colorbars: dict[str, Any] = {}
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
        template: Any = UNSET,
        layout: Any = UNSET,
        theme: Any = UNSET,
        chart_defaults: Any = UNSET,
        chart_rules: Any = UNSET,
        chart_configs: Any = UNSET,
        decorations: Any = UNSET,
        declarations: Any = UNSET,
        complete: bool = False,
    ):
        active_template = self._template if template is UNSET else template
        template_layout = UNSET if active_template is None else active_template.layout
        template_theme = UNSET if active_template is None else active_template.theme
        template_defaults = UNSET if active_template is None else active_template.chart_defaults
        template_rules = UNSET if active_template is None else active_template.chart_rules
        template_decorations = UNSET if active_template is None else active_template.decorations
        user_layout = self._layout if layout is UNSET else layout
        user_theme = self._theme if theme is UNSET else theme
        user_defaults = self._chart_defaults if chart_defaults is UNSET else chart_defaults
        user_rules = self._chart_rules if chart_rules is UNSET else chart_rules
        user_decorations = self._decorations if decorations is UNSET else decorations
        global_theme = _merge_template_value(template_theme, user_theme)
        source_user_defaults = UNSET if user_defaults is RESET else user_defaults
        source_user_rules = UNSET if user_rules is RESET else user_rules
        source_user_theme = UNSET if user_theme is RESET else user_theme
        effective = resolve_config(
            layout=_merge_template_value(template_layout, user_layout),
            theme=global_theme,
            chart_defaults=UNSET,
            chart_rules=UNSET,
            chart_configs=self._chart_configs if chart_configs is UNSET else chart_configs,
            decorations=_merge_template_value(template_decorations, user_decorations),
            charts=self._declarations() if declarations is UNSET else declarations,
            complete=complete,
            template_chart_defaults=template_defaults,
            template_chart_rules=template_rules,
            template_theme=template_theme,
            user_chart_defaults=source_user_defaults,
            user_chart_rules=source_user_rules,
            user_theme=source_user_theme,
        )

        pending = list(effective.pending)
        for chart in self._charts.values():
            for layer in chart._layers.values():
                spec = effective.charts[chart.id]
                try:
                    self._validate_layer_against_spec(layer, spec)
                except ContentError as exc:
                    if spec._subplots_declared or exc.code not in {"missing_target", "method_target_mismatch"}:
                        raise ConfigError(str(exc), code=exc.code, path=exc.path) from exc
                    pending.append(Issue(exc.code, str(exc), ("charts", chart.id, "layers", layer.id)))
        if complete and pending:
            raise ConfigError(issues=pending)
        return replace(effective, pending=tuple(pending))

    def _validate_effective_layers(self, effective: Any) -> None:
        for chart in self._charts.values():
            try:
                self._validate_chart_layers(chart, effective)
            except ContentError as exc:
                raise ConfigError(str(exc), code=exc.code, path=exc.path) from exc

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
        if chart_rules is UNSET:
            candidate_rules = self._chart_rules
        elif chart_rules is RESET:
            candidate_rules = UNSET
        else:
            candidate_rules = tuple(chart_rules)
        candidate_decorations = merge_config(self._decorations, decorations) if decorations is not UNSET else self._decorations
        effective = self._resolve(
            layout=candidate_layout, theme=candidate_theme,
            chart_defaults=candidate_defaults, chart_rules=candidate_rules,
            decorations=candidate_decorations, complete=bool(self._charts),
        )
        self._validate_effective_layers(effective)
        self._commit(
            layout=candidate_layout, theme=candidate_theme,
            chart_defaults=candidate_defaults, chart_rules=candidate_rules,
            chart_configs=self._chart_configs, decorations=candidate_decorations,
        )

    def apply_template(self, template: Any = None) -> None:
        """Atomically replace the optional template source."""

        self._ensure_open()
        candidate = _validate_panel_template(template)
        effective = self._resolve(template=candidate, complete=bool(self._charts))
        self._validate_effective_layers(effective)
        self._template = candidate
        self._revision += 1
        self._force_failed = False

    def _configure_chart(self, chart: Chart, patch: ChartSpec) -> None:
        self._ensure_open()
        current = self._chart_configs.get(chart.id, ChartSpec())
        candidate_config = merge_config(current, patch)
        candidate_configs = dict(self._chart_configs)
        candidate_configs[chart.id] = candidate_config
        effective = self._resolve(chart_configs=candidate_configs, complete=bool(self._charts))
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

    def _validate_layer_against_spec(self, layer: PlotLayer, spec: ChartSpec, *, allow_pending: bool = False) -> tuple[str, ...]:
        _validate_color_count(layer.style, layer.method, layer.id)
        _validate_expected_units(layer.style, layer.data if layer.method == "barbs" else (layer.data,))
        if allow_pending and not spec._subplots_declared:
            try:
                return self._validate_layer_against_spec(layer, spec)
            except ContentError as exc:
                if exc.code in {"missing_target", "method_target_mismatch"}:
                    return ()
                raise
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
            if (
                subplot.kind == "map"
                and layer.method == "barbs"
                and layer.vector_basis == "earth"
                and not isinstance(layer.data_crs, ccrs.PlateCarree)
            ):
                _content_error(
                    "earth-relative barbs require PlateCarree data_crs",
                    code="vector_basis_mismatch",
                    path=("charts", layer.chart.id, "layers", layer.id),
                )
        return targets

    def _add_layer(self, layer: PlotLayer) -> None:
        self._ensure_open()
        effective = self._resolve()
        spec = effective.charts[layer.chart.id]
        self._validate_layer_against_spec(layer, spec, allow_pending=True)
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
        new_style = _copy_style(style, data)
        candidate = PlotLayer(layer.chart, layer.id, layer.method, data, new_style, targets, crs, new_zorder, vector_basis)
        effective = self._resolve()
        self._validate_layer_against_spec(candidate, effective.charts[layer.chart.id], allow_pending=True)
        for binding in self._scales.values():
            if layer in binding.layers:
                candidate_layers = tuple(candidate if item is layer else item for item in binding.layers)
                _validate_scale_layers(candidate_layers, context=f"scale {binding.id!r}")
                if len({_style_scale_signature(item.style) for item in candidate_layers}) != 1:
                    _content_error(
                        f"update would make shared scale {binding.id!r} incompatible",
                        code="incompatible_scale",
                    )
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
        references = self._layer_references(layer)
        if references:
            _content_error(
                f"layer_in_use: layer {layer.id!r} is still referenced by {references!r}",
                code="layer_in_use",
            )
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
            return self._panel_titles
        return owner._titles

    def _normalise_binding_layers(
        self,
        owner: Chart | None,
        layers: PlotLayer | Sequence[PlotLayer],
        *,
        allow_single: bool = True,
    ) -> tuple[PlotLayer, ...]:
        if isinstance(layers, PlotLayer):
            values = (layers,)
        elif isinstance(layers, (list, tuple)):
            values = tuple(layers)
        else:
            _content_error(
                "layers must be a PlotLayer or a non-empty list/tuple of PlotLayer values",
                code="invalid_layer_reference",
            )
        if not values or (not allow_single and len(values) < 2):
            _content_error(
                "layers must contain at least one PlotLayer"
                if allow_single else "shared scale requires at least two PlotLayer values",
                code="invalid_layer_reference",
            )
        if any(not isinstance(layer, PlotLayer) for layer in values):
            _content_error("layers must contain only PlotLayer values", code="invalid_layer_reference")
        if len({id(layer) for layer in values}) != len(values):
            _content_error("layers cannot contain duplicate PlotLayer references", code="duplicate_reference")
        for layer in values:
            layer._ensure_available()
            if layer.chart._panel is not self:
                _content_error("layer belongs to a different Panel", code="cross_panel_reference")
            if owner is not None and layer.chart is not owner:
                _content_error("Chart.colorbar layers must belong to that Chart", code="cross_chart_reference")
        return values

    def _next_reference_id(self, kind: str) -> str:
        if kind == "colorbar":
            used, counter = self._used_colorbar_ids, self._next_colorbar_number
            prefix = "colorbar"
        else:
            used, counter = self._used_scale_ids, self._next_scale_number
            prefix = "scale"
        while f"{prefix}_{counter}" in used:
            counter += 1
        result = f"{prefix}_{counter}"
        if kind == "colorbar":
            self._next_colorbar_number = counter + 1
        else:
            self._next_scale_number = counter + 1
        return result

    def _register_colorbar(
        self,
        owner: Chart | None,
        layers: PlotLayer | Sequence[PlotLayer],
        *,
        id: str | None,
        subplots: str,
        label: str | None,
    ) -> str:
        self._ensure_open()
        values = self._normalise_binding_layers(owner, layers)
        if not isinstance(subplots, str) or (not subplots):
            _content_error("colorbar subplots must be a subplot ID or 'all'", code="invalid_target")
        if label is not None and not isinstance(label, str):
            _content_error("colorbar label must be a string or None", code="invalid_colorbar")
        for layer in values:
            spec = self._resolve().charts[layer.chart.id]
            _validate_colorbar_target(layer, spec, subplots)
        if id is None:
            id = self._next_reference_id("colorbar")
        _check_id(id, "colorbar id")
        existing = self._colorbars.get(id)
        if existing is not None and existing.owner is not owner:
            _content_error(
                f"colorbar {id!r} belongs to a different decoration scope",
                code="duplicate_id",
            )
        self._colorbars[id] = _ColorbarBinding(id, owner, values, subplots, label)
        self._used_colorbar_ids.add(id)
        self._revision += 1
        return id

    def _remove_colorbar(self, id: str, *, owner: Chart | None = None) -> None:
        self._ensure_open()
        _check_id(id, "colorbar id")
        binding = self._colorbars.get(id)
        if binding is None or (owner is not None and binding.owner is not owner):
            _content_error(f"colorbar {id!r} is not registered", code="missing_colorbar")
        del self._colorbars[id]
        self._rendered_colorbars.pop(id, None)
        self._revision += 1

    def _register_scale(
        self,
        layers: PlotLayer | Sequence[PlotLayer],
        *,
        id: str | None,
    ) -> str:
        self._ensure_open()
        values = self._normalise_binding_layers(None, layers, allow_single=False)
        if any(layer.method == "barbs" for layer in values):
            _content_error("shared scale requires scalar contour layers", code="incompatible_scale")
        for layer in values:
            if any(
                layer in binding.layers
                for scale_id, binding in self._scales.items()
                if scale_id != id
            ):
                _content_error(
                    f"layer {layer.id!r} already belongs to a shared scale",
                    code="incompatible_scale",
                )
        _validate_scale_layers(values, context="shared scale")
        signatures = {_style_scale_signature(layer.style) for layer in values}
        if len(signatures) != 1:
            _content_error(
                "shared scale layers must use compatible levels, norm, cmap and extend",
                code="incompatible_scale",
            )
        if id is None:
            id = self._next_reference_id("scale")
        _check_id(id, "scale id")
        self._scales[id] = _ScaleBinding(id, values)
        self._used_scale_ids.add(id)
        self._revision += 1
        return id

    def _remove_scale(self, id: str) -> None:
        self._ensure_open()
        _check_id(id, "scale id")
        if id not in self._scales:
            _content_error(f"scale {id!r} is not registered", code="missing_scale")
        del self._scales[id]
        self._revision += 1

    def _layer_references(self, layer: PlotLayer) -> tuple[str, ...]:
        result = [
            f"colorbar:{binding.id}"
            for binding in self._colorbars.values()
            if layer in binding.layers
        ]
        result.extend(
            f"scale:{binding.id}"
            for binding in self._scales.values()
            if layer in binding.layers
        )
        return tuple(result)

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
        generation = self._generation + 1
        temporary: Figure | None = None
        try:
            layers = tuple(
                layer
                for chart in self._charts.values()
                for layer in chart._layers.values()
            )
            prepared = {layer: _prepare_layer(layer) for layer in layers}
            resolved_styles = _resolve_render_styles(layers, prepared, self._scales)
            temporary = plt.figure(
                figsize=effective.layout.figsize,
                dpi=effective.layout.dpi,
                facecolor=effective.theme.figure_facecolor,
            )
            chart_boxes = _chart_boxes(temporary, effective, self._charts)
            slot_boxes = _slot_boxes(temporary, effective)
            rendered_subplots: dict[Chart, Mapping[str, Subplot]] = {}
            rendered_results: dict[PlotLayer, Mapping[str, LayerResult]] = {}
            for chart in self._charts.values():
                spec = effective.charts[chart.id]
                runtime_subplots = _create_subplots(
                    temporary,
                    chart,
                    spec,
                    chart_boxes[chart.id],
                    generation,
                )
                rendered_subplots[chart] = runtime_subplots
                for layer in sorted(chart._layers.values(), key=lambda item: item.zorder):
                    targets = self._validate_layer_against_spec(layer, spec)
                    layer_results: dict[str, LayerResult] = {}
                    for target in targets:
                        try:
                            ax = runtime_subplots[target]._ax
                        except KeyError as exc:
                            raise ConfigError(
                                f"layer {layer.id!r} target {target!r} has no rendered subplot",
                                code="missing_target",
                                path=("charts", chart.id, "subplots", target),
                            ) from exc
                        _validate_coverage(layer, spec.subplots[target], prepared[layer], target)
                        artist, mappable = _draw_layer(
                            ax,
                            layer,
                            map_axis=spec.subplots[target].kind == "map",
                            data_crs=layer.data_crs,
                            style=resolved_styles[layer],
                            prepared=prepared[layer],
                        )
                        layer_results[target] = LayerResult(
                            artists=(artist,), mappable=mappable, generation=generation,
                        )
                    rendered_results[layer] = layer_results
            _render_titles(
                temporary,
                effective,
                self._charts,
                chart_boxes,
                rendered_subplots,
                self._panel_titles,
                slot_boxes,
            )
            _render_annotations(
                temporary,
                effective,
                self._charts,
                chart_boxes,
                rendered_subplots,
                slot_boxes,
            )
            rendered_colorbars = _render_colorbars(
                temporary,
                effective,
                self._colorbars,
                rendered_results,
                resolved_styles,
                chart_boxes,
                rendered_subplots,
                slot_boxes,
            )
            temporary.canvas.draw()
        except RenderError:
            if temporary is not None:
                plt.close(temporary)
            self._force_failed = force
            raise
        except (ConfigError, ContentError):
            if temporary is not None:
                plt.close(temporary)
            self._force_failed = force
            raise
        except Exception as exc:
            if temporary is not None:
                plt.close(temporary)
            self._force_failed = force
            raise RenderError("rendering failed", stage="draw", cause=exc) from exc
        old_fig = self._fig
        self._fig = temporary
        self._generation = generation
        self._rendered_revision = self._revision
        self._force_failed = False
        self._rendered_colorbars = rendered_colorbars
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
        self._colorbars.clear()
        self._scales.clear()
        self._rendered_colorbars.clear()
        self._panel_titles.clear()
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


def _prepare_layer(layer: PlotLayer) -> Any:
    """Materialise one logical layer exactly once for a render transaction."""

    if layer.method in {"contourf", "contour"}:
        x, y, values = _field_xy(layer.data)
        _validate_expected_units(layer.style, (layer.data,))
        return x, y, values
    u, v = layer.data
    ux, uy, u_values = _field_xy(u)
    vx, vy, v_values = _field_xy(v)
    if u_values.shape != v_values.shape or not np.array_equal(ux, vx) or not np.array_equal(uy, vy):
        _content_error("barb components must have matching shapes and coordinates", code="invalid_data")
    _validate_expected_units(layer.style, (u, v))
    return ux, uy, u_values, v_values


def _validate_expected_units(style: Style, data_values: Sequence[xr.DataArray]) -> None:
    units = [item.attrs.get("units") for item in data_values]
    declared = {unit for unit in units if unit is not None}
    if len(declared) > 1:
        _content_error(f"barb components declare different units: {units!r}", code="unit_mismatch")
    duration = getattr(style, "accumulation_hours", None)
    if duration is not None and any(item.attrs.get("accumulation_hours") != duration for item in data_values):
        _content_error(f"style expects accumulation_hours {duration!r}", code="accumulation_mismatch")
    expected = getattr(style, "expected_units", None)
    if expected is None:
        return
    if any(unit != expected for unit in units):
        _content_error(
            f"style expects units {expected!r}, got {units!r}",
            code="unit_mismatch",
        )


def _finite_values(prepared: Any) -> np.ndarray:
    if len(prepared) == 3:
        values = prepared[2]
    else:
        values = np.concatenate((np.asarray(prepared[2]).ravel(), np.asarray(prepared[3]).ravel()))
    result = np.asarray(values, dtype=float)
    return result[np.isfinite(result)]


def _levels_for_values(values: np.ndarray, rule: LevelStep) -> tuple[float, ...]:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        _content_error("data-driven levels require at least one finite value", code="invalid_levels")
    step = rule.step
    reference = rule.reference
    lower = reference + math.floor((float(finite.min()) - reference) / step) * step
    upper = reference + math.ceil((float(finite.max()) - reference) / step) * step
    if math.isclose(lower, upper, rel_tol=0.0, abs_tol=step * 1e-12):
        lower -= step
        upper += step
    values = np.arange(lower, upper + step * 0.5, step, dtype=float)
    if values.size < 2:
        values = np.array((lower, lower + step), dtype=float)
    return tuple(float(value) for value in values)


def _resolved_style(layer: PlotLayer, prepared: Any, values: np.ndarray | None = None) -> Style:
    style = _copy_style(layer.style)
    if isinstance(style, ContourStyle) and isinstance(style.levels, LevelStep):
        style.levels = _levels_for_values(_finite_values(prepared) if values is None else values, style.levels)
    if isinstance(style, ContourStyle) and style.levels is not None:
        levels = np.asarray(style.levels, dtype=float)
        if levels.ndim != 1 or len(levels) < 2 or not np.all(np.isfinite(levels)):
            _content_error("contour levels must contain at least two finite values", code="invalid_levels")
        if style.norm == "log" and np.any(levels <= 0):
            _content_error("log contour levels must be positive", code="invalid_levels")
    return style


def _style_scale_signature(style: Style) -> tuple[Any, ...]:
    if not isinstance(style, ContourStyle):
        return (type(style).__name__,)
    levels = style.levels
    if isinstance(levels, LevelStep):
        level_signature = ("step", levels.step, levels.reference)
    elif levels is None:
        level_signature = None
    else:
        level_signature = tuple(float(item) for item in np.asarray(levels).ravel())
    colors = style.colors
    if colors is None or isinstance(colors, str):
        colors = plt.get_cmap(colors)
    if isinstance(colors, mcolors.Colormap):
        color_signature = (
            "cmap",
            tuple(np.asarray(colors(np.arange(colors.N))).ravel()),
            tuple(colors.get_under()),
            tuple(colors.get_over()),
            tuple(colors.get_bad()),
        )
    elif isinstance(colors, (list, tuple, np.ndarray)):
        color_signature = ("colors", tuple(map(tuple, mcolors.to_rgba_array(colors))))
    else:
        color_signature = ("color", colors)
    return (
        "contour",
        level_signature,
        style.norm,
        color_signature,
        style.extend,
        style.expected_units,
        style.accumulation_hours,
    )


def _data_metadata(layers: Sequence[PlotLayer]) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    units: list[Any] = []
    standard_names: list[Any] = []
    for layer in layers:
        values = layer.data if layer.method != "barbs" else layer.data
        arrays = values if layer.method == "barbs" else (values,)
        units.extend(item.attrs.get("units") for item in arrays)
        standard_names.extend(item.attrs.get("standard_name") for item in arrays)
    return tuple(units), tuple(standard_names)


def _validate_scale_layers(layers: Sequence[PlotLayer], *, context: str) -> None:
    if any(layer.method == "barbs" for layer in layers):
        _content_error(f"{context} cannot include barb layers", code="incompatible_scale")
    signatures = {_style_scale_signature(layer.style) for layer in layers}
    if len(signatures) != 1:
        _content_error(
            f"{context} layers must use identical levels, norm, cmap and extend",
            code="incompatible_scale",
        )
    units, standard_names = _data_metadata(layers)
    if len(layers) > 1:
        if any(unit is None for unit in units) or len(set(units)) != 1:
            _content_error(f"{context} layers must declare matching units", code="incompatible_scale")
        if any(not name for name in standard_names) or len(set(standard_names)) != 1:
            _content_error(
                f"{context} layers must declare the same standard_name",
                code="incompatible_scale",
            )


def _validate_colorbar_target(layer: PlotLayer, spec: ChartSpec, target: str) -> tuple[str, ...]:
    if target != "all" and target not in _layer_targets(layer, spec):
        _content_error(
            f"colorbar target {target!r} is not rendered by layer {layer.id!r}",
            code="missing_target",
        )
    return _layer_targets(layer, spec) if target == "all" else (target,)


def _resolve_render_styles(
    layers: Sequence[PlotLayer],
    prepared: Mapping[PlotLayer, Any],
    scales: Mapping[str, _ScaleBinding],
) -> dict[PlotLayer, Style]:
    resolved: dict[PlotLayer, Style] = {}
    grouped: set[PlotLayer] = set()
    for binding in scales.values():
        grouped.update(binding.layers)
        combined = np.concatenate([_finite_values(prepared[layer]) for layer in binding.layers])
        for layer in binding.layers:
            resolved[layer] = _resolved_style(layer, prepared[layer], combined)
    for layer in layers:
        if layer not in grouped:
            resolved[layer] = _resolved_style(layer, prepared[layer])
    return resolved


def _slot_boxes(figure: Figure, effective: Any) -> dict[str, tuple[float, float, float, float]]:
    layout = effective.layout
    if layout.mode == "absolute":
        return {
            slot_id: tuple(slot.position.bounds)
            for slot_id, slot in layout.slots.items()
            if slot.enabled and isinstance(slot.position, Rect)
        }
    grid = figure.add_gridspec(
        layout.rows,
        layout.columns,
        left=layout.margins[0],
        right=1 - layout.margins[1],
        bottom=layout.margins[2],
        top=1 - layout.margins[3],
        wspace=layout.wspace,
        hspace=layout.hspace,
    )
    bottoms, tops, lefts, rights = grid.get_grid_positions(figure)
    result: dict[str, tuple[float, float, float, float]] = {}
    for slot_id, slot in layout.slots.items():
        if not slot.enabled or not isinstance(slot.position, Cell):
            continue
        top, left, bottom, right = _cell_bounds(slot.position)
        result[slot_id] = (
            float(lefts[left]),
            float(bottoms[bottom - 1]),
            float(rights[right - 1] - lefts[left]),
            float(tops[top] - bottoms[bottom - 1]),
        )
    return result


def _bounds_in_unit_square(bounds: tuple[float, float, float, float]) -> bool:
    left, bottom, width, height = bounds
    return 0 <= left <= 1 and 0 <= bottom <= 1 and left + width <= 1 and bottom + height <= 1


def _decoration_mapping(owner: Chart | None, effective: Any, name: str) -> Mapping[str, Any]:
    if owner is None:
        decorations = effective.decorations
    else:
        decorations = effective.charts[owner.id].decorations
    value = getattr(decorations, name)
    return {} if value is UNSET else value


def _position_point(
    position: TextPosition,
    *,
    figure: Figure,
    chart_box: tuple[float, float, float, float] | None,
    subplots: Mapping[str, Subplot] | None,
    slot_boxes: Mapping[str, tuple[float, float, float, float]],
    owner: Chart | None,
) -> tuple[str, Any, float, float]:
    space = position.space
    x, y = position.xy
    if space == "figure":
        return "figure", None, x, y
    if space == "chart":
        if chart_box is None:
            raise ConfigError("chart-space decoration requires a Chart", code="invalid_decoration")
        left, bottom, width, height = chart_box
        return "figure", None, left + x * width, bottom + y * height
    if space == "slot":
        slot_id = position.slot
        if slot_id is UNSET or slot_id is None or slot_id not in slot_boxes:
            raise ConfigError(
                f"decoration references missing slot {slot_id!r}",
                code="missing_target",
            )
        left, bottom, width, height = slot_boxes[slot_id]
        return "figure", None, left + x * width, bottom + y * height
    if subplots is None:
        raise ConfigError("subplot-space decoration requires a Chart", code="invalid_decoration")
    subplot_id = "main" if position.subplot in (UNSET, None) else position.subplot
    try:
        return "subplot", subplots[subplot_id]._ax, x, y
    except KeyError as exc:
        raise ConfigError(
            f"decoration references missing subplot {subplot_id!r}",
            code="missing_target",
        ) from exc


def _rect_box(
    position: Rect,
    *,
    chart_box: tuple[float, float, float, float] | None,
    subplots: Mapping[str, Subplot] | None,
    slot_boxes: Mapping[str, tuple[float, float, float, float]],
) -> tuple[float, float, float, float]:
    if position.space == "figure":
        if not _bounds_in_unit_square(position.bounds):
            raise ConfigError("figure decoration Rect must stay within [0, 1]", code="layout_bounds")
        return tuple(position.bounds)
    if position.space == "chart":
        if chart_box is None:
            raise ConfigError("chart-space decoration requires a Chart", code="invalid_decoration")
        return _relative_box(chart_box, position.bounds, path=("decorations",))
    if position.space == "slot":
        slot_id = position.slot
        if slot_id is UNSET or slot_id is None or slot_id not in slot_boxes:
            raise ConfigError(f"decoration references missing slot {slot_id!r}", code="missing_target")
        return _relative_box(slot_boxes[slot_id], position.bounds, path=("decorations",))
    if subplots is None:
        raise ConfigError("subplot-space decoration requires a Chart", code="invalid_decoration")
    subplot_id = position.subplot
    if subplot_id is UNSET or subplot_id is None or subplot_id not in subplots:
        raise ConfigError(f"decoration references missing subplot {subplot_id!r}", code="missing_target")
    return _relative_box(
        subplots[subplot_id]._ax.get_position().bounds,
        position.bounds,
        path=("decorations",),
    )


def _render_one_title(
    figure: Figure,
    text: str,
    title: TitleSpec | None,
    *,
    owner: Chart | None,
    theme: Theme,
    chart_box: tuple[float, float, float, float] | None,
    subplots: Mapping[str, Subplot] | None,
    slot_boxes: Mapping[str, tuple[float, float, float, float]],
) -> None:
    title = title or TitleSpec()
    if title.enabled is False:
        return
    position = title.position
    if not isinstance(position, (TextPosition, Rect)):
        position = (
            TextPosition(space="figure", xy=(.5, .98), va="top")
            if owner is None
            else TextPosition(space="subplot", subplot="main", xy=(.5, 1.02), va="bottom")
        )
    fontsize = theme.title_fontsize if title.fontsize is UNSET else title.fontsize
    color = theme.text_color if title.color is UNSET else title.color
    if isinstance(position, Rect):
        left, bottom, width, height = _rect_box(
            position,
            chart_box=chart_box,
            subplots=subplots,
            slot_boxes=slot_boxes,
        )
        figure.text(
            left + width / 2,
            bottom + height / 2,
            text,
            ha="center",
            va="center",
            fontsize=fontsize,
            color=color,
            fontfamily=theme.font_family,
        )
        return
    kind, ax, x, y = _position_point(
        position,
        figure=figure,
        chart_box=chart_box,
        subplots=subplots,
        slot_boxes=slot_boxes,
        owner=owner,
    )
    kwargs = dict(
        ha="center" if position.ha is UNSET else position.ha,
        va="bottom" if position.va is UNSET else position.va,
        fontsize=fontsize,
        color=color,
        fontfamily=theme.font_family,
    )
    if kind == "figure":
        figure.text(x, y, text, **kwargs)
    else:
        ax.text(x, y, text, transform=ax.transAxes, clip_on=False, **kwargs)


def _render_titles(
    figure: Figure,
    effective: Any,
    charts: Mapping[str, Chart],
    chart_boxes: Mapping[str, tuple[float, float, float, float]],
    rendered_subplots: Mapping[Chart, Mapping[str, Subplot]],
    panel_titles: Mapping[str, str],
    slot_boxes: Mapping[str, tuple[float, float, float, float]],
) -> None:
    panel_specs = _decoration_mapping(None, effective, "titles")
    for title_id, text in panel_titles.items():
        _render_one_title(
            figure,
            text,
            panel_specs.get(title_id),
            owner=None,
            theme=effective.theme,
            chart_box=None,
            subplots=None,
            slot_boxes=slot_boxes,
        )
    for chart in charts.values():
        chart_specs = _decoration_mapping(chart, effective, "titles")
        for title_id, text in chart._titles.items():
            spec = effective.charts[chart.id]
            _render_one_title(
                figure,
                text,
                chart_specs.get(title_id),
                owner=chart,
                theme=spec.theme,
                chart_box=chart_boxes[chart.id],
                subplots=rendered_subplots[chart],
                slot_boxes=slot_boxes,
            )


def _render_annotations(
    figure: Figure,
    effective: Any,
    charts: Mapping[str, Chart],
    chart_boxes: Mapping[str, tuple[float, float, float, float]],
    rendered_subplots: Mapping[Chart, Mapping[str, Subplot]],
    slot_boxes: Mapping[str, tuple[float, float, float, float]],
) -> None:
    """Render resolved subplot annotations without creating logical content."""

    for chart in charts.values():
        chart_spec = effective.charts[chart.id]
        for subplot_id, subplot_spec in chart_spec.subplots.items():
            annotations = subplot_spec.annotations
            if not annotations or subplot_id not in rendered_subplots[chart]:
                continue
            for annotation in annotations.values():
                if annotation.enabled is False:
                    continue
                position = annotation.position
                if not isinstance(position, TextPosition):
                    continue
                if position.space == "subplot" and position.subplot in (UNSET, None):
                    position = replace(position, subplot=subplot_id)
                kind, ax, x, y = _position_point(
                    position,
                    figure=figure,
                    chart_box=chart_boxes[chart.id],
                    subplots=rendered_subplots[chart],
                    slot_boxes=slot_boxes,
                    owner=chart,
                )
                kwargs = {
                    "ha": "center" if position.ha is UNSET else position.ha,
                    "va": "center" if position.va is UNSET else position.va,
                    "fontsize": annotation.fontsize,
                    "color": annotation.color,
                    "fontfamily": chart_spec.theme.font_family,
                    "clip_on": False,
                }
                if annotation.bbox is not None:
                    kwargs["bbox"] = dict(annotation.bbox)
                if kind == "figure":
                    kwargs.pop("clip_on", None)
                    figure.text(x, y, annotation.text, **kwargs)
                else:
                    transform = ax.transAxes if annotation.crs is None else annotation.crs
                    ax.text(x, y, annotation.text, transform=transform, **kwargs)


def _mappable_signature(mappable: Any) -> tuple[Any, ...]:
    norm = mappable.norm
    boundaries = getattr(norm, "boundaries", None)
    if boundaries is not None:
        boundaries = tuple(float(item) for item in boundaries)
    cmap = mappable.cmap
    return (
        type(norm).__name__,
        getattr(norm, "vmin", None),
        getattr(norm, "vmax", None),
        boundaries,
        tuple(np.asarray(cmap(np.arange(cmap.N))).ravel()),
        tuple(cmap.get_under()),
        tuple(cmap.get_over()),
        tuple(cmap.get_bad()),
    )


def _colorbar_candidates(
    binding: _ColorbarBinding,
    effective: Any,
    rendered_results: Mapping[PlotLayer, Mapping[str, LayerResult]],
) -> list[tuple[PlotLayer, str, Any]]:
    candidates: list[tuple[PlotLayer, str, Any]] = []
    for layer in binding.layers:
        spec = effective.charts[layer.chart.id]
        targets = _validate_colorbar_target(layer, spec, binding.subplots)
        for target in targets:
            result = rendered_results[layer].get(target)
            if result is None or result.mappable is None:
                _content_error(
                    f"colorbar {binding.id!r} layer {layer.id!r} target {target!r} has no mappable",
                    code="invalid_colorbar",
                )
            candidates.append((layer, target, result.mappable))
    if not candidates:
        _content_error(f"colorbar {binding.id!r} has no mappable results", code="invalid_colorbar")
    return candidates


def _render_colorbars(
    figure: Figure,
    effective: Any,
    bindings: Mapping[str, _ColorbarBinding],
    rendered_results: Mapping[PlotLayer, Mapping[str, LayerResult]],
    resolved_styles: Mapping[PlotLayer, Style],
    chart_boxes: Mapping[str, tuple[float, float, float, float]],
    rendered_subplots: Mapping[Chart, Mapping[str, Subplot]],
    slot_boxes: Mapping[str, tuple[float, float, float, float]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for binding in bindings.values():
        candidates = _colorbar_candidates(binding, effective, rendered_results)
        first_layer, first_target, first_mappable = candidates[0]
        first_units = first_layer.data.attrs.get("units")
        first_standard_name = first_layer.data.attrs.get("standard_name")
        baseline = (
            _style_scale_signature(resolved_styles[first_layer]),
            _mappable_signature(first_mappable),
            first_units,
            first_standard_name,
        )
        differing: set[str] = set()
        for layer, target, mappable in candidates[1:]:
            units = layer.data.attrs.get("units")
            standard_name = layer.data.attrs.get("standard_name")
            current = (
                _style_scale_signature(resolved_styles[layer]),
                _mappable_signature(mappable),
                units,
                standard_name,
            )
            names = ("levels/norm/cmap/extend", "mappable", "units", "standard_name")
            differing.update(name for name, left, right in zip(names, baseline, current) if left != right)
        if len({layer for layer, _, _ in candidates}) > 1:
            units = [layer.data.attrs.get("units") for layer, _, _ in candidates]
            names = [layer.data.attrs.get("standard_name") for layer, _, _ in candidates]
            if any(value is None for value in units) or len(set(units)) != 1:
                differing.add("units")
            if any(not value for value in names) or len(set(names)) != 1:
                differing.add("standard_name")
        if differing:
            _content_error(
                f"colorbar={binding.id!r} has incompatible layers; differing={sorted(differing)!r}",
                code="incompatible_scale",
            )
        owner = binding.owner
        decoration = _decoration_mapping(owner, effective, "colorbars").get(binding.id)
        decoration = decoration or ColorbarSpec()
        orientation = "vertical" if decoration.orientation is UNSET else decoration.orientation
        ticks = None if decoration.ticks is UNSET else decoration.ticks
        if decoration.enabled is False:
            result[binding.id] = None
            continue
        if owner is None:
            theme = effective.theme
            chart_box = None
            subplots = None
        else:
            theme = effective.charts[owner.id].theme
            chart_box = chart_boxes[owner.id]
            subplots = rendered_subplots[owner]
        position = decoration.position
        if not isinstance(position, (Rect, TextPosition)):
            position = (
                Rect(space="figure", bounds=(.92, .15, .02, .7))
                if owner is None
                else Rect(space="chart", bounds=(.87, .12, .025, .76))
            )
        if isinstance(position, TextPosition):
            _, _, x, y = _position_point(
                position,
                figure=figure,
                chart_box=chart_box,
                subplots=subplots,
                slot_boxes=slot_boxes,
                owner=owner,
            )
            width, height = (.025, .7) if orientation == "vertical" else (.7, .025)
            position = Rect(space="figure", bounds=(x - width / 2, y - height / 2, width, height))
        box = _rect_box(
            position,
            chart_box=chart_box,
            subplots=subplots,
            slot_boxes=slot_boxes,
        )
        cax = figure.add_axes(box)
        colorbar = figure.colorbar(
            first_mappable,
            cax=cax,
            orientation=orientation,
        )
        if binding.label is not None:
            colorbar.set_label(binding.label)
        if ticks is not None:
            colorbar.set_ticks(ticks)
        tick_fontsize = theme.tick_fontsize if decoration.tick_fontsize is UNSET else decoration.tick_fontsize
        colorbar.ax.tick_params(labelsize=tick_fontsize)
        result[binding.id] = colorbar
    return result


def _validate_color_count(style: Style, method: str, layer_id: str) -> None:
    if not isinstance(style, ContourStyle) or style.levels is None or isinstance(style.levels, LevelStep):
        return
    palette = style.colors
    if palette is None or isinstance(palette, (str, mcolors.Colormap)):
        cmap = plt.get_cmap(palette) if not isinstance(palette, mcolors.Colormap) else palette
        if style.norm == "boundary" and cmap.N < len(style.levels) - 1:
            _content_error(f"layer {layer_id!r} colormap has insufficient colors", code="invalid_style")
    else:
        required = (len(style.levels) - 1 + (style.extend in {"min", "both"})
                    + (style.extend in {"max", "both"})) if method == "contourf" else len(style.levels)
        if len(palette) != required and not (method == "contour" and len(palette) == 1):
            _content_error(f"layer {layer_id!r} needs {required} colors, got {len(palette)}", code="invalid_style")


def _validate_coverage(layer: PlotLayer, spec: SubplotSpec, prepared: Any, target: str) -> None:
    if spec.kind != "map" or spec.domain is None:
        return
    domain = spec.domain
    if not isinstance(layer.data_crs, ccrs.PlateCarree) or layer.data_crs != domain.extent_crs:
        return
    west, east, south, north = domain.extent
    x, y = prepared[:2]
    # Geographic seam and polar domains cannot be proved by rectangular bounds.
    if (west < -180 or east > 180 or west >= east or east - west >= 360 or south <= -90 or north >= 90
            or np.min(x) < -180 or np.max(x) > 180
            or isinstance(spec.map_crs, (ccrs.NorthPolarStereo, ccrs.SouthPolarStereo))
            or not np.isfinite(x).all() or not np.isfinite(y).all()
            or np.any(np.abs(np.diff(x)) > 180)):
        return
    if not (np.min(x) <= west + 1e-8 and np.max(x) >= east - 1e-8
            and np.min(y) <= south + 1e-8 and np.max(y) >= north - 1e-8):
        _content_error(
            f"layer {layer.id!r} has insufficient coverage for domain extent {domain.extent!r} (subplot {target!r})",
            code="insufficient_coverage", path=("charts", layer.chart.id, "layers", layer.id, "domain", target),
        )


def _draw_layer(
    ax: Any,
    layer: PlotLayer,
    *,
    map_axis: bool = False,
    data_crs: Any = None,
    style: Style | None = None,
    prepared: Any = None,
) -> tuple[Artist, Any]:
    style = layer.style if style is None else style
    if prepared is None:
        prepared = _prepare_layer(layer)
    transform = {"transform": data_crs} if map_axis else {}
    if layer.method in {"contourf", "contour"}:
        x, y, values = prepared
        _validate_color_count(style, layer.method, layer.id)
        kwargs: dict[str, Any] = {"zorder": layer.zorder, **transform}
        if style.levels is not None:
            kwargs["levels"] = style.levels
        if style.linewidths is not None:
            kwargs["linewidths"] = style.linewidths
        if style.linestyles is not None:
            kwargs["linestyles"] = style.linestyles
        colors = style.colors
        cmap = None
        if colors is None or isinstance(colors, (str, mcolors.Colormap)):
            cmap = plt.get_cmap(colors) if not isinstance(colors, mcolors.Colormap) else colors
            kwargs["cmap"] = cmap
        else:
            count = len(colors)
            if layer.method == "contourf":
                lower = int(style.extend in {"min", "both"})
                upper = int(style.extend in {"max", "both"})
                cmap = mcolors.ListedColormap(colors[lower:count - upper])
                if lower:
                    cmap.set_under(colors[0])
                if upper:
                    cmap.set_over(colors[-1])
                kwargs["cmap"] = cmap
            else:
                kwargs["colors"] = colors
        if style.levels is not None:
            if style.norm == "linear":
                kwargs["norm"] = mcolors.Normalize(vmin=style.levels[0], vmax=style.levels[-1])
            elif style.norm == "log":
                kwargs["norm"] = mcolors.LogNorm(vmin=style.levels[0], vmax=style.levels[-1])
            elif cmap is not None:
                kwargs["norm"] = mcolors.BoundaryNorm(style.levels, ncolors=cmap.N, clip=False)
        kwargs["extend"] = style.extend
        if layer.method == "contourf":
            result = ax.contourf(x, y, values, **kwargs)
            return result, result
        result = ax.contour(x, y, values, **kwargs)
        if style.label:
            label = style.label_style or ContourLabelStyle()
            label_kwargs = {
                key: getattr(label, key)
                for key in ("fontsize", "inline", "inline_spacing", "fmt", "colors", "manual", "zorder")
                if getattr(label, key) is not None
            }
            labels = ax.clabel(result, levels=label.levels, **label_kwargs)
            if label.background_color is not None:
                for text in labels:
                    text.set_bbox(dict(facecolor=label.background_color, edgecolor="none", pad=.5))
        return result, result
    x, y, u_values, v_values = prepared
    xx, yy = np.meshgrid(x, y)
    result = ax.barbs(
        xx, yy, u_values, v_values,
        length=style.length, linewidth=style.linewidth, pivot=style.pivot,
        barbcolor=style.barbcolor, flagcolor=style.flagcolor,
        barb_increments=style.barb_increments, zorder=layer.zorder,
        **transform,
    )
    return result, None


def _cell_bounds(cell: Any) -> tuple[int, int, int, int]:
    return (
        cell.row,
        cell.column,
        cell.row + cell.rowspan,
        cell.column + cell.colspan,
    )


def _cells_overlap(left: Any, right: Any) -> bool:
    ltop, lleft, lbottom, lright = _cell_bounds(left)
    rtop, rleft, rbottom, rright = _cell_bounds(right)
    return ltop < rbottom and rtop < lbottom and lleft < rright and rleft < lright


def _chart_cells(effective: Any, charts: Mapping[str, Chart]) -> dict[str, Any]:
    """Materialize deterministic grid cells for the current Chart set."""

    layout = effective.layout
    declarations = tuple((chart.id, chart.role) for chart in charts.values())
    chart_order, order_issues = _ordered_chart_ids(layout, declarations)
    if order_issues:
        raise ConfigError(issues=order_issues)
    explicit = layout.placements
    occupied: list[Any] = [
        item for item in explicit.values() if hasattr(item, "row")
    ]
    occupied.extend(
        slot.position
        for slot in layout.slots.values()
        if slot.enabled and hasattr(slot.position, "row")
    )
    cells: dict[str, Any] = {}
    for chart_id in chart_order:
        if chart_id in explicit:
            cells[chart_id] = explicit[chart_id]
            continue
        found = None
        for row in range(layout.rows):
            for column in range(layout.columns):
                candidate = Cell(row=row, column=column, rowspan=1, colspan=1)
                if any(_cells_overlap(candidate, item) for item in occupied):
                    continue
                found = candidate
                break
            if found is not None:
                break
        if found is None:
            raise ConfigError(
                f"no free cell remains for Chart {chart_id!r}",
                code="layout_capacity",
                path=("layout",),
            )
        cells[chart_id] = found
        occupied.append(found)
    return cells


def _chart_boxes(figure: Figure, effective: Any, charts: Mapping[str, Chart]) -> dict[str, tuple[float, float, float, float]]:
    """Resolve Chart rectangles in normalized Figure coordinates."""

    layout = effective.layout
    if layout.mode == "absolute":
        return {
            chart_id: tuple(layout.placements[chart_id].bounds)
            for chart_id in charts
        }

    cells = _chart_cells(effective, charts)
    grid = figure.add_gridspec(
        layout.rows,
        layout.columns,
        left=layout.margins[0],
        right=1 - layout.margins[1],
        bottom=layout.margins[2],
        top=1 - layout.margins[3],
        wspace=layout.wspace,
        hspace=layout.hspace,
    )
    bottoms, tops, lefts, rights = grid.get_grid_positions(figure)
    boxes: dict[str, tuple[float, float, float, float]] = {}
    for chart_id, cell in cells.items():
        top, left, bottom, right = _cell_bounds(cell)
        figure_left = float(lefts[left])
        figure_right = float(rights[right - 1])
        figure_bottom = float(bottoms[bottom - 1])
        figure_top = float(tops[top])
        boxes[chart_id] = (
            figure_left,
            figure_bottom,
            figure_right - figure_left,
            figure_top - figure_bottom,
        )
    return boxes


def _relative_box(
    parent: tuple[float, float, float, float],
    bounds: tuple[float, float, float, float],
    *,
    path: tuple[str, ...],
) -> tuple[float, float, float, float]:
    left, bottom, width, height = bounds
    if left < 0 or bottom < 0 or left + width > 1 or bottom + height > 1:
        raise ConfigError(
            "relative subplot position must remain within its parent",
            code="layout_bounds",
            path=path,
        )
    parent_left, parent_bottom, parent_width, parent_height = parent
    return (
        parent_left + left * parent_width,
        parent_bottom + bottom * parent_height,
        width * parent_width,
        height * parent_height,
    )


def _subplot_boxes(
    spec: ChartSpec,
    chart_box: tuple[float, float, float, float],
) -> dict[str, tuple[float, float, float, float]]:
    """Resolve chart-local subplot rectangles, including relative children."""

    enabled = {
        subplot_id: subplot
        for subplot_id, subplot in spec.subplots.items()
        if subplot.enabled
    }
    boxes: dict[str, tuple[float, float, float, float]] = {}
    while len(boxes) < len(enabled):
        progress = False
        for subplot_id, subplot in sorted(
            enabled.items(),
            key=lambda item: (
                float(item[1].zorder),
                0 if item[0] == "main" else 1,
                item[0],
            ),
        ):
            if subplot_id in boxes:
                continue
            position = subplot.position
            if position.space == "chart":
                parent = chart_box
            elif position.space == "subplot":
                parent_id = position.subplot
                if parent_id not in boxes:
                    continue
                parent = boxes[parent_id]
            else:
                raise ConfigError(
                    "subplot positions must use chart or subplot space",
                    code="layout_position",
                    path=("subplots", subplot_id, "position"),
                )
            boxes[subplot_id] = _relative_box(
                parent,
                position.bounds,
                path=("subplots", subplot_id, "position"),
            )
            progress = True
        if not progress:
            unresolved = tuple(subplot_id for subplot_id in enabled if subplot_id not in boxes)
            raise ConfigError(
                f"subplot positions contain an unresolved parent: {unresolved!r}",
                code="layout_dependency",
                path=("subplots",),
            )
    return boxes


def _apply_axis_spec(
    ax: Any,
    axis: AxisSpec,
    *,
    map_axis: bool = False,
    tick_crs: Any = None,
) -> None:
    if axis.xticks is not None:
        if map_axis:
            ax.set_xticks(axis.xticks, crs=tick_crs)
        else:
            ax.set_xticks(axis.xticks)
    if axis.yticks is not None:
        if map_axis:
            ax.set_yticks(axis.yticks, crs=tick_crs)
        else:
            ax.set_yticks(axis.yticks)
    if axis.xformatter is not None:
        ax.xaxis.set_major_formatter(
            _axis_formatter(axis.xformatter, map_axis=map_axis, longitude=True)
        )
    if axis.yformatter is not None:
        ax.yaxis.set_major_formatter(
            _axis_formatter(axis.yformatter, map_axis=map_axis, longitude=False)
        )
    if not map_axis:
        if axis.xlim is not None:
            ax.set_xlim(axis.xlim)
        if axis.ylim is not None:
            ax.set_ylim(axis.ylim)
        if axis.invert_y:
            ax.invert_yaxis()
    if axis.gridlines is not None:
        grid = axis.gridlines
        if map_axis:
            from matplotlib.ticker import FixedLocator

            gridliner = ax.gridlines(
                draw_labels=grid.labels,
                color=grid.color,
                linewidth=grid.linewidth,
                alpha=grid.alpha,
            )
            if grid.xlocators is not None:
                gridliner.xlocator = FixedLocator(grid.xlocators)
            if grid.ylocators is not None:
                gridliner.ylocator = FixedLocator(grid.ylocators)
        else:
            ax.grid(
                True,
                color=grid.color,
                linewidth=grid.linewidth,
                alpha=grid.alpha,
            )
            if grid.xlocators is not None:
                ax.set_xticks(grid.xlocators, minor=True)
            if grid.ylocators is not None:
                ax.set_yticks(grid.ylocators, minor=True)
    border = axis.border
    for spine in ax.spines.values():
        spine.set_visible(border.enabled)
        spine.set_color(border.color)
        spine.set_linewidth(border.linewidth)


def _axis_formatter(value: str | TimeStepFormatter, *, map_axis: bool, longitude: bool) -> Any:
    """Materialize one declarative axis formatter at render time."""

    if isinstance(value, TimeStepFormatter):
        def format_time(step: float, _position: int) -> str:
            valid_time = value.start_time + timedelta(hours=float(step))
            label = valid_time.strftime("%HZ")
            if label == "00Z":
                label += f"\n{valid_time.strftime('%d%b').upper()}"
            if math.isclose(float(step), value.last_step):
                label += f"\n{valid_time.strftime('%Y')}"
            return label

        return FuncFormatter(format_time)

    if map_axis and value == "longitude":
        from cartopy.mpl.ticker import LongitudeFormatter

        return LongitudeFormatter(zero_direction_label=True, degree_symbol="")
    if map_axis and value == "latitude":
        from cartopy.mpl.ticker import LatitudeFormatter

        return LatitudeFormatter(degree_symbol="")

    def format_value(number: float, position: int) -> str:
        try:
            return value.format(x=number, pos=position)
        except (IndexError, KeyError):
            return value.format(number)

    return FuncFormatter(format_value)


def _map_info_values(value: Any) -> tuple[str, float, float]:
    if isinstance(value, Mapping):
        try:
            text, x, y = value["text"], value["x"], value["y"]
        except KeyError as exc:
            raise ConfigError(
                "map_info requires text, x and y",
                code="invalid_map_info",
                path=("basemap", "map_info"),
            ) from exc
    else:
        try:
            text, x, y = value.text, value.x, value.y
        except AttributeError as exc:
            raise ConfigError(
                "map_info requires text, x and y",
                code="invalid_map_info",
                path=("basemap", "map_info"),
            ) from exc
    if not isinstance(text, str):
        raise ConfigError("map_info.text must be a string", code="invalid_map_info")
    return text, float(x), float(y)


def _render_basemap(ax: Any, subplot_spec: SubplotSpec) -> None:
    basemap = subplot_spec.basemap
    domain = subplot_spec.domain
    if domain is None:
        raise ConfigError("map subplot requires a Domain", code="missing_domain")
    map_crs = subplot_spec.map_crs
    if not isinstance(map_crs, ccrs.Projection):
        raise ConfigError(
            "map subplot requires a Cartopy projection",
            code="invalid_map_crs",
        )
    boundary = domain.boundary
    if boundary == "global":
        ax.set_global()
    else:
        ax.set_extent(domain.extent, crs=domain.extent_crs)
    if boundary == "circle":
        theta = np.linspace(0, 2 * np.pi, 100)
        center, radius = (0.5, 0.5), 0.5
        vertices = np.vstack([np.sin(theta), np.cos(theta)]).T
        circle = mpath.Path(vertices * radius + center)
        ax.set_boundary(circle, transform=ax.transAxes)
    elif boundary == "extent" and not isinstance(map_crs, ccrs.PlateCarree):
        # LambertConformal used by EuropeAsia needs the same rectangular
        # clipping path as the legacy template.  PlateCarree keeps Cartopy's
        # normal extent boundary, which is already equivalent to the old
        # EastAsia/CnArea behavior.
        xmin, xmax, ymin, ymax = domain.extent
        resolution = 1
        vertices = (
            [(longitude, ymin) for longitude in np.arange(xmin, xmax + 1, resolution)]
            + [(xmax, latitude) for latitude in np.arange(ymin, ymax + 1, resolution)]
            + [(longitude, ymax) for longitude in np.arange(xmax, xmin - 1, -resolution)]
            + [(xmin, latitude) for latitude in np.arange(ymax, ymin - 1, -resolution)]
        )
        path = mpath.Path(vertices)
        projection_transform = domain.extent_crs._as_mpl_transform(ax) - ax.transData
        ax.set_boundary(projection_transform.transform_path(path))
    if basemap is None:
        return

    from cedarkit.plots.map import get_map_loader_class

    loader_value = basemap.loader
    loader_class = (
        get_map_loader_class(loader_value)
        if isinstance(loader_value, str)
        else loader_value
    )
    if not isinstance(loader_class, type):
        raise ConfigError("invalid map loader", code="invalid_map_loader")
    try:
        loader = loader_class(
            map_type=basemap.map_type,
            **dict(basemap.loader_kwargs),
        )
        for feature in basemap.features:
            if not feature.enabled:
                continue
            features = loader.get_feature(feature.name, **dict(feature.kwargs))
            if features is None:
                raise ContentError(
                    f"map feature {feature.name!r} returned None",
                    code="invalid_map_feature",
                )
            for item in features:
                ax.add_feature(item)
        if basemap.map_info is not None:
            text, x, y = _map_info_values(basemap.map_info)
            add_map_info_text(ax, x=x, y=y, text=text)
    except (ConfigError, ContentError):
        raise
    except Exception as exc:
        raise RenderError(
            "map resources failed to load",
            stage="map",
            cause=exc,
        ) from exc


def _create_subplots(
    figure: Figure,
    chart: Chart,
    spec: ChartSpec,
    chart_box: tuple[float, float, float, float],
    generation: int,
) -> dict[str, Subplot]:
    result: dict[str, Subplot] = {}
    enabled = {
        subplot_id: subplot
        for subplot_id, subplot in spec.subplots.items()
        if subplot.enabled
    }
    while len(result) < len(enabled):
        progress = False
        for subplot_id, subplot_spec in sorted(
            enabled.items(),
            key=lambda item: (
                float(item[1].zorder),
                0 if item[0] == "main" else 1,
                item[0],
            ),
        ):
            if subplot_id in result:
                continue
            position = subplot_spec.position
            if position.space == "chart":
                parent_box = chart_box
            elif position.space == "subplot":
                parent_id = position.subplot
                if parent_id not in result:
                    continue
                parent_box = result[parent_id]._ax.get_position().bounds
            else:
                raise ConfigError(
                    "subplot positions must use chart or subplot space",
                    code="layout_position",
                    path=("charts", chart.id, "subplots", subplot_id, "position"),
                )
            box = _relative_box(
                parent_box,
                position.bounds,
                path=("charts", chart.id, "subplots", subplot_id, "position"),
            )
            map_axis = subplot_spec.kind == "map"
            if map_axis:
                if not isinstance(subplot_spec.map_crs, ccrs.Projection):
                    raise ConfigError(
                        "map subplot requires a Cartopy projection",
                        code="invalid_map_crs",
                        path=("charts", chart.id, "subplots", subplot_id, "map_crs"),
                    )
                ax = figure.add_axes(box, projection=subplot_spec.map_crs)
            elif subplot_spec.kind == "xy":
                ax = figure.add_axes(box)
            else:
                raise ConfigError(
                    f"unsupported subplot kind {subplot_spec.kind!r}",
                    code="subplot_unavailable",
                    path=("charts", chart.id, "subplots", subplot_id, "kind"),
                )
            ax.set_facecolor(spec.theme.axes_facecolor)
            ax.tick_params(labelsize=spec.theme.tick_fontsize)
            ax.set_aspect(subplot_spec.aspect)
            ax.set_zorder(subplot_spec.zorder)
            ax.apply_aspect()
            _apply_axis_spec(
                ax,
                subplot_spec.axis,
                map_axis=map_axis,
                tick_crs=(subplot_spec.domain.extent_crs if map_axis else None),
            )
            if map_axis:
                _render_basemap(ax, subplot_spec)
                result[subplot_id] = MapSubplot(
                    chart,
                    subplot_id,
                    ax,
                    generation,
                    subplot_spec.domain,
                    subplot_spec.map_crs,
                )
            else:
                result[subplot_id] = Subplot(chart, subplot_id, ax, generation)
            progress = True
        if not progress:
            unresolved = tuple(subplot_id for subplot_id in enabled if subplot_id not in result)
            raise ConfigError(
                f"subplot positions contain an unresolved parent: {unresolved!r}",
                code="layout_dependency",
                path=("charts", chart.id, "subplots"),
            )
    return result


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

    def apply_template(self, template: Any = None) -> None:
        if self._legacy is not None:
            raise ConfigError("apply_template is unavailable for the legacy domain API", code="legacy_api")
        return self._impl.apply_template(template)

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

    def colorbar(
        self,
        layers: PlotLayer | Sequence[PlotLayer],
        *,
        id: str | None = None,
        subplots: str = "main",
        label: str | None = None,
    ) -> str:
        if self._legacy is not None:
            raise ConfigError("colorbar is unavailable for the legacy domain API", code="legacy_api")
        return self._impl._register_colorbar(
            None,
            layers,
            id=id,
            subplots=subplots,
            label=label,
        )

    def remove_colorbar(self, id: str) -> None:
        if self._legacy is not None:
            raise ConfigError("remove_colorbar is unavailable for the legacy domain API", code="legacy_api")
        return self._impl._remove_colorbar(id)

    def share_scale(self, layers: PlotLayer | Sequence[PlotLayer], *, id: str | None = None) -> str:
        if self._legacy is not None:
            raise ConfigError("share_scale is unavailable for the legacy domain API", code="legacy_api")
        return self._impl._register_scale(layers, id=id)

    def remove_scale(self, id: str) -> None:
        if self._legacy is not None:
            raise ConfigError("remove_scale is unavailable for the legacy domain API", code="legacy_api")
        return self._impl._remove_scale(id)

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
