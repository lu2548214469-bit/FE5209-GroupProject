"""Readable Chinese investability report with offline scenario filtering."""
from pathlib import Path
import json,base64,html
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE=Path(__file__).resolve().parent;R=HERE/'results';REPORT=HERE/'report';FIG=REPORT/'figures'
FAMILIES={'capital':'初始资金','participation':'参与率','volume':'成交量减半','order_life':'订单期限','lot_diagnostic':'1股单位诊断',
 'announced_lot_rules':'已公告整手规则','joint_stress':'联合不利情景','commission':'最低佣金','slippage':'滑点',
 'impact':'平方根冲击','tax_diagnostic':'费用GST情景','cash_reserve':'现金储备','settlement_diagnostic':'T+0诊断',
 'fresh_capital':'10月独立账户','tick_diagnostic':'10月报价档位','feedback_diagnostic':'实际持仓反馈'}

def load(name):return pd.read_csv(R/name)
def pct(v):return '—' if pd.isna(v) else f'{100*v:,.2f}%'
def amount(v):return f'{v:,.2f}'
def table(d):return d.to_html(index=False,border=0,escape=True,classes='data')
def pic(name):return '<img alt="'+name+'" src="data:image/png;base64,'+base64.b64encode((FIG/name).read_bytes()).decode()+'">'

