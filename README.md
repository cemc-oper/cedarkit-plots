# cedarkit-plots

![Maturity-Sandbox](https://img.shields.io/badge/Maturity-Sandbox-F9D71C)
![GitHub Release](https://img.shields.io/github/v/release/cemc-oper/cedarkit-plots)
![PyPI - Version](https://img.shields.io/pypi/v/cedarkit-plots)
![GitHub License](https://img.shields.io/github/license/cemc-oper/cedarkit-plots)
![GitHub Action Workflow Status](https://github.com/cemc-oper/cedarkit-plots/actions/workflows/ci.yaml/badge.svg)

`cedarkit-plots` 是构建在 Matplotlib 和 Cartopy 之上的气象绘图库。核心由
稳定的逻辑内容句柄 `Panel`、`Chart`、`PlotLayer` 及整图渲染器组成。调用方
可以直接配置布局、XY/地图子图、样式与装饰；`PanelTemplate`、`ChartTemplate`
只提供可复用的展示预设，不创建数据或图层。

本项目处于 Sandbox 阶段，公开 API 和 workflow recipe 仍可能调整。新绘图模型
不提供旧 Panel/domain 或旧绘图引擎的兼容层。

## 能力

- 构造 XY、多行多列及跨格布局，显式叠加填色、等值线和风羽图层。
- 使用地图主图/附图及 EastAsia、EuropeAsia、Global、NorthPolar 和集合展示预设。
- 使用内置 CEMC 样式、显式通用样式、原生色表与随数据范围计算的等级。
- 通过 `quickplot.plot()`、`quickplot.barbs()` 和 `quickplot.facet()` 快速绘图。
- 通过可选 workflow extra 加载 `cedarkit.plots/v3` recipe、静态编译计划并执行数据请求。
- 将中国地图 shapefile 与 palette 资源随包分发。

## 安装与开发

从 PyPI 安装：

```bash
pip install cedarkit-plots
```

直接使用 Panel/Chart 不需要 workflow extra。运行 workflow recipe 和相关
CLI 时安装该 extra；开发与运行测试：

```bash
cd repo/cedarkit-plots
uv sync --extra test --extra workflow
MPLBACKEND=Agg uv run pytest tests
```

安装选项、Cartopy 数据缓存和源码开发见
[`docs/getting_started/install.md`](docs/getting_started/install.md)。

## 快速示例

以下例子用固定合成温度场显式准备 K→°C，再匹配内置 CEMC 样式；不需要业务
数据：

```python
import numpy as np
import xarray as xr

from cedarkit.plots import quickplot

x, y = np.meshgrid(np.linspace(-1, 1, 30), np.linspace(-1, 1, 24))
temperature = xr.DataArray(
    273.15 + 15 + 20*x + 8*np.sin(3*y), dims=("y", "x"),
    attrs={"units": "K", "temperature_kind": "absolute",
           "cemc_name": "t2m", "standard_name": "air_temperature"},
)
with quickplot.plot(
    temperature,
    units="degC",
    title="2 m temperature",
    colorbar_label="°C",
    output="temperature.png",
) as result:
    print(result.conversions[0][0])
```

不使用快绘封装时，可直接创建 `Panel`、添加 `Chart`、登记 `PlotLayer` 并调用
`render()` / `save()`。完整的内容模型、主附图、模板切换和关闭语义见
[`docs/tutorials/templates.md`](docs/tutorials/templates.md)。

## 文档

- [快速开始](docs/getting_started/quick_start.md)与[核心概念](docs/getting_started/concepts.md)
- [直接配置、主附图与模板切换](docs/tutorials/templates.md)
- [单图、向量、facet 快绘与单位准备](docs/tutorials/quickplot.md)
- [CEMC/通用样式](docs/tutorials/styles.md)、[样式库](docs/tutorials/style_library.md)和[色表](docs/tutorials/colormap.md)
- [v3 workflow recipe 与 CLI](docs/tutorials/recipe_v3.md)
- [绘图图集](docs/gallery/index.md)及[API 参考](docs/api/index.md)
- [变更记录](docs/changelog.md)

文档页中的代表图由 MyST-NB 在 Sphinx 构建时动态生成，并随 HTML 站点作为构建产物输出。固定合成数据、
字体及独立 PNG 导出辅助脚本位于
[`docs/examples/render_plot_examples.py`](docs/examples/render_plot_examples.py)
；脚本默认将图像写入仓库外的临时目录。使用仓库锁文件运行：

```bash
uv sync --extra test --extra workflow
MPLBACKEND=Agg MPLCONFIGDIR=/tmp/cedarkit-plots-docs-mpl \
  uv run python docs/examples/render_plot_examples.py /tmp/cedarkit-plots-docs
```

## 许可与第三方资源

版权所有 &copy; 2021-2026, cemc-oper 开发者。本项目采用
[Apache License 2.0](LICENSE)。

- `cedarkit/plots/resources/map/china-shapefiles` 来源于
  [dongli/china-shapefiles](https://github.com/dongli/china-shapefiles)。
- 原生 palette 中保留的颜色及许可来源、校验和记录在
  `tools/palette_sources.json` 与 `cedarkit/plots/resources/palettes/`；原始 NCL
  表格和解析器不随运行包分发。
