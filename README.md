# cedarkit-maps

![GitHub Release](https://img.shields.io/github/v/release/cemc-oper/cedarkit-maps)
![PyPI - Version](https://img.shields.io/pypi/v/cedarkit-maps)
![GitHub License](https://img.shields.io/github/license/cemc-oper/cedarkit-maps)
![GitHub Action Workflow Status](https://github.com/cemc-oper/cedarkit-maps/actions/workflows/ci.yaml/badge.svg)

A plotting tool for meteorology data.

## Install

Install using pip:

```bash
pip install cedarkit-maps
```

Or download the latest source code from GitHub and install manually.

## Getting started

The following example uses CMA-GFS data to draw a 2m temperature contour fill plot.

Set some variables: 

```py
import pandas as pd

graph_name = "2m Temperature (C)"
system_name = "CMA-GFS"
start_time = pd.to_datetime("2024-11-09")
forecast_time = pd.to_timedelta("24h")
```

Get local data file path using reki:

```py
from reki.data_finder import find_local_file

data_file_path = find_local_file(
    "cma_gfs_gmf/grib2/orig",
    start_time=start_time,
    forecast_time=forecast_time,
)
```

Load 2m temperature field from file and convert unit:

```py
from reki.format.grib.eccodes import load_field_from_file

field_t_2m = load_field_from_file(
    data_file_path,
    parameter="2t",
) - 273.15
```

Create contour style, including levels and colormap.
In this example, a NCL colormap embedded in the project is used.

```py
import numpy as np
import matplotlib.colors as mcolors
from cedarkit.maps.colormap import get_ncl_colormap
from cedarkit.maps.style import ContourStyle

t_2m_level = [-24, -20, -16, -12, -8, -4, 0, 4, 8, 12, 16, 20, 24, 28, 32]

color_map = get_ncl_colormap("BlAqGrYeOrReVi200")
color_index = np.array([2, 12, 22, 32, 42, 52, 62, 72, 82, 92, 102, 112, 122, 132, 142, 152]) - 2
t_2m_color_map = mcolors.ListedColormap(color_map(color_index))

t_2m_style = ContourStyle(
    colors=t_2m_color_map,
    levels=t_2m_level,
    fill=True,
)
```

Create a build-in template `EastAsiaMapTemplate`.
A template is a pre-defined layout to put title, text info, colorbar in some position. 

```py
from cedarkit.maps.domains import EastAsiaMapTemplate

domain = EastAsiaMapTemplate()
```

Create plot panel and plot the field:

```py
from cedarkit.maps.chart import Panel

panel = Panel(domain=domain)
panel.plot(field_t_2m, style=t_2m_style)
```

Add title and colorbar:

```py
domain.set_title(
    panel=panel,
    graph_name=graph_name,
    system_name=system_name,
    start_time=start_time,
    forecast_time=forecast_time,
)
domain.add_colorbar(panel=panel, style=t_2m_style)
```

Show the picture:

```py
panel.show()
```

## LICENSE

Copyright &copy; 2021-2024, developers at cemc-oper.

`cedarkit-maps` is licensed under [Apache License V2.0](./LICENSE)

### Third party

cedarkit/maps/resources/map/china-shapefiles is from project [dongli/china-shapefiles](https://github.com/dongli/china-shapefiles).

cedarkit/maps/resources/colormap/ncl is from project [NCL](https://github.com/NCAR/ncl).
