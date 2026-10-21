# 最终三因子策略 Investability 交付

日期：2026-10-21。研究对象：K3 / IV weekly / top20。正式初始资金仍为100,000 SGD，源分红除权后14日到账。

## 阅读顺序

1. `report/K3_INVESTABILITY_ZH.html`：离线中文报告，8张图，含已计算情景筛选。双击用浏览器打开，无需联网或Python。
2. `REPORT_ZH.md`：便于组员整合和阅读的同版文字报告。
3. `results/scenario_summary.csv`：46条冻结目标情景、130个期间汇总；`feedback_summary.csv`另有2条状态反馈情景。
4. `results/verification.json`：48条账户路径的账务、股数、现金、整手及量上限核验。

## 主要结论

- 10万基准逐日NAV与正式交付一致；EVAL年化20.11%、最大回撤14.36%，金额完成率98.62%。
- 初始100万的冻结目标EVAL年化23.09%，金额完成率75.73%。高年化同时伴随更大目标偏离，不能据此给百万容量盖章。
- 10万完整路径4316笔订单：3032笔原日完成、1194笔延后完成、90笔未完成；99.45%的成交票触发5新币最低佣金。
- 新版原执行日零量订单28笔，无新建仓；旧版29笔/2笔新建仓结论不沿用。
- 9/30真实持仓的后续日行情退出代理：10万初始账户正常量约4日清仓、量减半约9日；历史其他尾部快照10日仍可能未清完。
- 10万实际持仓反馈与正式301次目标集合完全一致；100万有133次不同，表明放大资金后必须重视状态反馈。
- 独立检查2026-10-05 SGX首批11只股票整手修订：当前窗口不涉及这些目标，路径不变。
- 报价档位、费用、冲击及退出风险的完整限定见报告。结果是日频代理执行研究，不是券商真实成交认证。

## 数据与账户口径

来源为最新仓库 `lu2548214469-bit/FE5209-GroupProject`，主分支已整合归因的版本 `15f407466b61df60e3113eeaecc108ce7323a6ea`。策略与输入仍承接 `abf1c66ffd82b03c6183ff3546a5eb30749db934`。

源配置、输入及运行代码38个文件记录在 `source_manifest.json`。没有修改源策略、源数据、原有回测代码或既有归因。

- EVAL：2021年初现金起点至2026-09-30；当年收益2026仅至9月。
- WHOLE：同一连续账户至2026-10-15。
- OCTOBER_CLOSE：10/1收盘到10/15；不包含10/1首次建仓成本。
- OCTOBER_CASH：仅用于10月重新建仓的独立账户，从10万等各自初始现金起算。
- “初始100万账户”的净值会增长，后期持仓容量不同于始终固定100万当期净值。
- 金额完成率以信号价格衡量原订单和终止剩余；重复调仓请求重复进入分母。整手取整前的目标缺口另列。
- 行业、财务PIT、分红覆盖和价格股数单位等原研究限制保留。10月公司行动源无记录的完整性未认证。

## 情景范围

资本2.5/5/10/25/50/100/200/500万；参与率1/5/10%；成交量减半；1/3/5日订单期限；最低佣金0/1/5/10新币；滑点0/5/10/20/50bp；额外平方根冲击Y=0.25/0.5/1；1股可分割性诊断；已公告整手变化；费用GST9%诊断；5%现金储备；T+0诊断；联合不利情景；10月独立资金与报价档位情景。不是全参数笛卡尔组合，也不是穷尽最坏情况。

另有2条同规则实际持仓反馈情景，及3个历史日期×2种账户×2种量水平的12条退出路径。反馈及退出研究不替代冻结的正式结果。

## 组员如何复算

阅读报告不需要安装。复算使用Python3.12，依赖见 `requirements.txt`，不需要下载新的行情数据。

本模块已放入仓库内部，不需要移动原项目文件。源数据直接读取根目录data/，正式目标和逐日净值读取已合并的performance_attribution/，输出保存在本模块中。

```
FE5209-GroupProject/
  config/、data/、src/、performance_attribution/   # 原有内容
  investability/
    README.md                                  # 当前版本与历史版说明
    sg_k3_ivweekly_top20_20261021/                # 本次交付
```

在仓库根目录安装本模块依赖后，进入本目录执行。需要独立环境时按requirements.txt安装，不必改动原项目依赖或入口。也可以用环境变量FE5209_SOURCE_REPO显式指定源仓库。

进入本目录，按顺序运行：

```
python run_study.py
python diagnostics.py
python extra_diagnostics.py
python exit_replay.py
python feedback_replay.py
python verify_study.py
python build_report.py
python export_markdown.py
```

`run_study.py`先对账基准，再用2个本地进程运行独立情景。各情景保存完整股数、现金、成交及贡献流水。已算情景可缓存复用；关键源输入、代码、目标或情景设置变化会拒绝旧缓存，避免混用。文本哈希忽略Git换行符差异，压缩输入严格按字节检查。源策略改变时请新建研究目录，并更新基准，不要绕过控制。

`refresh_metrics.py`仅供维护：在确认源哈希不变时，从既有路径重新生成指标，不重做模拟。正常复算不需要它。

## 文件说明

- `scenarios/<情景>/`：压缩CSV流水与设置审计。
- `results/baseline_order_detail.csv`、`baseline_fill_detail.csv`：逐订单和成交票诊断。
- `signal_capacity_scenarios.csv`、`capacity_summary.csv`：信号时已知容量代理。
- `liquidation_full_position_detail.csv`、`liquidation_by_snapshot.csv`：整仓退出静态代理。
- `exit_replay_*.csv`：后续已观察行情退出与T+2卖出款账。排除原现金、旧应收和新分红，不作为总回报NAV。
- `capital_tracking_summary.csv`、`capital_year_results.csv`：不同资金的目标距离与年度表现。
- `board_lot_*.csv`：订单产生前的整手目标缺口。
- `feedback_*.csv`：实际持仓反馈及目标差异。
- `report/figures/`：8张PNG，可用于汇报。

CSV为UTF-8；如Excel直接打开中文乱码，请从“数据→从文本/CSV”选择UTF-8。

本版本按用户授权整合到指定GitHub仓库。完整场景流水已按CSV.gz逐项保存；为避免重复存储，不把内容相同的68MB离线ZIP再放入Git历史。如需单独离线包，在本目录运行python package_delivery.py即可生成。

旧版的定位与替代范围见上一级README.md。源live/risk.py、原回测入口、配置、数据和既有归因均保持不变。
