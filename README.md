# cedarkit-plots

![Maturity-Sandbox](https://img.shields.io/badge/Maturity-Sandbox-F9D71C)
![GitHub Release](https://img.shields.io/github/v/release/cemc-oper/cedarkit-plots)
![PyPI - Version](https://img.shields.io/pypi/v/cedarkit-plots)
![GitHub License](https://img.shields.io/github/license/cemc-oper/cedarkit-plots)
![GitHub Action Workflow Status](https://github.com/cemc-oper/cedarkit-plots/actions/workflows/ci.yaml/badge.svg)

`cedarkit-plots` is a low-level meteorological plotting library built on
Matplotlib and Cartopy. It provides map templates, panels and charts, plotting
styles, colormaps, and plot recipes. It is the plotting engine behind
higher-level packages such as `cedar-graph`.

> This project is at the Sandbox maturity level. Its public API and recipe
> format may still evolve.

## Features

- Compose multi-panel meteorological figures with `Panel`, `Chart`, and
  `Layer`.
- Quickly draw East Asia, Europe-Asia, global, North Polar, and ensemble
  forecast products with built-in map templates.
- Define contours, fills, wind barbs, and colorbars with reusable style
  libraries.
- Use bundled NCL colormaps and China shapefile resources.
- Load and generate plot products from declarative YAML recipes.

## Installation

Install from PyPI:

```bash
pip install cedarkit-plots
```

For development in this workspace, install dependencies and run the tests:

```bash
cd repo/cedarkit-plots
uv sync --extra test
pytest
```

For additional installation options, Cartopy data caching, and source-based
development, see the [installation guide](docs/getting_started/install.md).

## Quick start

This example uses synthetic data provided by the project, so it does not require
any operational data:

```python
import pandas as pd

from cedarkit.plots.chart import Panel
from cedarkit.plots.domains import EastAsiaMapTemplate
from cedarkit.plots.testing import east_asia_temperature_field, temperature_style

field = east_asia_temperature_field()
style = temperature_style()

panel = Panel(domain=EastAsiaMapTemplate())
panel.plot(field, style=style)
panel.set_title(
    graph_name="2m Temperature (°C)",
    system_name="cedarkit-plots demo",
    start_time=pd.Timestamp("2024-11-09 00:00:00"),
    forecast_time=pd.Timedelta("24h"),
)
panel.add_colorbar(style=style)
panel.save("temperature.png")
```

See [Quick start](docs/getting_started/quick_start.md) for a walkthrough.

## Documentation structure

Keep the README as the project entry point. Put detailed user and maintainer
documentation in `docs/`, organized as follows. This avoids maintaining the
same example or API documentation in more than one place.

```text
README.md                         Project overview, installation, minimal example, documentation links
docs/
├── getting_started/              Everything a new user needs for their first plot
│   ├── install.md                Installation, dependencies, and environment
│   ├── quick_start.md            Minimal end-to-end example
│   └── concepts.md               Panel / Chart / Layer / Style / Template concepts
├── tutorials/                    Reusable plotting workflows, organized by task
│   ├── synthetic_data.md         Synthetic data shared by documentation and tests
│   ├── styles.md                 Defining and applying styles
│   ├── style_library.md          Managing style libraries
│   ├── colormap.md               Selecting and customizing colormaps
│   ├── templates.md              Map templates and layout
│   └── recipe_v2.md              YAML plot recipes
├── gallery/                      Runnable examples, organized by final figure
├── api/                          Code-synchronized module and object reference
└── changelog.md                  Release history
```

The recommended reading order is: installation → quick start → core concepts →
relevant tutorials → gallery → API reference. When adding a feature, add a
tutorial or gallery example first; add it to the API reference only when its
public interface is stable and supported.

## Documentation

- [Installation](docs/getting_started/install.md): runtime environment and
  source-based development.
- [Quick start](docs/getting_started/quick_start.md): create your first figure
  from a synthetic temperature field.
- [Core concepts](docs/getting_started/concepts.md): responsibilities of the
  primary objects.
- [Tutorials](docs/tutorials/): styles, colormaps, templates, and YAML recipes.
- [Gallery](docs/gallery/index.md): complete figures by region and product type.
- [API reference](docs/api/index.md): generated reference for Python modules.
- [Changelog](docs/changelog.md): release history.

## License and third-party resources

Copyright &copy; 2021-2026, developers at cemc-oper.

`cedarkit-plots` is licensed under the [Apache License 2.0](LICENSE).

- `cedarkit/plots/resources/map/china-shapefiles` is from
  [dongli/china-shapefiles](https://github.com/dongli/china-shapefiles).
- `cedarkit/plots/resources/colormap/ncl` is from
  [NCL](https://github.com/NCAR/ncl).
