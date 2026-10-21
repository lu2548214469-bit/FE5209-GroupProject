"""Standalone Chinese report and exportable figures from reconciled attribution."""
from pathlib import Path
import json
import html
import base64
import hashlib
import zipfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
REPO=HERE.parent.parent if (HERE.parent.parent/'config/strategy.yaml').exists() else HERE.parent/'FE5209-GroupProject-attribution-review'
R=HERE/'results'
REPORT=HERE/'report'
FIG=REPORT/'figures'
SECTORS={'consumer':'消费','industrial':'工业','real estate':'房地产','financials':'金融',
         'technology & communications':'科技与通信','other':'其他','__CASH_AND_RECEIVABLES__':'现金及应收',
         '__CASH__':'现金','__COST__':'成本'}
STYLES={'Quality':'质量','Momentum':'动量','Low Risk':'低风险','Investment':'投资','Size':'小盘规模','Value':'价值','market_sgd':'STI市场'}


def read(name):return pd.read_csv(R/name)
def pct(x):return f'{x*100:,.2f}%'
def pp(x):return f'{x*100:,.4f}个百分点'
def money(x):return f'{x:,.2f}'
def image(name):
    data=base64.b64encode((FIG/name).read_bytes()).decode()
    return f'<img alt="{html.escape(name)}" src="data:image/png;base64,{data}">'
def table(frame):return frame.to_html(index=False,escape=True,border=0,classes='data')
def stocktable(name,n=5,bottom=False):
    d=read(name);d=d.tail(n) if bottom else d.head(n)
    return table(pd.DataFrame({'代码':d.ticker,'公司':d.company_name,'行业':d.six_sector.map(SECTORS),
                               '净贡献 SGD':d.net_pnl.map(money),'累计收益贡献 pp':d.contribution_pp.map(lambda x:f'{x:+.4f}')}))


def figures():
    FIG.mkdir(parents=True,exist_ok=True)
    font=Path('C:/Windows/Fonts/msyh.ttc')
    if font.exists():
        from matplotlib import font_manager
        font_manager.fontManager.addfont(str(font))
        plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({'axes.unicode_minus':False,'figure.dpi':150,'savefig.bbox':'tight',
                         'axes.spines.top':False,'axes.spines.right':False,'font.size':10})
    blue='#234e70';red='#b34343';green='#24765b'
    def finish(fig,name):
        fig.tight_layout();fig.savefig(FIG/name);plt.close(fig)
    d=pd.read_csv(HERE/'reproduced_main/execution/daily.csv',parse_dates=['date']).set_index('date')
    b=pd.read_csv(REPO/'data/sti_total_return_daily.csv',parse_dates=['date']).set_index('date').sti_tr_level
    ev=d[d.index<='2026-09-30']
    bn=b.reindex(ev.index,method='ffill')/b.loc[:'2021-01-07'].iloc[-1]*100000
    fig,ax=plt.subplots(figsize=(10,4.2));ax.plot(ev.index,ev.nav,label='连续执行账户',color=blue);ax.plot(bn.index,bn,label='STI全收益对照',color='#999999')
    ax.set(title='2021—2026年9月：以10万新币为起点',ylabel='SGD');ax.legend();ax.grid(alpha=.15)
    finish(fig,'01_historical_nav.png')
    f=pd.read_csv(HERE/'reproduced_fresh_live/daily.csv',parse_dates=['date']).set_index('date')
    f=f[f.index>='2026-10-01'];cont=d.loc[f.index]
    bn=b.reindex(f.index,method='ffill')
    fig,ax=plt.subplots(figsize=(10,4.2))
    for label,s,color in [('独立10万账户',f.nav,blue),('2021起连续账户',cont.nav,'#a3732b'),('STI',bn,'#888888')]:ax.plot(s.index,s/s.iloc[0]*100,label=label,color=color,marker='o',ms=3)
    ax.set(title='10月窗口：统一从10月1日收盘归一到100',ylabel='归一净值');ax.legend();ax.grid(alpha=.15)
    finish(fig,'02_october_nav.png')
    sector=read('fresh_live_close_to_close_sector.csv').sort_values('net_pnl')
    fig,ax=plt.subplots(figsize=(8.5,4));ax.barh(sector.six_sector.map(SECTORS),sector.contribution_pp,color=red)
    ax.axvline(0,color='#888',lw=.6);ax.set(title='10月独立账户：按源行业分组的净贡献',xlabel='百分点，合计等于−6.0125%')
    finish(fig,'03_october_sectors.png')
    stock=read('fresh_live_close_to_close_stock.csv').sort_values('net_pnl')
    fig,ax=plt.subplots(figsize=(9,6));ax.barh(stock.ticker,stock.contribution_pp,color=[red if x<0 else green for x in stock.net_pnl])
    ax.axvline(0,color='#888',lw=.6);ax.set(title='10月独立账户：18只股票的净贡献',xlabel='百分点，10月1日收盘至15日')
    finish(fig,'04_october_stocks.png')
    stock=read('execution_eval_stock.csv');show=pd.concat([stock.head(10),stock.tail(5)]).sort_values('net_pnl')
    fig,ax=plt.subplots(figsize=(9,5.4));ax.barh(show.ticker,show.net_pnl,color=[red if x<0 else green for x in show.net_pnl])
    ax.set(title='历史执行账户：主要贡献者与拖累者',xlabel='累计净贡献 SGD，2021至2026年9月')
    finish(fig,'05_historical_stocks.png')
    comp=read('execution_eval_component.csv');labels=['本地价格','汇率','价格×汇率','分红应收','费用','滑点']
    fig,ax=plt.subplots(figsize=(9,4.2));ax.bar(labels,comp.amount_sgd,color=[green if x>=0 else red for x in comp.amount_sgd]);ax.axhline(0,color='#888',lw=.6)
    ax.set(title='历史执行账户：净盈利185,647.38新币的会计分解',ylabel='SGD')
    finish(fig,'06_historical_components.png')
    weights=read('factor_weights_weekly.csv');weights.signal_date=pd.to_datetime(weights.signal_date)
    fig,ax=plt.subplots(figsize=(10,4.2))
    for name in STYLES:
        if name in weights:ax.plot(weights.signal_date,weights[name],label=STYLES[name],lw=1)
    ax.set(title='源策略实际使用的每周因子权重',ylabel='权重');ax.legend(ncol=3,fontsize=9);ax.grid(alpha=.15)
    finish(fig,'07_style_weights.png')
    coef=read('risk_model_market_plus_six_styles_coefficients.csv');coef=coef[coef.term!='alpha'].iloc[::-1]
    fig,ax=plt.subplots(figsize=(9,4.5))
    ax.errorbar(coef.coefficient,coef.term.map(STYLES),xerr=1.96*coef.hac_standard_error,fmt='o',color=blue,capsize=3)
    ax.axvline(0,color='#888',lw=.7);ax.set(title='SGD执行周收益：市场与风格暴露，HAC 95%区间',xlabel='回归系数，不是组合因子权重')
    finish(fig,'08_factor_exposures.png')