def figures(d):
    FIG.mkdir(parents=True,exist_ok=True)
    f=Path('C:/Windows/Fonts/msyh.ttc')
    if f.exists():
        font_manager.fontManager.addfont(str(f));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(f)).get_name()
    plt.rcParams.update({'axes.unicode_minus':False,'figure.dpi':150,'savefig.bbox':'tight','axes.spines.top':False,'axes.spines.right':False})
    blue='#234e70';red='#b34848';gold='#b2832f'
    def finish(fig,name):fig.tight_layout();fig.savefig(FIG/name);plt.close(fig)
    cap=d[d.family.eq('capital')&d.window.eq('EVAL')].sort_values('initial_cash')
    fig,axs=plt.subplots(1,2,figsize=(11,4));x=cap.initial_cash/10000
    axs[0].plot(x,cap.cagr*100,'o-',color=blue);axs[0].set(xscale='log',xlabel='初始资金（万SGD，对数轴）',ylabel='EVAL年化 %',title='同一冻结目标下的资本情景')
    axs[1].plot(x,cap.requested_value_completion*100,'o-',color=red);axs[1].set(xscale='log',xlabel='初始资金（万SGD，对数轴）',ylabel='订单金额完成率 %',title='高年化不代表更贴合目标')
    finish(fig,'01_capital_tradeoff.png')
    w=load('signal_capacity_scenarios.csv');w=w[w.basis.eq('adv20_signal')&w.participation.eq(.1)&w.days.eq(1)].copy();w.signal_date=pd.to_datetime(w.signal_date)
    fig,ax=plt.subplots(figsize=(10,4));ax.plot(w.signal_date,w.capacity_nav,label='单日NAV容量代理',color=gold,lw=1)
    ax.plot(w.signal_date,w.baseline_signal_nav,label='10万初始账户当期NAV',color=blue);ax.set(yscale='log',ylabel='SGD，对数轴',title='信号时已知ADV20：10%参与率，单日代理');ax.legend();finish(fig,'02_capacity_history.png')
    wanted=['capital_100000','minimum_0','minimum_1','minimum_10','slippage_50','impact_1','fee_tax_9pct','joint_adverse_100000']
    names=['正式基准','最低佣金0','最低佣金1','最低佣金10','滑点50bp','冲击Y=1','费用税9%','联合不利']
    ev=d[d.window.eq('EVAL')].set_index('scenario').loc[wanted]
    fig,ax=plt.subplots(figsize=(10,4));ax.bar(names,ev.cagr*100,color=[blue]+[gold]*6+[red]);ax.axhline(17.632053,color='#888',ls='--',label='源同窗STI年化');ax.set(ylabel='年化 %',title='成本与约束敏感性：均保持10万初始资金');ax.tick_params(axis='x',rotation=22);ax.legend();finish(fig,'03_cost_sensitivity.png')
    o=load('baseline_order_detail.csv');counts=[o.filled_original_day.sum(),o.filled_later.sum(),o.remaining.ne(0).sum()]
    fig,axs=plt.subplots(1,2,figsize=(11,4));axs[0].bar(['原日完成','延后完成','未完成'],counts,color=[blue,gold,red]);axs[0].set(title='2021—10/15：订单最终结果',ylabel='订单数')
    rr=load('attempt_reasons.csv');labels=['量或整手上限','现金或整手不足','源零成交量'];axs[1].barh(labels,rr.affected_orders,color=gold);axs[1].set(title='阻碍事件可涉及同一订单',xlabel='涉及订单数，不可简单相加');finish(fig,'04_execution_delays.png')
    liq=load('liquidation_by_snapshot.csv');fig,ax=plt.subplots(figsize=(9,4.2))
    vals=[liq[(liq.scenario==s)&(liq.volume_multiplier==v)].max_days for s,v in [('capital_100000',1),('capital_100000',.5),('capital_1000000',1),('capital_1000000',.5)]]
    ax.boxplot(vals,tick_labels=['初始10万','10万/量减半','初始100万','100万/量减半'],showfliers=True)
    ax.set(yscale='log',ylabel='静态退出天数代理，对数轴',title='历史实际持仓：全仓退出，不是小额再平衡');finish(fig,'05_liquidation.png')
    track=load('capital_tracking_summary.csv');fig,ax=plt.subplots(figsize=(9,4));ax.plot(track.initial_cash/10000,track.mean_half_l1_target_distance*100,'o-',label='平均目标距离');ax.plot(track.initial_cash/10000,track.p95_half_l1_target_distance*100,'o-',label='95分位');ax.set(xscale='log',xlabel='初始资金（万SGD）',ylabel='半L1距离 %',title='实际暴露与冻结目标的偏离');ax.legend();finish(fig,'06_target_distance.png')
    octo=d[d.scenario.isin(['fresh_capital_100000','fresh_tick_rounding_100000'])&d.window.eq('OCTOBER_CASH')].set_index('scenario')
    fig,axs=plt.subplots(1,2,figsize=(10,4));axs[0].bar(['基准10bp','另按档位取整'],octo.loc[['fresh_capital_100000','fresh_tick_rounding_100000'],'shortfall'],color=[blue,gold]);axs[0].set(ylabel='SGD',title='10月：含首次建仓的执行价偏移')
    axs[1].bar(['基准10bp','另按档位取整'],octo.loc[['fresh_capital_100000','fresh_tick_rounding_100000'],'cumulative_return']*100,color=[blue,gold]);axs[1].set(ylabel='收益 %',title='档位场景是保守代理，不是观测价差');finish(fig,'07_october_tick.png')
    ex=load('exit_replay_summary.csv');ex=ex[ex.volume_multiplier.eq(1)].copy();fig,ax=plt.subplots(figsize=(10,4))
    dates=sorted(ex.snapshot.unique());x=np.arange(len(dates))
    for i,(s,label,color) in enumerate([('capital_100000','初始10万',blue),('capital_1000000','初始100万',red)]):
        z=ex[ex.account.eq(s)].set_index('snapshot').loc[dates];ax.bar(x+(i-.5)*.32,z.residual_value_fraction_initial_market_value*100,width=.32,label=label,color=color)
    ax.set_xticks(x,dates);ax.set(ylabel='10日剩余市值 / 起始股票市值 %',title='后续真实日行情上的退出代理：未退部分不能当作已变现');ax.legend();finish(fig,'08_exit_replay.png')

