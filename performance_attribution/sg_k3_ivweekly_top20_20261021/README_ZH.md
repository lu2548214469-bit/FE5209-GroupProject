# 新加坡三因子策略：业绩归因交付

日期：2026-10-21。研究对象为组员最终确定的 **K3 / IV weekly / top20**。

## 先看什么

1. [完整中文报告（GitHub可直接阅读）](REPORT_ZH.md)；[离线HTML](report/SG_K3_ATTRIBUTION_ZH.html)含16节解释与8张内嵌图片。
2. `results/account_window_summary.csv`：历史账户与10月两种初始化的收益概览。
3. `results/execution_eval_stock.csv`、`fresh_live_close_to_close_stock.csv`：历史及10月个股贡献。
4. 对应的 `_sector.csv`、`_component.csv`：行业、价格、分红、汇率和成本贡献。
5. `results/workbook_reconciliation.csv`：18项Excel核对，17项通过，1项STI微差警告。

CSV采用标准UTF-8；Excel直接打开若中文乱码，请用“数据→从文本/CSV”，选择UTF-8。

## 策略与版本

权威来源：[FE5209-GroupProject](https://github.com/lu2548214469-bit/FE5209-GroupProject/tree/abf1c66ffd82b03c6183ff3546a5eb30749db934)，提交 `abf1c66ffd82b03c6183ff3546a5eb30749db934`。

- 年度从六个候选风格选择三个；每周重算三个风格的逆波动权重。
- 股票前20%，等权目标，沿用源保留缓冲及行业数量上限。
- 100,000 SGD初始现金；整手、最低佣金、参与率、T+2和分红除权后14日到账沿用源模型。
- **本项目不修改原策略、输入、执行引擎或两份Excel。**
- 两个旧仓库所有远端分支已核查；版本、分支和日期见 `source_audit/repositories.json`。
- 原始工作簿缓存、公式、路径与SHA256见 `source_audit/workbooks.json`。

## 三条账户口径

| 口径 | 起点 | 用途 |
|---|---|---|
| 历史连续执行 | 2021年100,000现金，至2026-09-30 | 历史业绩与长期贡献 |
| 10月独立现金账户 | 2026-10-01重新建100,000现金账户 | 对齐24策略Excel，含首次建仓费用 |
| 10月独立收盘账户 | 2026-10-01收盘99,781.854998，至10-15 | 与同窗STI比较，排除首次建仓成本 |

连续历史账户延伸到10月的结果另行输出，不能与独立10月账户金额混用。

## 方法与单位

实际损益来自源引擎逐日逐股贡献：价格损益 + 分红应收 − 费用 − 滑点。对外币价格进一步拆成本地价格、汇率和交互项。所有结果核对回净值变化。

- `contribution_pp`：该窗口净贡献金额/期初NAV×100，单位为**累计收益百分点**，不是年化贡献。
- 分红在除权日形成收益及应收，到账只是现金与应收转换，不重复计收益。
- 现金没有利息。现金“相对贡献”表示相对于承担同权重STI收益的差额。
- 跨周相对收益使用财富链接，不能直接相加每周收益差。
- 源周频研究使用上市币种收益；执行账户使用SGD。周频Brinson只相对源等权股票池，不是STI行业归因。
- 因子评分权重、因子多空诊断篮子、回归暴露与实际盈利贡献分别输出，不能互相替代。
- 回归没有扣无风险利率，“alpha”列是总收益回归截距。HAC采用Bartlett 4阶、n/(n−k)修正、渐近正态p值，仅作描述性分析。
- 行业是源研究分组，未认证为标准经济行业。CNMC被标成科技与通信，与官方黄金开采业务不一致；展示重分组敏感性单列，未改任何策略持仓或分数。

## 证据与限制

- 源执行测试31项通过；归因恒等式4项通过。
- 股票、行业、币种、成本与回撤逐项回勾，误差仅浮点数精度。
- 两份Excel的17项组合控制通过。STI为源数据微差：Excel−4.661500%，仓库−4.660983%，差0.000517个百分点；报告统一使用当前逐日仓库基准。
- 源公司行动最后日期2026-09-15。10月“零分红”仅代表源文件无记录，未独立核实真实事件完整性。
- 历史PIT、股票池生存偏差、历史交易单位、实际收盘成交与冲击仍是源研究限制；归因不能消除这些问题。
- 未完成的10月远期周收益不进入周频业绩归因与风险回归。
- 工作簿的“实盘”是模拟执行；没有验证券商真实成交。

## 文件目录

```
report/                    中文报告与8张PNG
results/                   CSV/JSON归因与核对
source_audit/              输入哈希、版本、工作簿缓存与公式
reproduced_main/           未修改源项目的主运行输出
reproduced_fresh_live/     10月独立账户输出
*.py                       本次归因计算及检查
requirements-attribution.txt  本次数值环境版本
```

## 组员如何复算

仅阅读交付无需安装软件。复算时使用Python3.12；建议按 `requirements-attribution.txt` 安装到独立虚拟环境。SLSQP优化对数值环境有微小敏感性，严格复现使用记录版本，不应为了通过对账而放松误差门槛。

本交付位于源仓库内部：

```
FE5209-GroupProject/
  config/、data/、src/                       # 原项目
  performance_attribution/
    sg_k3_ivweekly_top20_20261021/            # 本次归因
```

在仓库根目录执行主回测：

```
python run_backtest.py --out performance_attribution/sg_k3_ivweekly_top20_20261021/reproduced_main
```

然后进入 `performance_attribution/sg_k3_ivweekly_top20_20261021`，依次运行：

```
python attribution_engine.py
python sector_attribution.py
python active_attribution.py
python sector_label_audit.py
python test_attribution.py -v
python build_report.py
python export_markdown.py
python verify_delivery.py
```

最初工作簿取证已冻结在 `source_audit/` 中，包含原始文件哈希、缓存值和公式，移除了个人电脑绝对路径；复算使用该冻结快照。换新策略或新输入时应建立新交付、重做取证，不能继续使用旧缓存冒充新版本。

本版本为用户授权的GitHub归因交付；源数据沿用仓库锁定提交。没有改变策略、配置、输入或主运行入口。新增归因代码只读取原策略输出。README/GUIDE允许增加导航，源代码及输入的38个文件继续核验哈希。


## 核心结果

历史SGD连续执行账户2021—2026年9月：年化20.11%，累计185.65%，最大回撤14.36%；累计领先同窗STI 32.17个百分点。10月独立账户现金起点收益−6.2175%；10/1收盘至10/15收益−6.0125%，落后当前仓库STI 1.3515个百分点。10月工业与消费源分组合计约占净亏损70%。

31项源执行测试、4项归因恒等式测试通过；17项组合工作簿控制通过，STI微差作为第18项警告保留。事件源覆盖和行业标签局限均在完整报告中披露。
