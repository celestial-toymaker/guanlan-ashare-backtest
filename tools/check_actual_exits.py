"""逐日核对退出路径的开盘价、实际规则容量、后续行情边界与期末结清。"""
from collections import defaultdict
from decimal import Decimal as D, ROUND_FLOOR
import json

import pandas as pd

from ashare_bt.config import Config, ROOT
from ashare_bt.data import load_data
from ashare_bt.rules import tick
from ashare_bt.utils import atomic_json, dec


def check():
    data=load_data(Config())
    paths=0
    reports=[]
    for directory in sorted((ROOT/'runs').iterdir()):
        if not (directory.name.startswith('full-') or directory.name=='report-5dr'):
            continue
        summary=json.loads((directory/'summary.json').read_text())
        assert summary['exit_planning']['uses_future_market_data']
        assert summary['exit_planning']['completed']
        for key in ('ending_market_value','ending_receivables','ending_pending_equity'):
            assert D(summary[key])==0,(directory.name,key)
        assert summary['ending_positions']==0 and not summary['terminal_assumptions']
        exits=pd.read_parquet(directory/'exits.parquet')
        count=0
        for record in exits.to_dict('records'):
            assert record['uses_future_market_data']
            used=defaultdict(D)
            column=data.index[record['security']]
            for fill in json.loads(record['capacity_path']):
                assert record['date'] < fill['date'] <= summary['end']
                row=data.date_index[fill['date']]
                amount=data.arrays['amt'][row-20:row,column]
                cap=(min(dec(amount[-1]),sum((dec(v) for v in amount),D(0))/20)*D(summary['config']['participation'])).quantize(D('.01'),rounding=ROUND_FLOOR)
                assert D(fill['price'])==tick(data.arrays['open'][row,column])
                assert D(fill['capacity'])==cap
                used[fill['date']]+=D(fill['notional'])
                assert used[fill['date']]<=cap
                assert data.arrays['amt'][row,column]>0
                count+=1
        reports.append({'run_id':directory.name,'path_records':len(exits),'projected_fills_checked':count,
                        'terminal_equity_cleared':True,'synthetic_terminal_settlement':False})
        paths+=count
    assert len(reports)==11
    report={'passed':True,'scope':'后续行情仅供退出倒排与新增买入退出可行性校验；策略视图与日常撮合保持原有时间边界',
            'runs':reports,'projected_fills_checked':paths,'data_fingerprint':data.fingerprint}
    atomic_json(ROOT/'data/actual-exit-check.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':check()
