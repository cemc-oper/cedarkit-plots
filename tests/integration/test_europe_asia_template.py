import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from cedarkit.plots.domains import EuropeAsiaMapTemplate
from cedarkit.plots.chart import Panel


class TestEuropeAsiaMapTemplateContourf:
    
    def test_contourf_temperature(
        self, 
        europe_asia_temperature_field, 
        sample_start_time,
        sample_forecast_time,
        temperature_style,
        output_dir
    ):
        domain = EuropeAsiaMapTemplate()
        panel = Panel(domain=domain)
        
        panel.plot(europe_asia_temperature_field, style=temperature_style)

        panel.set_title(
            graph_name="2m Temperature (°C)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        
        panel.add_colorbar(style=temperature_style)
        
        output_path = output_dir / "europe_asia_temperature_contourf.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"


class TestEuropeAsiaMapTemplateContour:
    
    def test_pressure_contour(
        self,
        europe_asia_pressure_field,
        sample_start_time,
        sample_forecast_time,
        pressure_contour_style,
        output_dir
    ):
        domain = EuropeAsiaMapTemplate()
        panel = Panel(domain=domain)
        panel.plot(europe_asia_pressure_field, style=pressure_contour_style)
        
        panel.set_title(
            graph_name="MSLP (hPa)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        
        output_path = output_dir / "europe_asia_pressure_contour.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"


class TestEuropeAsiaMapTemplateBarb:
    
    def test_wind_barb(
        self,
        europe_asia_wind_fields,
        sample_start_time,
        sample_forecast_time,
        wind_barb_style,
        output_dir
    ):
        u_field, v_field = europe_asia_wind_fields
        
        domain = EuropeAsiaMapTemplate()
        panel = Panel(domain=domain)
        
        panel.plot([[u_field, v_field]], style=wind_barb_style)
        
        panel.set_title(
            graph_name="10m Wind (m/s)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        
        output_path = output_dir / "europe_asia_wind_barb.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"


class TestEuropeAsiaMapTemplateCombined:
    
    def test_temperature_with_wind(
        self,
        europe_asia_temperature_field,
        europe_asia_wind_fields,
        sample_start_time,
        sample_forecast_time,
        temperature_style,
        wind_barb_style_black,
        output_dir
    ):
        u_field, v_field = europe_asia_wind_fields
        
        domain = EuropeAsiaMapTemplate()
        panel = Panel(domain=domain)

        panel.plot(europe_asia_temperature_field, style=temperature_style)
        panel.plot([[u_field, v_field]], style=wind_barb_style_black)
        
        panel.set_title(
            graph_name="2m Temperature (°C) & 10m Wind",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        panel.add_colorbar(style=temperature_style)
        
        output_path = output_dir / "europe_asia_temperature_wind_combined.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"
    
    def test_pressure_contour_with_temperature_fill(
        self,
        europe_asia_temperature_field,
        europe_asia_pressure_field,
        sample_start_time,
        sample_forecast_time,
        temperature_style,
        pressure_contour_style,
        output_dir
    ):
        domain = EuropeAsiaMapTemplate()
        panel = Panel(domain=domain)
        
        panel.plot(europe_asia_temperature_field, style=temperature_style)
        panel.plot(europe_asia_pressure_field, style=pressure_contour_style)
        
        panel.set_title(
            graph_name="MSLP (hPa) & 2m Temperature (°C)",
            system_name="Test-Model",
            start_time=sample_start_time,
            forecast_time=sample_forecast_time,
        )
        panel.add_colorbar(style=temperature_style)
        
        output_path = output_dir / "europe_asia_pressure_temperature_combined.png"
        panel.save(output_path, dpi=150)
        plt.close()
        
        assert output_path.exists(), "image file should be created"
        assert output_path.stat().st_size > 0, "image file should not be empty"