def main():
    REPORT.mkdir(exist_ok=True)
    figures()
    windows=json.loads((R/'account_window_summary.json').read_text());W={x['window']:x for x in windows}
    verification=json.loads((R/'attribution_verification.json').read_text())
    model=json.loads((R/'risk_model_summary.json').read_text())
    factors=json.loads((R/'factor_analysis_summary.json').read_text())
    source=json.loads((HERE/'source_audit/repositories.json').read_text(encoding='utf-8'))
    head=source[-1]['head'];url='https://github.com/lu2548214469-bit/FE5209-GroupProject/tree/'+head
    execution=json.loads((HERE/'reproduced_main/EXECUTION_SUMMARY.json').read_text())
    parts=[]
    def section(title,body):parts.append(f'<section><h2>{title}</h2>{body}</section>')
    intro=f'''<p class="lead">最终研究对象：<strong>K3_IV_weekly_top20</strong>。年度选择三个风格，每周重估逆波动因子权重，股票取前20%并等权。归因直接承接组员两份Excel及新仓库 <code>{head[:12]}</code> 的持仓、成交、净值和成本，不沿用旧Top4业绩。</p>
    <div class="notice">本报告解释已交付的模拟执行结果。分红14日支付、价格/股数单位、市场冲击等仍沿用源模型假设；未将其升级为已核实的券商实盘结果。源分红事件只到2026-09-15，10月“零分红”是源记录口径。行业结果沿用源研究分组，其中CNMC被标为科技与通信，与官方黄金开采主营不一致，详见第五节。</div>'''
    summary=pd.DataFrame([{'结果口径':name,'起点净值 SGD':money(W[key]['start_nav']),'终点净值 SGD':money(W[key]['end_nav']),
        '累计收益':pct(W[key]['cumulative_return']),'相对STI pp':f"{W[key]['active_return']*100:+.4f}" if W[key]['active_return'] is not None else '不在此口径比较'}
        for name,key in [('历史执行账户：2021—2026/09','execution_eval'),('10月独立账户：含首次建仓','fresh_live_cash_start'),
                         ('10月独立账户：10/1收盘起','fresh_live_close_to_close'),('10月连续账户：10/1收盘起','execution_live_continuous')]])
    section('一、先明确：这次到底解释哪条收益曲线',intro+table(summary)+f'''<p>历史执行账户的日历年化为<strong>{pct(execution['EVAL']['cagr'])}</strong>，最大回撤{pct(W['execution_eval']['max_drawdown'])}。源周频研究回测的样本外年化为24.53%，是另一口径：本币远期复权收益、周频比例成本与历史目标持仓路径。不能把24.53%与20.11%的全部差额叫作交易费用。</p>
    <p>10月独立账户与2021起连续账户的初始状态、现金、股数和最低佣金负担不同，因此相同策略可以有不同的窗口收益。10月1日到15日只有11个收盘净值、10个收盘到收盘收益观察，不用短窗年化数值判断长期能力。</p>''')
    lineage=pd.DataFrame([{'仓库/分支':'原仓库 EricLu/sg-adaptive-top4','核查结论':'仍为def5d53旧路线，不是这次结果的直接入口'},
        {'仓库/分支':'原仓库 research/sg-single-factor-independent','核查结论':'0608b8e，10/21更新；单因子研究有用，已被新项目纳入测试'},
        {'仓库/分支':'Cross-Market-Adaptive-Multi-Factor-Strategy','核查结论':'main仍为487f45c；另有既有框架/Investability分支，无本次K3完整交付'},
        {'仓库/分支':'新仓库 FE5209-GroupProject/main','核查结论':head[:12]+'；包含96只股票数据、汇率、K3代码与执行引擎，作为本次权威来源'}])
    section('二、三个仓库的定位与两份Excel的衔接',table(lineage)+f'''<p>原两个仓库已显式读取所有远端分支，避免单分支克隆漏检。初次分析对新仓库40个来源文件记录哈希并复核未改动。GitHub交付允许README/GUIDE增加归因导航，其余38个策略、配置与输入文件继续锁定哈希。工作簿原件保持不变。</p>
    <p>配置排名表覆盖45种配置，K3/IV周/前20%在该表排第3；最终项目只比较K3、K4、EW及三种IV频率的24种配置，在这个集合中它排第1。两种排名范围不同，本报告按配置键衔接，不按行号衔接，也不重新选择最高收益策略。</p>
    <p>18项工作簿对照中，<strong>17项达到设定精度</strong>，包括样本内与样本外指标、每日NAV、费用、滑点、47笔成交、18只持仓及完成率。另1项是STI数据微差：Excel为−4.661500%，当前仓库逐日指数算得−4.660983%，相差0.000517个百分点，超出6位小数正常舍入范围。没有改写它来强行对齐；本报告统一使用仓库逐日STI，故独立账户相对收益为−1.351519个百分点，Excel为−1.351001个百分点。</p>
    <p><a href="{url}">核查版本</a> · <a href="{url}/config/strategy.yaml">策略配置</a> · <a href="{url}/config/execution.yaml">执行配置</a> · <a href="{url}/data/README.md">数据说明</a></p>''')
    section('三、归因方法：每一项贡献都必须加回净值',r'''<p>执行账户以新币记账，逐日逐股使用源引擎实际贡献：</p>
    <pre>净贡献 = 股价损益 + 分红应收 − 费用 − 滑点
所有股票净贡献之和 = 期末净值 − 期初净值
期间贡献百分点 = 期间贡献金额 ÷ 该期间期初净值 × 100</pre>
    <p>除权日按此前持股确认分红应收，支付日只是应收转为现金，不再记一遍收益。T+2卖出款到账也不产生第二遍收益。跨期累计使用损益金额或明确的财富链接，不简单相加每日收益率，更不把各股票CAGR相加。</p>
    <p>外币股票的价格损益进一步精确拆分：</p>
    <pre>q × (P₁F₁ − P₀F₀)
= q × (P₁−P₀)F₀       本地价格
+ q × P₀(F₁−F₀)       汇率
+ q × (P₁−P₀)(F₁−F₀)  交互项</pre>
    <p>q是前日持股，P是本币价格，F是每单位外币对应的新币。缺失报价日沿用源引擎最后一次新币估值，不自行插入汇率收益。逐股价格拆分最大误差约1.23×10⁻¹²新币。</p>
    <p>周频研究账户独立使用源w×远期收益，并把真实源成本差额单列。第t周贡献乘此前净财富后累加，因此股票与成本的总和精确等于累计净收益。输出中的百分点都是指定起点的累计贡献，不是年化百分点。</p>''')
    comp=read('execution_eval_component.csv');labels={'native_price_pnl':'本地价格','fx_pnl':'汇率','price_fx_interaction':'价格与汇率交互','action_income':'分红应收','fees':'费用','slippage_cost':'滑点'}
    section('四、历史执行账户：185,647.38新币利润从哪里来',image('01_historical_nav.png')+image('06_historical_components.png')+
        table(pd.DataFrame({'来源':comp.component.map(labels),'贡献 SGD':comp.amount_sgd.map(money),'累计收益贡献 pp':comp.contribution_pp.map(lambda x:f'{x:+.4f}')}))+'''<p>累计收益185.6474%。本地价格是最大正贡献，分红应收贡献46,268.76新币；费用和滑点合计扣减30,717.18新币。这里的分红贡献是已发生在当前持仓路径中的会计贡献，不能据此宣称“删除分红后CAGR一定下降多少”，因为再投资会改变后续股数、交易和费用。</p>
        <p>汇率及交互合计约370.01新币，整体影响较小。不能把历史超额收益主要归因于外汇。该结论仅解释源模型实际持有的外币证券，未核实分币种现金结算或真实换汇费用。</p>''')
    sec=read('execution_eval_sector.csv')
    section('五、历史个股与行业贡献者',image('05_historical_stocks.png')+'<h3>主要正贡献</h3>'+stocktable('execution_eval_stock.csv',10)+
        '<h3>主要拖累</h3>'+stocktable('execution_eval_stock.csv',5,True)+
        '<h3>行业净贡献</h3>'+table(pd.DataFrame({'行业':sec.six_sector.map(SECTORS),'净贡献 SGD':sec.net_pnl.map(money),'累计收益贡献 pp':sec.contribution_pp.map(lambda x:f'{x:+.4f}')}))+
        '''<p>CNMC、Hong Leong Asia、The Hour Glass、Bumitama与Centurion是历史主要贡献者。按源研究分组，工业贡献最高，六个分组均为正；这不是已认证标准行业分类下的结论。个股贡献取决于持仓规模、持有时间、交易与分红，不能用股票全样本涨幅替代。</p>
        <div class="notice"><strong>行业标签核查：</strong>源security_master与周频面板都把CNMC（5TP）归入科技与通信，二者互相一致，但与<a href="https://www.cnmc.com.hk/about_us.html">公司官方黄金勘探与开采主营</a>及<a href="https://investorrelations.sgx.com/news-releases/news-release-details/cnmc-goldmine-lists-catalist-expanding-sgx-commodities-resource">SGX资源板块说明</a>不一致。尚需组员确认它是自定义分组还是映射问题。仅在展示层把CNMC从科技移到“其他”，历史科技贡献会由30,441.49降至8,147.93新币，“其他”由31,808.34升至54,101.90，行业排名也会改变；账户总收益和CNMC个股贡献不变。该敏感性没有重跑行业中性化分数或行业约束，不能称为修正分类后的策略回测。10月CNMC净贡献约−2.70新币，这一单项重分组不改变工业、消费为主要拖累的结论。没有据此认证其余所有行业标签。</div>''')
    daily=pd.read_csv(HERE/'reproduced_main/execution/daily.csv',parse_dates=['date']).set_index('date')
    annual=[]
    for year in range(2021,2027):
        before=daily[daily.index<pd.Timestamp(f'{year}-01-01')]
        base=before.nav.iloc[-1] if len(before) else 100000.
        d=daily[(daily.index>=f'{year}-01-01')&(daily.index<=f'{year}-12-31')&(daily.index<='2026-09-30')]
        annual.append(dict(year=str(year) if year<2026 else '2026至9月',start_nav=float(base),end_nav=float(d.nav.iloc[-1]),pnl=float(d.nav.iloc[-1]-base),period_return=float(d.nav.iloc[-1]/base-1)))
    ad=pd.DataFrame(annual);ad.to_csv(R/'execution_year_summary.csv',index=False)
    section('六、年度表现：金额贡献与收益率分开阅读',table(pd.DataFrame({'期间':ad.year,'期初 SGD':ad.start_nav.map(money),'期末 SGD':ad.end_nav.map(money),'净损益 SGD':ad.pnl.map(money),'期间收益':ad.period_return.map(pct)}))+
        '<p>后期账户较大，同样百分比会带来更大的金额贡献。因此跨年比较应同时看金额和收益率。各年贡献明细已分别输出，2026年只到9月，不与完整年度直接比全年收益。</p>')
    section('七、10月独立账户：亏损主要是价格，而非未成交',image('02_october_nav.png')+image('03_october_sectors.png')+image('04_october_stocks.png')+
        '<h3>主要拖累</h3>'+stocktable('fresh_live_close_to_close_stock.csv',5,True)+
        '<h3>主要缓冲</h3>'+stocktable('fresh_live_close_to_close_stock.csv',3)+
        '''<p>10月1日收盘至15日，净亏损5,999.39新币、收益−6.0125%。本地价格损失5,837.50，后续费用149.83、滑点12.06；价格贡献−5.8503个百分点，费用及滑点约−0.1622个百分点。工业−2.2410个百分点、消费−1.9647个百分点，合计约占净亏损70%。</p>
        <p>ISDN、Sheng Siong、Boustead、Geo Energy和The Hour Glass是主要拖累。Q&amp;M贡献约+0.6958个百分点，是最明显的正缓冲。历史最大贡献者CNMC在这个短窗接近平价，说明长期赢家不保证每个窗口都能抵消其他持仓的损失。</p>
        <p>共有47笔模拟成交，订单数量完成率100%，10月15日现金约3.5044%。不能用未成交解释这次主要亏损；也不能把“模型全部完成”当作券商真实成交证明。当前18只持仓均以SGD报价，本窗口汇率贡献为零。</p>''')
    first_fee=276.4647334-149.82573099999999
    section('八、为什么−6.2175%、−6.0125%、−6.0992%和−6.1880%都出现了',table(summary.iloc[1:])+'''<p><strong>现金起点与收盘起点：</strong>10万现金在10月1日建仓后，收盘NAV为99,781.854998。首次建仓费用约126.64、滑点91.51，合计218.15新币。因此现金起点收益−6.2175%额外包含这笔建仓成本；收盘到收盘收益−6.0125%排除它。二者分母也不同，不是简单减0.21815个百分点。</p>
    <p><strong>独立与连续账户：</strong>连续账户10月1日收盘NAV为283,633.73，10月15日为266,334.30，窗口收益−6.0992%。其股数、现金、应收和最低费用相对规模与新建10万账户不同。不能把两个账户的个股金额混在一起。</p>
    <p><strong>周频研究延伸：</strong>配置排名表的−6.1880%来自源理论日净值，含首日比例建仓费用，且不受股数、最低佣金、交收与成交量约束。它用于对应源研究结果，不是24策略工作簿的股数现金账户收益。</p>''')
    active=read('active_STI_summary.csv');ac=active[active.window.eq('fresh_live_close_to_close')].iloc[0]
    section('九、相对STI：把现金缓冲单独解释',f'''<p>统一使用仓库逐日STI后，10月独立账户相对收益为<strong>{pp(W['fresh_live_close_to_close']['active_return'])}</strong>。我们对每一天的实际期初股票权重减去同权重的STI收益，再加现金及应收相对STI的效果，并进行财富链接。</p>
    <pre>股票净相对贡献 {ac.linked_stock_active_effect*100:+.4f} pp
现金及应收缓冲 {ac.cash_and_receivable_effect*100:+.4f} pp
合计相对STI     {ac.active_cumulative_return*100:+.4f} pp</pre>
    <p>现金本身在模型里没有利息收入。正的相对贡献表示市场下跌时，未投资现金少承受了一部分跌幅，不是现金实际赚取了相同金额。历史上涨窗口则相反：现金及应收的相对效果约−15.5038个累计百分点，部分抵消股票相对效果+47.6724个百分点，剩余约+32.1685个百分点。</p>
    <p>这是以总体STI收益为门槛的实际暴露分解，<strong>不是STI行业Brinson归因</strong>。仓库没有历史STI行业权重和行业收益，不能把行业净贡献直接叫作行业配置能力。</p>''')
    br=read('brinson_EW_summary.csv');ev=br[br.window.eq('weekly_eval_2021_2026')].iloc[0]
    section('十、行业配置还是行业内选股：相对等权股票池的补充分析',f'''<p>源项目已有等权可投资股票池基准，可从同一周的股票、源行业分组和收益构造基准权重。我们在<strong>源周频本币收益及原研究分组口径</strong>下做Brinson-Fachler分解；它不替代SGD执行账户，也不冒充相对STI的行业归因。CNMC等分组的经济含义未全部认证，因此下面配置/选股项也受源分类影响。</p>'''+
        table(pd.DataFrame({'效果':['行业配置','行业内选股','交互','源交易成本','合计超额'],
            '累计贡献 pp':[f'{x*100:+.4f}' for x in [ev.allocation,ev.selection,ev.interaction,ev.cost,ev.active_cumulative_return]]}))+
        '''<p>该口径中，行业内选股项远大于行业配置项，负交互项抵消部分收益。可解释为“相对源等权股票池，行业内持仓选择贡献较多”；不能据此断言相对STI的选股alpha已获证明。</p>
        <pre>Aᵢ = (wᵢ−bᵢ)(Rᵦᵢ−Rᵦ)
Sᵢ = bᵢ(Rₚᵢ−Rᵦᵢ)
Iᵢ = (wᵢ−bᵢ)(Rₚᵢ−Rᵦᵢ)</pre>
        <p>现金也作为一个类别，源净收益与毛收益的差额单列成本。没有组合持仓的行业用该行业基准收益作中性补全，使选股及交互项不凭空出现。跨周链接系数为“此前策略净财富×该周之后的基准增长”，各项精确加回策略与基准期末财富之差。</p>''')
    latest=pd.DataFrame(factors['latest_weights'])
    selection=pd.DataFrame(factors['annual_decisions'])
    section('十一、三个因子如何作用：信号解释不能冒充损益分摊',image('07_style_weights.png')+
        table(selection.rename(columns={'year':'年份','selected':'当年入选因子'}))+
        table(pd.DataFrame({'信号日':latest.signal_date,'质量':latest.Quality.map(pct),'动量':latest.Momentum.map(pct),'小盘规模':latest.Size.map(pct)}))+
        '''<p>三因子指每年选择三个风格，并非三只股票，也不是固定永远选择同三个风格。2026年为规模、动量、质量。10月窗口信号中，质量约36%、规模约35%、动量约29%；股票本身仍按目标股数规模对应的等权目标执行。</p>
        <p>我们通过只记录返回值、随后恢复函数的观察包装，重跑未修改的源策略，捕获真实每周IV权重；验证其加权分数逐股加回源composite_score。没有用年度表里四舍五入的初始权重代替整年的周权重。</p>
        <p>Top20%、保留缓冲和行业上限使股票选择非线性，因此不能说“质量36%就贡献36%的收益”。输出的因子分数分量解释排序；因子模拟多空篮子仅作诊断，不加进真实账户贡献总和。</p>
        <p>三次10月目标都是同一组18只股票、相同等权目标。周IV权重确实略有变化，但没有改变入选集合。这解释了工作簿中周IV与月IV前20%结果一致，短窗相同不等于规则没有执行。</p>''')
    coef=read('risk_model_market_plus_six_styles_coefficients.csv')
    section('十二、市场与风格风险回归：小盘和动量暴露突出',image('08_factor_exposures.png')+
        table(pd.DataFrame({'项':coef.term.map(lambda x:STYLES.get(x,x)), '系数':coef.coefficient.map(lambda x:f'{x:+.4f}'),
            'HAC统计量':coef.hac_z_stat.map(lambda x:f'{x:+.3f}'),'双侧p值':coef.p_value_normal_approx.map(lambda x:f'{x:.4g}')}))+
        '''<p>使用298个完整周，将执行账户收益与STI和六个因子模拟收益全部统一为SGD，并使用同一执行日至下一执行日。风格模拟收益由原股票池、原分数、同样前后30%构造，只用于解释；不反馈到原策略的因子选择。因子是可交易性未经验证的多空研究组合。</p>
        <p>单市场模型beta约0.710、R²约28.7%，年化算术alpha约+7.79%，HAC p约0.187，不能说有显著正alpha。加入六风格后R²约82.3%，规模暴露约0.740、动量约0.261；低风险暴露约−0.367，说明即使没有显式选择低风险因子，也可能间接偏向高波动股票。</p>
        <p>七因子解释模型的年化算术alpha约−7.36%，p约0.012。这表示相对当前市场/风格代理组合仍有负的未解释均值；可能涉及长多约束、现金、交易费用、风格代理与持仓构造差异。它不是“策略绝对收益为负”，也不自动识别某个因子导致了损失。</p>
        <p>这里使用组合及市场总收益，没有扣除无风险利率。因此表中的alpha严格说是这一总收益回归的截距，不是已按无风险利率调整的Jensen alpha；其显著性也不能作为正式资产定价检验结论。</p>
        <p>R²是周收益变动的样本内解释程度，不是利润的82.3%。回归系数不是组合权重，alpha×52是算术年化均值，不是CAGR。HAC采用Bartlett权重、4阶滞后及n/(n−k)修正，p值用渐近正态近似；这些是描述性回归，不构成因果或前瞻预测证据。</p>''')
    dd=W['fresh_live_close_to_close']
    section('十三、最大回撤与短窗下跌集中度',f'''<p>独立账户在{dd['drawdown_peak']}收盘达到峰值{money(dd['drawdown_peak_nav'])}，在{dd['drawdown_trough']}收盘降至{money(dd['drawdown_trough_nav'])}，最大回撤{pct(dd['max_drawdown'])}。回撤归因以峰值净值为分母、峰值后至谷值的实际损益为分子，与10月1日起点的贡献不同。</p>'''+
        table(read('fresh_live_close_to_close_max_drawdown_stocks.csv')[['ticker','company_name','net_pnl','drawdown_contribution_pp']].head(6).rename(columns={'ticker':'代码','company_name':'公司','net_pnl':'峰谷净损益 SGD','drawdown_contribution_pp':'回撤贡献 pp'}).round(4))+
        '<p>账户回撤不等于每只股票回撤的平均。持股数量、入场时点和现金会改变贡献；因此我们按峰谷窗口重新汇总贡献，而不是把全窗口个股损失直接当成回撤贡献。</p>')
    section('十四、仍然存在的限制：哪些已查清，哪些没有',r'''<ol>
    <li><strong>10月公司行动覆盖未认证。</strong>事件源止于9月15日，故10月记零是源记录结果；如果实际有除息、配股等遗漏，相关净值和归因应重算。当前没有用推测填补。</li>
    <li><strong>价格与股数历史单位。</strong>源价格已作拆股调整，保留源股数单位和100股整手假设，未认证为每个历史日期的真实不复权交易单位；不重复应用拆股表。</li>
    <li><strong>周频与执行币种不同。</strong>源forward_return是上市币种收益，SGD执行账户包含FX；周频行业与个股结论限定在原口径，不把它当SGD实盘总回报。</li>
    <li><strong>源未来持有期标签。</strong>最新周的next_execution_date为10月19日，而日行情只到10月15日；本报告不把这类未完成周用于周频业绩或风险回归。10月采用已观察到的逐日账户。</li>
    <li><strong>最近四周资格标志。</strong>清洗说明将price_eligible空值按合格处理，需要数据团队确认含义；本报告承接此选择，没有自行换股票池。</li>
    <li><strong>PIT与历史股票池。</strong>年报滞后183天、修订版本、历史成员及退市覆盖仍未独立核验。通过源代码的时间顺序测试不代表所有输入满足PIT。</li>
    <li><strong>成交是代理。</strong>日收盘价和全日量上限不能证明收盘时可成交，盘口、价差、排队和规模冲击未校准。FX换汇与结算也采用源模型简化。</li>
    <li><strong>目标冻结与实际持仓。</strong>执行账户承接源策略的目标和保留缓冲路径；未成交不触发重新选股。按源结果归因有效，但不能宣称闭环实盘组合与它完全相同。</li>
    <li><strong>基准不足。</strong>没有历史STI行业成分权重与行业收益，因此不做STI行业配置/选股Brinson分解。EW股票池补充分析及STI整体门槛分析均有单独标签。</li>
    <li><strong>选择偏差与时间证据。</strong>按项目定义区分2016—20选择期、2021—26评估期、10月测试期；未独立审计所有实验日志和“选定前未看后期数据”的时间证据。10月样本很短，不以短窗排名重选策略。</li>
    <li><strong>基准微差保留。</strong>工作簿STI与仓库逐日值有0.000517个百分点差异，源组合NAV全部按原数保留，超额结果统一使用当前逐日基准。</li>
    <li><strong>源行业标签未认证。</strong>已确认CNMC源科技标签与官方资源业务不一致；仅展示重分类敏感性，未改源策略。它可能同时影响上游行业中性化及行业持仓上限，应由数据组确认原始映射。</li>
    </ol>''')
    section('十五、可以在汇报中说什么',r'''<blockquote>我们严格承接最新K3、每周IV因子调权、前20%选股配置，并复现两份Excel中该策略的净值与交易结果。历史执行账户的收益主要来自本地价格上涨及分红，CNMC、Hong Leong Asia等是主要贡献者；10月独立账户的亏损则主要集中于工业、消费及ISDN等持仓。订单在模型中全部完成，因此不能主要归因于未成交。风格回归显示明显小盘与动量暴露，但不能宣称有稳定且独立于风格的正alpha。所有贡献都核对回净值，因子信号贡献和实际盈利贡献分开呈现。</blockquote>
    <h3>常见提问</h3><dl>
    <dt>三因子是不是三只股票？</dt><dd>不是。三个风格用于评分，当前窗口目标持有18只股票。</dd>
    <dt>周调权为何与月调权同收益？</dt><dd>三次调仓的最终18只股票及等权目标相同，小幅因子权重变化没有跨过选股边界。</dd>
    <dt>成交率100%为什么还亏？</dt><dd>完成订单只是实现持仓，股票随后下跌仍会亏损。模型成交也不等于真实券商成交。</dd>
    <dt>能说历史战胜STI吗？</dt><dd>在源执行模型及相同窗口下，历史累计相对收益为正；10月则落后。不能把这直接等同于显著、稳定的选股alpha。</dd>
    <dt>手续费是不是24.53%降到20.11%的全部原因？</dt><dd>不能。两个系列在币种、日期、初始化、分红再投资和执行约束上都有差异。</dd>
    <dt>行业净贡献就是行业配置能力吗？</dt><dd>不是。净贡献没有扣除行业基准收益；STI行业数据缺失，不能强行拆分。</dd>
    <dt>质量权重36%是否解释36%的利润？</dt><dd>不能。股票选择非线性，因子权重只解释评分。损益必须从实际持股和价格变化计算。</dd>
    <dt>分红为零已经查实了吗？</dt><dd>只查实源文件窗口内无记录，真实10月事件完整性仍待确认。</dd>
    </dl>''')
    section('十六、复核和交付内容',r'''<p>源执行测试31项通过（30项合成、1项真实数据整合）；新增归因恒等式4项通过。两份Excel对照18项，17项精确或在既定精度内通过，STI微差单列。股票、行业、币种、现金、成本和峰谷回撤均回勾净值；策略、输入与原Excel未修改。</p>
    <ul><li><code>results/</code>：账户窗口、逐股逐日、行业、币种、费用、回撤、周频链接、因子权重及HAC回归CSV。</li>
    <li><code>source_audit/</code>：工作簿缓存值与公式记录、三个仓库版本、源输入与代码哈希。</li>
    <li><code>reproduced_main/</code>：未修改源项目的完整复现输出。</li>
    <li><code>reproduced_fresh_live/</code>：与24策略Excel同初始化的独立账户输出。</li>
    <li><code>report/figures/</code>：8张可直接用于汇报的图。</li></ul>
    <p>复现顺序：原仓库主程序→attribution_engine.py→sector_attribution.py→active_attribution.py→sector_label_audit.py→归因测试→build_report.py→verify_delivery.py。具体步骤见包内README_ZH.md。本版本为用户授权的GitHub归因交付，新增归因结果及文档，源策略和输入数据保持不变。</p>''')
    section('方法参考',r'''<p>会计恒等式和财富链接在本报告中明确列出。方法定位参考：
    <a href="https://rpc.cfainstitute.org/research/foundation/2019/performance-attribution">CFA Institute：Performance Attribution: History and Progress</a>；
    <a href="https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/portfolio-performance-evaluation">CFA Institute：Portfolio Performance Evaluation</a>；
    <a href="https://www.statsmodels.org/stable/generated/statsmodels.stats.sandwich_covariance.cov_hac.html">statsmodels：Newey–West HAC与Bartlett权重</a>。以上为方法参考，行情、持仓和回测数字均来自本次锁定的项目与工作簿。</p>''')
    css='''body{font-family:"Microsoft YaHei",Arial,sans-serif;line-height:1.85;color:#23313e;background:#f4f6f8;margin:0}main{max-width:1120px;margin:auto;background:white;padding:42px 54px}h1{font-size:29px;margin-bottom:12px}h2{font-size:22px;border-bottom:1px solid #ccd6df;padding-bottom:8px;margin-top:36px}h3{font-size:17px}p,li,dd{font-size:15px}.lead{font-size:17px}.notice{background:#fff6df;padding:14px 18px;border-left:4px solid #b78525}.data{border-collapse:collapse;width:100%;font-size:13px;margin:20px 0}.data th{background:#234e70;color:white;text-align:left;padding:8px}.data td{border-bottom:1px solid #e3e8ee;padding:7px;vertical-align:top}.data tr:nth-child(even){background:#f7f9fb}img{display:block;width:100%;max-width:1000px;margin:22px auto}pre{background:#f1f4f7;padding:16px;white-space:pre-wrap;font-size:14px}code{font-size:13px}blockquote{border-left:4px solid #234e70;padding:10px 22px;background:#f4f7fa}dt{font-weight:bold;margin-top:12px}dd{margin-left:0}a{color:#205d8a}small{color:#5d6b77}@media print{body{background:white}main{padding:0;max-width:none}section{break-inside:auto}h2{break-after:avoid}img{max-height:500px;object-fit:contain}.notice{border:1px solid #aaa}}'''
    document='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>新加坡三因子策略业绩归因</title><style>'+css+'</style><main><h1>新加坡三因子策略业绩归因</h1><p><small>2026-10-21　源版本 '+head[:12]+'　K3 / IV weekly / top20　币种：SGD执行账户</small></p>'+''.join(parts)+'</main></html>'
    path=REPORT/'SG_K3_ATTRIBUTION_ZH.html';path.write_text(document,encoding='utf-8')
    print(path)


if __name__=='__main__':main()
