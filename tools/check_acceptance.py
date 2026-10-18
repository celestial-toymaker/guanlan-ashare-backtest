"""审计十份正式回测的证券池、撮合、账本、版本和交付证据。"""
from collections import defaultdict
from decimal import Decimal as D, getcontext
from pathlib import Path
import json
import xml.etree.ElementTree as ET

import pandas as pd

from ashare_bt.config import Config, ROOT
from ashare_bt.data import load_data
from ashare_bt.rules import FeeModel, tick
from ashare_bt.status import StatusProvider
from ashare_bt.strategies import SPECS
from ashare_bt.utils import atomic_json, money, sha256

getcontext().prec=38


def check():
    config=Config()
    completed=json.loads((ROOT/'data/full-acceptance.json').read_text())
    assert completed['completed']==completed['total']==10
    data=load_data(config)
    status=StatusProvider(data.dates,data.securities,config.path('status_dir'))
    days=[data.dates[i] for i in data.trading_indices(config)]
    assert len(days)==424 and days[0]=='2025-01-02' and days[-1]=='2026-09-30'
    assert data.dates[data.date_index[days[0]]-1]=='2024-12-31'
    baseline=None
    reports=[]
    application_changes={}
    required=('equity','orders','trades','fees','journal','positions','events','exits','universe','selection','diagnostics','terminal_settlements','benchmark_equity')
    for spec in SPECS:
        directory=ROOT/'runs'/('full-'+spec.id.replace('_','-'))
        summary=json.loads((directory/'summary.json').read_text())
        manifest=json.loads((directory/'manifest.json').read_text())
        actual=Config.from_dict(summary['config'])
        assert actual.start==config.start and actual.end==config.end
        for key in ('initial_cash','commission_rate','min_commission','stamp_tax_rate','slippage_rate','exit_mode'):
            assert getattr(actual,key)==getattr(config,key),(spec.id,key)
        for name in required:
            assert (directory/f'{name}.parquet').exists(),(spec.id,name)
        for name,digest in manifest['source_sha256'].items():
            assert sha256(directory/'source'/name)==digest,(spec.id,name)
            current=sha256(ROOT/'src/ashare_bt'/name)
            if name=='server.py':
                if current!=digest:application_changes[name]={'run_sha256':digest,'publication_sha256':current}
            else:
                assert current==digest,(spec.id,name)
        assert summary['exit_planning']['basis']=='actual_path' and summary['exit_planning']['completed']
        assert summary['ending_positions']==0 and D(summary['ending_market_value'])==0
        assert D(summary['ending_receivables'])==D(summary['ending_pending_equity'])==0
        assert not summary['terminal_assumptions']
        exits=pd.read_parquet(directory/'exits.parquet')
        if len(exits):
            assert exits.uses_future_market_data.all()
        assert summary['input_fingerprint']==data.fingerprint
        assert summary['status_fingerprint']==status.fingerprint
        assert summary['status_coverage']['unknown_stock_days']==0
        equity=pd.read_parquet(directory/'equity.parquet')
        trades=pd.read_parquet(directory/'trades.parquet')
        orders=pd.read_parquet(directory/'orders.parquet')
        positions=pd.read_parquet(directory/'positions.parquet')
        journal=pd.read_parquet(directory/'journal.parquet')
        events=pd.read_parquet(directory/'events.parquet')
        universe=pd.read_parquet(directory/'universe.parquet')
        selected=pd.read_parquet(directory/'selection.parquet',filters=[('selected','==',True)])
        assert equity.date.tolist()==days and equity.positions.max()<=20
        assert universe.date.iloc[0]=='2024-12-31' and len(universe)==425
        assert universe.securities.eq(5451).all() and universe.stocks.eq(5450).all()
        assert universe.selected.le(20).all() and events.event_id.is_unique
        assert selected.is_st.eq(0).all() and selected.eligible.all()
        assert selected.groupby('date').target_weight.sum().le(.950000001).all()
        assert all(data.stock_mask[data.index[s]] for s in selected.security)
        if spec.id=='momentum':
            assert summary['first_trade_date']=='2025-01-02'
            assert selected[selected.date=='2024-12-31']['rank'].max()==20
        order_map={row['order_id']:row for row in orders.to_dict('records')}
        position_map={(r['date'],r['security']):(D(r['quantity']),D(r['factor'])) for r in positions.to_dict('records')}
        used=defaultdict(D);sold=defaultdict(D);costs=defaultdict(D)
        fee_model=FeeModel(actual)
        for trade in trades.to_dict('records'):
            day,security=trade['date'],trade['security']
            row,column=data.date_index[day],data.index[security]
            order=order_map[trade['order_id']]
            assert trade['decision_date']==data.dates[row-1]
            assert D(trade['price'])==tick(data.arrays['open'][row,column])
            assert data.arrays['amt'][row,column]>0
            assert money(D(trade['quantity'])*D(trade['price']))==D(trade['notional'])
            key=(day,security)
            used[key]+=D(trade['notional'])
            assert used[key]<=D(trade['capacity']),key
            expected=fee_model.quote(security,day,trade['side'],D(trade['notional']))
            assert sum(expected.values())==D(trade['fees'])
            for kind,amount in expected.items():
                assert amount==D(trade[kind]),(spec.id,trade['trade_id'],kind)
                costs[kind]+=amount
            if trade['side']=='buy':
                assert status.open_values[row,column]==0 and data.stock_mask[column]
                assert D(trade['quantity'])<=D(order['quantity'])
            else:
                old_quantity,old_factor=position_map.get((data.dates[row-1],security),(D(0),D(1)))
                available=old_quantity*(D(str(data.arrays['cumadj'][row,column]))/old_factor)
                sold[key]+=D(trade['quantity'])
                assert sold[key]<=available+D('1e-20'),(spec.id,key,'T+1')
            boundary='upper' if trade['side']=='buy' else 'lower'
            assert all(D(trade['price'])!=D(band[boundary]) for band in trade['candidate_limits'])
        entries=defaultdict(D);accounts=defaultdict(D)
        for record in journal.to_dict('records'):
            amount=D(record['amount'])
            entries[record['entry_id']]+=amount
            accounts[record['account']]+=amount
        assert all(amount==0 for amount in entries.values())
        assert sum(accounts.values())==0
        assert accounts.get('cash:available',D(0))+accounts.get('cash:frozen',D(0))==D(summary['ending_cash'])
        nav=D(summary['ending_cash'])+D(summary['ending_market_value'])+D(summary['ending_receivables'])+D(summary['ending_pending_equity'])-D(summary['ending_liabilities'])
        assert nav==D(summary['ending_nav'])
        assert D(summary['net_profit'])==nav-D(actual.initial_cash)
        assert sum(costs.values())==D(summary['total_costs'])
        reference=pd.read_parquet(directory/'benchmark_equity.parquet')
        if baseline is None:baseline=reference.to_json()
        assert reference.to_json()==baseline
        reports.append({'strategy':spec.id,'name':spec.name,'trading_days':len(equity),'trades':len(trades),
                        'non_st_entry':True,'shared_capacity':True,'t_plus_one':True,'fees':True,
                        'double_entry':True,'source_snapshot':True,'common_reference':True,
                        'actual_path_exit':True,'terminal_equity_cleared':True})
        print(f"通过：{spec.name}，{len(trades):,} 笔成交",flush=True)
    tests=ET.parse(ROOT/'work/python-tests.xml').getroot().find('testsuite').attrib
    browser=json.loads((ROOT/'work/browser-tests.json').read_text())['stats']
    assert int(tests['failures'])==int(tests['errors'])==0
    assert browser['unexpected']==browser['flaky']==0
    gpu=json.loads((ROOT/'data/mps_validation.json').read_text())
    assert all(item['targets_equal'] for item in gpu['checks']['ten_strategy_signal_precision'].values())
    lifecycle=json.loads((ROOT/'work/lifecycle-browser.json').read_text())
    assert lifecycle['passed']
    replay=json.loads((ROOT/'work/full-replay-check.json').read_text())
    assert replay['passed']
    assert replay['source_sha256']==json.loads((ROOT/'runs/full-momentum/manifest.json').read_text())['source_sha256']
    web=json.loads((ROOT/'web/package.json').read_text())
    report={'passed':True,'period':{'start':days[0],'end':days[-1],'trading_days':424,'first_decision':'2024-12-31'},
            'strategies':reports,'python_tests':int(tests['tests']),'browser_tests':browser['expected'],
            'mps':{'device':gpu['device']['device_name'],'all_ten_strategy_signals':True,'block_boundaries':True},
            'task_lifecycle':lifecycle,
            'full_replay':replay,
            'web':{'dependencies':web['dependencies'],'dev_dependencies':web['devDependencies'],
                   'source_sha256':{str(path.relative_to(ROOT)):sha256(path) for path in sorted((ROOT/'web/src').glob('*')) if path.is_file()}},
            'cuda':{'implementation':'可用同一验收脚本验证','hardware_acceptance':'待 NVIDIA 实机；用户确认当前仅有 Mac'},
            'application_publication_changes':application_changes,'financial_source_matches':True}
    atomic_json(ROOT/'data/acceptance.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='strategies'},ensure_ascii=False,indent=2))


if __name__=='__main__':check()
