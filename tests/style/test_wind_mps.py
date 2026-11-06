"""Physical wind vectors and the explicit CEMC m/s symbol contract."""

import matplotlib

matplotlib.use("Agg")

import numpy as np
import xarray as xr
import cartopy.crs as ccrs

from cedarkit.plots import Panel
from cedarkit.plots.config import BasemapSpec, SubplotSpec
from cedarkit.plots.domains import Domain
from cedarkit.plots.style import StyleRegistry


def test_explicit_mps_variant_preserves_the_existing_default():
    registry = StyleRegistry.default()
    physical = registry.get_style("cemc.wind:cn_mps")
    legacy = registry.get_style("cemc.wind:cn")
    assert physical.expected_units == "m/s"
    assert physical.barb_increments == {"half": 2, "full": 4, "flag": 20}
    assert registry._lookup("wind", "cn_mps")[3].barb_increments == physical.barb_increments
    assert registry._lookup("wind", "cn")[3].barb_increments is None
    assert legacy.barb_increments == {"half": 2, "full": 4, "flag": 20}


def test_rendered_mps_symbols_receive_physical_vectors_without_rescaling():
    # Calm, half feather, full feather, flag, flag+full+half, and northward full.
    u = xr.DataArray([[0., 2., 4., 20., 26., 0.]], dims=("y", "x"), attrs={"units": "m/s"})
    v = u.copy(data=[[0., 0., 0., 0., 0., 4.]])
    before_u, before_v = u.copy(deep=True), v.copy(deep=True)
    style = StyleRegistry.default().get_style("cemc.wind:cn_mps")
    with Panel() as panel:
        layer = panel.add_chart().barbs(u, v, style=style)
        panel.render()
        artist = layer.results["main"].artists[0]
        np.testing.assert_array_equal(artist.u, u.values.ravel())
        np.testing.assert_array_equal(artist.v, v.values.ravel())
        assert artist.barb_increments == {"half": 2, "full": 4, "flag": 20}
        assert artist.rounding is True
        paths = [path.vertices for path in artist.get_paths()]
        assert len(paths) == 6
        # A half feather reaches half the transverse height of a full feather.
        np.testing.assert_allclose(paths[1][:, 1].max() * 2, paths[2][:, 1].max())
        # Full feathers retrace a line; flags form a non-degenerate triangle.
        np.testing.assert_allclose(paths[2][1], paths[2][3])
        flag = paths[3][1:4]
        area = np.linalg.det(np.stack((flag[1] - flag[0], flag[2] - flag[0])))
        assert abs(area) > 0
        assert len(paths[4]) > len(paths[3])
        # A northward full-feather symbol rotates the eastward symbol by 90°.
        np.testing.assert_allclose(paths[5], np.column_stack((-paths[2][:, 1], paths[2][:, 0])), atol=1e-12)
    xr.testing.assert_identical(u, before_u)
    xr.testing.assert_identical(v, before_v)


def test_earth_relative_mps_vectors_rotate_without_changing_speed():
    lon, lat = [90., 105., 120.], [20., 45.]
    u = xr.DataArray(np.full((2, 3), 4.), dims=("lat", "lon"),
                     coords={"lat": lat, "lon": lon}, attrs={"units": "m/s"})
    v = u.copy(data=np.zeros((2, 3)))
    domain = Domain(extent=(90, 120, 20, 45), extent_crs=ccrs.PlateCarree(),
                    map_crs=ccrs.LambertConformal(central_longitude=105, central_latitude=35))
    with Panel() as panel:
        chart = panel.add_chart()
        chart.configure(subplots={"main": SubplotSpec(kind="map", domain=domain,
                                                       basemap=BasemapSpec(features=()))})
        layer = chart.barbs(u, v, style=StyleRegistry.default().get_style("cemc.wind:cn_mps"),
                            data_crs=ccrs.PlateCarree(), vector_basis="earth")
        panel.render()
        artist = layer.results["main"].artists[0]
        rotated_u, rotated_v = artist.u.reshape((2, 3)), artist.v.reshape((2, 3))
        np.testing.assert_allclose(np.hypot(rotated_u, rotated_v), 4., rtol=0, atol=1e-12)
        np.testing.assert_allclose(rotated_u[:, 1], 4., rtol=0, atol=1e-9)
        np.testing.assert_allclose(rotated_v[:, 1], 0., rtol=0, atol=1e-4)
        assert np.all(rotated_v[:, 0] < 0) and np.all(rotated_v[:, 2] > 0)
        np.testing.assert_array_equal(layer.data[0], u)
        np.testing.assert_array_equal(layer.data[1], v)
