---
mystnb:
  execution_mode: 'off'
---

# 安装

## 从 PyPI 安装

```bash
pip install cedarkit-plots
```

会同时安装运行时依赖：`numpy`、`pandas`、`matplotlib`、
`cartopy>=0.23`、`xarray`、`reki`、`cedarkit-comp`。

`cedarkit-plots` 实际使用 `reki` 来读取真实 GRIB2 数据；
本文档示例不会触碰真实数据，因此 `reki` 与 ecCodes 都不是
运行示例所必需的。

## 从源码安装（uv）

cedarkit-plots 源码仓库与姊妹包（`reki`、`cedarkit-comp`）
并列于 `cedarkit/` 工作区目录下。`pyproject.toml` 中的
`[tool.uv.sources]` 已经把姊妹包配置成本地可编辑安装，
因此对任一姊妹包的修改都会立即生效。

```bash
uv sync                  # 安装运行时依赖
uv sync --extra test     # 同时安装 pytest + scipy（集成测试需要）
uv sync --extra docs     # 同时安装 Sphinx + sphinx-book-theme
```

## Cartopy 自然地球数据

`cartopy>=0.23` 在第一次调用海岸线、国界等要素时会从
[Natural Earth](https://www.naturalearthdata.com/) 下载数据。
如果在离线环境构建文档，请在有网络的机器上预先调用一次
`Panel.fig` 触发下载，然后把
`~/.local/share/cartopy/`（或 conda 环境下的对应目录）
拷贝到无网络的机器即可。
