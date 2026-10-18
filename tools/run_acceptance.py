"""全量验收：共享数据和设备因子，逐个运行十类策略。"""
from pathlib import Path
from datetime import datetime
import json
import time

from ashare_bt.config import Config
from ashare_bt.compute import compute_features
from ashare_bt.data import load_data
from ashare_bt.engine import run, status_requirement
from ashare_bt.status import StatusProvider
from ashare_bt.strategies import SPECS
from ashare_bt.utils import atomic_json


def main():
    config=Config()
    progress_path=config.root/'work/full-acceptance-progress.json'
    while not (config.path('status_dir')/'coverage.json').exists():
        atomic_json(progress_path,{'stage':'status','message':'等待历史状态全量覆盖审计完成'})
        time.sleep(5)
    config.auto_sync_status=False
    def progress(**record):
        atomic_json(progress_path,{**record,'strategy':config.strategy})
        if record.get('stage')!='backtest' or record.get('done',0)%50==1:
            print(record,flush=True)
    data=load_data(config,progress)
    assert data.dates[-1]=='2026-09-30' and len(data.trading_indices(config))==424
    features=compute_features(data,config,progress)
    status=StatusProvider(data.dates,data.securities,config.path('status_dir'))
    coverage=status.coverage(status_requirement(data,features,config))
    assert coverage['unknown_stock_days']==0,coverage
    atomic_json(config.root/'data/profile.json',features.profile)
    atomic_json(config.root/'data/formal-status-coverage.json',coverage)
    reports=[]
    for spec in SPECS:
        config=Config(name=f'{spec.name} · 全市场 10 亿',strategy=spec.id,auto_sync_status=False)
        ident='full-'+spec.id.replace('_','-')
        destination=config.path('output_dir')/ident
        if (destination/'summary.json').exists():
            summary=json.loads((destination/'summary.json').read_text())
        else:
            result=run(config,data=data,features=features,status=status,run_id=ident,progress=progress)
            summary=result.summary
        assert summary['trading_days']==424
        if spec.id=='momentum':assert summary['first_trade_date']=='2025-01-02'
        reports.append({key:summary[key] for key in ('run_id','strategy','return','net_profit','max_drawdown','average_exposure','trade_count','total_costs','first_trade_date','ending_market_value')})
        atomic_json(config.root/'data/full-acceptance.json',{'completed':len(reports),'total':len(SPECS),'strategies':reports,'status':coverage})
        print(reports[-1],flush=True)
    atomic_json(progress_path,{'stage':'completed','done':10,'total':10,'message':'10 类策略全量验收运行已完成'})


if __name__=='__main__':main()
