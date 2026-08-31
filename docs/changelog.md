---
mystnb:
  execution_mode: 'off'
---

# 变更记录

权威的变更日志在 [GitHub Releases](https://github.com/cemc-oper/cedarkit-plots/releases)
中维护。重要变更会同步在这里。

## 待发布

- `RequestKey` 保留稳定 parameter ID，而 Recipe v2/PlotPlan 继续不保存
  dataset、source、CMADaaS 名称、data code 或认证信息。availability provider
  对不能 metadata-only 检查的 direct-result source 可以明确返回 `unknown`。
- 新增版本化 Recipe v2、不可变 PlotPlan、静态 `recipe plan` 预览和
  plugin/availability public API。v1 reader 与 `PlotModuleAdapter` 保持兼容；
  新 recipe 应使用 v2 与显式 data units，未来弃用会先在本记录公告。
- 新增 ReadTheDocs 文档站点（Sphinx + sphinx-book-theme）。
- 新增公开模块 {mod}`cedarkit.plots.testing`，与集成测试套件
  共用合成数据生成函数与预设样式。
