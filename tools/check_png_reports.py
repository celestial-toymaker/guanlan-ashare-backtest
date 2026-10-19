"""核验 PNG 曲线、报告引用与刷新前财务结果的一致性。"""
from pathlib import Path
import json

import pandas as pd
from PIL import Image

from ashare_bt.config import ROOT
from ashare_bt.utils import atomic_json, sha256


def check():
    baseline=json.loads((ROOT/'work/png-report-baseline.json').read_text())
    for name,digest in baseline.items():
        assert sha256(ROOT/name)==digest,name
    reports=[]
    for directory in sorted((ROOT/'runs').iterdir()):
        if not (directory.name.startswith('full-') or directory.name=='report-5dr'):
            continue
        image_path=directory/'equity-curve.png'
        with Image.open(image_path) as image:
            assert image.format=='PNG' and image.size==(1880,580)
            image.verify()
        with Image.open(image_path) as image:
            assert image.convert('RGB').getpixel((0,0))==(255,255,255)
        manifest=json.loads((directory/'manifest.json').read_text())
        assert manifest['report']['chart']=='equity-curve.png'
        assert manifest['report']['chart_sha256']==sha256(image_path)
        assert manifest['report_refresh']['verified_statistics_unchanged']
        for source,digest in manifest['source_sha256'].items():
            assert sha256(directory/'source'/source)==sha256(ROOT/'src/ashare_bt'/source)==digest
        markdown=(directory/'report.md').read_text()
        assert '![策略与参考组合的累计收益曲线](equity-curve.png)' in markdown
        equity=pd.read_parquet(directory/'equity.parquet')
        assert len(equity)==424
        reports.append({'run_id':directory.name,'chart_sha256':sha256(image_path),'size':[1880,580],
                        'daily_points':len(equity),'financial_files_unchanged':True})
    assert len(reports)==11
    result={'passed':True,'format':'png','renderer':'Matplotlib Agg','financial_files_checked':len(baseline),
            'render_cases':['逐日原始净值','按日期对齐参考组合','单曲线','零交易的平坦净值'],
            'reports':reports}
    atomic_json(ROOT/'data/png-report-check.json',result)
    print(json.dumps({'passed':True,'reports':len(reports),'financial_files_unchanged':len(baseline)},ensure_ascii=False))


if __name__=='__main__':check()
