import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from cedarkit.plots.domains import GlobalMapTemplate
from cedarkit.plots.chart import Panel


class TestGlobalMapTemplateContourf:
    
    def test_contourf_temperature(
        self, 
        global_temperature_field, 
        sample_start_time,
        sample_forecast_time,
        temperature_style,
        output_dir
    ):
        domain = GlobalMapTemplate()
        panel = Panel(domain=domain)
        
        panel.plot(global_temperature_field, style=temperature_style)

        panel.set_title(
            graph_name="2m Temperature (°C)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        
        panel.add_colorbar(style=temperature_style)
        
        output_path = output_dir / "global_temperature_contourf.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"


class TestGlobalMapTemplateContour:
    
    def test_pressure_contour(
        self,
        global_pressure_field,
        sample_start_time,
        sample_forecast_time,
        pressure_contour_style,
        output_dir
    ):
        domain = GlobalMapTemplate()
        panel = Panel(domain=domain)
        panel.plot(global_pressure_field, style=pressure_contour_style)
        
        panel.set_title(
            graph_name="MSLP (hPa)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        
        output_path = output_dir / "global_pressure_contour.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"


class TestGlobalMapTemplateBarb:
    
    def test_wind_barb(
        self,
        global_wind_fields,
        sample_start_time,
        sample_forecast_time,
        wind_barb_style,
        output_dir
    ):
        u_field, v_field = global_wind_fields
        
        domain = GlobalMapTemplate()
        panel = Panel(domain=domain)
        
        panel.plot([[u_field, v_field]], style=wind_barb_style)
        
        panel.set_title(
            graph_name="10m Wind (m/s)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        
        output_path = output_dir / "global_wind_barb.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"


class TestGlobalMapTemplateCombined:
    
    def test_temperature_with_wind(
        self,
        global_temperature_field,
        global_wind_fields,
        sample_start_time,
        sample_forecast_time,
        temperature_style,
        wind_barb_style_black,
        output_dir
    ):
        u_field, v_field = global_wind_fields
        
        domain = GlobalMapTemplate()
        panel = Panel(domain=domain)

        panel.plot(global_temperature_field, style=temperature_style)
        panel.plot([[u_field, v_field]], style=wind_barb_style_black)
        
        panel.set_title(
            graph_name="2m Temperature (°C) & 10m Wind",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        panel.add_colorbar(style=temperature_style)
        
        output_path = output_dir / "global_temperature_wind_combined.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"
    
    def test_pressure_contour_with_temperature_fill(
        self,
        global_temperature_field,
        global_pressure_field,
        sample_start_time,
        sample_forecast_time,
        temperature_style,
        pressure_contour_style,
        output_dir
    ):
        domain = GlobalMapTemplate()
        panel = Panel(domain=domain)
        
        panel.plot(global_temperature_field, style=temperature_style)
        panel.plot(global_pressure_field, style=pressure_contour_style)
        
        panel.set_title(
            graph_name="MSLP (hPa) & 2m Temperature (°C)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        panel.add_colorbar(style=temperature_style)
        
        output_path = output_dir / "global_pressure_temperature_combined.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"
