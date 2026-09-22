"""New Chart style strings and explicitly selected generic auto matching."""
import cartopy.crs as ccrs

from cedarkit.plots import Panel
from cedarkit.plots.style import LevelStep, StyleRegistry, resolve_style
from cedarkit.plots.templates import global_map


def test_explicit_style_spec(global_temperature_field, output_dir):
    field = global_temperature_field.assign_attrs(cemc_name="t")
    panel = Panel(template=global_map())
    try:
        chart = panel.add_chart(id="temperature")
        layer = chart.contourf(field, style="generic.t:default", data_crs=ccrs.PlateCarree())
        assert panel.fig is None
        assert layer.style.levels == LevelStep(4, 0)
        output_path = output_dir / "global_temperature_style_spec.png"
        panel.save(output_path, dpi=150)
        assert tuple(layer.results) == ("main",)
        assert output_path.exists() and output_path.stat().st_size > 0
    finally:
        panel.close()


def test_explicit_generic_auto_style(global_temperature_field, output_dir):
    field = global_temperature_field.assign_attrs(cemc_name="t")
    registry = StyleRegistry.default(profile="generic")
    assert registry.explain({"cemc_name": "t"})["selected"] == "generic.t:default"
    style = resolve_style("auto", field, registry=registry)
    panel = Panel(template=global_map())
    try:
        chart = panel.add_chart(id="temperature")
        layer = chart.contourf(field, style=style, data_crs=ccrs.PlateCarree())
        output_path = output_dir / "global_temperature_auto_style.png"
        panel.save(output_path, dpi=150)
        assert layer.style.levels == LevelStep(4, 0)
        assert tuple(layer.results) == ("main",)
        assert output_path.exists() and output_path.stat().st_size > 0
    finally:
        panel.close()
