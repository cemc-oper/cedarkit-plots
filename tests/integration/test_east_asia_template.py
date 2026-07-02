import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from cedarkit.plots.domains import EastAsiaMapTemplate
from cedarkit.plots.chart import Panel
from cedarkit.plots.style import ContourStyle


class TestEastAsiaMapTemplateContourf:
    
    def test_contourf_temperature(
        self,
        east_asia_temperature_field,
        sample_start_time,
        sample_forecast_time,
        temperature_style,
        output_dir
    ):
        domain = EastAsiaMapTemplate()
        panel = Panel(domain=domain)
        
        panel.plot(east_asia_temperature_field, style=temperature_style)

        panel.set_title(
            graph_name="2m Temperature (°C)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        
        panel.add_colorbar(style=temperature_style)
        
        output_path = output_dir / "east_asia_temperature_contourf.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"
    
    def test_contourf_precipitation(
        self,
        east_asia_precipitation_field,
        sample_start_time,
        sample_forecast_time,
        precipitation_style,
        output_dir
    ):
        domain = EastAsiaMapTemplate()
        panel = Panel(domain=domain)
        panel.plot(east_asia_precipitation_field, style=precipitation_style)
        
        panel.set_title(
            graph_name="24h Precipitation (mm)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        panel.add_colorbar(style=precipitation_style)
        
        output_path = output_dir / "east_asia_precipitation_contourf.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"


class TestEastAsiaMapTemplateContour:
    
    def test_pressure_contour(
        self,
        east_asia_pressure_field,
        sample_start_time,
        sample_forecast_time,
        pressure_contour_style,
        output_dir
    ):
        domain = EastAsiaMapTemplate()
        panel = Panel(domain=domain)
        panel.plot(east_asia_pressure_field, style=pressure_contour_style)
        
        panel.set_title(
            graph_name="MSLP (hPa)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        
        output_path = output_dir / "east_asia_pressure_contour.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"


class TestEastAsiaMapTemplateBarb:
    def test_wind_barb(
        self,
        east_asia_wind_fields,
        sample_start_time,
        sample_forecast_time,
        wind_barb_style,
        output_dir
    ):
        u_field, v_field = east_asia_wind_fields
        
        domain = EastAsiaMapTemplate()
        panel = Panel(domain=domain)
        
        panel.plot([[u_field, v_field]], style=wind_barb_style, layer=[0])
        
        panel.set_title(
            graph_name="10m Wind (m/s)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        
        output_path = output_dir / "east_asia_wind_barb.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"


class TestEastAsiaMapTemplateCombined:
    def test_temperature_with_wind(
        self,
        east_asia_temperature_field,
        east_asia_wind_fields,
        sample_start_time,
        sample_forecast_time,
        temperature_style,
        wind_barb_style_black,
        output_dir
    ):
        u_field, v_field = east_asia_wind_fields
        
        domain = EastAsiaMapTemplate()
        panel = Panel(domain=domain)

        panel.plot(east_asia_temperature_field, style=temperature_style)
        panel.plot([[u_field, v_field]], style=wind_barb_style_black, layer=[0])
        
        panel.set_title(
            graph_name="2m Temperature (°C) & 10m Wind",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        panel.add_colorbar(style=temperature_style)
        
        output_path = output_dir / "east_asia_temperature_wind_combined.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"
    
    def test_pressure_contour_with_temperature_fill(
        self,
        east_asia_temperature_field,
        east_asia_pressure_field,
        sample_start_time,
        sample_forecast_time,
        temperature_style,
        pressure_contour_style,
        output_dir
    ):
        domain = EastAsiaMapTemplate()
        panel = Panel(domain=domain)
        
        panel.plot(east_asia_temperature_field, style=temperature_style)
        panel.plot(east_asia_pressure_field, style=pressure_contour_style)
        
        panel.set_title(
            graph_name="MSLP (hPa) & 2m Temperature (°C)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        panel.add_colorbar(style=temperature_style)
        
        output_path = output_dir / "east_asia_pressure_temperature_combined.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"


class TestEastAsiaMapTemplateOptions:
    def test_without_sub_area(
        self,
        east_asia_temperature_field,
        sample_start_time,
        sample_forecast_time,
        temperature_style,
        output_dir
    ):
        domain = EastAsiaMapTemplate(with_sub_area=False)
        panel = Panel(domain=domain)
        panel.plot(east_asia_temperature_field, style=temperature_style)
        
        panel.set_title(
            graph_name="2m Temperature (°C)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        panel.add_colorbar(style=temperature_style)
        
        output_path = output_dir / "east_asia_without_sub_area.png"
        panel.save(output_path, dpi=150)
        plt.close()

        assert len(panel.charts[0].layers) == 1
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"
    
    def test_with_sub_area(
        self,
        east_asia_temperature_field,
        temperature_style,
        output_dir
    ):
        domain = EastAsiaMapTemplate(with_sub_area=True)
        panel = Panel(domain=domain)
        panel.plot(east_asia_temperature_field, style=temperature_style)
        
        output_path = output_dir / "east_asia_with_sub_area.png"
        panel.save(output_path, dpi=150)
        plt.close()

        assert len(panel.charts[0].layers) == 2
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"


class TestEastAsiaMapTemplateEdgeCases:
    
    def test_empty_style_levels(self, east_asia_temperature_field, output_dir):
        """测试空 levels 的处理"""
        style = ContourStyle(
            colors="RdYlBu_r",
            levels=None,
            fill=True,
        )
        
        domain = EastAsiaMapTemplate()
        panel = Panel(domain=domain)
        
        panel.plot(east_asia_temperature_field, style=style)
        output_path = output_dir / "east_asia_empty_levels.png"
        panel.save(output_path, dpi=150)
        plt.close()

        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"

    
    def test_single_value_field(
        self, 
        east_asia_coords, 
        temperature_style,
        output_dir
    ):
        """测试单一值场的处理"""
        import xarray as xr
        
        lons, lats = east_asia_coords
        data = np.full((len(lats), len(lons)), 25.0)
        field = xr.DataArray(
            data,
            dims=['latitude', 'longitude'],
            coords={'latitude': lats, 'longitude': lons}
        )
        
        domain = EastAsiaMapTemplate()
        panel = Panel(domain=domain)
        panel.plot(field, style=temperature_style)
        
        output_path = output_dir / "east_asia_single_value_field.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"
