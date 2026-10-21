# Ported from fangling114514, Backtest-Framework-Top4 branch (commit 4faa7f2),
# delivery/sg/top4_backtest/final_preset.py: the frozen dividend policy and prepare_source_dividends
# (function body unchanged).
"""Source cash dividends, assumed to be paid 14 calendar days after the ex-date."""
import numpy as np
import pandas as pd

PERFORMANCE_SCOPE = 'SOURCE_DIVIDEND_14D_ESTIMATE_UNVERIFIED_PRICE_SHARE_BASIS'
DIVIDEND_POLICY = dict(
    enabled=True, source_member='data/corporate_actions_2006.csv',
    payment_delay_calendar_days=14,
    payment_roll='first_proxy_session_on_or_after_assumed_payment_date',
    amount_basis='source_vendor_per_share_as_given',
    currency_assumption='SGD',
    tax_assumption='source_amount_used_without_additional_tax_deduction',
    apply_source_split_events=False)


def prepare_source_dividends(source, targets, sessions, end):
    """Retain vendor per-share units. Never certify payment dates or add splits.

    Only source cash events in the evaluation span and ever-targeted names are
    included. Actual entitlement is calculated by the engine from pre-ex-date
    holdings. Source dates outside the calendar stop the run, not silently roll.
    """
    if source is None:
        raise ValueError('Final dividend preset requires the original source corporate-action member')
    a = source.copy()
    required = {'date', 'ticker', 'action_type', 'dividend', 'split_ratio'}
    if required-set(a):
        raise ValueError('Source corporate-action fields missing')
    a['date'] = pd.to_datetime(a.date, errors='raise')
    if a.date.isna().any() or a.duplicated(['date','ticker','action_type']).any():
        raise ValueError('Missing or duplicate source event date/key')
    selected = (a.action_type.eq('cash_dividend') & a.ticker.isin(targets.ticker)
                & a.date.between(pd.Timestamp(targets.signal_date.min()), pd.Timestamp(end)))
    a = a[selected].copy()
    a['dividend'] = pd.to_numeric(a.dividend, errors='raise')
    if not np.isfinite(a.dividend).all() or (a.dividend < 0).any():
        raise ValueError('Invalid source cash dividend')
    calendar = pd.DatetimeIndex(pd.to_datetime(sessions))
    if not a.date.isin(calendar).all():
        raise ValueError('Source ex-date outside proxy sessions: resolve rather than silently shift')
    if a.empty:
        raise ValueError('Final preset found no source cash events; check package and evaluation coverage')
    result = pd.DataFrame(dict(
        event_id='SOURCE_DIVIDEND_ASSUMED14D_'+a.index.astype(str),
        ticker=a.ticker, ex_date=a.date, kind='dividend', value=a.dividend,
        pay_date=a.date+pd.Timedelta(days=14)))
    result['payment_date_is_assumed'] = True
    result['currency_is_assumed'] = True
    return result.reset_index(drop=True)
