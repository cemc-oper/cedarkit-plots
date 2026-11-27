"""Render fixed inputs through the public plotting APIs for layout comparisons."""

import argparse
from dataclasses import replace
from datetime import datetime
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

import cartopy.crs as ccrs
import matplotlib
import numpy as np
from PIL import Image
import xarray as xr

from cedarkit.plots import Panel
from cedarkit.plots.config import LayoutSpec
from cedarkit.plots.map import set_default_map_loader_package
from cedarkit.plots.style import ContourLabelStyle, ContourStyle
from cedarkit.plots.templates import (
    cn_area,
    east_asia,
    europe_asia,
    global_area,
    global_map,
    north_polar,
    time_profile,
    xy,
)
from cedarkit.plots.testing import east_asia_temperature_field, temperature_style

GFS_INIT = "2026-11-02T12:00:00Z"
GEPS_INIT = "2026-09-22T00:00:00Z"
PLATE_CARREE = ccrs.PlateCarree()


def box_pixels(box):
    return [round(value, 2) for value in box.bounds]


def save(panel, output, name, basemap):
    path = output / f"{name}.png"
    with panel:
        panel.save(path, bbox_inches="tight")
        figure = panel.fig
        axes = {
            f"{chart.id}.{name}": subplot.ax
            for chart in panel.charts.values()
            for name, subplot in chart.subplots.items()
        }
        with Image.open(path) as image:
            return {
                "canvas_pixels": [round(size * figure.dpi) for size in figure.get_size_inches()],
                "png_pixels": list(image.size),
                "sha256": sha256(path.read_bytes()).hexdigest(),
                "dpi": figure.dpi,
                "basemap": basemap,
                "axes_xywh_pixels": {key: box_pixels(ax.bbox) for key, ax in axes.items()},
                "colorbar_xywh_pixels": [
                    box_pixels(ax.bbox) for ax in figure.axes if ax not in axes.values()
                ],
                "figure_text": [item.get_text() for item in figure.texts],
                "axes_text": {
                    key: [item.get_text() for item in ax.texts if item.get_visible()]
                    for key, ax in axes.items()
                },
            }


def synthetic_cases():
    longitude, latitude = np.arange(-180, 181, 2), np.arange(-90, 91, 2)
    lon, lat = np.meshgrid(np.deg2rad(longitude), np.deg2rad(latitude))
    temperature = xr.DataArray(
        27 - 58 * np.sin(lat) ** 2 + 8 * np.cos(3 * lon + 2 * lat),
        dims=("latitude", "longitude"),
        coords={"latitude": latitude, "longitude": longitude},
        attrs={"units": "degC"},
    )
    height = temperature.copy(data=5700 + 600 * np.sin(lat) + 120 * np.sin(4 * lon))
    height.attrs = {"units": "gpm"}
    height = height.sel(longitude=slice(20, 170), latitude=slice(0, 70))
    national = east_asia_temperature_field(
        coords=(np.arange(70, 141), np.arange(0, 61))
    )
    steps, levels = np.arange(0, 79, 3), [1000, 925, 850, 700, 500, 300, 200]
    hour, pressure = np.meshgrid(steps, levels)
    profile = xr.DataArray(
        18 - .07 * (1000 - pressure) + 6 * np.cos(hour / 5 + pressure / 200),
        dims=("pressure", "step"),
        coords={"pressure": levels, "step": steps},
        attrs={"units": "degC"},
    )
    yield "cn_area", cn_area(with_inset=True), national, "National 2 m temperature", None
    yield "cn_area_north", cn_area(area=(108, 124, 33, 45)), national, "North China 2 m temperature", None
    yield "europe_asia", europe_asia(), temperature, "Europe and Asia | Temperature and height", height
    yield "europe_asia_inset", europe_asia(with_inset=True), temperature, "Europe and Asia | Temperature and height", height
    yield "global_map", global_map(), temperature, "Global 2 m temperature", None
    yield "global_area", global_area(), temperature, "Global 2 m temperature", None
    yield "global_area_region", global_area(area=(20, 150, -20, 60)), temperature, "Regional 2 m temperature", None
    yield "north_polar", north_polar(), temperature, "Northern Hemisphere 2 m temperature", None
    wide_polar = replace(north_polar(), layout=LayoutSpec(figsize=(12, 7), dpi=160))
    yield "north_polar_wide", wide_polar, temperature, "Northern Hemisphere 2 m temperature", None
    axes_labels = {"xlabel": "Lead time (h)", "ylabel": "Pressure (hPa)"}
    yield "xy", xy(**axes_labels), profile, "Filled temperature section", None
    line = xy(xlim=(6, 66), ylim=(300, 1000), xticks=(6, 30, 54),
              yticks=(300, 500, 700, 1000), invert_y=True, **axes_labels)
    yield "xy_lines", line, profile, "Temperature isolines", None
    yield "time_profile", time_profile(steps, levels, datetime.fromisoformat(GFS_INIT)), profile, "Beijing | Temperature", None


