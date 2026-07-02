import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from cedarkit.plots.domains import NorthPolarMapTemplate
from cedarkit.plots.chart import Panel


class TestNorthPolarMapTemplateContourf:
    
    def test_contourf_temperature(
        self, 
        north_polar_temperature_field, 
        sample_start_time,
        sample_forecast_time,
        temperature_style,
        output_dir
    ):
        domain = NorthPolarMapTemplate()
        panel = Panel(domain=domain)
        
        panel.plot(north_polar_temperature_field, style=temperature_style)

        panel.set_title(
            graph_name="2m Temperature (°C)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        
        panel.add_colorbar(style=temperature_style)
        
        output_path = output_dir / "north_polar_temperature_contourf.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"


class TestNorthPolarMapTemplateContour:
    
    def test_pressure_contour(
        self,
        north_polar_pressure_field,
        sample_start_time,
        sample_forecast_time,
        pressure_contour_style,
        output_dir
    ):
        domain = NorthPolarMapTemplate()
        panel = Panel(domain=domain)
        panel.plot(north_polar_pressure_field, style=pressure_contour_style)
        
        panel.set_title(
            graph_name="MSLP (hPa)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        
        output_path = output_dir / "north_polar_pressure_contour.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"


class TestNorthPolarMapTemplateBarb:
    
    def test_wind_barb(
        self,
        north_polar_wind_fields,
        sample_start_time,
        sample_forecast_time,
        wind_barb_style,
        output_dir
    ):
        u_field, v_field = north_polar_wind_fields
        
        domain = NorthPolarMapTemplate()
        panel = Panel(domain=domain)
        
        panel.plot([[u_field, v_field]], style=wind_barb_style)
        
        panel.set_title(
            graph_name="10m Wind (m/s)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        
        output_path = output_dir / "north_polar_wind_barb.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"


class TestNorthPolarMapTemplateCombined:
    
    def test_temperature_with_wind(
        self,
        north_polar_temperature_field,
        north_polar_wind_fields,
        sample_start_time,
        sample_forecast_time,
        temperature_style,
        wind_barb_style_black,
        output_dir
    ):
        u_field, v_field = north_polar_wind_fields
        
        domain = NorthPolarMapTemplate()
        panel = Panel(domain=domain)

        panel.plot(north_polar_temperature_field, style=temperature_style)
        panel.plot([[u_field, v_field]], style=wind_barb_style_black)
        
        panel.set_title(
            graph_name="2m Temperature (°C) & 10m Wind",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        panel.add_colorbar(style=temperature_style)
        
        output_path = output_dir / "north_polar_temperature_wind_combined.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"
    
    def test_pressure_contour_with_temperature_fill(
        self,
        north_polar_temperature_field,
        north_polar_pressure_field,
        sample_start_time,
        sample_forecast_time,
        temperature_style,
        pressure_contour_style,
        output_dir
    ):
        domain = NorthPolarMapTemplate()
        panel = Panel(domain=domain)
        
        panel.plot(north_polar_temperature_field, style=temperature_style)
        panel.plot(north_polar_pressure_field, style=pressure_contour_style)
        
        panel.set_title(
            graph_name="MSLP (hPa) & 2m Temperature (°C)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        panel.add_colorbar(style=temperature_style)
        
        output_path = output_dir / "north_polar_pressure_temperature_combined.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"
