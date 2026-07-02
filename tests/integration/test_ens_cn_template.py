import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from cedarkit.plots.domains import EnsCNMapTemplate
from cedarkit.plots.chart import Panel


class TestEnsCNMapTemplateContourf:

    def test_contourf_temperature(
        self,
        ens_cn_temperature_fields,
        sample_start_time,
        sample_forecast_time,
        temperature_style,
        output_dir,
    ):
        """15 个成员的温度填充图。"""
        domain = EnsCNMapTemplate()
        panel = Panel(domain=domain)

        panel.plot(ens_cn_temperature_fields, style=temperature_style)

        domain.set_title(
            panel=panel,
            graph_name="2m Temperature (°C)",
            system_name="EPS-Test",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        domain.add_colorbar(panel=panel, style=temperature_style)

        output_path = output_dir / "ens_cn_temperature_contourf.png"
        panel.save(output_path, dpi=150)
        plt.close()

        assert output_path.exists()
        assert output_path.stat().st_size > 0


class TestEnsCNMapTemplateWithMax:

    def test_contourf_with_max(
        self,
        ens_cn_temperature_fields_with_max,
        sample_start_time,
        sample_forecast_time,
        temperature_style,
        output_dir,
    ):
        """15 个成员 + MAX 的温度填充图。"""
        domain = EnsCNMapTemplate(enable_max=True)
        panel = Panel(domain=domain)

        panel.plot(ens_cn_temperature_fields_with_max, style=temperature_style)

        domain.set_title(
            panel=panel,
            graph_name="2m Temperature (°C)",
            system_name="EPS-Test",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        domain.add_colorbar(panel=panel, style=temperature_style)

        output_path = output_dir / "ens_cn_temperature_with_max.png"
        panel.save(output_path, dpi=150)
        plt.close()

        assert output_path.exists()
        assert output_path.stat().st_size > 0


class TestEnsCNMapTemplateStructure:

    def test_chart_count_default(self, ens_cn_temperature_fields):
        """默认模式应创建 15 个 chart。"""
        domain = EnsCNMapTemplate()
        panel = Panel(domain=domain)

        assert len(panel.charts) == 15

        plt.close()

    def test_chart_count_with_max(self, ens_cn_temperature_fields):
        """enable_max 模式应创建 16 个 chart。"""
        domain = EnsCNMapTemplate(enable_max=True)
        panel = Panel(domain=domain)

        assert len(panel.charts) == 16

        plt.close()

    def test_each_chart_has_one_layer(self, ens_cn_temperature_fields):
        """每个 chart 应有 1 个 layer。"""
        domain = EnsCNMapTemplate()
        panel = Panel(domain=domain)

        for chart in panel.charts:
            assert len(chart.layers) == 1

        plt.close()
