# Built-in layout validation

## L01-01 · Baseline

Run from the repository root in a Python 3.12 environment with the local package installed. The baseline used cedarkit-plots `a8e00ed`, Cartopy 0.26.0, Matplotlib 3.11.2, NumPy 2.5.5 and xarray 2026.9.0. The two mounted cases also used cedar-graph `d270391` and reki 2026.11.0.

```sh
python doc/layout-validation/render.py /tmp/layout-synthetic --cemc-basemap
python doc/layout-validation/render.py /tmp/layout-gfs east_asia east_asia_no_inset --cmadaas /CMADAAS
python doc/layout-validation/render.py /tmp/layout-geps ens_cn ens_cn_3 ens_cn_3_no_max --cmadaas /CMADAAS
```

The script holds the inputs, styles and PNG export options fixed. Each output directory contains `metrics.json` with the figure and PNG dimensions, DPI and axes rectangles in pixels before tight cropping. The direct map calls use the `cemc-meda-data` map loader at `c244696` when selected. The mounted products use the default loader with Natural Earth 50m and the packaged China shapefiles. Both use Agg and DejaVu Sans.

| Preset | Input and public entry point |
| --- | --- |
| `east_asia` | `cn.t2m` on CMA-GFS 2026-11-02 12 UTC +6 h, `cn_summer`, with and without an inset through `render_result`. The R05-01 CLI image is the original comparison. |
| `cn_area` | Fixed 2 m temperature in °C, nationwide with a South China Sea inset and North China without one. |
| `europe_asia` | Fixed temperature in °C and height isolines in gpm within 20–170°E and 0–70°N, with and without an inset. |
| `global_map` | Periodic temperature field on a 2° global grid, including equal samples at ±180°. |
| `global_area` | The same field, also plotted for 20°E–150°E, 20°S–60°N. |
| `north_polar` | The same field on two canvas shapes. |
| `ens_cn` | `cn.ens_t2m` on CMA-GEPS 2026-09-22 00 UTC +24 h, m000/m001/m002, three and five columns with optional MAX. This reuses the D15 sample. |
| `xy` | Fixed two-dimensional section, as filled contours and isolines with caller-supplied bounds, ticks and inverted Y. |
| `time_profile` | Beijing example using the same synthetic section, 200–1000 hPa and +0 to +78 h. |

The workspace layout checklist stores the before and after PNGs, mounted data identifiers and time-pinned business references.
