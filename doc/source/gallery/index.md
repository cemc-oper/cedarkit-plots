---
mystnb:
  execution_mode: 'off'
---

# 绘图图集

图集样例使用当前 `Panel`/`Chart`/`PlotLayer` 内容模型和固定合成场，不读取
业务数据。区域预设只提供展示配置；调用方创建的内容才会绘制。

```{toctree}
:maxdepth: 1

east_asia
europe_asia
global
north_polar
ens_cn
```

图库中的可视化由可执行 Notebook 单元格在文档构建时动态生成，图像资源随 Sphinx 站点一同输出。更多快绘样例见
{doc}`../tutorials/quickplot`；如需单独导出 PNG，可运行
[`render_plot_examples.py`](../examples/render_plot_examples.py)，默认写入仓库外的临时目录。
