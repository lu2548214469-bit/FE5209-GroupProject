# Investability：当前版本与历史版本

## 当前正式策略版

本仓库最终策略为K3 / IV weekly / top20，初始100,000 SGD，源分红除权后14日到账。

- [完整中文报告](sg_k3_ivweekly_top20_20261021/REPORT_ZH.md)
- [复算与目录说明](sg_k3_ivweekly_top20_20261021/README_ZH.md)
- [离线HTML报告](sg_k3_ivweekly_top20_20261021/report/K3_INVESTABILITY_ZH.html)
- [资金及执行情景汇总](sg_k3_ivweekly_top20_20261021/results/scenario_summary.csv)
- [校验结果](sg_k3_ivweekly_top20_20261021/results/verification.json)

48条账户路径与12条退出路径均在独立目录中保存。本模块读取既有策略和归因输出，不进入原选股、调仓或回测调用链。原来的src/sgfactor/live/risk.py继续保留，它负责原账户风险暴露报告，不是应删除的旧Investability。

## 旧版在哪里，如何处理

本次核查时，本仓库main及可见远端分支没有旧版独立Investability。旧交付在另一个仓库：

[Cross-Market-Adaptive-Multi-Factor-Strategy / Investability（冻结提交）](https://github.com/anminye/Cross-Market-Adaptive-Multi-Factor-Strategy/tree/5d6dadaed1b5ccbd45677cd4e28ed210bae59cfb/delivery/sg/investability)

| 项目 | 旧版2026-10-18 | 当前2026-10-21 |
|---|---|---|
| 研究对象 | SG_6F_Adaptive_Top3_IV | 最终K3 / IV weekly / top20 |
| 主要数据及持仓 | 旧共同池，每周约13—14只 | 更新的96只股票池，当前目标18只 |
| 交易研究 | 从目标恢复理论净订单和费用/容量情景 | 股数现金账、整手、最低佣金、成交量、T+2及延期；另含状态反馈与退出路径 |
| 原执行日零量 | 29笔，含2笔新建仓 | 28笔，无新建仓 |
| 使用方式 | 保留为历史研究和方法来源 | 用于当前最终策略的可投资性汇报 |

处理原则：保留旧仓库及其冻结证据，不删除、不覆盖、不把旧数字改写成新版。对于本项目当前策略的汇报，使用本目录新版，并同时保留数据和执行代理的限制。这个替代关系是适用范围更新，不表示旧版当时的分析无效。

本次没有修改另一个仓库。如团队今后希望给旧仓库补“历史版本”提示，可单独提交只改说明的PR；不需要为了当前整合改写旧报告或旧计算结果。
