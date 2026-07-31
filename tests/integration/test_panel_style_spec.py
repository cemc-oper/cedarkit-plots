"""Integration tests for Panel.plot style specs (style="auto" / "id:variant")."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from cedarkit.plots.domains import GlobalMapTemplate
from cedarkit.plots.chart import Panel


class TestPanelStyleSpec:
    def test_explicit_style_spec(
        self,
        global_temperature_field,
        output_dir,
    ):
        """panel.plot(field, style="id:variant") uses the style library."""
        field = global_temperature_field
        field.attrs["cemc_name"] = "t"

        domain = GlobalMapTemplate()
        panel = Panel(domain=domain)
        panel.plot(field, style="t:default")

        output_path = output_dir / "global_temperature_style_spec.png"
        panel.save(output_path, dpi=150)
        plt.close()

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_auto_style(
        self,
        global_temperature_field,
        output_dir,
    ):
        """panel.plot(field, style="auto") matches metadata and plots."""
        field = global_temperature_field
        field.attrs["cemc_name"] = "t"

        domain = GlobalMapTemplate()
        panel = Panel(domain=domain)
        panel.plot(field, style="auto")

        output_path = output_dir / "global_temperature_auto_style.png"
        panel.save(output_path, dpi=150)
        plt.close()

        assert output_path.exists()
        assert output_path.stat().st_size > 0