def synthetic_panel(name, template, field, title, overlay):
    panel = Panel(template=template)
    try:
        chart = panel.add_chart(id="main")
        chart.set_title(title)
        if name == "xy_lines":
            chart.contour(field, style=ContourStyle(colors=("black",), levels=range(-40, 31, 10), label=True))
        else:
            kwargs = {} if name in {"xy", "time_profile"} else dict(data_crs=PLATE_CARREE, subplots="all")
            layer = chart.contourf(field, style=temperature_style(), **kwargs)
            chart.colorbar(layer, label="°C")
            if overlay is not None:
                style = ContourStyle(
                    colors=("#292634",), levels=range(5200, 6500, 200), linewidths=.7,
                    label=True, label_style=ContourLabelStyle(fontsize=7, fmt="%.0f"),
                )
                chart.contour(overlay, style=style, data_crs=PLATE_CARREE)
        if name == "time_profile":
            chart.set_title("Init 2026-11-02 12 UTC", id="init")
        return panel
    except BaseException:
        panel.close()
        raise


def mounted_cases(root, selected):
    from cedar_graph.data import RekiProvider
    from cedar_graph.recipes.ensemble_product import EnsembleRequest, EnsembleT2MProduct
    from cedar_graph.recipes.workflow_product import select_workflow_product
    from cedarkit.plots.workflow.plan import CompileContext
    from cedarkit.plots.workflow.render import render_result

    gfs = {"east_asia": True, "east_asia_no_inset": False}
    if not selected or selected & gfs.keys():
        product = select_workflow_product("cn.t2m")
        plan = product.compile(CompileContext(
            start_time=GFS_INIT, forecast_time="6h",
            params={"style_variant": "cn_summer", "model": "CMA-GFS"},
        ))
        with RekiProvider({"kind": "local", "dataset": "cma_gfs_gmf", "root": str(root)}) as provider:
            result = plan.execute(provider, registry=product.discovery.ops)
        for name, with_inset in gfs.items():
            if not selected or name in selected:
                yield name, render_result(result, templates={"east_asia": east_asia(with_inset=with_inset)}, render=False)
    layouts = {"ens_cn": (5, True), "ens_cn_3": (3, True), "ens_cn_3_no_max": (3, False)}
    if not selected or selected & layouts.keys():
        product = EnsembleT2MProduct()
        with RekiProvider({"kind": "local", "dataset": "cma_geps", "root": str(root)}) as provider:
            for name, (columns, max_enabled) in layouts.items():
                if not selected or name in selected:
                    request = EnsembleRequest(
                        member_ids=("m001", "m002"), control_id="m000", include_control_in_max=max_enabled,
                        columns=columns, max_enabled=max_enabled, style_variant="cn_summer", model="CMA-GEPS",
                    )
                    prepared = product.prepare(provider, start_time=GEPS_INIT, forecast_time="24h", request=request)
                    yield name, prepared.render(render=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("cases", nargs="*")
    parser.add_argument("--cmadaas", type=Path, help="CMADaaS mount root for the real cases")
    parser.add_argument("--cemc-basemap", action="store_true", help="Use the installed cemc-meda-data loader")
    args = parser.parse_args()
    matplotlib.use("Agg")
    matplotlib.rcParams["font.family"] = "DejaVu Sans"
    args.output.mkdir(parents=True, exist_ok=True)
    selected = set(args.cases)
    evidence = {}
    basemap = "default / Natural Earth 50m"
    if args.cemc_basemap:
        set_default_map_loader_package("cedarkit.plots.map.cemc")
        basemap = "CEMC / Natural Earth 50m"
    if args.cmadaas:
        for name, panel in mounted_cases(args.cmadaas, selected):
            evidence[name] = save(panel, args.output, name, basemap)
    for name, template, field, title, overlay in synthetic_cases():
        if not selected or name in selected:
            source = None if name.startswith("xy") or name == "time_profile" else basemap
            evidence[name] = save(synthetic_panel(name, template, field, title, overlay), args.output, name, source)
    if missing := selected - evidence.keys():
        parser.error(f"unknown or missing input for cases: {sorted(missing)}")
    versions = {name: version(name) for name in ("cedarkit-plots", "cartopy", "matplotlib", "numpy", "xarray")}
    if args.cmadaas:
        versions.update({name: version(name) for name in ("cedar-graph", "reki")})
    if args.cemc_basemap:
        versions["cemc-meda-data"] = version("cemc-meda-data")
    (args.output / "metrics.json").write_text(json.dumps({"versions": versions, "cases": evidence}, indent=2) + "\n")
    print(", ".join(evidence))


if __name__ == "__main__":
    main()
