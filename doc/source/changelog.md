---
mystnb:
  execution_mode: 'off'
---

# 变更记录

正式版本和发行日期以 [GitHub Releases](https://github.com/cemc-oper/cedarkit-plots/releases)
为准。以下记录当前开发版尚未发行的功能和迁移说明。

## 未发布

- 完成统一的新绘图内容模型：`Panel` 持有稳定的 `Chart` 与 `PlotLayer`；
  `Subplot` 和 Matplotlib artists 由渲染产生，可在模板或配置变更后重建。
- `Panel`、`Chart` 支持直接配置，也支持值对象形式的可选
  `PanelTemplate`/`ChartTemplate`。模板仅负责布局、子图、区域和展示规则，不
  创建图层、数据或成员。
- 使用 `contourf`、`contour` 和显式 `barbs(u, v)` 登记图层；增加地图主图/附图
  多目标、显式 CRS、共享色阶/色标、配置校验和 Figure 生命周期管理。
- 内置 CEMC 与通用样式、原生 palette、明确单位准备，以及单场、向量和 facet
  快绘。样式检查已准备的数据，不执行隐式单位转换。
- 收拢为 `cedarkit.plots.workflow` v3 recipe/plan/provider/renderer 与
  `cedarkit-plots recipe validate|plan` CLI。workflow 是可选依赖，普通
  Panel/Chart 绘图不依赖它。
- 删除旧 Panel/domain 建图协议、旧 Layer/engine/plan/recipe 执行路径和相关
  兼容入口；此版本不提供旧绘图 API、导入路径或 schema 的兼容/自动迁移服务。
- 文档示例固定合成场和 DejaVu Sans，可通过 Agg 后端重建，代表图及脚本位于
  `docs/examples/`。