def main():
    REPORT.mkdir(exist_ok=True);d=load('scenario_summary.csv');figures(d)
    ds=json.loads((R/'diagnostics_summary.json').read_text());tick=json.loads((R/'tick_summary.json').read_text())
    ev=d[d.window.eq('EVAL')].set_index('scenario');base=ev.loc['capital_100000'];million=ev.loc['capital_1000000'];joint=ev.loc['joint_adverse_100000']
    parts=[]
    def section(title,body):parts.append('<section><h2>'+title+'</h2>'+body+'</section>')
    section('一、结论与适用范围',f'''<p class="lead">本次只研究最终的<strong>K3／IV每周调权／前20%</strong>。正式基准仍为初始100,000新币、源分红除权后14日到账。旧Investability的数值不直接沿用。</p>
    <div class="notice">结论：10万基准在当前日频执行模型下可复现、能完成大部分调仓，但最低佣金、价格档位与退出尾部风险仍重要。现有数据无法认证盘口成交、收盘集合竞价容量或实盘市场冲击，不能把模型结果写成实盘成交保证。</div>
    <p>完成46条冻结目标执行情景、2条实际持仓反馈情景、12条历史快照退出路径。正式基准逐日NAV与原回测完全一致。没有改动原策略、配置、输入数据或原回测入口。</p>
    <p>历史EVAL：2021年初至2026-09-30；另报2026-10-01收盘至10-15的连续账户及10月重新建仓账户。完整账户流水至10-15；下文4316笔订单等全路径统计包含10月，EVAL收益及容量对照均单独标明。</p>''')
    cap=d[d.family.eq('capital')&d.window.eq('EVAL')].sort_values('initial_cash')
    section('二、资金增大以后发生了什么',pic('01_capital_tradeoff.png')+table(pd.DataFrame({'初始资金 SGD':cap.initial_cash.map(amount),'9/30期末NAV SGD':cap.end_nav.map(amount),'年化':cap.cagr.map(pct),'最大回撤':cap.max_drawdown.map(pct),'订单金额完成率':cap.requested_value_completion.map(pct),'订单数完成率':cap.requested_count_completion.map(pct)}))+f'''
    <p>初始100万的年化{pct(million.cagr)}高于10万的{pct(base.cagr)}，但金额完成率降至{pct(million.requested_value_completion)}。大资金摊薄最低佣金，同时改变哪些订单被完成及完成时间，因此它的收益不是把10万曲线等比例放大。不能单用较高CAGR认定100万容量通过验证，更不能事后挑出收益最高资金作为“最优资本”。</p>
    <p>每个账户都从各自初始现金完整运行，NAV随后增长或下降。这里“初始100万”在9/30已变为{amount(million.end_nav)}新币，退出检查使用的是这个增长后账户的实际股数。它不同于始终维持100万当期净值。</p>''')
    section('三、成交率、目标偏离与金额分母',pic('06_target_distance.png')+f'''
    <pre>金额完成率 = 1 − Σ(|剩余股数| × 信号时估值价) / Σ(|原请求股数| × 信号时估值价)
笔数完成率 = 最终全部完成的订单数 / 生成的订单数</pre>
    <p>金额完成率按全期间累计买卖请求计算，重复调仓请求会重复进入分母；它不是“组合有多少比例成功投资”，75.7%也不表示25%净值一直空仓。它从整手取整后生成的订单起算，取整时已放弃的零碎目标不在分母里。</p>
    <p>另计算每日股票及非投资部分相对99%目标股票暴露的半L1距离。它同时包括价格漂移、现金、应收、整手和未完成执行，不被解释为纯未成交损失。10万账户平均约2.28%，100万约3.14%，500万约6.51%；这些是偏离量，不是损失收益率。</p>''')
    section('四、真实股数流水：延期不能被忽略',pic('04_execution_delays.png')+f'''
    <p>完整路径生成{ds['orders']}笔订单、{ds['fills']}笔日聚合模拟成交，涉及46只曾持有股票。{ds['fully_same_day']}笔原日全部完成，{ds['fully_later']}笔延后完成，{ds['unfinished']}笔在被替换或过期时仍有剩余。约{pct(ds['delayed_ticket_fraction'])}的成交票发生在原激活日之后。</p>
    <p>“原日完成”“最终完成”“成交票数”是不同指标。部分成交可能跨日支付多次最低佣金。原引擎允许卖出款T+2到账再买入，不能在同一日把所有卖出款立即重复使用。T+0情景仅用于识别约束敏感性，不是SGX现行交收承诺。</p>
    '''+table(load('attempt_reasons.csv'))+'<p>原因表统计尝试次数及涉及订单数，同一订单可能出现不同原因，不可把原因行相加当成独立订单。现金与整手共用一个拒绝标签，现有日志不支持再精确拆开。</p>')
    zero=load('zero_or_missing_volume_initial_orders.csv')
    section('五、零成交量和报价质量',f'''
    <p>新策略有<strong>{len(zero)}笔原执行日零量订单</strong>，均为再平衡，没有新建仓。其中25笔后来完成、3笔在新计划替换时仍有剩余。源引擎在零量日没有强行成交。另有48笔订单曾在某次尝试遇到零量；它包括延期过程，不能与28笔原日零量相混淆。</p>
    <p>因此旧报告“29笔、含2笔新建仓”的数字不适用于本版。零量仍是源数据记录，不等于已逐一认证现实中全天完全无交易。曾出现过跨来源冲突的1D0等股票仍需保留来源不确定性，本研究不借用其他股票的成交量填补。</p>
    <p>实际持仓中有{ds['stock_days_zero_volume']}个零量股票日；源标记的缺失报价沿用日数大于0的持仓日为{ds['stock_days_stale']}。没有缺价不代表有可交易深度，零量日的沿用或报价也不证明该价位能够成交。</p>'''+table(zero[['ticker','activation','original_requested','remaining','status','first_fill_delay_sessions']]))
    capacity=load('capacity_summary.csv');c=capacity[capacity.basis.eq('adv20_signal')&capacity.participation.eq(.1)]
    section('六、资金容量：信号时已知信息与历史尾部',pic('02_capacity_history.png')+'''
    <pre>订单占NAV比例 = 信号时请求金额 / 信号时NAV
单笔NAV容量代理 = p × D × 信号时已知成交额代理 / 订单占NAV比例
当周容量代理 = 所有买卖订单的最小单笔容量</pre>
    <p>ADV用SGD价格×股数成交量计算，只用信号日收盘及以前的20/60个交易日；零量保留，未知不填零。ADV20、ADV60与60日中位数均检查。它是close×volume代理，不是交易所逐笔成交额或VWAP。</p>
    '''+table(pd.DataFrame({'假定完成天数':c.days,'最差NAV容量 SGD':c.min_capacity_nav.map(amount),'5分位 SGD':c.p05_capacity_nav.map(amount),'中位数 SGD':c.median_capacity_nav.map(amount),'基准NAV落在代理范围内的周':c.baseline_weeks_within_capacity.map(pct)}))+'''
    <p>10%参与率、单日ADV20的历史中位容量约227.8万，但最差仅3.46万，不能用中位数给出资金上限。按5×ADV20线性外推，本版301个信号都可容纳10万初始账户的当期NAV；实际执行仍出现90笔未完成。这说明ADV和天数相乘只能提供筛查，无法涵盖逐日零量、整手、现金和计划替换。</p>
    <p>输出另列“基准增长路径线性缩放的初始资金约束”。这只是固定订单结构的缩放，不等于其他初始资金真实订单路径的容量；真正资本敏感性使用第二节完整账户重跑。</p>''')
    section('七、退出能力：不能从调仓容量推导',pic('05_liquidation.png')+'''
    <p>用每个信号时的完整实际持股，按10%已知ADV20、100股整手估计静态退出天数。10万初始账户历史快照的中位约2日、最差18日；初始100万账户中位21日、最差119日。成交量减半时进一步变长。</p>
    <p>这些是持仓时点的流动性代理，假定未来每天维持近期ADV，不预测未来真实成交。快照取每周信号与9/30、10/15，不代表对每个盘中最坏时刻都已穷尽。</p>
    <p>还单列10月新建账户的固定规模检查：10月15日，初始100万独立账户按当时ADV的退出代理约7日，量减半约13日。它与已增长到约329万的长期100万初始账户不应混用。</p>''')
    ex=load('exit_replay_summary.csv');q=ex[ex.snapshot.eq('2026-09-30')]
    section('八、用后续已观察日行情实际排退出股数',pic('08_exit_replay.png')+table(pd.DataFrame({'账户':q.account,'成交量倍数':q.volume_multiplier,'10日内卖完所需日':q.fully_liquidated_session.fillna('10日内未清完'),'10日后剩余股票数':q.remaining_names,'剩余市值/起始股票市值':q.residual_value_fraction_initial_market_value.map(pct)}))+'''
    <p>从实际持股开始，只卖不买，逐日使用随后已观察的收盘价、全日量和此前ADV限额；未交收买入股数先锁定，卖出款T+2到账。另选历史静态退出尾部的2023-04-14和2025-02-07作为压力快照，不通过后验结果选择最容易退出的日期。</p>
    <p>10万初始账户9/30快照正常量约4个交易日卖完，量减半约9日；在2023-04-14快照，正常量10日后仍剩约3.02%的起始股票市值。100万初始账户9/30快照正常量10日后剩约6.34%，量减半约21.12%。因此基准资金也没有“任何历史时点都能几天退出”的保证。</p>
    <p>这项退出账只报告股票卖出及净卖出款到账，排除了原现金、旧应收和新分红；不把它误写成另一条总回报NAV。退出采用连续10日卖出任务，不套用正常调仓5日订单过期；它是退出预案代理，不是盘口成交认证。</p>''')
    section('九、最低佣金、整手与碎单',pic('03_cost_sensitivity.png')+f'''
    <p>全路径{pct(ds['min_commission_fraction'])}的成交票触发5新币最低佣金。5bp佣金的最低收费转折金额为10,000新币；许多再平衡成交远低于它。因此最低佣金敏感性比只提高几个bp的滑点更大。</p>
    <p>10万EVAL：最低佣金从5改为0（比例佣金仍收）时，年化约23.66%；改为1时约23.03%；改为10时约16.05%。正式5元基准约20.11%。这些是完整现金路径重跑，不是把总费用简单除以初始本金。</p>
    <p>整手在订单生成前平均留下约{pct(ds['mean_rounding_gap_fraction'])}NAV的目标缺口，最大约{pct(ds['max_rounding_gap_fraction'])}，另有1%预留现金。把单位从100股改成1股是可分割性诊断，并未认证为真实普通整手市场；10万年化反而约18.10%，因为更细碎的再平衡增加最低佣金负担。“更精细执行”不保证净收益更高。</p>''')
    section('十、滑点、冲击、GST与现金约束',f'''
    <p>基准固定10bp偏移、额外平方根冲击Y=0。滑点提高到50bp时，10万年化约{pct(ev.loc['slippage_50','cagr'])}；Y=1时约{pct(ev.loc['impact_1','cagr'])}。冲击公式为额外偏移=Y×滞后20日波动×√(单笔金额/滞后ADV20)，只在原引擎声明的参与率域内计算。Y=0.25/0.5/1均未用本市场真实成交校准。</p>
    <p>10bp基础偏移与额外冲击是明确的叠加情景。如果把10bp理解为已包含全部冲击的经验成本，再加Y可能重复计量；本报告不把二者校准成真实成本估计。</p>
    <p>源手续费税率为0。将费用税率全历史统一设9%的诊断年化约{pct(ev.loc['fee_tax_9pct','cagr'])}；这不是历史GST回放，实际税率、客户身份、券商计费对象及平台/托管/换汇费仍需具体券商资料。</p>
    <p>5%现金预留、T+0和1/3日订单期限也单列。限制更严格有时反而提高样本收益，例如1日过期减少费用并跳过部分交易；这是执行改变路径的结果，不能借此反向优化冻结规则或认为未成交没有风险。</p>''')
    section('十一、10月报价档位与2026年整手修订',pic('07_october_tick.png')+f'''
    <p>10月新建10万账户，47笔基础成交报价均落在相应原币最小报价档位上。按假定半档位计算的成交额加权机械偏移约{tick['weighted_half_tick_bps']:.2f}bp；这不是观测到的买卖价差，也不证明真实成本必然高于10bp，收盘集合竞价未必需要支付假定半档位。</p>
    <p>把基础偏移后的成交价向不利方向对齐到报价档位，含首日建仓的累计收益由−6.2175%变为约−6.8356%；10/1收盘到15日由−6.0125%变为约−6.1080%。该场景说明低价股票不能无限细分报价，不能说真实成交一定额外损失这一数额；真实收盘集合竞价成交机制和限价路径仍缺失。</p>
    <p>SGX官方公告2026-10-05首批11只股票由100股改10股。按名单和生效日建立独立规则情景；当前10月目标没有这些股票，10万和100万账户路径均与原整手基准一致。因此这项修订已核查，本窗口无需为了它改写正式基准；不能把100股永久不变推广到全部股票和未来日期。</p>''')
    feedback=load('feedback_summary.csv')
    section('十二、补上实际持仓反馈检查',table(pd.DataFrame({'初始资金 SGD':feedback.initial_cash.map(amount),'同规则反馈年化':feedback.cagr.map(pct),'金额完成率':feedback.requested_value_completion.map(pct),'目标集合不同的信号数':feedback.signals_with_different_target_set,'总信号数':feedback.signals}))+'''
    <p>前46情景固定正式目标，以隔离执行影响。这里首次目标仍固定为正式目标；此后调用原有保留缓冲函数，把实际持有名字传入，其他因子、打分、阈值和行业数量上限不变。</p>
    <p>10万账户301次目标集合全部一致，补充验证了本版基准不存在由这一状态差异引起的选股路径偏差。100万有133次不同，反馈年化约24.12%，金额完成率约80.51%；它是另一条条件执行路径，不替代正式冻结目标的23.09%。大资金下不能忽略状态反馈。</p>''')
    section('十三、联合不利情景与结论边界',f'''
    <p>预设组合：参与率5%、成交量减半、滑点20bp、额外冲击Y=0.5、最低佣金10新币、费用税率统一9%。10万EVAL年化约<strong>{pct(joint.cagr)}</strong>，最大回撤{pct(joint.max_drawdown)}，金额完成率{pct(joint.requested_value_completion)}。源同窗STI年化约17.63%，因此更不利执行条件下相对优势可以消失。</p>
    <p>这是多项假设共同变化后的压力结果，不能把年化差分别归因于每个项目；影响具有非线性与路径依赖。不是最坏情景证明，也不宣称这些参数已被实盘测得。</p>
    <p><strong>可交付结论：</strong>保留10万基准作为本次研究账户是合理的既定口径；当前研究支持较高但非百分之百的执行完成，以及对最低佣金、档位和退出尾部的敏感性。尚不能给出“全历史无条件容量”或可靠百万实盘容量。后续若实际交易，最有价值的补充是选定券商费表与真实价差/成交回报，而不是再调参挑最高CAGR。</p>''')
    section('十四、数据、模型与尚未认证的部分','''<ul>
    <li>行情为日收盘与全日量，无法验证盘口、收盘集合竞价份额、排队、限价未成交或日内极端波动。</li>
    <li>成交价10bp、冲击Y、GST全历史9%等是情景；真实佣金档位、平台费、交收指令费、换汇费与账户适用税务未按指定券商校准。</li>
    <li>价格已拆股调整、历史股数及成交量单位尚未逐证券认证。100股模型与历史真实交易股数的一致性仍有条件；不重复应用拆股表。</li>
    <li>事件源仅至2026-09-15，10月零分红只代表源无记录。分红14日到账仍为组内假设，外币应收在除权日折成固定SGD。</li>
    <li>股票池、财务183日可得性代理、历史成员/退市、未来收益可得性筛选和源行业标签等研究局限保留。未用Investability修复因子研究输入。</li>
    <li>源交易日历是多数股票有正量的代理，外币共同银行日及完整历史停牌名录未独立认证。</li>
    <li>10月短窗仅11个收盘净值；不以短窗年化衡量长期可交易性。退出样本不是所有历史时刻的穷尽最坏情况。</li>
    <li>多个情景的高收益不能当作新的选模依据。正式策略、初始资金和参数均未重选。</li>
    </ul>''')
    # Offline filtering of precomputed cases, not interpolation or new optimisation.
    jsrows=pd.concat([d,feedback],ignore_index=True).replace([np.inf,-np.inf],np.nan).astype(object)
    jsrows=jsrows.where(pd.notna(jsrows),None)
    controls='''<p>下表切换的是已计算结果，不在浏览器中重跑模型，也不对未测试资金插值。</p>
    <label>期间 <select id="scope"><option>EVAL</option><option>WHOLE</option><option>OCTOBER_CASH</option><option>OCTOBER_CLOSE</option></select></label>
    <label>情景类别 <select id="family"><option value="all">全部</option>'''+''.join('<option value="'+k+'">'+v+'</option>' for k,v in FAMILIES.items())+'''</select></label><div class="scroll"><table class="data"><thead><tr><th>情景</th><th>初始资金</th><th>年化</th><th>期间收益</th><th>回撤</th><th>金额完成率</th><th>笔数完成率</th><th>费用</th><th>偏移成本</th></tr></thead><tbody id="cases"></tbody></table></div>'''
    script='<script>const rows='+json.dumps(jsrows.to_dict('records'),ensure_ascii=False,allow_nan=False)+''';
    const fmt=(x,p=false)=>x===null||x===undefined?'—':(p?(100*x).toFixed(2)+'%':Number(x).toLocaleString('en-US',{maximumFractionDigits:2}));
    function render(){let w=document.getElementById('scope').value,f=document.getElementById('family').value;
    document.getElementById('cases').innerHTML=rows.filter(r=>r.window===w&&(f==='all'||r.family===f)).sort((a,b)=>a.initial_cash-b.initial_cash||a.scenario.localeCompare(b.scenario)).map(r=>'<tr><td>'+r.scenario+'</td><td>'+fmt(r.initial_cash)+'</td><td>'+fmt(r.cagr,true)+'</td><td>'+fmt(r.cumulative_return,true)+'</td><td>'+fmt(r.max_drawdown,true)+'</td><td>'+fmt(r.requested_value_completion,true)+'</td><td>'+fmt(r.requested_count_completion,true)+'</td><td>'+fmt(r.fees)+'</td><td>'+fmt(r.shortfall)+'</td></tr>').join('');}
    document.getElementById('scope').onchange=render;document.getElementById('family').onchange=render;render();</script>'''
    section('十五、全部执行情景对照',controls)
    section('十六、工作流程与汇报用语','''<ol><li>锁定源策略与输入哈希，复现正式逐日NAV。</li><li>固定目标重跑资本与执行假设，记录每一条股数、现金和成本路径。</li><li>逐笔对账、识别原日/延期/未完成，另报整手前目标损失。</li><li>用信号时已知流动性计算容量代理，用完整持仓计算退出需求。</li><li>选定历史尾部快照，使用后续已观察日行情逐日排退出与T+2到账。</li><li>调用原缓冲规则检验实际持仓反馈，核查官方整手、报价与交收规则。</li><li>输出完整明细、图表及可复算说明。</li></ol>
    <p>最终校验：48条账户路径全部通过损益与净值对账、原请求股数=已成交股数+剩余股数、现金非负、整手及成交量/ADV上限、成交日晚于信号日检查。正式连续账户与10月独立账户逐日NAV均复现；38个源文件内容保持一致。另有3项退出账测试通过，覆盖未交收股数、T+2卖出款、零量与不足一整手的互动。完整证据见results/verification.json及account_path_verification.csv。</p>
    <blockquote>我们已用最终三因子、每周IV调权、前20%策略重做可投资性分析。10万基准逐日结果完全复现，大部分订单能在模型中完成，但约三成成交票发生延期，最低佣金和退出尾部仍重要。初始100万虽然样本年化较高，订单金额完成率与目标贴合度下降，不能据此认定容量通过。另做真实持仓反馈、报价档位和历史退出压力检查，保留原策略，不以压力测试结果重新选资金或规则。</blockquote>''')
    section('官方规则依据','''<p>规则查询日2026-10-21。原文用于核对机制；模型成本数值仍以冻结配置及明确情景为准。</p><ul>
    <li><a href="https://www.sgx.com/securities/trading">SGX证券交易：整手、交易机制与费用</a></li>
    <li><a href="https://www.sgx.com/research-education/market-updates/20261006-10-share-lots-see-immediate-uptake-first-11-stocks">SGX：2026-10-05首批11只股票改10股整手</a></li>
    <li><a href="https://rulebook.sgx.com/rulebook/833-0">SGX-ST规则8.3.3：普通股票报价档位</a></li>
    <li><a href="https://rulebook.sgx.com/rulebook/91a-settlement-basis-and-eligibility-clearing-cdp">SGX-ST规则9.1A：T+2与外币共同银行日</a></li>
    <li><a href="https://www.iras.gov.sg/quick-links/tax-rates/goods-and-services-tax-%28gst%29-rates">IRAS：历史GST税率</a></li>
    <li><a href="https://sgp.itiger.com/sg/commissions/fees/stocks_etf">Tiger官方费表：按日最低费及GST实例（未指定为策略券商）</a></li></ul>''')
    css='''body{margin:0;background:#f3f5f7;color:#263543;font-family:"Microsoft YaHei",Arial,sans-serif;line-height:1.85}main{max-width:1100px;margin:auto;background:white;padding:40px 48px}h1{font-size:29px}h2{margin-top:36px;border-bottom:1px solid #ccd5dd;padding-bottom:7px;font-size:22px}p,li{font-size:15px}.lead{font-size:17px}.notice{padding:15px 18px;background:#fff5dc;border-left:4px solid #b2832f}.data{border-collapse:collapse;width:100%;font-size:13px;margin:20px 0}.data th{padding:8px;background:#234e70;color:white;text-align:left}.data td{padding:7px;border-bottom:1px solid #e2e7ec}.data tr:nth-child(even){background:#f5f7f9}img{width:100%;display:block;margin:22px auto}pre{background:#f1f4f7;padding:15px;white-space:pre-wrap}a{color:#205d8a}blockquote{padding:14px 22px;border-left:4px solid #234e70;background:#f2f6f9}.scroll{max-height:540px;overflow:auto}.scroll th{position:sticky;top:0}select{padding:7px;margin:10px 20px 10px 4px}small{color:#5e6d7b}@media print{main{padding:0}.scroll{max-height:none;overflow:visible}select{display:none}img{max-height:480px;object-fit:contain}}'''
    doc='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>最终三因子策略 Investability</title><style>'+css+'</style><main><h1>最终三因子策略 Investability</h1><p><small>2026-10-21　K3 / IV weekly / top20　金额：SGD　基准资金：100,000</small></p>'+''.join(parts)+script+'</main></html>'
    path=REPORT/'K3_INVESTABILITY_ZH.html';path.write_text(doc,encoding='utf-8');print(path)

if __name__=='__main__':main()
