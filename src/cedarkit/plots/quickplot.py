"""Small plotting factories over the ordinary Panel/Chart lifecycle.

These functions render once and return caller-owned content handles. They do
not fetch fields, infer vector components, create ensemble statistics, or
maintain a second rendering path.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from os import PathLike
from typing import Any, Literal

import xarray as xr

from .chart import Chart, Panel, PlotLayer
from .config import UNSET, LayoutSpec
from .style import BarbStyle, ContourStyle, StyleRegistry, resolve_style
from .templates import PanelTemplate
from .units import TemperatureKind, UnitConversion, prepare_field, prepare_vector

__all__ = ['FacetItem', 'QuickPlotResult', 'plot', 'barbs', 'facet']


@dataclass(frozen=True)
class FacetItem:
    """An explicitly identified scalar member; roles never imply statistics."""

    id: str
    field: xr.DataArray
    role: str | None = 'member'
    title: str | None = None


@dataclass(frozen=True)
class QuickPlotResult:
    """Caller owns ``panel``; handles remain stable through render/re-layout.

    ``conversions`` aligns with ``layers``: zero records when no preparation
    was requested, one for a scalar, two for vector components. Records
    describe the initial preparation, not subsequent caller layer updates.
    """

    panel: Panel
    charts: tuple[Chart, ...]
    layers: tuple[PlotLayer, ...]
    conversions: tuple[tuple[UnitConversion, ...], ...]
    scale_id: str | None = None

    @property
    def chart(self) -> Chart:
        if len(self.charts) != 1:
            raise ValueError('use charts for a multi-chart result')
        return self.charts[0]

    @property
    def layer(self) -> PlotLayer:
        if len(self.layers) != 1:
            raise ValueError('use layers for a multi-layer result')
        return self.layers[0]

    def close(self) -> None:
        self.panel.close()

    def __enter__(self) -> QuickPlotResult:
        self.panel.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.close()
        return False


def _scalar(field: xr.DataArray) -> None:
    if not isinstance(field, xr.DataArray) or field.ndim != 2:
        raise TypeError('scalar plotting requires a two-dimensional xarray.DataArray; use facet with an explicit dim')


def _identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        raise ValueError(f'{name} must be a non-empty string without whitespace')


def _method(method: str) -> None:
    if method not in ('contourf', 'contour'):
        raise ValueError('scalar method must be contourf or contour; vectors use barbs(u, v)')


def _colorbar(value: bool | None, method: str) -> bool:
    if value is not None and not isinstance(value, bool):
        raise TypeError('colorbar must be bool or None')
    return method == 'contourf' if value is None else value


def _prepare(field, units, source_units, temperature_kind):
    _scalar(field)
    if units is None and source_units is None and temperature_kind is None:
        return field, ()
    prepared = prepare_field(field, units=units, source_units=source_units,
                             temperature_kind=temperature_kind)
    return prepared.field, (prepared.conversion,)


def _style(style, field, registry, overrides, expected_type):
    resolved = resolve_style(style, field, registry=registry, overrides=overrides)
    if not isinstance(resolved, expected_type):
        raise TypeError(f'this method requires {expected_type.__name__}')
    if isinstance(resolved, ContourStyle) and resolved.levels is None:
        raise ValueError("quick scalar styles require fixed levels or LevelStep; supply style_overrides")
    return resolved


def _output(panel, output, save_kwargs):
    if output is None:
        panel.render()
    else:
        panel.save(output, **dict(save_kwargs or {}))


def _output_options(output, save_kwargs):
    if save_kwargs is not None:
        if not isinstance(save_kwargs, Mapping):
            raise TypeError('save_kwargs must be a mapping')
        if output is None:
            raise ValueError('save_kwargs requires output')
        unknown = set(save_kwargs) - {'dpi', 'format', 'bbox_inches', 'transparent'}
        if unknown:
            raise ValueError(f'unsupported save options: {sorted(unknown)}')


def plot(
    field: xr.DataArray, *, method: Literal['contourf', 'contour'] = 'contourf',
    style: ContourStyle | str | None = None, registry: StyleRegistry | None = None,
    style_overrides: Mapping[str, Any] | None = None,
    units: str | None = None, source_units: str | None = None,
    temperature_kind: TemperatureKind | None = None,
    chart_id: str = 'main', role: str | None = None, title: str | None = None,
    colorbar: bool | None = None, colorbar_id: str = 'colorbar',
    colorbar_label: str | None = None, data_crs: Any = None, subplots: Any = 'main',
    template: PanelTemplate | None = None, layout: Any = UNSET, theme: Any = UNSET,
    chart_defaults: Any = UNSET, chart_rules: Any = UNSET, decorations: Any = UNSET,
    output: str | PathLike | None = None, save_kwargs: Mapping[str, Any] | None = None,
) -> QuickPlotResult:
    """Render one scalar field using an explicit method, never Style.fill.

    None/"auto" style resolves from prepared metadata in the default CEMC
    registry. Pass a registry for another profile or explicit generic fallback.
    Without preparation keywords the input is bound as-is, never converted
    to fit a style. Successful results stay open, including after saving.
    """
    _method(method)
    _identifier(chart_id, 'chart_id')
    _output_options(output, save_kwargs)
    with_colorbar = _colorbar(colorbar, method)
    _identifier(colorbar_id, "colorbar_id")
    field, records = _prepare(field, units, source_units, temperature_kind)
    resolved = _style(style, field, registry, style_overrides, ContourStyle)
    panel = Panel(template=template, layout=layout, theme=theme, chart_defaults=chart_defaults,
                  chart_rules=chart_rules, decorations=decorations)
    try:
        chart = panel.add_chart(id=chart_id, role=role)
        draw = chart.contourf if method == 'contourf' else chart.contour
        layer = draw(field, style=resolved, id='field', data_crs=data_crs, subplots=subplots)
        if title is not None:
            chart.set_title(title)
        if with_colorbar:
            chart.colorbar(layer, id=colorbar_id, label=colorbar_label, subplots="all")
        _output(panel, output, save_kwargs)
        return QuickPlotResult(panel, (chart,), (layer,), (records,))
    except BaseException:
        panel.close()
        raise


def barbs(
    u: xr.DataArray, v: xr.DataArray, *, style: BarbStyle | str | None = None,
    registry: StyleRegistry | None = None, style_overrides: Mapping[str, Any] | None = None,
    units: str | None = None, source_units: tuple[str | None, str | None] | None = None,
    chart_id: str = 'main', role: str | None = None, title: str | None = None,
    data_crs: Any = None, subplots: Any = 'main', vector_basis: str = 'grid',
    template: PanelTemplate | None = None, layout: Any = UNSET, theme: Any = UNSET,
    chart_defaults: Any = UNSET, chart_rules: Any = UNSET, decorations: Any = UNSET,
    output: str | PathLike | None = None, save_kwargs: Mapping[str, Any] | None = None,
) -> QuickPlotResult:
    """Render explicit u/v components; automatic identity matching uses u.

    Both components are validated by Chart. Explicit preparation uses the
    shared vector helper and retains both conversion records. No colorbar is
    meaningful for this method; no tuple unpacking or component guessing.
    """
    _scalar(u)
    _scalar(v)
    _identifier(chart_id, 'chart_id')
    _output_options(output, save_kwargs)
    records = ()
    if units is not None or source_units is not None:
        prepared = prepare_vector(u, v, units=units, source_units=source_units)
        u, v, records = prepared.u, prepared.v, prepared.conversions
    resolved = _style(style, u, registry, style_overrides, BarbStyle)
    panel = Panel(template=template, layout=layout, theme=theme, chart_defaults=chart_defaults,
                  chart_rules=chart_rules, decorations=decorations)
    try:
        chart = panel.add_chart(id=chart_id, role=role)
        layer = chart.barbs(u, v, style=resolved, id='wind', data_crs=data_crs,
                            subplots=subplots, vector_basis=vector_basis)
        if title is not None:
            chart.set_title(title)
        _output(panel, output, save_kwargs)
        return QuickPlotResult(panel, (chart,), (layer,), (records,))
    except BaseException:
        panel.close()
        raise


def _members(data, dim, ids, roles):
    if isinstance(data, xr.DataArray):
        if not isinstance(dim, str) or dim not in data.dims or data.ndim != 3:
            raise ValueError('DataArray facet requires an explicit dim leaving exactly two field dimensions')
        count = data.sizes[dim]
        if ids is None:
            if dim not in data.coords or data.coords[dim].dims != (dim,):
                raise ValueError('facet dimension needs a one-dimensional coordinate or explicit ids')
            ids = tuple(str(value) for value in data.coords[dim].values)
        else:
            if isinstance(ids, (str, bytes)):
                raise TypeError('ids must be a sequence of strings')
            ids = tuple(ids)
        if roles is None:
            roles = ('member',) * count
        else:
            if isinstance(roles, (str, bytes)):
                raise TypeError('roles must be a sequence')
            roles = tuple(roles)
        if len(ids) != count or len(roles) != count:
            raise ValueError('ids and roles must match the facet dimension length')
        members = tuple(FacetItem(identifier, data.isel({dim: index}), role)
                        for index, (identifier, role) in enumerate(zip(ids, roles)))
    else:
        if dim is not None or ids is not None or roles is not None:
            raise ValueError('iterable facets carry IDs/roles in FacetItem; dim/ids/roles apply only to DataArray')
        if isinstance(data, (xr.Dataset, str, bytes, Mapping)):
            raise TypeError('facet requires a DataArray or a finite iterable of FacetItem')
        members = tuple(data)  # Materialize a finite iterable exactly once, before creating a Panel.
    if not members:
        raise ValueError('facet input must not be empty')
    seen = set()
    for member in members:
        if not isinstance(member, FacetItem):
            raise TypeError('iterable facet members must be FacetItem instances')
        _identifier(member.id, 'member id')
        if member.id in seen:
            raise ValueError(f'duplicate facet id {member.id!r}')
        seen.add(member.id)
        if member.role is not None:
            _identifier(member.role, 'member role')
        _scalar(member.field)
    return members


def facet(
    data: xr.DataArray | Iterable[FacetItem], *, dim: str | None = None,
    ids: Sequence[str] | None = None, roles: Sequence[str | None] | None = None,
    method: Literal['contourf', 'contour'] = 'contourf',
    style: ContourStyle | str | None = None, registry: StyleRegistry | None = None,
    style_overrides: Mapping[str, Any] | None = None,
    units: str | None = None, source_units: str | None = None,
    temperature_kind: TemperatureKind | None = None,
    level_policy: Literal['per_chart', 'shared'] = 'per_chart',
    title: str | None = None, colorbar: bool | None = None,
    colorbar_id: str = 'colorbar', colorbar_label: str | None = None,
    data_crs: Any = None, subplots: Any = 'main',
    template: PanelTemplate | None = None, layout: Any = UNSET, theme: Any = UNSET,
    chart_defaults: Any = UNSET, chart_rules: Any = UNSET, decorations: Any = UNSET,
    output: str | PathLike | None = None, save_kwargs: Mapping[str, Any] | None = None,
) -> QuickPlotResult:
    """Render scalar members, preserving explicit identity and input order.

    DataArray requires a named dimension; coordinate strings become IDs unless
    supplied explicitly. All roles default to member, including coordinate 0.
    An iterable must contain FacetItem and is consumed once. No CTL/MAX is made.
    Shared levels use Panel.share_scale (same units/standard_name/style rules);
    dynamic levels otherwise use each field's range. Fixed levels stay fixed.
    """
    _method(method)
    if level_policy not in ('per_chart', 'shared'):
        raise ValueError('level_policy must be per_chart or shared')
    _output_options(output, save_kwargs)
    with_colorbar = _colorbar(colorbar, method)
    _identifier(colorbar_id, "colorbar_id")
    members = _members(data, dim, ids, roles)
    prepared = []
    for member in members:
        field, records = _prepare(member.field, units, source_units, temperature_kind)
        resolved = _style(style, field, registry, style_overrides, ContourStyle)
        prepared.append((member, field, records, resolved))
    if layout is UNSET and (template is None or (isinstance(template, PanelTemplate) and template.layout is UNSET)):
        # Factory defaults have template priority, not user-override priority:
        # a later apply_template must be able to replace the default grid.
        fallback = LayoutSpec(rows='auto', columns=min(3, len(members)))
        template = PanelTemplate(layout=fallback) if template is None else replace(template, layout=fallback)
    panel = Panel(template=template, layout=layout, theme=theme, chart_defaults=chart_defaults,
                  chart_rules=chart_rules, decorations=decorations)
    try:
        charts, layers, conversions = [], [], []
        for member, field, records, resolved in prepared:
            chart = panel.add_chart(id=member.id, role=member.role)
            chart.set_title(member.title if member.title is not None else member.id)
            draw = chart.contourf if method == 'contourf' else chart.contour
            layer = draw(field, style=resolved, id='field', data_crs=data_crs, subplots=subplots)
            charts.append(chart)
            layers.append(layer)
            conversions.append(records)
            if with_colorbar and level_policy == 'per_chart':
                chart.colorbar(layer, id=f'{colorbar_id}_{member.id}', label=colorbar_label, subplots="all")
        scale_id = None
        if level_policy == 'shared':
            if len(layers) > 1:
                scale_id = panel.share_scale(layers, id='shared')
            if with_colorbar:
                panel.colorbar(layers, id=colorbar_id, label=colorbar_label, subplots="all")
        if title is not None:
            panel.set_title(title)
        _output(panel, output, save_kwargs)
        return QuickPlotResult(panel, tuple(charts), tuple(layers), tuple(conversions), scale_id)
    except BaseException:
        panel.close()
        raise
