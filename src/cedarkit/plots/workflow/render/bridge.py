"""One-way bridge from a materialized result to stable plotting content."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import cartopy.crs as ccrs

from ... import Panel
from ...config import (
    UNSET, AnnotationSpec, AxisSpec, BasemapSpec, BorderSpec, Cell,
    ChartRule, ChartSelector, ChartSpec, ColorbarSpec, DecorationSpec,
    GridlineSpec, LayoutSpec, MapFeatureSpec, Rect, SlotSpec, SubplotSpec,
    TextPosition, Theme, TitleSpec,
)
from ...domains import Domain
from ...domains.registry import DomainRegistry
from ...map import MapType
from ...painter.map_painter import MapInfo
from ...style.registry import StyleRegistry, get_default_registry
from ...templates import PanelTemplate
from ..recipe.schema import Display
from ..runtime.model import WorkflowResult


class WorkflowRenderError(ValueError):
    def __init__(self, recipe_identity: str, path: str, cause: Exception):
        self.recipe_identity, self.path, self.cause = recipe_identity, path, cause
        super().__init__(f"product={recipe_identity} at {path}: {cause}")


def _crs(value: str | None) -> Any:
    if value is None:
        return None
    if value == "plate_carree":
        return ccrs.PlateCarree()
    if value == "geodetic":
        return ccrs.Geodetic()
    raise ValueError(f"unsupported CRS {value!r}; use plate_carree or geodetic")


def _position(value: Mapping[str, Any]) -> Rect | TextPosition:
    if "bounds" in value:
        return Rect(**value)
    if "xy" in value:
        return TextPosition(**value)
    raise ValueError("position requires bounds or xy")


def _decorations(value: Mapping[str, Any]) -> DecorationSpec:
    extra = set(value) - {"titles", "colorbars"}
    if extra:
        raise ValueError(f"unknown decoration fields {sorted(extra)}")
    titles = {name: TitleSpec(**{**entry, **({"position": _position(entry["position"])}
                                        if "position" in entry else {})})
              for name, entry in value.get("titles", {}).items()}
    bars = {name: ColorbarSpec(**{**entry, **({"position": _position(entry["position"])}
                                          if "position" in entry else {})})
            for name, entry in value.get("colorbars", {}).items()}
    return DecorationSpec(titles=titles, colorbars=bars)


def _basemap(value: Mapping[str, Any]) -> BasemapSpec:
    fields = dict(value)
    if "map_type" in fields and isinstance(fields["map_type"], str):
        fields["map_type"] = MapType(fields["map_type"])
    if "features" in fields:
        fields["features"] = tuple(MapFeatureSpec(**entry) for entry in fields["features"])
    if "map_info" in fields and isinstance(fields["map_info"], Mapping):
        fields["map_info"] = MapInfo(**fields["map_info"])
    return BasemapSpec(**fields)


def _axis(value: Mapping[str, Any]) -> AxisSpec:
    fields = dict(value)
    if isinstance(fields.get("gridlines"), Mapping):
        fields["gridlines"] = GridlineSpec(**fields["gridlines"])
    if isinstance(fields.get("border"), Mapping):
        fields["border"] = BorderSpec(**fields["border"])
    return AxisSpec(**fields)


def _subplot(value: Mapping[str, Any]) -> SubplotSpec:
    fields = dict(value)
    if isinstance(fields.get("domain"), Mapping):
        domain = dict(fields["domain"])
        domain["extent_crs"] = _crs(domain["extent_crs"])
        if "map_crs" in domain:
            domain["map_crs"] = _crs(domain["map_crs"])
        fields["domain"] = Domain(**domain)
    if "map_crs" in fields:
        fields["map_crs"] = _crs(fields["map_crs"])
    if isinstance(fields.get("position"), Mapping):
        fields["position"] = Rect(**fields["position"])
    if isinstance(fields.get("axis"), Mapping):
        fields["axis"] = _axis(fields["axis"])
    if isinstance(fields.get("basemap"), Mapping):
        fields["basemap"] = _basemap(fields["basemap"])
    if isinstance(fields.get("annotations"), Mapping):
        annotations = {}
        for name, entry in fields["annotations"].items():
            annotation = dict(entry)
            if "crs" in annotation:
                annotation["crs"] = _crs(annotation["crs"])
            if isinstance(annotation.get("position"), Mapping):
                annotation["position"] = TextPosition(**annotation["position"])
            annotations[name] = AnnotationSpec(**annotation)
        fields["annotations"] = annotations
    return SubplotSpec(**fields)


def _chart_spec(value: Mapping[str, Any]) -> ChartSpec:
    fields = dict(value)
    if "subplots" in fields:
        fields["subplots"] = {name: _subplot(item) for name, item in fields["subplots"].items()}
    if "theme" in fields:
        fields["theme"] = Theme(**fields["theme"])
    if "decorations" in fields:
        fields["decorations"] = _decorations(fields["decorations"])
    return ChartSpec(**fields)


def _layout(value: Mapping[str, Any]) -> LayoutSpec:
    fields = dict(value)
    if "placements" in fields:
        fields["placements"] = {name: Rect(**item) if "space" in item else Cell(**item)
                                for name, item in fields["placements"].items()}
    if "slots" in fields:
        slots = {}
        for name, item in fields["slots"].items():
            slot = dict(item)
            if "position" in slot:
                slot["position"] = (Rect(**slot["position"]) if "space" in slot["position"]
                                    else Cell(**slot["position"]))
            slots[name] = SlotSpec(**slot)
        fields["slots"] = slots
    if "order" in fields:
        fields["order"] = tuple(ChartSelector(**item) for item in fields["order"])
    return LayoutSpec(**fields)


def _template(name: str | None, templates: Mapping[str, Any] | None,
              domains: DomainRegistry | None) -> PanelTemplate | None:
    if name is None:
        return None
    if templates is not None and name in templates:
        candidate = templates[name]
    else:
        return (domains or DomainRegistry.builtins()).create(name)
    value = candidate() if callable(candidate) else candidate
    if not isinstance(value, PanelTemplate):
        raise TypeError(f"template {name!r} must resolve to PanelTemplate")
    return value


def _display(value: Display | Mapping[str, Any]) -> Display:
    return value if isinstance(value, Display) else Display.model_validate(value)


def render_result(
    result: WorkflowResult, *, display: Display | Mapping[str, Any] | None = None,
    style_registry: StyleRegistry | None = None, templates: Mapping[str, Any] | None = None,
    domains: DomainRegistry | None = None,
    render: bool = True,
) -> Panel:
    """Create stable content from prepared values, optionally render once.

    The returned Panel owns its Figure, not the provider or WorkflowResult.
    A failed build/render closes the temporary Panel before raising.
    """
    presentation = result.display if display is None else _display(display)
    panel: Panel | None = None
    path = "spec.display"
    try:
        template = _template(presentation.template, templates, domains)
        options: dict[str, Any] = {}
        if presentation.layout:
            options["layout"] = _layout(presentation.layout)
        elif template is None and len(result.content.charts) > 1:
            options["layout"] = LayoutSpec(rows="auto", columns=1)
        if presentation.chart_defaults:
            options["chart_defaults"] = _chart_spec(presentation.chart_defaults)
        if presentation.chart_rules:
            options["chart_rules"] = tuple(ChartRule(selector=ChartSelector(**item["selector"]),
                                                       spec=_chart_spec(item["spec"]))
                                           for item in presentation.chart_rules)
        if presentation.decorations:
            options["decorations"] = _decorations(presentation.decorations)
        panel = Panel(template=template, **options)
        styles = style_registry or get_default_registry()
        layers: dict[tuple[str, str], Any] = {}
        for chart_spec in result.content.charts:
            path = f"spec.content.charts.{chart_spec.id}"
            chart = panel.add_chart(id=chart_spec.id, role=chart_spec.role)
            if chart_spec.id in presentation.charts:
                override = _chart_spec(presentation.charts[chart_spec.id])
                chart.configure(subplots=override.subplots, theme=override.theme,
                                decorations=override.decorations)
            for plot in chart_spec.plots:
                path = f"spec.content.charts.{chart_spec.id}.plots.{plot.id}"
                data = (result.outputs[plot.vector.u], result.outputs[plot.vector.v]) if plot.vector else result.outputs[plot.field]
                style = styles.get_style(plot.style, data=data[0] if isinstance(data, tuple) else data)
                kwargs = {"style": style, "id": plot.id, "subplots": plot.targets,
                          "data_crs": _crs(plot.data_crs)}
                if plot.zorder is not None:
                    kwargs["zorder"] = plot.zorder
                if plot.method == "barbs":
                    layer = chart.barbs(*data, vector_basis=plot.vector_basis or "grid", **kwargs)
                else:
                    layer = getattr(chart, plot.method)(data, **kwargs)
                layers[(chart_spec.id, plot.id)] = layer
            for title in chart_spec.titles:
                chart.set_title(title.text, id=title.id)
            for bar in chart_spec.colorbars:
                path = f"spec.content.charts.{chart_spec.id}.colorbars.{bar.id}"
                chart.colorbar(tuple(layers[(ref.chart, ref.plot)] for ref in bar.plots),
                               id=bar.id, subplots=bar.target, label=bar.label)
        for title in result.content.titles:
            panel.set_title(title.text, id=title.id)
        for bar in result.content.colorbars:
            path = f"spec.content.colorbars.{bar.id}"
            panel.colorbar(tuple(layers[(ref.chart, ref.plot)] for ref in bar.plots),
                           id=bar.id, subplots=bar.target, label=bar.label)
        if render:
            path = "render"
            panel.render()
        return panel
    except Exception as exc:
        if panel is not None:
            panel.close()
        if isinstance(exc, WorkflowRenderError):
            raise
        raise WorkflowRenderError(result.recipe_identity, path, exc) from exc
