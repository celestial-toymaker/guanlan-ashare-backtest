from dataclasses import replace

import numpy as np
import pytest
from decimal import Decimal

from ashare_bt.compute import compute_features
from ashare_bt.engine import run
from ashare_bt.strategies import SPECS


@pytest.mark.parametrize("strategy",[s.id for s in SPECS])
def test_ten_strategies_full_clock(market,strategy):
    config,data,features,status = market
    config.strategy = strategy
    result = run(config,data=data,features=features,status=status,output=False,collect_selection=True)
    assert result.equity.date.iloc[0] == config.start
    assert result.equity.date.iloc[-1] == config.end
    assert len(result.selection) == (len(result.equity)+1)*len(data.securities)
    assert result.equity.positions.max() <= config.max_positions
    assert result.equity.nav.astype(float).min() > 0
    if strategy in {"momentum","liquidity","buy_hold","reversal","low_volatility","multifactor"}:
        assert result.summary["first_trade_date"] == config.start


def test_replay_and_future_market_stability(market):
    config,data,features,status = market
    config.exit_mode = "strict_end"
    first = run(config,data=data,features=features,status=status,output=False)
    repeated = run(config,data=data,features=features,status=status,output=False)
    assert first.journal.to_json() == repeated.journal.to_json()
    cutoff = data.date_index["2025-01-15"]
    for name in ("open","high","low","close"):
        data.arrays[name][cutoff:] *= 1.25
    changed = compute_features(data,config,use_cache=False)
    future = run(config,data=data,features=changed,status=status,output=False)
    before = lambda result: result.orders[result.orders.decision_date < "2025-01-15"].drop(columns="last_reason")
    assert before(first).to_json() == before(future).to_json()


@pytest.mark.parametrize("mode",["latest_feasible","force_cash","strict_end"])
def test_exit_modes_and_reports(market,mode):
    config,data,features,status = market
    config.exit_mode = mode
    result = run(config,data=data,features=features,status=status,run_id=mode)
    assert (result.run_dir / "report.md").exists()
    from xml.etree import ElementTree
    assert ElementTree.parse(result.run_dir / "equity-curve.svg").getroot().tag == "{http://www.w3.org/2000/svg}svg"
    assert (result.run_dir / "manifest.json").exists()
    assert Decimal(result.summary["ending_market_value"]) == 0


def test_canonical_event_snapshot_replays_identical_ledger(market):
    from ashare_bt.events import Event,EventSource
    config,data,features,status=market
    source=EventSource([Event('tax','tax','2025-01-10T09:00:00','2025-01-13T12:00:00',payload={'amount':'12.34'})])
    first=run(config,data=data,features=features,status=status,event_source=source,run_id='event-snapshot')
    assert first.summary['costs']['tax']=='12.34'
    assert first.fees[first.fees.type=='tax'].event_id.tolist()==['tax']
    replay=EventSource.from_jsonl(first.run_dir/'input_events.jsonl')
    second=run(config,data=data,features=features,status=status,event_source=replay,output=False)
    assert first.journal.to_json()==second.journal.to_json()
    assert first.orders.to_json()==second.orders.to_json()
    assert first.equity.to_json()==second.equity.to_json()


def test_longer_strategy_window_increases_valid_history(market):
    from ashare_bt.strategies import StrategyRegistry
    config,data,features,status=market
    config.strategy='momentum';config.parameters={'window':120}
    StrategyRegistry().create(config)
    assert config.min_history==121


def test_liquidity_threshold_refines_float32_boundary(market):
    from ashare_bt.engine import eligibility
    config,data,features,status=market
    row=data.date_index[config.start]-1
    data.arrays['amt'][row-19:row+1,0]=19999999.5
    features.values['adv_20'][row,0]=20000000
    eligible,reasons=eligibility(data,features,status,config,row)
    assert not eligible[0] and reasons[0]==7


def test_buy_hold_retries_until_first_actual_fill(market):
    config,data,features,status=market
    config.strategy='buy_hold';config.parameters={'symbol':'000001.SZ'}
    config.exit_mode='strict_end'
    first=data.date_index[config.start]
    data.arrays['open'][first,0]=np.nan
    result=run(config,data=data,features=features,status=status,output=False)
    assert result.summary['first_trade_date']==data.dates[first+1]
    assert result.orders.iloc[0].status=='expired'
    buys=result.trades[result.trades.side=='buy']
    assert buys.date.nunique()==1


def test_daily_selection_distinguishes_carried_intent_and_qualified_target(market):
    from ashare_bt.strategies import Strategy,TargetWeights
    config,data,features,status=market
    first=data.date_index[config.start]
    data.arrays['open'][first,0]=np.nan
    data.arrays['amt'][first,0]=0
    config.exit_mode="strict_end"
    class OneDecision(Strategy):
        def __init__(self):self.called=False
        def on_close(self,history,portfolio):
            if self.called:return TargetWeights({},rebalance=False)
            self.called=True
            return TargetWeights({'000001.SZ':Decimal('.95')})
    result=run(config,OneDecision(),data=data,features=features,status=status,output=False,collect_selection=True)
    row=result.selection[(result.selection.date==config.start)&(result.selection.security=='000001.SZ')].iloc[0]
    assert row.strategy_weight==.95 and row.target_weight==0
    assert not row.selected and not row.eligible
    assert '资格约束' in row.selection_reason


def test_actual_exit_future_access_preserves_signal_boundary(market):
    config,data,features,status=market
    first=run(config,data=data,features=features,status=status,output=False,collect_selection=True)
    cutoff=data.date_index['2025-01-15']
    for field in ('open','high','low','close'):
        data.arrays[field][cutoff:]*=1.25
    data.arrays['amt'][cutoff:]*=.01
    changed=compute_features(data,config,use_cache=False)
    second=run(config,data=data,features=changed,status=status,output=False,collect_selection=True)
    columns=['date','security','score','rank','eligible','is_st']
    before=lambda result:result.selection[result.selection.date<'2025-01-15'][columns]
    import pandas as pd
    pd.testing.assert_frame_equal(before(first),before(second),check_exact=True)
    assert first.summary['exit_planning']['uses_future_market_data']
    assert first.summary['ending_positions']==second.summary['ending_positions']==0
