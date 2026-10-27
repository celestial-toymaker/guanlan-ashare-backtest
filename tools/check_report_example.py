"""核对 100 只 5DR 的全市场选择、逐笔账本、容量及完整重放。"""
from collections import defaultdict
from decimal import Decimal as D
import json
import pandas as pd
from PIL import Image
from ashare_bt.config import Config,ROOT
from ashare_bt.data import load_data
from ashare_bt.rules import FeeModel,tick
from ashare_bt.status import StatusProvider
from ashare_bt.utils import atomic_json,sha256


def check():
    directory=ROOT/'runs/report-5dr-100'
    summary=json.loads((directory/'summary.json').read_text())
    config=Config.from_dict(summary['config']);data=load_data(config)
    status=StatusProvider(data.dates,data.securities,config.path('status_dir'))
    assert config.max_positions==100 and config.strategy=='reversal' and config.parameters=={'window':5,'allocation':'equal'}
    assert config.name==Config.load(ROOT/'configs/5dr.toml').name
    assert config.initial_cash=='1000000000.00' and summary['compute']['device']=='mps'
    assert (summary['start'],summary['end'],summary['trading_days'])==('2025-01-02','2026-09-30',424)
    assert summary['warmup']['last_decision']=='2024-12-31' and summary['first_trade_date']=='2025-01-02'
    assert summary['exit_planning']['completed'] and summary['status_coverage']['unknown_stock_days']==0
    assert summary['ending_positions']==0 and not summary['terminal_assumptions']
    assert all(D(summary[key])==0 for key in ('ending_market_value','ending_receivables','ending_pending_equity','ending_liabilities'))
    assert not any(key.startswith('benchmark_') for key in summary)
    assert 'benchmark' not in summary['config'] and not list(directory.glob('benchmark_*'))
    frames={name:pd.read_parquet(directory/f'{name}.parquet') for name in ('equity','orders','trades','positions','fees','journal','universe')}
    assert len(frames['equity'])==424 and frames['equity'].positions.le(100).all()
    assert frames['universe'].securities.eq(5451).all() and frames['universe'].stocks.eq(5450).all()
    assert frames['universe'].selected.le(100).all()
    selected=pd.read_parquet(directory/'selection.parquet',filters=[('selected','==',True)])
    initial=selected[selected.date=='2024-12-31']
    assert len(initial)==100 and initial.target_weight.eq(.0095).all()
    assert selected.is_st.eq(0).all() and selected.eligible.all()
    assert selected.groupby('date').target_weight.sum().le(.95000000001).all()
    order_map={row['order_id']:row for row in frames['orders'].to_dict('records')}
    positions={(p['date'],p['security']):(D(p['quantity']),D(p['factor'])) for p in frames['positions'].to_dict('records')}
    used=defaultdict(D);sold=defaultdict(D);fees=defaultdict(D);model=FeeModel(config)
    for trade in frames['trades'].to_dict('records'):
        day,security=trade['date'],trade['security'];row,column=data.date_index[day],data.index[security]
        assert trade['decision_date']==data.dates[row-1]
        assert D(trade['price'])==tick(data.arrays['open'][row,column])
        key=(day,security);used[key]+=D(trade['notional'])
        assert used[key]<=D(trade['capacity'])
        quoted=model.quote(security,day,trade['side'],D(trade['notional']))
        assert sum(quoted.values())==D(trade['fees'])
        for kind,value in quoted.items():
            assert value==D(trade[kind]);fees[kind]+=value
        if trade['side']=='buy':
            assert status.open_values[row,column]==0 and data.stock_mask[column]
            assert D(trade['quantity'])<=D(order_map[trade['order_id']]['quantity'])
        else:
            quantity,factor=positions.get((data.dates[row-1],security),(D(0),D(1)))
            sold[key]+=D(trade['quantity'])
            assert sold[key]<=quantity*D(str(data.arrays['cumadj'][row,column]))/factor+D('1e-20')
        boundary='upper' if trade['side']=='buy' else 'lower'
        assert all(D(trade['price'])!=D(band[boundary]) for band in trade['candidate_limits'])
    entries=defaultdict(D)
    for row in frames['journal'].to_dict('records'):entries[row['entry_id']]+=D(row['amount'])
    assert all(value==0 for value in entries.values())
    assert sum(fees.values())==D(summary['total_costs'])
    assert D(summary['ending_cash'])==D(summary['ending_nav'])
    assert D(summary['net_profit'])==D(summary['ending_nav'])-D(config.initial_cash)
    manifest=json.loads((directory/'manifest.json').read_text())
    for name,digest in manifest['source_sha256'].items():
        assert sha256(directory/'source'/name)==sha256(ROOT/'src/ashare_bt'/name)==digest
    markdown=(directory/'report.md').read_text()
    assert '**100 只**' in markdown and '![策略累计收益曲线]' in markdown and '参考组合' not in markdown
    assert f'{summary["return"]:.2%}' in markdown and f'{summary["max_drawdown"]:.2%}' in markdown
    assert f'{D(summary["net_profit"]):,.2f}' in markdown and '事后规划' in markdown
    with Image.open(directory/'equity-curve.png') as image:
        assert image.format=='PNG' and image.size==(1880,580);image.verify()
    assert manifest['report']['chart_sha256']==sha256(directory/'equity-curve.png')
    replay=json.loads((ROOT/'validation/5dr100-replay-check.json').read_text());assert replay['passed']
    ranks=json.loads((ROOT/'data/5dr100-ranking-check.json').read_text())
    assert len(ranks['checks'])==425 and all(item['top100_equal'] for item in ranks['checks'])
    report={'passed':True,'run_id':summary['run_id'],'strategy':'5DR（5 日反转）','max_positions':100,
        'first_target_count':len(initial),'max_actual_positions':int(frames['equity'].positions.max()),
        'device':summary['compute']['device'],'trading_days':424,'tables':replay['tables'],
        'non_st_entry':True,'shared_capacity':True,'t_plus_one':True,'fees':True,'double_entry':True,
        'terminal_equity_cleared':True,'daily_top100_original_precision':True,
        'config_sha256':sha256(ROOT/'configs/5dr.toml'),'source_sha256':manifest['source_sha256'],
        'report_sha256':sha256(directory/'report.md')}
    atomic_json(ROOT/'data/5dr-report-check.json',report)
    print(json.dumps({key:report[key] for key in ('passed','run_id','max_positions','first_target_count','max_actual_positions')},ensure_ascii=False))


if __name__=='__main__':check()
