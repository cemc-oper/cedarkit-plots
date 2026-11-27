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

To rerun the baseline, use the renderer from `af63568` with the baseline checkouts. For the Europe and Asia height overlay, use the renderer from `a5a86e1` and select only `europe_asia` and `europe_asia_inset`.

## Accepted candidate

The plotting candidate was `2262b84` with cedar-graph `2f3c770`, cemc-plots-kit `8e5395e` and cedarkit-notebook `c0e6014`. The same Python 3.12 and reki 2026.11.0 environment drove the layout tests and product runs.

| Preset | Before PNG (pixels) | After PNG (pixels) | Visual check |
| --- | --- | --- | --- |
| `east_asia` | 1097 × 928 | 1193 × 856 | The main frame and full scale are both 691 px high. The gap is 42 px. |
| `cn_area` | 597 × 506 | 772 × 436 | National and North China extents have separate tick density and map notes. |
| `europe_asia` | 828 × 418 | 960 × 513 | Lambert edge labels and the height contours fit with either inset setting. |
| `global_map` | 908 × 449 | 992 × 502 | The frame keeps a 2:1 ratio and the 80°E center. The seam is filled on both sides. |
| `global_area` | 908 × 449 | 992 × 502 | The 10° graticule reads over country borders. A caller-selected regional extent renders separately. |
| `north_polar` | 729 × 608 | 703 × 661 | The circle and its twelve meridian labels fit in both tested canvas shapes. |
| `ens_cn` | 1613 × 318 | 1662 × 313 | CTL, MAX and members share one temperature scale. Unused grid cells stay empty. |
| `xy` | 598 × 553 | 764 × 484 | Filled and line-only cases fit with caller-supplied ticks and axis limits. |
| `time_profile` | 598 × 569 | 826 × 510 | UTC increases from left to right and pressure decreases upwards. The final tick includes the year. |

Run the commands from the owning checkout with the candidate packages installed.

```sh
# cedarkit-plots
PYTHONPATH="$PWD/src" python -m pytest -q tests
python doc/layout-validation/render.py /tmp/layout-cemc east_asia --cmadaas /CMADAAS --cemc-basemap

# cedar-graph
PYTHONPATH="$PWD/src" python -m pytest -q tests/mock

# cemc-plots-kit
PYTHONPATH="$PWD/src" python -m pytest -q tests/unit
cemc-plots run examples/task-v2-gfs-layout-validation.yaml
cemc-plots run examples/task-v2-ensemble.yaml
```

The suites passed 456, 65 and 112 tests respectively. The two CLI tasks produced five images. The implicit November palette output matched the explicit winter image byte for byte. The ensemble manifest confirmed all three selected GEPS fields and their pointwise MAX. Jupyter Book 2.1.6 built the executed Notebook outputs, and 56 image assets across 36 pages passed the file and dimensions checks.

Natural Earth 50m country outlines are downloaded on demand for the public global-area loader. The optional CEMC loader supplies operational province and river features. The standalone CEMC run uses the same GFS temperature field as R05. The Notebook build used the local file branch of the MUSIC tutorial and documented synthetic inputs for the three examples limited by the local archive.
