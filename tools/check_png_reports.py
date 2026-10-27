"""核对主策略单曲线、Markdown 引用与保存净值的对应关系。"""
import json
import pandas as pd
from PIL import Image
from ashare_bt.config import ROOT
from ashare_bt.utils import atomic_json,sha256


def check():
    refresh=json.loads((ROOT/'data/report-refresh-check.json').read_text());assert refresh['passed']
    reports=[]
    directories=[*sorted((ROOT/'runs').glob('full-*')),ROOT/'runs/report-5dr-100']
    for directory in directories:
        path=directory/'equity-curve.png'
        with Image.open(path) as image:
            assert image.format=='PNG' and image.size==(1880,580);image.verify()
        with Image.open(path) as image:assert image.convert('RGB').getpixel((0,0))==(255,255,255)
        manifest=json.loads((directory/'manifest.json').read_text())
        assert manifest['report']['chart_sha256']==sha256(path)
        for name,digest in manifest['source_sha256'].items():
            assert sha256(directory/'source'/name)==sha256(ROOT/'src/ashare_bt'/name)==digest
        text=(directory/'report.md').read_text()
        assert '![策略累计收益曲线](equity-curve.png)' in text and '参考组合' not in text
        equity=pd.read_parquet(directory/'equity.parquet');assert len(equity)==424
        if directory.name.startswith('full-'):
            previous=manifest['report_refresh']['verified_main_strategy_financial_files']
            assert all(sha256(directory/name)==digest for name,digest in previous.items())
        reports.append({'run_id':directory.name,'chart_sha256':sha256(path),'size':[1880,580],'daily_points':424,'series':1})
    assert len(reports)==11
    result={'passed':True,'format':'png','renderer':'Matplotlib Agg','series_per_report':1,
        'historical_financial_files_checked':sum(row['financial_files_checked'] for row in refresh['runs']),
        'render_cases':['全部逐日原始净值','单策略累计收益','零交易的平坦净值'],'reports':reports}
    atomic_json(ROOT/'data/png-report-check.json',result)
    print(json.dumps({'passed':True,'reports':len(reports),'series_per_report':1},ensure_ascii=False))


if __name__=='__main__':check()
