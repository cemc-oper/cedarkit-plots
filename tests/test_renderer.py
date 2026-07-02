"""Unit tests for PlotRenderer interface and registry."""
from unittest.mock import MagicMock

import pytest

from cedarkit.plots.style import Style, ContourStyle, BarbStyle
from cedarkit.plots.chart.renderer import (
    PlotRenderer,
    ContourRenderer,
    BarbRenderer,
    register_renderer,
    get_renderer,
    _renderer_registry,
)


class TestPlotRendererInterface:
    """Test that PlotRenderer is abstract and cannot be instantiated directly."""

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            PlotRenderer()

    def test_contour_renderer_is_plot_renderer(self):
        assert isinstance(ContourRenderer(), PlotRenderer)

    def test_barb_renderer_is_plot_renderer(self):
        assert isinstance(BarbRenderer(), PlotRenderer)


class TestDefaultRegistrations:
    """Test that default renderers are registered for ContourStyle and BarbStyle."""

    def test_contour_style_registered(self):
        style = ContourStyle()
        renderer = get_renderer(style)
        assert isinstance(renderer, ContourRenderer)

    def test_barb_style_registered(self):
        style = BarbStyle()
        renderer = get_renderer(style)
        assert isinstance(renderer, BarbRenderer)


class TestGetRendererUnregistered:
    """Test that get_renderer raises NotImplementedError for unregistered styles."""

    def test_unregistered_style_raises(self):
        class CustomStyle(Style):
            pass

        with pytest.raises(NotImplementedError) as exc_info:
            get_renderer(CustomStyle())
        assert "CustomStyle" in str(exc_info.value)
        assert "register_renderer()" in str(exc_info.value)


class TestRegisterRenderer:
    """Test custom renderer registration."""

    def test_register_and_retrieve_custom_renderer(self):
        class MyStyle(Style):
            pass

        class MyRenderer(PlotRenderer):
            def render(self, layer, data, style, **kwargs):
                return "custom_result"

        renderer = MyRenderer()
        register_renderer(MyStyle, renderer)
        try:
            retrieved = get_renderer(MyStyle())
            assert retrieved is renderer
        finally:
            # Clean up to avoid polluting global state
            _renderer_registry.pop(MyStyle, None)


class TestContourRendererBehavior:
    """Test ContourRenderer dispatches to layer.contourf or layer.contour based on style.fill."""

    def test_fill_true_calls_contourf(self):
        layer = MagicMock()
        layer.contourf.return_value = "contourf_result"
        style = ContourStyle(fill=True)
        data = MagicMock()

        renderer = ContourRenderer()
        result = renderer.render(layer, data, style)

        layer.contourf.assert_called_once_with(data=data, style=style)
        assert result == "contourf_result"

    def test_fill_false_calls_contour(self):
        layer = MagicMock()
        layer.contour.return_value = "contour_result"
        style = ContourStyle(fill=False)
        data = MagicMock()

        renderer = ContourRenderer()
        result = renderer.render(layer, data, style)

        layer.contour.assert_called_once_with(data=data, style=style)
        assert result == "contour_result"

    def test_kwargs_forwarded(self):
        layer = MagicMock()
        layer.contourf.return_value = "result"
        style = ContourStyle(fill=True)
        data = MagicMock()

        renderer = ContourRenderer()
        renderer.render(layer, data, style, extra_param="value")

        layer.contourf.assert_called_once_with(data=data, style=style, extra_param="value")


class TestBarbRendererBehavior:
    """Test BarbRenderer dispatches to layer.barb with data[0] and data[1]."""

    def test_calls_barb_with_data_components(self):
        layer = MagicMock()
        layer.barb.return_value = "barb_result"
        style = BarbStyle()
        data = [MagicMock(name="u_field"), MagicMock(name="v_field")]

        renderer = BarbRenderer()
        result = renderer.render(layer, data, style)

        layer.barb.assert_called_once_with(x=data[0], y=data[1], style=style)
        assert result == "barb_result"

    def test_kwargs_forwarded(self):
        layer = MagicMock()
        layer.barb.return_value = "result"
        style = BarbStyle()
        data = [MagicMock(), MagicMock()]

        renderer = BarbRenderer()
        renderer.render(layer, data, style, extra_param="value")

        layer.barb.assert_called_once_with(x=data[0], y=data[1], style=style, extra_param="value")
